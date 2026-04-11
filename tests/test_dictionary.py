"""Tests for dictionary-based name detection."""

from reduct.detectors.dictionary import detect_dictionary


def _texts(spans):
    return [s[3] for s in spans]


def test_first_name_detection():
    text = "Johan kommer imorgon."
    spans = detect_dictionary(text)
    assert "Johan" in _texts(spans)


def test_surname_detection():
    text = "Mr. Andersson signed the contract."
    spans = detect_dictionary(text)
    assert "Andersson" in _texts(spans)


def test_full_name_detection():
    text = "Johan Andersson är vd."
    spans = detect_dictionary(text)
    found = _texts(spans)
    assert "Johan" in found
    assert "Andersson" in found


def test_lowercase_name_not_tagged_dictionary_person():
    """Dictionary PERSON requires a capitalized token; lowercase 'johan' is skipped."""
    text = "JOHAN and johan are the same name."
    spans = detect_dictionary(text)
    found = _texts(spans)
    assert "JOHAN" in found
    assert "johan" not in found


def test_whole_word_only():
    # 'Bo' is a name, but 'Bond' should not match
    text = "James Bond is a character."
    spans = detect_dictionary(text)
    found = _texts(spans)
    assert "Bond" not in found


def test_no_match_unknown_word():
    text = "Xyzzy is not a real name."
    spans = detect_dictionary(text)
    assert _texts(spans) == []


def test_swedish_chars_in_name():
    text = "Åsa kommer också."
    spans = detect_dictionary(text)
    assert "Åsa" in _texts(spans)


def test_all_returned_spans_are_person_type():
    text = "Erik och Anna träffades."
    spans = detect_dictionary(text)
    assert all(s[2] == "PERSON" for s in spans)
    assert len(spans) >= 2
