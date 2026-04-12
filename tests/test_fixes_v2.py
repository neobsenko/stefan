"""Regression tests for fixes v2 (all 15 fix areas)."""

import pytest
from stefan.redactor import redact
from stefan.detectors.merger import merge_spans


# --- Fix 1: Hyphenated apostrophe double surnames ---

@pytest.mark.parametrize("name,full", [
    ("Henrik O'Sullivan-Berg ringde", "Henrik O'Sullivan-Berg"),
    ("Henrik O'Brien-Lundgren ringde", "Henrik O'Brien-Lundgren"),
    ("Sean O'Sullivan-Murphy ringde", "Sean O'Sullivan-Murphy"),
    ("Charlotte d'Aubign\u00e9-Lindberg ringde", "Charlotte d'Aubign\u00e9-Lindberg"),
])
def test_apostrophe_hyphen_name_is_one_person(name, full):
    _, m = redact(name, use_spacy=False)
    assert full in m.values()


# --- Fix 2: Multi-word company names ---

@pytest.mark.parametrize("org", [
    "Bygg & Pl\u00e5t i Stockholm AB",
    "Svensk Bygg & Konstruktion AB",
    "Stockholms Byggservice & Renovering HB",
    "El & Kraft Stockholm KB",
    "Stockholm Vatten och Avfall AB",
    "Bygg och Anl\u00e4ggning Stockholm AB",
])
def test_multiword_company_name_one_org(org):
    _, m = redact(f"Partner: {org} ringde", use_spacy=False)
    assert org in m.values()


# --- Fix 3: Extended Unicode characters in names ---

@pytest.mark.parametrize("text,full", [
    ("Aigars B\u0113rzi\u0146\u0161 ringde", "Aigars B\u0113rzi\u0146\u0161"),
    ("\u00c7a\u011fr\u0131 Y\u0131lmaz-Demir ringde", "\u00c7a\u011fr\u0131 Y\u0131lmaz-Demir"),
    ("Krzysztof Wi\u015bniewski ringde", "Krzysztof Wi\u015bniewski"),
    ("Fran\u00e7ois d'Aubign\u00e9 ringde", "Fran\u00e7ois d'Aubign\u00e9"),
])
def test_extended_unicode_names(text, full):
    _, m = redact(text, use_spacy=False)
    assert full in m.values()


# --- Fix 4: Address with apartment ---

@pytest.mark.parametrize("addr", [
    "Storgatan 45, lgh 1203, 112 45 Stockholm",
    "Storgatan 8B, lgh 1402, 112 45 Stockholm",
    "Hornsgatan 156, 118 28 Stockholm",
    "Villav\u00e4gen 8, 187 65 T\u00e4by",
])
def test_address_with_apartment(addr):
    _, m = redact(f"Adress: {addr}", use_spacy=False)
    assert addr in m.values()


# --- Fix 5: Sjukhus/institutions as ORG ---

@pytest.mark.parametrize("org", [
    "Karolinska Universitetssjukhuset Solna",
    "Karolinska Institutet",
    "Stockholms Universitet",
    "Sahlgrenska Universitetssjukhuset",
    "Akademiska Sjukhuset Uppsala",
])
def test_institution_as_org(org):
    _, m = redact(f"Projekt: {org}", use_spacy=False)
    assert org in m.values()


# --- Fix 6: SEB as ORG not PERSON ---

def test_seb_bank_as_org_not_person():
    r, m = redact("mitt konto: SEB 5439-10 123 45 678", use_spacy=False)
    assert "SEB" in m.values()
    assert "PERSON" not in r


# --- Fix 7: Quoted nicknames ---

@pytest.mark.parametrize("text,full", [
    ('Anders "Anki" Bergstr\u00f6m ringde', 'Anders "Anki" Bergstr\u00f6m'),
    ('Per-Olof "P-O" H\u00e4gglund-Str\u00f6mberg ringde',
     'Per-Olof "P-O" H\u00e4gglund-Str\u00f6mberg'),
    ('Lars-Erik "Lasse" Johansson ringde', 'Lars-Erik "Lasse" Johansson'),
    ('Robert "Bob" Smith ringde', 'Robert "Bob" Smith'),
])
def test_quoted_nickname_one_person(text, full):
    _, m = redact(text, use_spacy=False)
    assert full in m.values()


# --- Fix 8: Familjen + surname ---

@pytest.mark.parametrize("text,full", [
    ("Familjen Andersson har kommit", "Familjen Andersson"),
    ("Familjen von Heidenstam-Lagerl\u00f6f har kommit",
     "Familjen von Heidenstam-Lagerl\u00f6f"),
    ("Familjen Bergstr\u00f6m har kommit", "Familjen Bergstr\u00f6m"),
])
def test_familjen_surname(text, full):
    _, m = redact(text, use_spacy=False)
    assert full in m.values()


# --- Fix 9: Unions as ORG ---

def test_unionen_as_org():
    _, m = redact(
        "fackrepresentant Stig Bergstr\u00f6m fr\u00e5n Unionen",
        use_spacy=False,
    )
    assert "Unionen" in m.values()


# --- Fix 10: Address city after postal code ---

@pytest.mark.parametrize("addr", [
    "Bj\u00f6rkv\u00e4gen 12, 152 41 S\u00f6dert\u00e4lje",
    "Storgatan 45, 112 45 Stockholm",
    "Industrigatan 5, 117 43 Stockholm",
])
def test_address_city_after_postal(addr):
    _, m = redact(f"Adress: {addr}", use_spacy=False)
    assert addr in m.values()


# --- Fix 11: International phone ---

@pytest.mark.parametrize("phone", [
    "+47 22 11 33 44",
    "+48 22 555 4455",
    "+353 1 234 5678",
])
def test_international_phone(phone):
    _, m = redact(f"Ring {phone} imorgon", use_spacy=False)
    assert phone in m.values()


# --- Fix 12: Swedish public sector ---

@pytest.mark.parametrize("org", [
    "Region Stockholm",
    "Stockholms Idrottsf\u00f6rvaltning",
    "Utbildningsf\u00f6rvaltningen Stockholm",
    "\u00d6stermalms Stadsdelsf\u00f6rvaltning",
    "Solna Stad",
])
def test_public_sector_org(org):
    _, m = redact(f"Projekt: {org}", use_spacy=False)
    assert org in m.values()


# --- Fix 13: International company suffixes ---

@pytest.mark.parametrize("org", [
    "M\u00fcller GmbH",
    "M\u00fcller GmbH & Co. KG",
    "O'Brien Construction Ltd",
    "Bouygues Construction",
    "KONE Oyj",
])
def test_intl_company_suffix(org):
    _, m = redact(f"Partner: {org} ringde", use_spacy=False)
    assert org in m.values()


# --- Fix 14: Box addresses ---

def test_box_address():
    _, m = redact("Box 1234, 123 45 Stockholm", use_spacy=False)
    assert "Box 1234, 123 45 Stockholm" in m.values()


# --- Fix 15: Coreference with hyphenated first names ---

def test_coreference_hyphenated_first_name():
    text = (
        "Mats-Erik Lundqvist ringde.\n"
        "Hej Mats-Erik,\n"
        "Mats-Erik sa att det var bra."
    )
    r, m = redact(text, use_spacy=False)
    person_keys = [k for k in m if k.startswith("PERSON_")]
    assert len(person_keys) == 1
    assert m[person_keys[0]] == "Mats-Erik Lundqvist"
    assert r.count(person_keys[0]) >= 3
