"""Regression tests for spaCy-enabled false positives."""

from stefan.detectors.merger import merge_spans
from stefan.redactor import redact


def _values_by_prefix(mapping: dict[str, str], prefix: str) -> list[str]:
    return [v for k, v in mapping.items() if k.startswith(prefix)]


def test_spacy_location_cannot_reclassify_locked_dictionary_org(monkeypatch):
    text = "Veidekke och Skanska deltog."

    def fake_detect_spacy(_: str):
        return [(0, 8, "LOCATION", "Veidekke")]

    monkeypatch.setattr("stefan.redactor.detect_spacy", fake_detect_spacy)

    _, mapping = redact(text, use_spacy=True)

    assert "Veidekke" in _values_by_prefix(mapping, "ORG_")
    assert "Veidekke" not in _values_by_prefix(mapping, "LOCATION_")


def test_spacy_greeting_location_false_positive_is_dropped(monkeypatch):
    text = "Pozdrowienia OK det var allt."

    def fake_detect_spacy(_: str):
        return [(0, 12, "LOCATION", "Pozdrowienia")]

    monkeypatch.setattr("stefan.redactor.detect_spacy", fake_detect_spacy)

    redacted, mapping = redact(text, use_spacy=True)

    assert "Pozdrowienia" in redacted
    assert "Pozdrowienia" not in mapping.values()


def test_spacy_hyphenated_location_false_positive_is_dropped(monkeypatch):
    text = "Pont-Lefèvre skrev rapporten."

    def fake_detect_spacy(_: str):
        return [(0, 12, "LOCATION", "Pont-Lefèvre")]

    monkeypatch.setattr("stefan.redactor.detect_spacy", fake_detect_spacy)

    redacted, mapping = redact(text, use_spacy=True)

    assert "Pont-Lefèvre" in _values_by_prefix(mapping, "PERSON_")
    assert "Pont-Lefèvre" not in _values_by_prefix(mapping, "LOCATION_")

    merged = merge_spans([], [], [(0, 12, "LOCATION", "Pont-Lefèvre")], text=text)
    assert merged == []


def test_spacy_reference_code_org_false_positive_is_dropped(monkeypatch):
    text = "Ärende BL-2026-9999 ska inte vara organisation."
    start = text.index("BL-2026-9999")
    end = start + len("BL-2026-9999")

    def fake_detect_spacy(_: str):
        return [(start, end, "ORG", "BL-2026-9999")]

    monkeypatch.setattr("stefan.redactor.detect_spacy", fake_detect_spacy)

    redacted, mapping = redact(text, use_spacy=True)

    assert "BL-2026-9999" in redacted
    assert "BL-2026-9999" not in mapping.values()


def test_dictionary_org_survives_spacy_split_for_raddningstjansten():
    text = "Räddningstjänsten Storstockholm kontaktades."
    merged = merge_spans(
        [],
        [(0, 31, "ORG", "Räddningstjänsten Storstockholm")],
        [
            (0, 17, "ORG", "Räddningstjänsten"),
            (18, 31, "LOCATION", "Storstockholm"),
        ],
        text=text,
    )

    assert merged == [(0, 31, "ORG", "Räddningstjänsten Storstockholm")]


def test_spacy_org_truncated_to_role_line_is_dropped(monkeypatch):
    text = "& Huvudägare\nBjörkviks Bygg & Entreprenad AB"
    start = text.index("Huvudägare")
    end = len(text)

    def fake_detect_spacy(_: str):
        return [(start, end, "ORG", text[start:end])]

    monkeypatch.setattr("stefan.redactor.detect_spacy", fake_detect_spacy)

    _, mapping = redact(text, use_spacy=True)

    assert "Huvudägare" not in mapping.values()
    assert "Björkviks Bygg & Entreprenad AB" in _values_by_prefix(mapping, "ORG_")
