"""Click CLI entry point for stefan."""

import json
import sys
from pathlib import Path

import platform

import click

DEFAULT_MAP_FILE = ".stefan_map.json"


def _read_input(input_path):
    if input_path:
        return Path(input_path).read_text(encoding="utf-8")
    return sys.stdin.read()


def _write_output(output_path, content):
    if output_path:
        Path(output_path).write_text(content, encoding="utf-8")
    else:
        sys.stdout.write(content)


@click.group()
@click.version_option()
def cli():
    """stefan: reversible text redaction."""


@cli.command("redact")
@click.option("--input", "-i", "input_path", type=click.Path(exists=True, dir_okay=False),
              help="Input file (defaults to stdin).")
@click.option("--output", "-o", "output_path", type=click.Path(dir_okay=False),
              help="Output file (defaults to stdout).")
@click.option("--map", "map_path", type=click.Path(dir_okay=False),
              default=DEFAULT_MAP_FILE, show_default=True,
              help="Path to write the placeholder mapping JSON.")
def redact_cmd(input_path, output_path, map_path):
    """Detect sensitive entities and replace them with placeholders."""
    from reduct.redactor import redact

    text = _read_input(input_path)
    redacted, mapping = redact(text)
    Path(map_path).write_text(
        json.dumps(mapping, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    _write_output(output_path, redacted)


@cli.command("serve")
@click.option("--host", default="0.0.0.0", show_default=True,
              help="Interface to bind.")
@click.option("--port", default=80, show_default=True, type=int,
              help="Port to bind. Use 5000 if you can't run as admin.")
@click.option(
    "--debug",
    is_flag=True,
    help="Flask debug pages/tracebacks. Does not enable auto-reload (use --reload for that).",
)
@click.option(
    "--reload/--no-reload",
    default=False,
    show_default=True,
    help="Restart when code changes and refresh open tabs (slower startup; use while editing).",
)
@click.option("-q", "--quiet", is_flag=True, help="Print URL only; hide HTTP access logs.")
@click.option(
    "--no-spacy",
    is_flag=True,
    help="Skip spaCy NER (regex + name list only). Much faster; less coverage for people/places/orgs.",
)
def serve_cmd(host, port, debug, reload, quiet, no_spacy):
    """Start the local web UI (use http://stefan.local after hosts setup)."""
    try:
        from reduct.web import run
    except ImportError as e:
        raise click.ClickException(
            "Flask is required for 'stefan serve'. Install with: pip install flask"
        ) from e

    loopback = "http://127.0.0.1" + ("" if port == 80 else f":{port}")
    if quiet:
        click.echo(loopback)
    else:
        local_url = "http://stefan.local" + ("" if port == 80 else f":{port}")
        click.echo(f"Listening on {loopback}  (bound {host}:{port})")
        click.echo(f"Open in browser: {local_url}  or  {loopback}")
        click.echo("")
        click.echo("For stefan.local to resolve, add this line to your hosts file (one-time):")
        click.echo("  127.0.0.1  stefan.local")
        if platform.system() == "Windows":
            click.echo(
                r"  Windows (edit as Administrator): C:\Windows\System32\drivers\etc\hosts"
            )
        else:
            click.echo("  macOS/Linux: /etc/hosts")
        click.echo("")
        if port == 80:
            click.echo(
                "Port 80 often needs Administrator; if bind fails, use: stefan serve --port 5000"
            )
            click.echo("then open http://stefan.local:5000")
        click.echo("")
        if reload:
            click.echo(
                "Auto-reload: on — server restarts on save; the page refreshes after restart."
            )
            click.echo("")
        else:
            click.echo(
                "Tip: use --reload while editing server code (restarts + browser refresh)."
            )
            click.echo("")
        if not no_spacy:
            click.echo(
                "The UI loads a Swedish spaCy model once (see terminal): prefers "
                "sv_core_news_sm, else sv_core_news_lg. Max accuracy: set "
                "REDUCT_SPACY_MODEL=sv_core_news_lg. Regex-only (no ML): --no-spacy."
            )
            click.echo("")

    run(
        host=host,
        port=port,
        debug=debug,
        reload=reload,
        quiet=quiet,
        use_spacy=not no_spacy,
    )


@cli.command("hydrate")
@click.option("--input", "-i", "input_path", type=click.Path(exists=True, dir_okay=False),
              help="Input file (defaults to stdin).")
@click.option("--output", "-o", "output_path", type=click.Path(dir_okay=False),
              help="Output file (defaults to stdout).")
@click.option("--map", "map_path", type=click.Path(exists=True, dir_okay=False),
              default=DEFAULT_MAP_FILE, show_default=True,
              help="Path to read the placeholder mapping JSON.")
def hydrate_cmd(input_path, output_path, map_path):
    """Replace placeholders with their original values from the mapping."""
    from reduct.hydrator import hydrate

    text = _read_input(input_path)
    mapping = json.loads(Path(map_path).read_text(encoding="utf-8"))
    restored = hydrate(text, mapping)
    _write_output(output_path, restored)


if __name__ == "__main__":
    cli()
