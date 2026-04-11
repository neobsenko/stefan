"""Structural name patterns (morphology) — dictionary priority in the merger."""

import re
from typing import List, Optional, Tuple

# Capitalized tokens that should not be pulled in as a “first name” when extending left.
_STOP_PRECEDING = frozenset(
    {
        "the",
        "and",
        "but",
        "for",
        "not",
        "all",
        "are",
        "our",
        "was",
        "his",
        "her",
        "its",
        "det",
        "att",
        "som",
        "för",
        "med",
        "till",
        "från",
        "var",
        "här",
        "den",
        "der",
        "die",
        "das",
        "des",
        "ein",
        "eine",
        "les",
        "von",
        "van",
        "de",
        "zu",
        "bin",
        "ibn",
    }
)

# Polish surname endings (Latin script).
_POLISH_SUR = re.compile(
    r"\b[A-ZÄÖÅŚŁŻŹĆŃ][a-zäöåśłżźćń]+(?:ski|ska|cki|cka|wicz|wski|wska|czyk|czak)\b"
)
# East Slavic-style endings (Latin transliteration).
_SLAVIC_SUR = re.compile(
    r"\b[A-Z][a-z]+(?:enko|chuk|ov|ova|ev|eva|sky|skaya|skiy|skaya)\b"
)
# Finnish-style surnames.
_FINNISH_SUR = re.compile(
    r"\b[A-ZÄÖ][a-zäö]+(?:nen|la|lä|sto|stö)\b"
)
# Germanic surname with particles (single span), including “van der …”.
_GERMANIC = re.compile(
    r"\b[A-ZÄÖÅ][a-zäöå]+\s+(?:van\s+der|Van\s+der)\s+[A-ZÄÖÅ][a-zäöå]+\b"
    r"|\b[A-ZÄÖÅ][a-zäöå]+\s+(?:van|von|de|zu)\s+[A-ZÄÖÅ][a-zäöå]+\b",
)

# Given name + al-/El- hyphenated surname (Latin transliteration).
_ARABIC_COMPOUND = re.compile(
    r"\b[A-ZÄÖÅĄĆĘŁŃÓŚŹŻ][a-zäöåąćęłńóśźż]+\s+(?:[Aa]l|[Ee]l)-[A-ZÄÖÅĄĆĘŁŃÓŚŹŻa-zäöåąćęłńóśźż][a-zäöåA-ZÄÖÅĄĆĘŁŃÓŚŹŻąćęłńóśźż\-]+\b"
)

# Arabic particle names, e.g. Yusuf bin Abdullah, Mohammed ibn Rashid.
_ARABIC_PARTICLE = re.compile(
    r"\b[A-ZÄÖÅĄĆĘŁŃÓŚŹŻ][a-zäöåąćęłńóśźż]+\s+"
    r"(?:bin|ibn|Abu|abu)\s+"
    r"[A-ZÄÖÅĄĆĘŁŃÓŚŹŻ][a-zäöåąćęłńóśźż]+\b"
)

# Romance apostrophe/particle names, e.g. Charlotte d'Aubigné-Lindberg.
_ROMANCE_PARTICLE = re.compile(
    r"\b[A-ZÄÖÅÀ-ÖØ-Ý][A-Za-zÄÖÅÀ-ÖØ-Ýäöåà-öø-ÿ'\-]+\s+"
    r"(?:d'|D'|l'|L'|de\s+la|de|du|des)\s*"
    r"[A-ZÄÖÅÀ-ÖØ-Ý][A-Za-zÄÖÅÀ-ÖØ-Ýäöåà-öø-ÿ'\-]+"
    r"(?:-[A-ZÄÖÅÀ-ÖØ-Ý][A-Za-zÄÖÅÀ-ÖØ-Ýäöåà-öø-ÿ'\-]+)?\b"
)


def _prev_alnum_word(text: str, start: int) -> Optional[Tuple[int, int, str]]:
    """Return span and text of the word immediately before position ``start``."""
    i = start - 1
    while i >= 0 and text[i].isspace():
        i -= 1
    if i < 0:
        return None
    end = i + 1
    while i >= 0 and (text[i].isalnum() or text[i] in "-'’"):
        i -= 1
    wstart = i + 1
    if wstart >= end:
        return None
    w = text[wstart:end]
    if not any(c.isalpha() for c in w):
        return None
    return (wstart, end, w)


def _extend_left_if_capitalized_name(
    text: str, start: int, end: int, max_steps: int = 2
) -> Tuple[int, int]:
    """If the token before ``start`` looks like a capitalized given name, include it."""
    cur_start = start
    for _ in range(max_steps):
        prev = _prev_alnum_word(text, cur_start)
        if prev is None:
            break
        pstart, pend, w = prev
        if not w[0].isupper():
            break
        if w.lower() in _STOP_PRECEDING:
            break
        cur_start = pstart
    return (cur_start, end)


def detect_name_morphology(text: str) -> List[Tuple[int, int, str, str]]:
    """Return PERSON spans from morphology rules (dictionary priority)."""
    spans: List[Tuple[int, int, str, str]] = []

    for m in _GERMANIC.finditer(text):
        spans.append((m.start(), m.end(), "PERSON", m.group(0)))

    for pattern in (_POLISH_SUR, _SLAVIC_SUR, _FINNISH_SUR):
        for m in pattern.finditer(text):
            s, e = _extend_left_if_capitalized_name(text, m.start(), m.end())
            spans.append((s, e, "PERSON", text[s:e]))

    for m in _ARABIC_COMPOUND.finditer(text):
        s, e = _extend_left_if_capitalized_name(text, m.start(), m.end(), max_steps=1)
        spans.append((s, e, "PERSON", text[s:e]))

    for m in _ARABIC_PARTICLE.finditer(text):
        spans.append((m.start(), m.end(), "PERSON", m.group(0)))

    for m in _ROMANCE_PARTICLE.finditer(text):
        spans.append((m.start(), m.end(), "PERSON", m.group(0)))

    # Dedupe identical spans (pattern overlap)
    seen = set()
    out: List[Tuple[int, int, str, str]] = []
    for sp in spans:
        key = (sp[0], sp[1], sp[3])
        if key in seen:
            continue
        seen.add(key)
        out.append(sp)
    return out
