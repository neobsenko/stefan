"""Context-based PERSON detection (regex / high priority in merger)."""

import re
from typing import List, Tuple

# Capture group index for the name span (always group 1).
_PATTERNS: List[Tuple[re.Pattern, int]] = [
    (
        re.compile(
            r"^Hej\s+"
            r"([A-ZÄÖÅĄĆĘŁŃÓŚŹŻ][a-zäöåA-ZÄÖÅĄĆĘŁŃÓŚŹŻ\-]+"
            r"(?:[ \t]+[A-ZÄÖÅĄĆĘŁŃÓŚŹŻ][a-zäöåA-ZÄÖÅĄĆĘŁŃÓŚŹŻ\-]+)?)[ \t]*,?",
            re.MULTILINE,
        ),
        1,
    ),
    (
        re.compile(
            r"(?:Mvh|Med vänlig hälsning|Vänliga hälsningar|Hälsningar|Bästa hälsningar|"
            r"BR|Best regards),?\s*\n+\s*"
            r"([A-ZÄÖÅĄĆĘŁŃÓŚŹŻ][a-zäöåA-ZÄÖÅĄĆĘŁŃÓŚŹŻ\-]+"
            r"(?:[ \t]+[A-ZÄÖÅĄĆĘŁŃÓŚŹŻ][a-zäöåA-ZÄÖÅĄĆĘŁŃÓŚŹŻ\-]+){0,2})",
            re.MULTILINE | re.IGNORECASE,
        ),
        1,
    ),
    (
        re.compile(
            r"(?<!\w)(?:Från|From):\s*"
            r"([A-ZÄÖÅĄĆĘŁŃÓŚŹŻ][a-zäöåA-ZÄÖÅĄĆĘŁŃÓŚŹŻ\-]+"
            r"(?:[ \t]+[A-ZÄÖÅĄĆĘŁŃÓŚŹŻ][a-zäöåA-ZÄÖÅĄĆĘŁŃÓŚŹŻ\-]+){0,2})",
            re.IGNORECASE,
        ),
        1,
    ),
    (
        re.compile(
            r"(?<!\w)(?:Till|To):\s*"
            r"([A-ZÄÖÅĄĆĘŁŃÓŚŹŻ][a-zäöåA-ZÄÖÅĄĆĘŁŃÓŚŹŻ\-]+"
            r"(?:[ \t]+[A-ZÄÖÅĄĆĘŁŃÓŚŹŻ][a-zäöåA-ZÄÖÅĄĆĘŁŃÓŚŹŻ\-]+){0,2})",
            re.IGNORECASE,
        ),
        1,
    ),
    (
        re.compile(
            r"(?:kontaktperson(?:en)?\s+(?:är|heter)|"
            r"vår\s+(?:VD|chef|platschef|projektledare|koordinator))\s+"
            r"([A-ZÄÖÅĄĆĘŁŃÓŚŹŻ][a-zäöåA-ZÄÖÅĄĆĘŁŃÓŚŹŻ\-]+"
            r"(?:[ \t]+[A-ZÄÖÅĄĆĘŁŃÓŚŹŻ][a-zäöåA-ZÄÖÅĄĆĘŁŃÓŚŹŻ\-]+){0,3})",
            re.IGNORECASE,
        ),
        1,
    ),
]


def detect_context_triggers(text: str) -> List[Tuple[int, int, str, str]]:
    """Return PERSON spans from contextual patterns (email-style cues)."""
    spans: List[Tuple[int, int, str, str]] = []
    for pattern, g in _PATTERNS:
        for m in pattern.finditer(text):
            try:
                span = m.span(g)
            except IndexError:
                continue
            if span[0] == span[1]:
                continue
            value = text[span[0] : span[1]].strip()
            if not value:
                continue
            spans.append((span[0], span[1], "PERSON", value))
    return spans
