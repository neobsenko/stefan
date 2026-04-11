"""Tests for span merging and priority resolution."""

from reduct.detectors.merger import merge_spans
from reduct.redactor import redact


def test_no_overlap_keeps_all():
    regex = [(0, 5, "EMAIL", "a@b.c")]
    dict_ = [(10, 15, "PERSON", "Johan")]
    spacy = [(20, 25, "ORG", "Volvo")]
    merged = merge_spans(regex, dict_, spacy)
    assert len(merged) == 3


def test_regex_beats_dictionary_on_overlap():
    # Imagine "Johan" overlaps with "johan@x.se" — regex should win.
    regex = [(0, 11, "EMAIL", "johan@x.se")]
    dict_ = [(0, 5, "PERSON", "johan")]
    merged = merge_spans(regex, dict_, [])
    assert len(merged) == 1
    assert merged[0][2] == "EMAIL"


def test_dictionary_beats_spacy_on_overlap():
    dict_ = [(0, 5, "PERSON", "Johan")]
    spacy = [(0, 14, "PERSON", "Johan Andersso")]
    merged = merge_spans([], dict_, spacy)
    # PERSON overlap rule is widest span first (cross-source), then priority.
    assert len(merged) == 1
    assert merged[0][3] == "Johan Andersso"


def test_regex_beats_spacy_on_overlap():
    regex = [(5, 20, "EMAIL", "a@example.com")]
    spacy = [(0, 25, "ORG", "Some big org name here")]
    merged = merge_spans(regex, [], spacy)
    assert len(merged) == 1
    assert merged[0][2] == "EMAIL"


def test_returned_spans_sorted_by_start():
    regex = [(50, 60, "EMAIL", "x@y.z")]
    dict_ = [(0, 5, "PERSON", "Erik")]
    spacy = [(20, 30, "ORG", "Volvo")]
    merged = merge_spans(regex, dict_, spacy)
    starts = [s[0] for s in merged]
    assert starts == sorted(starts)


def test_no_overlapping_output():
    # Create messy overlapping inputs from all sources
    regex = [(0, 10, "EMAIL", "a@b.com")]
    dict_ = [(5, 15, "PERSON", "Johan")]
    spacy = [(8, 20, "ORG", "Bolaget")]
    merged = merge_spans(regex, dict_, spacy)
    for i, a in enumerate(merged):
        for b in merged[i + 1 :]:
            assert a[1] <= b[0] or b[1] <= a[0]


def test_adjacent_persons_merged_with_text():
    text = "Erik Andersson kom hit."
    dict_ = [(0, 4, "PERSON", "Erik"), (5, 14, "PERSON", "Andersson")]
    merged = merge_spans([], dict_, [], text=text)
    assert len(merged) == 1
    assert merged[0] == (0, 14, "PERSON", "Erik Andersson")


def test_adjacent_persons_chain_merged():
    # Three consecutive PERSON spans should collapse into one in repeated passes
    text = "Erik Anders Andersson kom hit."
    dict_ = [
        (0, 4, "PERSON", "Erik"),
        (5, 11, "PERSON", "Anders"),
        (12, 21, "PERSON", "Andersson"),
    ]
    merged = merge_spans([], dict_, [], text=text)
    assert len(merged) == 1
    assert merged[0] == (0, 21, "PERSON", "Erik Anders Andersson")


def test_persons_not_merged_when_gap_too_wide():
    text = "Erik och Andersson är kollegor."
    dict_ = [(0, 4, "PERSON", "Erik"), (9, 18, "PERSON", "Andersson")]
    merged = merge_spans([], dict_, [], text=text)
    assert len(merged) == 2


def test_persons_not_merged_across_other_type():
    text = "Erik Volvo Andersson"
    dict_ = [(0, 4, "PERSON", "Erik"), (11, 20, "PERSON", "Andersson")]
    spacy = [(5, 10, "ORG", "Volvo")]
    merged = merge_spans([], dict_, spacy, text=text)
    # ORG sits between the two persons, so they must remain separate
    types = [m[2] for m in merged]
    assert types.count("PERSON") == 2
    assert "ORG" in types


def test_no_text_param_skips_person_glue():
    # Backwards-compat: omitting text leaves adjacent persons unmerged
    dict_ = [(0, 4, "PERSON", "Erik"), (5, 14, "PERSON", "Andersson")]
    merged = merge_spans([], dict_, [])
    assert len(merged) == 2


def test_within_same_source_longer_wins():
    spacy = [
        (0, 5, "PERSON", "Johan"),
        (0, 14, "PERSON", "Johan Andersso"),
    ]
    merged = merge_spans([], [], spacy)
    assert len(merged) == 1
    assert merged[0][3] == "Johan Andersso"


def test_merge_adjacent_org_ikea_fastigheter_ab():
    text = "IKEA Fastigheter AB"
    dict_ = [(0, 4, "ORG", "IKEA"), (5, 19, "ORG", "Fastigheter AB")]
    merged = merge_spans([], dict_, [], text=text)
    assert len(merged) == 1
    assert merged[0] == (0, len(text), "ORG", text)


def test_merge_adjacent_org_volvo_group_sverige_ab():
    text = "Volvo Group Sverige AB"
    dict_ = [(0, 5, "ORG", "Volvo"), (12, 22, "ORG", "Sverige AB")]
    merged = merge_spans([], dict_, [], text=text)
    assert len(merged) == 1
    assert merged[0] == (0, len(text), "ORG", text)


def test_merge_adjacent_org_skanska_international_holdings():
    text = "Skanska International Holdings"
    dict_ = [(0, 7, "ORG", "Skanska"), (22, 30, "ORG", "Holdings")]
    merged = merge_spans([], dict_, [], text=text)
    assert len(merged) == 1
    assert merged[0] == (0, len(text), "ORG", text)


def test_redact_single_org_ikea_fastigheter_ab_end_to_end():
    text = "IKEA Fastigheter AB"
    redacted, mapping = redact(text, use_spacy=False)
    assert redacted == "ORG_1"
    assert mapping == {"ORG_1": text}


def test_redact_single_org_volvo_group_sverige_ab_end_to_end():
    text = "Volvo Group Sverige AB"
    redacted, mapping = redact(text, use_spacy=False)
    assert redacted == "ORG_1"
    assert mapping == {"ORG_1": text}


def test_redact_single_org_skanska_international_holdings_end_to_end():
    text = "Skanska International Holdings"
    redacted, mapping = redact(text, use_spacy=False)
    assert redacted == "ORG_1"
    assert mapping == {"ORG_1": text}


def test_stopword_id06_not_tagged_as_any_entity():
    text = "alla nya arbetare måste registreras i ID06"
    redacted, mapping = redact(text, use_spacy=False)
    assert "ID06" in redacted
    assert "ID06" not in mapping.values()


def test_stopword_hr_not_tagged_but_skanska_still_detected():
    text = "kan någon från HR på Skanska fixa det"
    redacted, mapping = redact(text, use_spacy=False)
    assert "HR" in redacted
    assert "HR" not in mapping.values()
    assert any(v == "Skanska" for v in mapping.values())


def test_coreference_links_unambiguous_first_name_to_full_name():
    text = "Tomasz Wiśniewski ringde. Senare rapporterade Tomasz."
    redacted, mapping = redact(text, use_spacy=False)
    person_keys = [k for k in mapping if k.startswith("PERSON_")]
    assert len(person_keys) == 1
    assert mapping[person_keys[0]] == "Tomasz Wiśniewski"
    assert redacted.count(person_keys[0]) == 2


def test_coreference_skips_ambiguous_shared_first_name():
    text = "Anna Andersson mötte Anna Bergström. Senare sa Anna hej."
    redacted, mapping = redact(text, use_spacy=False)
    person_keys = [k for k in mapping if k.startswith("PERSON_")]
    assert len(person_keys) == 2
    assert "Anna hej" in redacted


def test_coreference_respects_lowercase_pronoun_collision():
    text = "Hans van der Berg kom. senare behövde hans polska team hjälp."
    redacted, mapping = redact(text, use_spacy=False)
    assert any(v == "Hans van der Berg" for v in mapping.values())
    assert "hans polska team" in redacted


def test_stopword_innan_not_tagged_after_id06():
    text = "registreras i ID06 innan de börjar"
    redacted, mapping = redact(text, use_spacy=False)
    assert "ID06" in redacted
    assert "innan" in redacted
    assert "ID06" not in mapping.values()
    assert "innan" not in mapping.values()


def test_stopword_currency_and_units_not_tagged():
    text = "Budgetpåverkan: 340 000 SEK och vikt 50 KG"
    redacted, mapping = redact(text, use_spacy=False)
    assert "SEK" in redacted
    assert "KG" in redacted
    assert "SEK" not in mapping.values()
    assert "KG" not in mapping.values()


def test_coreference_links_capitalized_hans_to_full_name():
    text = "Hans van der Berg kom först. Hans lovade att ringa senare."
    redacted, mapping = redact(text, use_spacy=False)
    person_keys = [k for k in mapping if k.startswith("PERSON_")]
    assert len(person_keys) == 1
    assert mapping[person_keys[0]] == "Hans van der Berg"
    assert redacted.count(person_keys[0]) == 2


def test_org_span_wins_over_nested_location_for_stockholm_name():
    text = "Stockholm Vatten och Avfall AB"
    regex = [(0, len(text), "ORG", text)]
    spacy = [(0, 9, "LOCATION", "Stockholm")]
    merged = merge_spans(regex, [], spacy, text=text)
    assert merged == [(0, len(text), "ORG", text)]
