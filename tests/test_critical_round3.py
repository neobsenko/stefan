"""Critical regression tests from latest QA report."""

from stefan.redactor import redact


def _values_by_prefix(mapping: dict[str, str], prefix: str) -> list[str]:
    return [v for k, v in mapping.items() if k.startswith(prefix)]


def test_iban_detected_and_not_phone():
    text = (
        "SE45 5000 0000 0583 9825 7466\n"
        "DE89 3704 0044 0532 0130 00\n"
        "FR14 2004 1010 0505 0001 3M02 606"
    )
    _, mapping = redact(text, use_spacy=False)
    assert "SE45 5000 0000 0583 9825 7466" in _values_by_prefix(mapping, "IBAN_")
    assert "DE89 3704 0044 0532 0130 00" in _values_by_prefix(mapping, "IBAN_")
    assert "FR14 2004 1010 0505 0001 3M02 606" in _values_by_prefix(mapping, "IBAN_")
    assert not _values_by_prefix(mapping, "PHONE_")


def test_nationality_and_descriptor_words_not_entities():
    text = "Norska Polska Finska kontoret har Multipla Olika Flera ärenden."
    redacted, mapping = redact(text, use_spacy=False)
    for token in ("Norska", "Polska", "Finska", "Multipla", "Olika", "Flera"):
        assert token in redacted
        assert token not in mapping.values()


def test_bank_terms_greetings_and_ok_not_entities():
    text = "Bankgiro Plusgiro IBAN BIC SWIFT OCR KID Pozdrowienia OK det var allt."
    redacted, mapping = redact(text, use_spacy=False)
    for token in (
        "Bankgiro",
        "Plusgiro",
        "IBAN",
        "BIC",
        "SWIFT",
        "OCR",
        "KID",
        "Pozdrowienia",
        "OK",
    ):
        assert token in redacted
        assert token not in mapping.values()


def test_trygg_hansa_and_saint_gobain_are_org():
    text = "försäkringen hos Trygg-Hansa. KAM hos Saint-Gobain."
    _, mapping = redact(text, use_spacy=False)
    assert "Trygg-Hansa" in _values_by_prefix(mapping, "ORG_")
    assert "Saint-Gobain" in _values_by_prefix(mapping, "ORG_")
    assert "Trygg-Hansa" not in _values_by_prefix(mapping, "PERSON_")
    assert "Saint-Gobain" not in _values_by_prefix(mapping, "PERSON_")


def test_multiword_orgs_kept_whole():
    text = (
        "Hägglund Bygg & Entreprenad AB och Saint-Gobain Sweden AB "
        "samt Bosch Rexroth deltog."
    )
    _, mapping = redact(text, use_spacy=False)
    org_values = _values_by_prefix(mapping, "ORG_")
    assert "Hägglund Bygg & Entreprenad AB" in org_values
    assert "Saint-Gobain Sweden AB" in org_values
    assert "Bosch Rexroth" in org_values


def test_org_nr_label_not_tagged_as_org_word():
    text = "Org.nr: 232100-0016"
    redacted, mapping = redact(text, use_spacy=False)
    assert "Org.nr" in redacted
    assert "Org.nr" not in mapping.values()
    assert "232100-0016" in _values_by_prefix(mapping, "ORG_NR_")


def test_phone_does_not_consume_closing_parenthesis():
    text = "(PERSON_X, +46 73 555 12 34)"
    redacted, mapping = redact(text, use_spacy=False)
    assert any(v == "+46 73 555 12 34" for v in mapping.values())
    assert redacted.endswith(")")
    assert ")" in redacted

