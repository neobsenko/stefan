"""Coverage for Swedish construction-document LOCATION detection."""

import pytest

from stefan.redactor import redact


def _values(mapping, prefix):
    return {value for key, value in mapping.items() if key.startswith(prefix)}


@pytest.mark.parametrize("city", ["Stockholm", "Göteborg", "Uppsala"])
def test_major_swedish_cities_are_locations(city):
    _, mapping = redact(f"Plats: {city}\nByggstart nästa vecka.", use_spacy=False)

    assert city in _values(mapping, "LOCATION_")


@pytest.mark.parametrize(
    "location",
    [
        "Karolinska Universitetssjukhuset Solna",
        "Sahlgrenska Universitetssjukhuset",
    ],
)
def test_institutional_locations_are_locations(location):
    _, mapping = redact(f"Arbetsplats: {location}\nSkyddsronder bokas.", use_spacy=False)

    assert location in _values(mapping, "LOCATION_")
    assert location not in _values(mapping, "ORG_")


def test_boverket_is_location_in_regulatory_context():
    _, mapping = redact(
        "Handlingar skickas till Boverket enligt kontrollplanen.",
        use_spacy=False,
    )

    assert "Boverket" in _values(mapping, "LOCATION_")
    assert "Boverket" not in _values(mapping, "ORG_")


def test_municipal_area_is_location():
    _, mapping = redact(
        "Samråd hålls med Östermalms Stadsdelsförvaltning under projekteringen.",
        use_spacy=False,
    )

    assert "Östermalms Stadsdelsförvaltning" in _values(mapping, "LOCATION_")
    assert "Östermalms Stadsdelsförvaltning" not in _values(mapping, "ORG_")


@pytest.mark.parametrize("city_authority", ["Göteborgs Stad", "Stockholms Stad"])
def test_city_authorities_are_locations_not_orgs(city_authority):
    _, mapping = redact(
        f"Bygglovsdialog med {city_authority} fortsätter på torsdag.",
        use_spacy=False,
    )

    assert city_authority in _values(mapping, "LOCATION_")
    assert city_authority not in _values(mapping, "ORG_")


def test_compact_postal_code_full_address_is_single_location():
    text = "Plats: Mäster Samuelsgatan 16, 11144 Stockholm"
    _, mapping = redact(text, use_spacy=False)
    assert "Mäster Samuelsgatan 16, 11144 Stockholm" in _values(mapping, "LOCATION_")


def test_compact_postal_code_vag_address_is_single_location():
    text = "Adress: Drottning Kristinas väg 14, 11434 Stockholm"
    _, mapping = redact(text, use_spacy=False)
    assert "Drottning Kristinas väg 14, 11434 Stockholm" in _values(mapping, "LOCATION_")
