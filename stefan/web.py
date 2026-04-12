"""Single-window web UI for stefan.

Smart-paste workflow: paste raw text to redact in place, paste text containing
placeholders to hydrate from localStorage. Selection-based manual tagging.
The backend exposes one detection endpoint; everything else is client-side.
"""

import os
import sys
from html import escape
from pathlib import Path
from typing import Optional

from flask import Flask, jsonify, make_response, redirect, request

app = Flask(__name__)
# Regex + dictionary only (no spaCy). Set via `stefan serve --no-spacy` or STEFAN_WEB_NO_SPACY=1.
app.config.setdefault("STEFAN_USE_SPACY", True)

_DEFAULT_MAX_DETECT_CHARS = 100_000
# New value each process start — used to tell the browser when the dev server restarted.
SERVER_BOOT_ID = os.urandom(8).hex()

# UI shell loaded on first GET / so importing this module stays cheap (faster `stefan serve`).
_STATIC_INDEX = Path(__file__).resolve().parent / "static" / "index.html"
_CUSTOM_NAMES_PATH = Path(__file__).resolve().parent / "data" / "custom_names.txt"
_CONSTRUCTION_ORGS_PATH = Path(__file__).resolve().parent / "data" / "construction_orgs.txt"
_index_html_mtime: Optional[float] = None
_index_html_cached: Optional[str] = None

_MAX_DICTIONARY_LINE_LEN = 500


def _base_index_html() -> str:
    """Load UI shell; reload from disk when ``index.html`` changes (mtime).

    A one-shot cache survives edits until process exit — confusing when only
    ``static/index.html`` changes. Browsers also cache ``GET /`` unless we send
    ``Cache-Control: no-store`` (see ``index()``).
    """
    global _index_html_mtime, _index_html_cached
    try:
        mtime = _STATIC_INDEX.stat().st_mtime
    except OSError:
        mtime = -1.0
    if _index_html_cached is None or _index_html_mtime != mtime:
        raw = _STATIC_INDEX.read_text(encoding="utf-8")
        end = raw.find("</html>")
        if end != -1:
            raw = raw[: end + len("</html>")]
        _index_html_cached = raw
        _index_html_mtime = mtime
    return _index_html_cached


# Injected before </body> when reload is enabled so the tab picks up new HTML/JS after a restart.
_LIVERELOAD_SNIPPET = """
<script>
(function () {
  var seen = null;
  setInterval(function () {
    fetch("/api/_stefan/boot", { cache: "no-store" })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (!d || d.boot == null) return;
        if (seen === null) seen = d.boot;
        else if (d.boot !== seen) location.reload();
      })
      .catch(function () {});
  }, 1200);
})();
</script>
"""


def _index_html_response():
    html = _base_index_html()
    if app.config.get("STEFAN_BROWSER_REFRESH"):
        html = html.replace("</body>", _LIVERELOAD_SNIPPET + "\n</body>", 1)
    return html


@app.route("/")
def index():
    html = _index_html_response()
    resp = make_response(html)
    resp.headers["Cache-Control"] = "no-store, max-age=0, must-revalidate"
    return resp


@app.route("/api/_stefan/boot")
def api_stefan_boot():
    """Stable until the dev server process restarts; used for browser auto-refresh."""
    return jsonify({"boot": SERVER_BOOT_ID})


@app.route("/admin/custom-names", methods=["GET", "POST"])
def admin_custom_names():
    """Append names to ``data/custom_names.txt`` and reload dictionaries (local / trusted use)."""
    from stefan.detectors.dictionary import reload_name_dictionaries

    if request.method == "POST":
        raw = request.form.get("names", "") or ""
        lines = [ln.strip() for ln in raw.replace("\r\n", "\n").split("\n") if ln.strip()]
        _CUSTOM_NAMES_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _CUSTOM_NAMES_PATH.open("a", encoding="utf-8") as f:
            for line in lines:
                f.write(line + "\n")
        reload_name_dictionaries()
        return redirect("/admin/custom-names?saved=1")

    saved = request.args.get("saved") == "1"
    existing = ""
    if _CUSTOM_NAMES_PATH.is_file():
        existing = _CUSTOM_NAMES_PATH.read_text(encoding="utf-8")
    notice = (
        "<p><strong>Saved.</strong> Names are active for new detection runs.</p>"
        if saved
        else ""
    )
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>Custom names</title></head>
<body>
<h1>Custom names</h1>
{notice}
<p>One name per line. Appends to <code>data/custom_names.txt</code> and reloads dictionaries.</p>
<form method="post">
<label for="names">Add names</label><br>
<textarea id="names" name="names" rows="12" cols="60" placeholder="E.g. company staff…">{escape(existing)}</textarea>
<br><button type="submit">Save</button>
</form>
</body>
</html>"""


@app.route("/api/dictionary/add", methods=["POST"])
def api_dictionary_add():
    """Append a line to local name or org dictionary (JSON API for the web UI)."""
    from stefan.detectors.dictionary import reload_name_dictionaries
    from stefan.detectors.dictionary_orgs import reload_org_dictionaries

    payload = request.get_json(silent=True) or {}
    kind = payload.get("kind")
    text = payload.get("text", "")
    if kind not in ("name", "org"):
        return jsonify({"error": 'kind must be "name" or "org"'}), 400
    if not isinstance(text, str):
        return jsonify({"error": "text must be a string"}), 400
    line = " ".join(text.split()).strip()
    if not line:
        return jsonify({"error": "text is empty"}), 400
    if len(line) > _MAX_DICTIONARY_LINE_LEN:
        return jsonify({"error": f"text too long (max {_MAX_DICTIONARY_LINE_LEN} chars)"}), 400

    if kind == "name":
        _CUSTOM_NAMES_PATH.parent.mkdir(parents=True, exist_ok=True)
        existing_lower = set()
        if _CUSTOM_NAMES_PATH.is_file():
            existing_lower = {
                ln.strip().lower()
                for ln in _CUSTOM_NAMES_PATH.read_text(encoding="utf-8").splitlines()
                if ln.strip()
            }
        if line.lower() in existing_lower:
            reload_name_dictionaries()
            return jsonify({"ok": True, "duplicate": True, "file": "custom_names.txt"})
        with _CUSTOM_NAMES_PATH.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
        reload_name_dictionaries()
        return jsonify({"ok": True, "duplicate": False, "file": "custom_names.txt"})

    # kind == "org"
    _CONSTRUCTION_ORGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    existing = set()
    if _CONSTRUCTION_ORGS_PATH.is_file():
        existing = {
            ln.strip() for ln in _CONSTRUCTION_ORGS_PATH.read_text(encoding="utf-8").splitlines() if ln.strip()
        }
    if line in existing:
        reload_org_dictionaries()
        return jsonify({"ok": True, "duplicate": True, "file": "construction_orgs.txt"})
    with _CONSTRUCTION_ORGS_PATH.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    reload_org_dictionaries()
    return jsonify({"ok": True, "duplicate": False, "file": "construction_orgs.txt"})


def _max_detect_chars() -> int:
    raw = os.environ.get("STEFAN_MAX_DETECT_CHARS", str(_DEFAULT_MAX_DETECT_CHARS))
    try:
        n = int(raw)
    except ValueError:
        return _DEFAULT_MAX_DETECT_CHARS
    return max(1_000, min(n, 2_000_000))


@app.route("/api/detect", methods=["POST"])
def api_detect():
    from stefan.detectors import (
        detect_dictionary,
        detect_dictionary_orgs,
        detect_regex,
        detect_spacy,
        merge_spans,
    )
    from stefan.detectors.context_triggers import detect_context_triggers
    from stefan.detectors.name_morphology import detect_name_morphology

    payload = request.get_json(silent=True) or {}
    text = payload.get("text", "")
    if not isinstance(text, str):
        return jsonify({"error": "text must be a string"}), 400

    limit = _max_detect_chars()
    if len(text) > limit:
        return (
            jsonify(
                {
                    "error": f"text too long ({len(text)} chars; max {limit}). "
                    "Paste a smaller chunk or raise STEFAN_MAX_DETECT_CHARS."
                }
            ),
            413,
        )

    regex_spans = detect_regex(text) + detect_context_triggers(text)
    dict_spans = (
        detect_dictionary(text)
        + detect_dictionary_orgs(text)
        + detect_name_morphology(text)
    )
    spacy_spans = []
    if app.config.get("STEFAN_USE_SPACY", True):
        try:
            spacy_spans = detect_spacy(text)
        except RuntimeError:
            spacy_spans = []

    spans = merge_spans(regex_spans, dict_spans, spacy_spans, text=text)
    return jsonify({
        "spans": [
            {"start": s[0], "end": s[1], "type": s[2], "value": s[3]}
            for s in spans
        ]
    })


def _warm_spacy_model(quiet: bool, use_spacy: bool) -> None:
    """Load spaCy before the first HTTP request so the UI does not hang on 'Working…'."""
    if not use_spacy:
        return
    if not quiet:
        print(
            "Loading Swedish NER for full redaction (people, orgs, places + regex + names)…",
            file=sys.stderr,
            flush=True,
        )
    from stefan.detectors.nlp import warm_model_for_web

    if warm_model_for_web(quiet=quiet):
        if not quiet:
            print("NER model ready.", file=sys.stderr, flush=True)
    elif not quiet:
        print(
            "Continuing with regex + dictionary redaction only (install a spaCy model for ML entities).",
            file=sys.stderr,
            flush=True,
        )


def run(
    host: str = "0.0.0.0",
    port: int = 80,
    debug: bool = False,
    *,
    reload: bool = False,
    quiet: bool = False,
    use_spacy: bool = True,
) -> None:
    """Start the Flask development server.

    With ``reload=True``, the stat reloader restarts the process on ``.py`` saves
    and the UI polls ``/api/_stefan/boot`` so open tabs refresh (slower startup
    than default). ``--debug`` alone does not enable the reloader.
    """
    if os.environ.get("STEFAN_WEB_NO_SPACY", "").strip().lower() in ("1", "true", "yes"):
        use_spacy = False
    app.config["STEFAN_USE_SPACY"] = bool(use_spacy)

    if quiet:
        import logging

        for name in ("werkzeug", "werkzeug.serving", "flask.app"):
            logging.getLogger(name).setLevel(logging.ERROR)

    _warm_spacy_model(quiet=quiet, use_spacy=bool(use_spacy))

    if not quiet:
        print(f"Web UI HTML (must contain your edits): {_STATIC_INDEX}", file=sys.stderr, flush=True)

    app.config["STEFAN_BROWSER_REFRESH"] = bool(reload) or bool(debug)
    # Only `--reload` uses the stat reloader (extra process + slow startup). `--debug` alone
    # keeps the interactive debugger without paying reloader cost.
    use_reloader = bool(reload)
    app.run(
        host=host,
        port=port,
        debug=debug,
        use_reloader=use_reloader,
        threaded=True,
    )
