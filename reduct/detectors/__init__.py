"""Detection modules for reduct."""

from reduct.detectors.regex import detect_regex
from reduct.detectors.dictionary import detect_dictionary
from reduct.detectors.dictionary_orgs import detect_dictionary_orgs
from reduct.detectors.nlp import detect_spacy
from reduct.detectors.merger import merge_spans

__all__ = [
    "detect_regex",
    "detect_dictionary",
    "detect_dictionary_orgs",
    "detect_spacy",
    "merge_spans",
]
