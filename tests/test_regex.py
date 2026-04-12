"""Tests for regex pattern detection."""

import pytest

from stefan.detectors.regex import detect_regex


def _types(spans):
    return {s[2] for s in spans}


def _texts(spans, kind=None):
    return {s[3] for s in spans if kind is None or s[2] == kind}


def test_email_detection():
    text = "Contact me at johan.andersson@volvo.se for details."
    spans = detect_regex(text)
    assert "johan.andersson@volvo.se" in _texts(spans, "EMAIL")


def test_multiple_emails():
    text = "Send to a@example.com and b@example.org."
    spans = detect_regex(text)
    emails = _texts(spans, "EMAIL")
    assert "a@example.com" in emails
    assert "b@example.org" in emails


def test_url_detection():
    text = "Visit https://example.com/path?q=1 or www.test.se today."
    spans = detect_regex(text)
    urls = _texts(spans, "URL")
    assert any("example.com" in u for u in urls)
    assert any("test.se" in u for u in urls)


def test_swedish_personnummer_full():
    text = "Personnummer: 19850615-1234 är registrerat."
    spans = detect_regex(text)
    assert "19850615-1234" in _texts(spans, "SSN")


def test_swedish_personnummer_short():
    text = "Använd 850615-1234 som id."
    spans = detect_regex(text)
    assert "850615-1234" in _texts(spans, "SSN")


def _ssns(spans):
    return {s[3] for s in spans if s[2] == "SSN"}


def _org_nrs(spans):
    return {s[3] for s in spans if s[2] == "ORG_NR"}


def test_ssn_requires_dash_bare_digits_not_matched():
    text = "Order id 7208154729 without dash."
    spans = detect_regex(text)
    assert "SSN" not in _types(spans)


def test_phone_compact_not_tagged_ssn():
    text = "hennes nummer är 0701234567 och personnummer 720815-4729."
    spans = detect_regex(text)
    assert "0701234567" in _phones(spans)
    assert "720815-4729" in _ssns(spans)
    assert "0701234567" not in _ssns(spans)


def test_personnummer_twelve_digit_with_dash():
    text = "Registrerad 19720815-4729 här."
    spans = detect_regex(text)
    assert "19720815-4729" in _ssns(spans)


def test_personnummer_masked_last_four():
    text = "PERSON_2 (personnummer: 850512-XXXX) PERSON_3 (personnummer: 910303-XXXX)"
    spans = detect_regex(text)
    assert "850512-XXXX" in _ssns(spans)
    assert "910303-XXXX" in _ssns(spans)


def test_personnummer_twelve_digit_masked():
    text = "ID 19850615-XXXX är maskerat."
    spans = detect_regex(text)
    assert "19850615-XXXX" in _ssns(spans)


def test_org_nr_org_dot_nr_label():
    text = "Org.nr: 556789-1234"
    spans = detect_regex(text)
    assert "556789-1234" in _org_nrs(spans)
    assert "556789-1234" not in _ssns(spans)


def test_org_nr_organisationsnummer_label():
    text = "Organisationsnummer 556789-1234"
    spans = detect_regex(text)
    assert "556789-1234" in _org_nrs(spans)
    assert "556789-1234" not in _ssns(spans)


def test_org_nr_case_insensitive_label():
    text = "orgnr 556789-1234"
    spans = detect_regex(text)
    assert "556789-1234" in _org_nrs(spans)


def test_ipv4_detection():
    text = "Server at 192.168.1.100 and 10.0.0.1 are online."
    spans = detect_regex(text)
    ips = _texts(spans, "IP")
    assert "192.168.1.100" in ips
    assert "10.0.0.1" in ips


def test_ipv4_rejects_invalid_octet():
    text = "Not an IP: 999.999.999.999"
    spans = detect_regex(text)
    assert "999.999.999.999" not in _texts(spans, "IP")


def _phones(spans):
    return {s[3] for s in spans if s[2] == "PHONE"}


def test_phone_swedish_plus46_landline_spaced():
    text = "Central: +46 8 739 60 00"
    spans = detect_regex(text)
    assert "+46 8 739 60 00" in _phones(spans)


def test_phone_swedish_plus46_optional_zero_paren():
    text = "Alt: +46(0)8 739 60 00"
    spans = detect_regex(text)
    assert "+46(0)8 739 60 00" in _phones(spans)


def test_phone_swedish_landline_dash():
    text = "Ring 08-739 60 00 för info."
    spans = detect_regex(text)
    assert "08-739 60 00" in _phones(spans)


def test_phone_swedish_landline_spaced():
    text = "Eller 08 739 60 00 samma dag."
    spans = detect_regex(text)
    assert "08 739 60 00" in _phones(spans)


def test_phone_swedish_mobile_compact():
    text = "Mobil 0701234567 funkar."
    spans = detect_regex(text)
    assert "0701234567" in _phones(spans)


def test_phone_swedish_mobile_dash_grouped():
    text = "Säg 070-998 76 54 till dem."
    spans = detect_regex(text)
    assert "070-998 76 54" in _phones(spans)


def test_phone_swedish_mobile_spaced():
    text = "Nås på 070 998 76 54 kvällstid."
    spans = detect_regex(text)
    assert "070 998 76 54" in _phones(spans)


@pytest.mark.parametrize(
    "phone_text",
    [
        "+46 70 123 45 67",
        "+46 72 555 88 99",
        "+46 73 555 88 99",
        "+46 76 123 45 67",
        "+46 79 123 45 67",
        "+46(0)70 123 45 67",
        "+46-70-123-45-67",
        "070 123 45 67",
        "0701234567",
        "070-123 45 67",
    ],
)
def test_phone_requested_mobile_formats(phone_text):
    text = f"Kontakta mig på {phone_text} imorgon."
    spans = detect_regex(text)
    phones = [s for s in spans if s[2] == "PHONE"]
    assert len(phones) == 1
    assert phones[0][3] == phone_text


@pytest.mark.parametrize(
    "phone_text",
    [
        "0046-(0)8-545 67 890",
        "0046 73 555 88 99",
        "08-508 270 00",
        "08-508 09 000",
        "08 508 27000",
        "+358 50 1234567",
    ],
)
def test_phone_requested_additional_formats(phone_text):
    text = f"Tel: {phone_text}"
    spans = detect_regex(text)
    phones = [s for s in spans if s[2] == "PHONE"]
    assert any(p[3] == phone_text for p in phones)


def test_phone_min_digits():
    # Five digits is not a phone number
    text = "Order 12345 has shipped."
    spans = detect_regex(text)
    assert "PHONE" not in _types(spans)


def test_no_false_positives_on_plain_text():
    text = "The quick brown fox jumps over the lazy dog."
    spans = detect_regex(text)
    assert spans == []


def test_swedish_company_org_suffix():
    text = "We hired NCC Group, Peab Sverige AB, and Lindbergs Bygg AB for the project."
    spans = detect_regex(text)
    orgs = _texts(spans, "ORG")
    assert "NCC Group" in orgs
    assert "Peab Sverige AB" in orgs
    assert "Lindbergs Bygg AB" in orgs


@pytest.mark.parametrize(
    "org_text",
    [
        "El & Kraft AB",
        "H & M Sverige AB",
        "Atlas Copco AB",
        "Bergqvist & Söner Bygg HB",
    ],
)
def test_swedish_company_org_suffix_with_ampersand(org_text):
    spans = detect_regex(f"Avtal med {org_text} skrevs idag.")
    orgs = [s for s in spans if s[2] == "ORG"]
    assert len(orgs) == 1
    assert orgs[0][3] == org_text


@pytest.mark.parametrize(
    "org_text",
    [
        "Stockholm Vatten och Avfall AB",
        "Bygg och Anläggning AB",
        "Hus och Hem HB",
    ],
)
def test_swedish_company_org_suffix_with_connector_words(org_text):
    spans = detect_regex(f"Avtal med {org_text} skrevs idag.")
    orgs = [s for s in spans if s[2] == "ORG"]
    assert len(orgs) == 1
    assert orgs[0][3] == org_text


@pytest.mark.parametrize(
    "muni_text",
    [
        "Solna Stad",
        "Stockholms Stad",
        "Västerås Kommun",
        "Örebro Kommun",
        "Malmö Stad",
        "Göteborgs Stad",
        "Uppsala Kommun",
    ],
)
def test_swedish_municipality_authority_pattern(muni_text):
    spans = detect_regex(f"Avtal med {muni_text} signerades.")
    orgs = [s for s in spans if s[2] == "ORG"]
    assert len(orgs) == 1
    assert orgs[0][3] == muni_text


def _locs(spans):
    return {s[3] for s in spans if s[2] == "LOCATION"}


def test_swedish_address_full():
    text = "Besök oss på Sjöviksvägen 42, 120 65 Stockholm."
    spans = detect_regex(text)
    locs = _locs(spans)
    assert "Sjöviksvägen 42, 120 65 Stockholm" in locs


def test_swedish_address_street_number_only():
    text = "Butiken ligger på Drottninggatan 5."
    spans = detect_regex(text)
    assert "Drottninggatan 5" in _locs(spans)


def test_swedish_address_number_with_letter_and_postal():
    text = "Leverans till Storgatan 12B, 411 38 Göteborg."
    spans = detect_regex(text)
    assert "Storgatan 12B, 411 38 Göteborg" in _locs(spans)


def test_swedish_address_hamnplatsen():
    text = "Möte vid Hamnplatsen 3 imorgon."
    spans = detect_regex(text)
    assert "Hamnplatsen 3" in _locs(spans)


def test_swedish_address_multiword_street():
    text = "Besök Mäster Samuelsgatan 20, 111 44 Stockholm."
    spans = detect_regex(text)
    locs = _locs(spans)
    assert any("Mäster Samuelsgatan 20" in loc for loc in locs)
    assert not any(loc.startswith("Besök") for loc in locs)


def test_swedish_address_building_number_range():
    text = "Kontor Vasagatan 47-49 i stan."
    spans = detect_regex(text)
    assert "Vasagatan 47-49" in _locs(spans)


def test_swedish_address_kristinas_vag_separate_token():
    text = "Drottning Kristinas väg 14, 114 51 Stockholm."
    spans = detect_regex(text)
    locs = _locs(spans)
    assert any("Kristinas väg 14" in loc for loc in locs)


def test_swedish_apartment_lagenhet_list():
    text = "i lägenhet 1101, 1102 och 1201 ska särskild"
    spans = detect_regex(text)
    assert "lägenhet 1101, 1102 och 1201" in _locs(spans)


def test_swedish_apartment_lagenhet_single():
    text = "Boende i lägenhet 501 har anmält."
    spans = detect_regex(text)
    assert "lägenhet 501" in _locs(spans)


def test_swedish_apartment_lgh_standalone():
    text = "Ring innan besök, lgh 12B."
    spans = detect_regex(text)
    assert "lgh 12B" in _locs(spans)


def test_swedish_apartment_lagenhet_lgh_number():
    text = "badrummet i lägenhet LGH 1002 (som ägs"
    spans = detect_regex(text)
    assert "lägenhet LGH 1002" in _locs(spans)


def test_swedish_apartment_hyresgast_i_number():
    text = "Dessutom har hyresgästen i 1001, en fru"
    spans = detect_regex(text)
    assert "hyresgästen i 1001" in _locs(spans)


def test_advokatbyran_ampersand_co_org():
    text = "juridiska ombud på Advokatbyrån Nordquist & Co."
    spans = detect_regex(text)
    orgs = _texts(spans, "ORG")
    assert "Advokatbyrån Nordquist & Co." in orgs


def test_polish_sp_zoo_org():
    text = "underentreprenörer från Budimex z o.o. lämnat"
    spans = detect_regex(text)
    assert "Budimex z o.o." in _texts(spans, "ORG")


def _vals(spans, kind):
    return {s[3] for s in spans if s[2] == kind}


def test_swedish_bankgiro_patterns():
    text = "Bankgiro: 891-2746 och 5021-3456."
    spans = detect_regex(text)
    assert _vals(spans, "BANKGIRO") == {"891-2746", "5021-3456"}


def test_swedish_plusgiro_spaced():
    text = "Plusgiro: 47 11 47-9"
    spans = detect_regex(text)
    assert "47 11 47-9" in _vals(spans, "PLUSGIRO")


def test_swedish_bank_account_seb():
    text = "SEB-konto: 5439-10 123 45 678"
    spans = detect_regex(text)
    assert "5439-10 123 45 678" in _vals(spans, "BANK_ACCOUNT")


def test_swedish_bank_account_swedbank():
    text = "Swedbanks konto 8327-9 123 456 789-0"
    spans = detect_regex(text)
    assert "8327-9 123 456 789-0" in _vals(spans, "BANK_ACCOUNT")


def test_swedish_bank_account_nordea():
    text = "Nordea 3300 12 3456"
    spans = detect_regex(text)
    assert "3300 12 3456" in _vals(spans, "BANK_ACCOUNT")


def test_swedish_iban_unchanged():
    text = "IBAN SE45 5000 0000 0583 9825 7466"
    spans = detect_regex(text)
    assert "SE45 5000 0000 0583 9825 7466" in _vals(spans, "IBAN")


def test_bank_routing_not_misclassified_as_phone():
    text = "Ring oss 5439-10 123 45 678 för mer info."
    spans = detect_regex(text)
    assert "5439-10 123 45 678" in _vals(spans, "BANK_ACCOUNT")
    phones = _phones(spans)
    assert not any("5439" in p or "123 45" in p for p in phones)


@pytest.mark.parametrize(
    "ref_text",
    [
        "BL-2026-9999",
        "RS-2026-04-1847",
        "F-2026-12",
        "2026-9999",
        "Ref: 2026-04-1847",
    ],
)
def test_reference_ids_not_tagged_as_bank_routing(ref_text):
    spans = detect_regex(ref_text)
    assert _vals(spans, "BANK_ACCOUNT") == set()
    assert _vals(spans, "BANKGIRO") == set()
    assert _vals(spans, "PLUSGIRO") == set()


def test_combined_swedish_payment_routing_redact():
    """End-to-end: bank routing numbers become placeholders, not plain text."""
    from stefan.redactor import redact

    text = (
        "Bankgiro: 891-2746 och Bankgiro: 5021-3456. "
        "Plusgiro: 47 11 47-9. "
        "SEB-konto: 5439-10 123 45 678. "
        "Swedbanks konto 8327-9 123 456 789-0. "
        "Nordea 3300 12 3456. "
        "IBAN SE45 5000 0000 0583 9825 7466."
    )
    redacted, mapping = redact(text, use_spacy=False)
    for secret in (
        "891-2746",
        "5021-3456",
        "47 11 47-9",
        "5439-10 123 45 678",
        "8327-9 123 456 789-0",
        "3300 12 3456",
        "SE45 5000 0000 0583 9825 7466",
    ):
        assert secret not in redacted
        assert secret in mapping.values()
