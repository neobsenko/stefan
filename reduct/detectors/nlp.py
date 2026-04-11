"""spaCy NER-based detection."""

import os
import sys
from functools import lru_cache
from typing import List, Optional, Tuple

# Web UI tries these in order when REDUCT_SPACY_MODEL is unset (fast sm, then accurate lg).
_WEB_SERVE_MODEL_ORDER = ("sv_core_news_sm", "sv_core_news_lg")

# spaCy entity label -> our type
_LABEL_MAP = {
    "PER": "PERSON",
    "PERSON": "PERSON",
    "ORG": "ORG",
    "LOC": "LOCATION",
    "GPE": "LOCATION",
}

# Override with e.g. REDUCT_SPACY_MODEL=sv_core_news_sm for much faster (slightly less accurate) NER.
_DEFAULT_MODEL = "sv_core_news_lg"


def _model_name() -> str:
    return os.environ.get("REDUCT_SPACY_MODEL", _DEFAULT_MODEL).strip() or _DEFAULT_MODEL


@lru_cache(maxsize=1)
def _load_model():
    """Lazily load the Swedish spaCy model."""
    import spacy

    name = _model_name()
    try:
        nlp = spacy.load(name)
    except OSError as e:
        raise RuntimeError(
            f"spaCy model {name!r} is not installed. "
            f"Install with: python -m spacy download {name}"
        ) from e
    # NER does not need these pipes; skipping them cuts CPU time per document.
    for pipe in ("parser", "lemmatizer", "attribute_ruler"):
        if pipe in nlp.pipe_names:
            try:
                nlp.disable_pipe(pipe)
            except ValueError:
                pass
    return nlp


def warm_model_for_web(*, quiet: bool = False) -> bool:
    """Load spaCy for ``stefan serve``: prefer small model, fall back to lg. Returns True if loaded."""
    if os.environ.get("REDUCT_SPACY_MODEL", "").strip():
        try:
            _load_model()
            if not quiet:
                print(
                    f"Using spaCy model: {_model_name()}",
                    file=sys.stderr,
                    flush=True,
                )
            return True
        except Exception as e:
            if not quiet:
                print(f"NER model failed: {e}", file=sys.stderr, flush=True)
            return False

    last_err: Optional[Exception] = None
    for name in _WEB_SERVE_MODEL_ORDER:
        os.environ["REDUCT_SPACY_MODEL"] = name
        _load_model.cache_clear()
        try:
            _load_model()
            if not quiet:
                print(
                    f"Using spaCy model: {name}",
                    file=sys.stderr,
                    flush=True,
                )
            return True
        except Exception as e:
            last_err = e
            continue

    if not quiet:
        print(
            "No Swedish spaCy model found. For full redaction (people/orgs/places), run:\n"
            "  python -m spacy download sv_core_news_sm\n"
            f"(Last error: {last_err})",
            file=sys.stderr,
            flush=True,
        )
    return False


def detect_spacy(text: str) -> List[Tuple[int, int, str, str]]:
    """Run spaCy NER on text.

    Returns a list of (start, end, entity_type, matched_text) tuples
    for PER, ORG, LOC entities.
    """
    nlp = _load_model()
    doc = nlp(text)
    spans: List[Tuple[int, int, str, str]] = []
    for ent in doc.ents:
        mapped = _LABEL_MAP.get(ent.label_)
        if mapped is None:
            continue
        spans.append((ent.start_char, ent.end_char, mapped, ent.text))
    return spans
