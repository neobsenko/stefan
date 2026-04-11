"""Structural name patterns (morphology) — dictionary priority in the merger."""

import re
from typing import List, Optional, Tuple

# Extended Unicode character classes for European names.
# Covers Nordic, Polish, Czech/Slovak, Turkish, Latvian/Lithuanian,
# French, Spanish, German, Romanian, Hungarian.
# TODO: Cyrillic and Arabic script support — out of scope for v1.
_UC = (
    r"A-ZÄÖÅÆØĄĆĘŁŃÓŚŹŻÇĞIŞÜČĎĚŇŘŠŤŮŽÁÉÍÓÚÝÀÈÌÒÙÂÊÎÔÛËÏŸ"
    r"ĄĆĘŁŃÓŚŹŻÇĞIŞÜČĎĚŇŘŠŤŮŽÁÉÍÓÚÝÀÈÌÒÙÂÊÎÔÛËÏŸ"
    r"ĀĒĪŌŪĶĻŅȘȚŐŰ"
)
_LC = (
    r"a-zäöåæøąćęłńóśźżçğıişüčďěňřšťůžáéíóúýàèìòùâêîôûëïÿ"
    r"āēīōūķļņșțőű"
)
_CAP_TOKEN = rf"[{_UC}][{_LC}]+"
_CAP_TOKEN_APOS = rf"[{_UC}][{_LC}''\-]*"

# Capitalized tokens that should not be pulled in as a "first name" when extending left.
_STOP_PRECEDING = frozenset(
    {
        "the", "and", "but", "for", "not", "all", "are", "our", "was",
        "his", "her", "its",
        "det", "att", "som", "för", "med", "till", "från", "var", "här", "den",
        "der", "die", "das", "des", "ein", "eine", "les",
        "von", "van", "de", "zu", "bin", "ibn",
        "hej", "tack", "ring", "skicka", "kontakta", "boka",
    }
)

# Polish surname endings (Latin script).
_POLISH_SUR = re.compile(
    rf"\b[{_UC}][{_LC}]+(?:ski|ska|cki|cka|wicz|wski|wska|czyk|czak)\b"
)
# East Slavic-style endings (Latin transliteration).
_SLAVIC_SUR = re.compile(
    rf"\b[{_UC}][{_LC}]+(?:enko|chuk|ov|ova|ev|eva|sky|skaya|skiy)\b"
)
# Finnish-style surnames.
_FINNISH_SUR = re.compile(
    rf"\b[{_UC}][{_LC}]+(?:nen|la|lä|sto|stö)\b"
)
# Latvian-style surnames (e.g. Bērziņš).
_LATVIAN_SUR = re.compile(
    rf"\b[{_UC}][{_LC}]+(?:iņš|iņa|aņš|iņi)\b"
)
# Turkish hyphenated surnames (e.g. Yılmaz-Demir, with Turkish chars).
_TURKISH_SUR = re.compile(
    rf"\b[{_UC}][{_LC}]+(?:-[{_UC}][{_LC}]+)+\b"
)
# Germanic surname with particles (single span), including "van der …".
_GERMANIC = re.compile(
    rf"\b{_CAP_TOKEN}\s+(?:van\s+der|Van\s+der)\s+{_CAP_TOKEN}\b"
    rf"|\b{_CAP_TOKEN}\s+(?:van|von|de|zu)\s+{_CAP_TOKEN}\b",
)

# Whitespace only — never match across newlines.
_WS = r"[ \t]+"

# Given name + al-/El- hyphenated surname (Latin transliteration), e.g. Khalid Al-Hassan.
_ARABIC_COMPOUND = re.compile(
    rf"\b{_CAP_TOKEN}\s+(?:[Aa]l|[Ee]l)-[{_UC}{_LC}\-]+\b"
)

# Chains with bin/ibn and optional trailing Al-/al- segment.
_ARABIC_BIN_CHAIN = re.compile(
    rf"(?<!Abu )(?<!abu )"
    rf"\b[{_UC}][\w''\-]*(?:{_WS}(?:bin|Bin|ibn|Ibn){_WS}[{_UC}][\w''\-]*)+(?:{_WS}(?:Al|al|El|el)-[\w''\-]+)?\b",
    re.UNICODE,
)

# Abu Bakr ibn Yusuf — Abu + given + bin|ibn + given.
_ARABIC_ABU_IBN = re.compile(
    rf"\bAbu{_WS}[{_UC}][\w''\-]*{_WS}(?:bin|Bin|ibn|Ibn){_WS}[{_UC}][\w''\-]*\b",
    re.UNICODE,
)

# Romance apostrophe/particle names, e.g. Charlotte d'Aubigné-Lindberg, François de la Tour.
_ROMANCE_PARTICLE = re.compile(
    rf"\b[{_UC}][\w''\-]+\s+"
    rf"(?:d'|D'|l'|L'|de\s+la|de|du|des)\s*"
    rf"[{_UC}][\w''\-]+"
    rf"(?:-[{_UC}][\w''\-]+)?\b",
    re.UNICODE,
)

# Irish/Scottish apostrophe names with optional hyphen extension.
# O'Sullivan-Berg, O'Brien-Lundgren, d'Aubigné-Lindberg
# Handles straight apostrophe ('), curly right quote (\u2019), and backtick-style (\u2018).
_APOSTROPHE_HYPHEN = re.compile(
    rf"\b[{_UC}]['\u2019\u2018][{_UC}][{_LC}]+(?:-[{_UC}][{_LC}]+)*\b"
)

# Familjen + surname (Swedish family collective).
_FAMILJEN = re.compile(
    rf"\bFamiljen\s+(?:(?:von|van\s+der|de\s+la)\s+)?{_CAP_TOKEN}(?:-{_CAP_TOKEN})?\b"
)


def _prev_alnum_word(text: str, start: int) -> Optional[Tuple[int, int, str]]:
    """Return span and text of the word immediately before position ``start``."""
    i = start - 1
    while i >= 0 and text[i].isspace():
        i -= 1
    if i < 0:
        return None
    end = i + 1
    while i >= 0 and (text[i].isalnum() or text[i] in "-''"):
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

    for pattern in (_POLISH_SUR, _SLAVIC_SUR, _FINNISH_SUR, _LATVIAN_SUR, _TURKISH_SUR):
        for m in pattern.finditer(text):
            s, e = _extend_left_if_capitalized_name(text, m.start(), m.end())
            spans.append((s, e, "PERSON", text[s:e]))

    for m in _ARABIC_BIN_CHAIN.finditer(text):
        spans.append((m.start(), m.end(), "PERSON", m.group(0)))

    for m in _ARABIC_ABU_IBN.finditer(text):
        spans.append((m.start(), m.end(), "PERSON", m.group(0)))

    for m in _ARABIC_COMPOUND.finditer(text):
        s, e = _extend_left_if_capitalized_name(text, m.start(), m.end(), max_steps=1)
        spans.append((s, e, "PERSON", text[s:e]))

    for m in _ROMANCE_PARTICLE.finditer(text):
        spans.append((m.start(), m.end(), "PERSON", m.group(0)))

    # Apostrophe-hyphen names: O'Sullivan-Berg, O'Brien-Lundgren
    for m in _APOSTROPHE_HYPHEN.finditer(text):
        s, e = _extend_left_if_capitalized_name(text, m.start(), m.end(), max_steps=1)
        spans.append((s, e, "PERSON", text[s:e]))

    # Familjen + surname
    for m in _FAMILJEN.finditer(text):
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

    # Prefer longest span when patterns overlap.
    out.sort(key=lambda s: -(s[1] - s[0]))
    kept: List[Tuple[int, int, str, str]] = []
    for sp in out:
        a0, a1 = sp[0], sp[1]
        if any(a0 < b[1] and b[0] < a1 for b in kept):
            continue
        kept.append(sp)
    kept.sort(key=lambda s: s[0])
    return kept
