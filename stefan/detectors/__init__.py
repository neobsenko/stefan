"""Detection modules for stefan."""

from stefan.detectors.regex import detect_regex
from stefan.detectors.dictionary import detect_dictionary
from stefan.detectors.dictionary_orgs import detect_dictionary_orgs
from stefan.detectors.nlp import detect_spacy
from stefan.detectors.merger import merge_spans

__all__ = [
    "detect_regex",
    "detect_dictionary",
    "detect_dictionary_orgs",
    "detect_spacy",
    "merge_spans",
]
