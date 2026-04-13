"""Dictionary-based name detection."""

import re
from functools import lru_cache
from pathlib import Path
from typing import List, Set, Tuple

DATA_DIR = Path(__file__).parent.parent / "data"

_NAME_FILES = (
    "swedish_first_names.txt",
    "swedish_surnames.txt",
    "polish_names.txt",
    "finnish_names.txt",
    "arabic_names_transliterated.txt",
    "slavic_names.txt",
    "custom_names.txt",
)

# Swedish name/word collisions. Lowercase forms are treated as common words,
# not people names, unless the token itself is capitalized.
PRONOUN_COLLISION_NAMES = frozenset(
    {"hans", "sin", "sina", "kim", "tor", "pär", "per", "bo", "siv", "ann"}
)


def reload_name_dictionaries() -> None:
    """Invalidate cached name lists (e.g. after editing ``custom_names.txt``)."""
    _load_names.cache_clear()


@lru_cache(maxsize=1)
def _load_names() -> Set[str]:
    """Load first/surnames from bundled + custom lists (lowercased)."""
    names: Set[str] = set()
    for filename in _NAME_FILES:
        path = DATA_DIR / filename
        if not path.exists():
            continue
        with path.open(encoding="utf-8") as f:
            for line in f:
                name = line.strip()
                if name:
                    names.add(name.lower())
    return names


# Swedish postal code prefix that precedes city names: 5 digits with optional space (NNN NN or NNNNN) + space.
# Used to exclude false PERSON matches (e.g. "Lund" in "203 93 Lund" or "Uppsala" in "481 82 Uppsala").
_POSTAL_CODE_PREFIX_RE = re.compile(r"\d{3}\s?\d{2}\s+$")

# Unicode word tokens (covers Polish, Nordic, etc.).
_WORD_RE = re.compile(r"\b\w+\b", re.UNICODE)

# Hyphenated compounds split into separate \w tokens; protect known abbreviations
# so sub-tokens (e.g. BAS from BAS-U) are not tagged as PERSON.
_PROTECTED_COMPOUND_RE = re.compile(
    r"\b(?:BAS-U|BAS-P|BASU|BASP|ID-06|F-skatt|F-skattebevis|"
    r"A-traktor|B-körkort|C-körkort|D-körkort|E-handel|E-faktura|E-post|"
    r"A-kassa|P-plats|P-hus|T-bana|T-shirt)\b",
    re.IGNORECASE,
)


def _protected_compound_spans(text: str) -> List[Tuple[int, int]]:
    return [(m.start(), m.end()) for m in _PROTECTED_COMPOUND_RE.finditer(text)]


def _overlaps_any(start: int, end: int, ranges: List[Tuple[int, int]]) -> bool:
    return any(start < pe and end > ps for ps, pe in ranges)


def detect_dictionary(text: str) -> List[Tuple[int, int, str, str]]:
    """Find known personal names in text.

    Returns a list of (start, end, "PERSON", matched_text) tuples.
    Whole-token matching, case-insensitive.
    """
    names = _load_names()
    protected = _protected_compound_spans(text)
    spans: List[Tuple[int, int, str, str]] = []
    tokens = list(_WORD_RE.finditer(text))
    for i, match in enumerate(tokens):
        w0, w1 = match.start(), match.end()
        if protected and _overlaps_any(w0, w1, protected):
            continue
        word = match.group(0)
        if not any(c.isalpha() for c in word):
            continue
        word_l = word.lower()
        if word_l not in names:
            continue

        # Dictionary PERSON matches must start with a capital letter.
        if not word[0].isupper():
            continue

        # Guardrail for lowercase name/common-word collisions in prose.
        if word.islower() and word_l in PRONOUN_COLLISION_NAMES and i + 1 < len(tokens):
            nxt = tokens[i + 1].group(0)
            if nxt and nxt[0].islower():
                continue

        # Skip names that follow a Swedish postal code (e.g. "203 93 Lund").
        if _POSTAL_CODE_PREFIX_RE.search(text[:w0]):
            continue

        spans.append((match.start(), match.end(), "PERSON", word))
    return spans
