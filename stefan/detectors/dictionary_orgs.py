"""Dictionary-based detection of well-known Swedish company names and acronyms."""

import re
from functools import lru_cache
from pathlib import Path
from typing import List, Optional, Tuple

DATA_DIR = Path(__file__).parent.parent / "data"
_ORG_DICTIONARY_FILES = (
    "swedish_org_acronyms.txt",
    "construction_orgs.txt",
    "swedish_insurance_finance.txt",
    "swedish_law_firms.txt",
    "staffing_companies.txt",
    "swedish_municipal_departments.txt",
)


@lru_cache(maxsize=1)
def _phrases_by_length() -> List[str]:
    """Phrases longest-first so multi-word names win over embedded tokens."""
    phrases: List[str] = []
    for filename in _ORG_DICTIONARY_FILES:
        path = DATA_DIR / filename
        if not path.exists():
            continue
        with path.open(encoding="utf-8") as f:
            for line in f:
                p = line.strip()
                if p:
                    phrases.append(p)
    # Preserve first occurrence order while deduping across files.
    phrases = list(dict.fromkeys(phrases))
    phrases.sort(key=len, reverse=True)
    return phrases


@lru_cache(maxsize=1)
def _compiled_pattern() -> Optional[re.Pattern]:
    phrases = _phrases_by_length()
    if not phrases:
        return None
    body = "|".join(re.escape(p) for p in phrases)
    return re.compile(rf"\b(?:{body})\b")


def reload_org_dictionaries() -> None:
    """Invalidate cached org phrase lists (e.g. after editing ``construction_orgs.txt``)."""
    _phrases_by_length.cache_clear()
    _compiled_pattern.cache_clear()


def detect_dictionary_orgs(text: str) -> List[Tuple[int, int, str, str]]:
    """Match known org acronyms / names as whole tokens (case-sensitive), tag ORG."""
    pattern = _compiled_pattern()
    if pattern is None:
        return []
    spans: List[Tuple[int, int, str, str]] = []
    for m in pattern.finditer(text):
        spans.append((m.start(), m.end(), "ORG", m.group(0)))
    return spans
