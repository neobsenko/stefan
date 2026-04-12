"""Tests for Swedish org acronym dictionary detection."""

from stefan.detectors.dictionary_orgs import detect_dictionary_orgs, reload_org_dictionaries


def _orgs(spans):
    return {s[3] for s in spans if s[2] == "ORG"}


def test_org_acronym_abb_case_sensitive():
    spans = detect_dictionary_orgs("Contract with ABB for motors.")
    assert "ABB" in _orgs(spans)


def test_org_acronym_lowercase_not_matched():
    spans = detect_dictionary_orgs("The abb lowercase should not tag.")
    assert "abb" not in _orgs(spans)
    assert _orgs(spans) == set()


def test_org_multiword_phrase():
    spans = detect_dictionary_orgs("Atlas Copco supplies compressors.")
    assert "Atlas Copco" in _orgs(spans)


def test_org_h_and_m():
    spans = detect_dictionary_orgs("Shop at H&M in Stockholm.")
    assert "H&M" in _orgs(spans)


def test_construction_supplier_ahlsell_detected_as_org():
    spans = detect_dictionary_orgs("Vi beställer från Ahlsell idag.")
    assert "Ahlsell" in _orgs(spans)


def test_construction_supplier_rexel_detected_as_org():
    spans = detect_dictionary_orgs("Han föreslog Rexel som backup.")
    assert "Rexel" in _orgs(spans)


def test_construction_supplier_multiword_detected_as_org():
    spans = detect_dictionary_orgs("Leverans från Schneider Electric kom fram.")
    assert "Schneider Electric" in _orgs(spans)


def test_authority_boverket_detected_as_org():
    spans = detect_dictionary_orgs("Vi väntar på besked från Boverket.")
    assert "Boverket" in _orgs(spans)


def test_authority_trafikverket_detected_as_org():
    spans = detect_dictionary_orgs("Även Trafikverket har hört av sig.")
    assert "Trafikverket" in _orgs(spans)


def test_staffing_manpower_bare_word():
    reload_org_dictionaries()
    spans = detect_dictionary_orgs("anställd via Manpower som konsult.")
    assert "Manpower" in _orgs(spans)


def test_law_firm_vinge():
    reload_org_dictionaries()
    spans = detect_dictionary_orgs("kontaktat Advokatfirman Vinge.")
    assert "Advokatfirman Vinge" in _orgs(spans)


def test_municipal_stadsbyggnadskontoret():
    reload_org_dictionaries()
    spans = detect_dictionary_orgs("ärendet hos Stadsbyggnadskontoret.")
    assert "Stadsbyggnadskontoret" in _orgs(spans)
