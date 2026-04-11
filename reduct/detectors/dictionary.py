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


# Unicode word tokens (covers Polish, Nordic, etc.).
_WORD_RE = re.compile(r"\b\w+\b", re.UNICODE)


def detect_dictionary(text: str) -> List[Tuple[int, int, str, str]]:
    """Find known personal names in text.

    Returns a list of (start, end, "PERSON", matched_text) tuples.
    Whole-token matching, case-insensitive.
    """
    names = _load_names()
    spans: List[Tuple[int, int, str, str]] = []
    tokens = list(_WORD_RE.finditer(text))
    for i, match in enumerate(tokens):
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

        spans.append((match.start(), match.end(), "PERSON", word))
    return spans
