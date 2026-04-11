"""Tests for the redact + hydrate roundtrip and placeholder numbering."""

import re

from reduct.hydrator import hydrate
from reduct.redactor import redact


def test_basic_redact_returns_mapping():
    text = "Email me at test@example.com."
    redacted, mapping = redact(text, use_spacy=False)
    assert "test@example.com" not in redacted
    assert "EMAIL_1" in redacted
    assert mapping["EMAIL_1"] == "test@example.com"


def test_placeholder_numbering_per_type():
    text = (
        "Contact a@x.com or b@y.com. "
        "Server at 10.0.0.1 and 10.0.0.2."
    )
    _, mapping = redact(text, use_spacy=False)
    assert mapping["EMAIL_1"] == "a@x.com"
    assert mapping["EMAIL_2"] == "b@y.com"
    assert mapping["IP_1"] == "10.0.0.1"
    assert mapping["IP_2"] == "10.0.0.2"


def test_repeated_value_reuses_placeholder():
    text = "Erik wrote to Erik again."
    redacted, mapping = redact(text, use_spacy=False)
    # Erik should map to a single placeholder appearing twice
    person_placeholders = [k for k in mapping if k.startswith("PERSON_")]
    assert len(person_placeholders) == 1
    assert redacted.count(person_placeholders[0]) == 2


def test_hydrate_roundtrip_simple():
    original = "Send mail to test@example.com about the meeting."
    redacted, mapping = redact(original, use_spacy=False)
    restored = hydrate(redacted, mapping)
    assert restored == original


def test_hydrate_roundtrip_mixed_entities():
    original = (
        "Johan Andersson från Volvo skickade ett mail till "
        "anna@example.se från IP 192.168.1.5 om personnummer 19800101-1234."
    )
    redacted, mapping = redact(original, use_spacy=False)
    restored = hydrate(redacted, mapping)
    assert restored == original


def test_hydrate_unknown_placeholder_left_alone():
    text = "Hello PERSON_99 and EMAIL_42."
    restored = hydrate(text, {})
    assert restored == text


def test_redacted_text_has_no_original_values():
    original = "Erik bor i Stockholm. Mejla erik@test.se."
    redacted, mapping = redact(original, use_spacy=False)
    for value in mapping.values():
        assert value not in redacted


def test_placeholder_format():
    text = "Reach me at foo@bar.com."
    redacted, _ = redact(text, use_spacy=False)
    placeholders = re.findall(
        r"\b(?:PERSON|ORG|ORG_NR|LOCATION|EMAIL|PHONE|URL|SSN|IP)_\d+\b", redacted
    )
    assert len(placeholders) >= 1
    for p in placeholders:
        assert re.fullmatch(r"(?:ORG_NR|[A-Z]+)_\d+", p)


def test_full_name_collapses_to_single_placeholder():
    text = "Erik Andersson kom hit."
    redacted, mapping = redact(text, use_spacy=False)
    assert mapping == {"PERSON_1": "Erik Andersson"}
    assert redacted == "PERSON_1 kom hit."
    assert hydrate(redacted, mapping) == text


def test_overlap_resolution_in_pipeline():
    # 'Erik' (a name) inside an email — only the email should be redacted.
    text = "Mail address: erik@example.com is mine."
    redacted, mapping = redact(text, use_spacy=False)
    # The full email should appear in the mapping under EMAIL_1
    assert mapping["EMAIL_1"] == "erik@example.com"
    # The substring 'erik' should not have its own PERSON entry that overlaps
    # the email — i.e., we shouldn't double-redact.
    assert "erik@example.com" not in redacted
    # And the redacted output shouldn't contain a leftover bare PERSON_N
    # spliced into the middle of an email.
    assert "@example.com" not in redacted


def test_lowercase_hans_pronoun_not_tagged_person():
    text = "hans polska team"
    redacted, mapping = redact(text, use_spacy=False)
    assert redacted == text
    assert not any(k.startswith("PERSON_") for k in mapping)


def test_capitalized_hans_van_der_berg_tagged_as_one_person():
    text = "Hans van der Berg"
    redacted, mapping = redact(text, use_spacy=False)
    assert redacted == "PERSON_1"
    assert mapping == {"PERSON_1": text}


def test_lowercase_sin_not_tagged_person():
    text = "sin egen bil"
    redacted, mapping = redact(text, use_spacy=False)
    assert redacted == text
    assert not any(k.startswith("PERSON_") for k in mapping)


def test_capitalized_kim_andersson_tagged_person():
    text = "Kim Andersson ringde"
    redacted, mapping = redact(text, use_spacy=False)
    assert redacted.startswith("PERSON_1 ")
    assert mapping == {"PERSON_1": "Kim Andersson"}


def test_capitalized_hans_standalone_tagged_person():
    text = "Hans lovade"
    redacted, mapping = redact(text, use_spacy=False)
    assert redacted == "PERSON_1 lovade"
    assert mapping == {"PERSON_1": "Hans"}


def test_lowercase_per_common_phrase_not_tagged():
    text = "per kvadratmeter"
    redacted, mapping = redact(text, use_spacy=False)
    assert redacted == text
    assert not any(k.startswith("PERSON_") for k in mapping)


def test_capitalized_per_andersson_tagged_person():
    text = "Per Andersson"
    redacted, mapping = redact(text, use_spacy=False)
    assert redacted == "PERSON_1"
    assert mapping == {"PERSON_1": "Per Andersson"}


def test_hyphenated_name_lars_erik_johansson_is_single_person():
    text = "Lars-Erik Johansson"
    redacted, mapping = redact(text, use_spacy=False)
    assert redacted == "PERSON_1"
    assert mapping == {"PERSON_1": text}


def test_hyphenated_name_karl_johan_bergstrom_is_single_person():
    text = "Karl-Johan Bergström"
    redacted, mapping = redact(text, use_spacy=False)
    assert redacted == "PERSON_1"
    assert mapping == {"PERSON_1": text}


def test_hyphenated_name_anna_karin_lindqvist_is_single_person():
    text = "Anna-Karin Lindqvist"
    redacted, mapping = redact(text, use_spacy=False)
    assert redacted == "PERSON_1"
    assert mapping == {"PERSON_1": text}


def test_stopword_email_header_labels_not_tagged():
    text = "Datum: 18 mars 2026 14:32\nFrån: Anna\nTill: Erik"
    redacted, mapping = redact(text, use_spacy=False)
    assert "Datum" in redacted
    assert "Från" in redacted
    assert "Till" in redacted
    assert "Datum" not in mapping.values()
    assert "Från" not in mapping.values()
    assert "Till" not in mapping.values()


def test_stopword_sharepoint_not_tagged():
    text = "Hon delade Sharepoint: https://example.com/x"
    redacted, mapping = redact(text, use_spacy=False)
    assert "Sharepoint" in redacted
    assert "Sharepoint" not in mapping.values()


def test_signature_name_does_not_absorb_next_line_title():
    text = "Per-Olof Hägglund-Strömberg\nVD & Grundare"
    redacted, mapping = redact(text, use_spacy=False)
    assert any(v == "Per-Olof Hägglund-Strömberg" for v in mapping.values())
    assert not any("VD" in v for v in mapping.values())
    assert "VD & Grundare" in redacted


def test_hyphenated_double_surname_is_single_person():
    text = "Aleksandra Kowalczyk-Nowak"
    redacted, mapping = redact(text, use_spacy=False)
    assert redacted == "PERSON_1"
    assert mapping == {"PERSON_1": text}


def test_apos_particle_hyphenated_name_is_single_person():
    text = "Charlotte d'Aubigné-Lindberg"
    redacted, mapping = redact(text, use_spacy=False)
    assert redacted == "PERSON_1"
    assert mapping == {"PERSON_1": text}


def test_arabic_bin_name_is_single_person():
    text = "Yusuf bin Abdullah"
    redacted, mapping = redact(text, use_spacy=False)
    assert redacted == "PERSON_1"
    assert mapping == {"PERSON_1": text}


def test_arabic_ibn_name_is_single_person():
    text = "Mohammed ibn Rashid"
    redacted, mapping = redact(text, use_spacy=False)
    assert redacted == "PERSON_1"
    assert mapping == {"PERSON_1": text}


def test_arabic_abu_al_name_is_single_person():
    text = "Abu Bakr al-Sayed"
    redacted, mapping = redact(text, use_spacy=False)
    assert redacted == "PERSON_1"
    assert mapping == {"PERSON_1": text}
