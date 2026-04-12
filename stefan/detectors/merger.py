"""Span merging with priority-based deduplication."""

import re
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

# ORG spans separated only by whitespace or by 1–2 of these tokens are merged into one ORG.
_ORG_LINKER_WORDS = frozenset(
    {
        "Fastigheter",
        "Sverige",
        "Holding",
        "Holdings",
        "Group",
        "Bygg",
        "Entreprenad",
        "Konsult",
        "Förvaltning",
        "Invest",
        "International",
        "Nordic",
        "Scandinavia",
        "Construction",
    }
)

# Higher number = higher priority.
# Hard regex identifiers must win over dictionaries; dictionary ORGs are locked above
# fuzzy regex LOCATION/etc. so known companies cannot be reclassified by later NER.
_PRIORITY = {
    "regex_hard": 6,
    "regex_org": 5,
    "dictionary_org": 4,
    "regex": 3,
    "dictionary": 2,
    "spacy": 1,
}

_HARD_REGEX_TYPES = frozenset(
    {
        "BANK_ACCOUNT",
        "BANKGIRO",
        "EMAIL",
        "IBAN",
        "IP",
        "KID",
        "OCR",
        "ORG_NR",
        "PAYMENT_REF",
        "PHONE",
        "PLUSGIRO",
        "SSN",
        "URL",
    }
)

# Max run of whitespace-only gap when gluing adjacent PERSON spans.
_MAX_PERSON_WS_GAP = 48
_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_PERSON_HYPHEN_TAIL_RE = re.compile(
    r"-(?:[A-ZÀ-ÖØ-ÝÅÄÖÇĞIŞÜČĎĚŇŘŠŤŮŽĀĒĪŌŪĶĻŅȘȚŐŰ]"
    r"[A-Za-zÀ-ÖØ-öø-ÿÅÄÖåäöçğışüčďěňřšťůžāēīōūķļņșțőű''\-]*)"
)

# Gap pattern for adjacent PERSON merging: plain whitespace/tabs OR a hyphen with optional spaces.
_PERSON_GAP_RE = re.compile(r"(?:[ \t]+|[ \t]*-[ \t]*)")

# Quoted nickname gap: " \s+ \"Nick\" \s+ " between two PERSON spans.
_QUOTED_NICK_RE = re.compile(
    r'^[ \t]+["\u201c\u201d][A-Za-zÀ-ÿ\-]+["\u201c\u201d][ \t]+$'
)


@lru_cache(maxsize=1)
def _load_stopwords() -> Set[str]:
    stopwords_path = _DATA_DIR / "stopwords_construction.txt"
    if not stopwords_path.exists():
        return set()
    with stopwords_path.open(encoding="utf-8") as f:
        return {line.strip() for line in f if line.strip()}


def _filter_stopword_spans(
    spans: List[Tuple[int, int, str, str, int]],
) -> List[Tuple[int, int, str, str, int]]:
    stopwords = _load_stopwords()
    if not stopwords:
        return spans
    out: List[Tuple[int, int, str, str, int]] = []
    for span in spans:
        value = span[3]
        if value in stopwords:
            continue
        # Remove spans that are entirely composed of stopword tokens
        # (e.g. "Norska Polska Finska" merged as one PERSON span).
        tokens = re.findall(r"\b[\w\.-]+\b", value, re.UNICODE)
        if tokens and all(tok in stopwords for tok in tokens):
            continue
        out.append(span)
    return out


def _overlaps(a: Tuple[int, int], b: Tuple[int, int]) -> bool:
    """Two half-open intervals overlap iff they share any positions."""
    return a[0] < b[1] and b[0] < a[1]


def _merge_adjacent_persons(
    spans: List[Tuple[int, int, str, str]],
    text: str,
) -> List[Tuple[int, int, str, str]]:
    """Merge adjacent PERSON spans separated only by whitespace, hyphen, or quoted nickname.

    Repeats until a full pass produces no further merges, so chains like
    "Erik Anders Andersson" collapse into a single span.
    Also merges A + "Nick" + B when all three are adjacent PERSON spans
    and the middle one is wrapped in quotes.
    """
    spans = sorted(spans, key=lambda s: s[0])
    while True:
        merged: List[Tuple[int, int, str, str]] = []
        changed = False
        i = 0
        while i < len(spans):
            # Try 3-span quoted nickname merge: PERSON "PERSON" PERSON
            if i + 2 < len(spans):
                a, b, c = spans[i], spans[i + 1], spans[i + 2]
                if a[2] == "PERSON" and b[2] == "PERSON" and c[2] == "PERSON":
                    gap_ab = text[a[1] : b[0]]
                    gap_bc = text[b[1] : c[0]]
                    ab_is_quote_open = gap_ab.strip() in ('"', '\u201c', '\u201d')
                    bc_is_quote_close = gap_bc.strip() in ('"', '\u201c', '\u201d')
                    if ab_is_quote_open and bc_is_quote_close:
                        combined = (a[0], c[1], "PERSON", text[a[0] : c[1]])
                        merged.append(combined)
                        i += 3
                        changed = True
                        continue
            # Try 2-span merge
            if i + 1 < len(spans):
                a = spans[i]
                b = spans[i + 1]
                if a[2] == "PERSON" and b[2] == "PERSON":
                    gap = text[a[1] : b[0]]
                    if gap and len(gap) <= _MAX_PERSON_WS_GAP and (
                        _PERSON_GAP_RE.fullmatch(gap)
                        or _QUOTED_NICK_RE.match(gap)
                    ):
                        combined = (a[0], b[1], "PERSON", text[a[0] : b[1]])
                        merged.append(combined)
                        i += 2
                        changed = True
                        continue
            merged.append(spans[i])
            i += 1
        spans = merged
        if not changed:
            return spans


def _extend_hyphenated_person_surnames(
    spans: List[Tuple[int, int, str, str]],
    text: str,
) -> List[Tuple[int, int, str, str]]:
    """Extend PERSON spans with trailing hyphenated surname part, e.g. Kowalczyk-Nowak."""
    if not spans:
        return spans
    extended: List[Tuple[int, int, str, str]] = []
    for start, end, entity_type, original in spans:
        if entity_type != "PERSON":
            extended.append((start, end, entity_type, original))
            continue
        cur_end = end
        while True:
            m = _PERSON_HYPHEN_TAIL_RE.match(text[cur_end:])
            if m is None:
                break
            cur_end += len(m.group(0))
        if cur_end != end:
            extended.append((start, cur_end, entity_type, text[start:cur_end]))
        else:
            extended.append((start, end, entity_type, original))

    out: List[Tuple[int, int, str, str]] = []
    for span in sorted(extended, key=lambda s: (s[0], -(s[1] - s[0]))):
        if any(
            _overlaps((span[0], span[1]), (cur[0], cur[1])) and span[2] == cur[2]
            for cur in out
        ):
            continue
        out.append(span)
    out.sort(key=lambda s: s[0])
    return out


def _org_gap_allows_merge(gap: str) -> bool:
    if not gap.strip():
        return True
    parts = [p for p in re.split(r"\s+", gap.strip()) if p]
    if len(parts) > 2:
        return False
    return all(p in _ORG_LINKER_WORDS for p in parts)


def _merge_adjacent_orgs(
    spans: List[Tuple[int, int, str, str]],
    text: str,
) -> List[Tuple[int, int, str, str]]:
    """Merge adjacent ORG spans, or ORGs separated only by linker words."""
    spans = sorted(spans, key=lambda s: s[0])
    while True:
        merged: List[Tuple[int, int, str, str]] = []
        changed = False
        i = 0
        while i < len(spans):
            if i + 1 < len(spans):
                a = spans[i]
                b = spans[i + 1]
                if a[2] == "ORG" and b[2] == "ORG":
                    gap = text[a[1] : b[0]]
                    if _org_gap_allows_merge(gap):
                        combined = (a[0], b[1], "ORG", text[a[0] : b[1]])
                        merged.append(combined)
                        i += 2
                        changed = True
                        continue
            merged.append(spans[i])
            i += 1
        spans = merged
        if not changed:
            return spans


# Polish company suffix "spółka z o.o." written as "z o.o." after the trade name.
# No trailing \b after the last dot: "." is non-word, so \b would not match before a space.
_ORG_ZOO_SUFFIX = re.compile(
    r"^(?:(?:\s*\.)?\s+)z\s+o\.o\.(?=\s|[,;:.!?\)]|$)", re.IGNORECASE
)


def _extend_org_polish_zoo(
    spans: List[Tuple[int, int, str, str]],
    text: str,
) -> List[Tuple[int, int, str, str]]:
    """Extend ORG spans to include a following ``z o.o.`` (Polish limited company)."""
    out: List[Tuple[int, int, str, str]] = []
    for span in spans:
        if span[2] != "ORG":
            out.append(span)
            continue
        start, end = span[0], span[1]
        m = _ORG_ZOO_SUFFIX.match(text[end:])
        if not m:
            out.append(span)
            continue
        new_end = end + m.end()
        out.append((start, new_end, "ORG", text[start:new_end]))
    return out


def _merge_non_person(
    spans: List[Tuple[int, int, str, str, int]],
) -> List[Tuple[int, int, str, str, int]]:
    """Greedy non-overlap: higher priority wins; then longer span."""
    spans = sorted(spans, key=lambda x: (-x[4], -(x[1] - x[0]), x[0]))
    accepted: List[Tuple[int, int, str, str, int]] = []
    for span in spans:
        start, end = span[0], span[1]
        overlapping = [a for a in accepted if _overlaps((start, end), (a[0], a[1]))]
        if overlapping:
            # A wider ORG span from another detector may extend a locked dictionary
            # ORG without changing its type. This keeps "Skanska Sverige AB" whole
            # while still preventing LOCATION/PERSON reclassification of "Skanska".
            if (
                span[2] == "ORG"
                and all(a[2] == "ORG" for a in overlapping)
                and all(start <= a[0] and a[1] <= end for a in overlapping)
                and (end - start) > max(a[1] - a[0] for a in overlapping)
                and not any(a[4] == _PRIORITY["regex_hard"] for a in overlapping)
            ):
                accepted = [
                    a
                    for a in accepted
                    if not _overlaps((start, end), (a[0], a[1]))
                ]
            else:
                continue
        if any(_overlaps((start, end), (a[0], a[1])) for a in accepted):
            continue
        accepted.append(span)
    return accepted


_FIRST_GIVEN_RE = re.compile(
    r"^("
    r"[A-Z][\w'']+(?:-[A-Z][\w'']+)+"  # Pia-Maria, Karl-Johan, Mats-Erik
    r"|[A-Z][\w'']{2,}"
    r")",
    re.UNICODE,
)


def _first_given_name(person_slice: str) -> Optional[str]:
    """Leading given name, including hyphenated forms (e.g. Pia-Maria, Karl-Johan)."""
    t = person_slice.strip()
    m = _FIRST_GIVEN_RE.match(t)
    if not m:
        return None
    return m.group(1)


def _coreference_person_first_names(
    spans: List[Tuple[int, int, str, str]],
    text: str,
) -> List[Tuple[int, int, str, str]]:
    """Link standalone first-name mentions to a unique full PERSON span."""
    stopwords = _load_stopwords()
    occupied = [(s[0], s[1]) for s in spans]
    person_spans = [s for s in spans if s[2] == "PERSON"]
    first_to_full: Dict[str, Set[str]] = {}

    for start, end, _, original in person_spans:
        surface = text[start:end]
        rest = surface
        rest = re.sub(
            r"^(?:bin|ibn|Bin|Ibn|Abu|abu)\s+",
            "",
            rest,
            count=1,
        )
        first = _first_given_name(rest)
        if first is None:
            continue
        if len(first) < 3:
            continue
        if not first[0].isupper():
            continue
        if first.lower() in {"bin", "ibn", "abu"}:
            continue
        if first in stopwords:
            continue
        remainder = rest[len(first):].strip()
        if not remainder:
            continue
        first_to_full.setdefault(first, set()).add(original)

    ambiguous_firsts = {
        first for first, full_names in first_to_full.items() if len(full_names) > 1
    }

    out = [
        s
        for s in spans
        if not (s[2] == "PERSON" and s[3] in ambiguous_firsts and text[s[0] : s[1]] == s[3])
    ]
    linkable = {
        first: next(iter(full_names))
        for first, full_names in first_to_full.items()
        if len(full_names) == 1
    }

    # Rewrite existing standalone first-name PERSON spans to canonical full-name value.
    if linkable:
        rewritten: List[Tuple[int, int, str, str]] = []
        for s in out:
            if s[2] != "PERSON":
                rewritten.append(s)
                continue
            surface = text[s[0] : s[1]]
            canonical = linkable.get(surface)
            if canonical is not None and s[3] == surface:
                rewritten.append((s[0], s[1], s[2], canonical))
            else:
                rewritten.append(s)
        out = rewritten

    occupied = [(s[0], s[1]) for s in out]

    if not linkable:
        return out
    for first, canonical_name in linkable.items():
        pattern = re.compile(rf"(?<!\w){re.escape(first)}(?!\w)")
        for match in pattern.finditer(text):
            m_start, m_end = match.span()
            if any(_overlaps((m_start, m_end), iv) for iv in occupied):
                continue
            out.append((m_start, m_end, "PERSON", canonical_name))
            occupied.append((m_start, m_end))

        # Swedish possessive/genitive: Anna → Annas, Krzysztof → Krzysztofs (whole word includes "s").
        if not first.endswith("s") and not first.endswith("S"):
            gen = f"{first}s"
            if gen.lower() in stopwords:
                continue
            gpat = re.compile(rf"(?<!\w){re.escape(gen)}(?!\w)")
            for match in gpat.finditer(text):
                m_start, m_end = match.span()
                if any(_overlaps((m_start, m_end), iv) for iv in occupied):
                    continue
                out.append((m_start, m_end, "PERSON", canonical_name))
                occupied.append((m_start, m_end))

    out.sort(key=lambda s: s[0])
    return out


# Non-person types that may be spaCy false positives fully inside a wider PERSON.
_SUBSUMABLE_IN_PERSON = frozenset({"LOCATION", "ORG"})


def _person_blocked_by_non_person(
    start: int,
    end: int,
    blocked: List[Tuple[int, int, str, str, int]],
) -> bool:
    """True if this PERSON span must yield to an accepted non-person span.

    spaCy LOCATION/ORG that are fully contained in a wider PERSON are subsumed.
    EMAIL / PHONE / etc. still block.
    """
    for b in blocked:
        b_start, b_end, b_type = b[0], b[1], b[2]
        if not _overlaps((start, end), (b_start, b_end)):
            continue
        if (
            b_type in _SUBSUMABLE_IN_PERSON
            and b[4] == _PRIORITY["spacy"]
            and start <= b_start
            and b_end <= end
        ):
            continue
        return True
    return False


def _merge_person_widest(
    spans: List[Tuple[int, int, str, str, int]],
    blocked: List[Tuple[int, int, str, str, int]],
) -> List[Tuple[int, int, str, str, int]]:
    """Among PERSON spans, prefer the widest overlapping candidate; then priority."""
    spans = sorted(
        spans,
        key=lambda x: (-(x[1] - x[0]), -x[4], x[0]),
    )
    accepted: List[Tuple[int, int, str, str, int]] = []
    for span in spans:
        start, end = span[0], span[1]
        if _person_blocked_by_non_person(start, end, blocked):
            continue
        if any(_overlaps((start, end), (a[0], a[1])) for a in accepted):
            continue
        accepted.append(span)
    return accepted


_LOOKAHEAD_NAME_RE = re.compile(r"[^\W\d_]+(?:-[^\W\d_]+)*", re.UNICODE)


def _is_capitalized_alpha_token(token: str) -> bool:
    parts = token.split("-")
    return bool(parts) and all(
        len(part) > 2 and part.isalpha() and part[0].isupper()
        for part in parts
    )


def _extend_person_lookahead(
    spans: List[Tuple[int, int, str, str, int]],
    text: str,
) -> List[Tuple[int, int, str, str, int]]:
    """Extend PERSON by one following same-line capitalized token."""
    if not spans:
        return spans
    stopwords = {w.lower() for w in _load_stopwords()}
    occupied = [(s[0], s[1]) for s in spans]
    out: List[Tuple[int, int, str, str, int]] = []
    for start, end, etype, val, pri in spans:
        if etype != "PERSON":
            out.append((start, end, etype, val, pri))
            continue
        i = end
        while i < len(text) and text[i] in " \t":
            i += 1
        if i == end or i >= len(text) or text[i] in "\r\n":
            out.append((start, end, etype, val, pri))
            continue
        m = _LOOKAHEAD_NAME_RE.match(text, i)
        if not m:
            out.append((start, end, etype, val, pri))
            continue
        token = m.group(0)
        new_end = m.end()
        if (
            _is_capitalized_alpha_token(token)
            and token.lower() not in stopwords
            and not any(_overlaps((i, new_end), iv) for iv in occupied)
        ):
            out.append((start, new_end, etype, text[start:new_end], pri))
        else:
            out.append((start, end, etype, val, pri))
    return out


def _drop_non_person_subsumed_by_person(
    accepted_np: List[Tuple[int, int, str, str, int]],
    accepted_p: List[Tuple[int, int, str, str, int]],
) -> List[Tuple[int, int, str, str, int]]:
    """Remove LOCATION/ORG/etc. that lie entirely inside a kept PERSON span."""
    if not accepted_p:
        return accepted_np
    p_boxes = [(s[0], s[1]) for s in accepted_p]
    out: List[Tuple[int, int, str, str, int]] = []
    for np in accepted_np:
        n0, n1 = np[0], np[1]
        if any(p0 <= n0 and n1 <= p1 for p0, p1 in p_boxes):
            continue
        out.append(np)
    return out


def _truncate_span_at_line_break(text: str, start: int, end: int) -> Tuple[int, int]:
    """Keep only the segment before the first newline; entities must not span lines."""
    if end <= start:
        return (start, start)
    chunk = text[start:end]
    for sep in ("\n", "\r"):
        if sep in chunk:
            chunk = chunk.split(sep)[0]
            break
    new_end = start + len(chunk)
    while new_end > start and text[new_end - 1] in " \t":
        new_end -= 1
    if new_end <= start:
        return (start, start)
    return (start, new_end)


def merge_spans(
    regex_spans: List[Tuple[int, int, str, str]],
    dict_spans: List[Tuple[int, int, str, str]],
    spacy_spans: List[Tuple[int, int, str, str]],
    text: Optional[str] = None,
) -> List[Tuple[int, int, str, str]]:
    """Merge spans from multiple sources, resolving overlaps by priority.

    Non-PERSON entities use source priority, then length. Hard regex identifiers
    stay above dictionaries; dictionary ORGs stay above fuzzy entity detectors.

    Overlapping PERSON spans from any source: keep the **widest** span; tie-break by
    source priority.

    Returns a list of non-overlapping spans, sorted by start position.
    """
    tagged: List[Tuple[int, int, str, str, int]] = []
    for s in regex_spans:
        if s[2] in _HARD_REGEX_TYPES:
            priority = _PRIORITY["regex_hard"]
        elif s[2] == "ORG":
            priority = _PRIORITY["regex_org"]
        else:
            priority = _PRIORITY["regex"]
        tagged.append((*s, priority))
    for s in dict_spans:
        priority = (
            _PRIORITY["dictionary_org"]
            if s[2] == "ORG"
            else _PRIORITY["dictionary"]
        )
        tagged.append((*s, priority))
    for s in spacy_spans:
        tagged.append((*s, _PRIORITY["spacy"]))
    tagged = _filter_stopword_spans(tagged)

    if text is not None:
        trimmed: List[Tuple[int, int, str, str, int]] = []
        for start, end, etype, val, pri in tagged:
            ns, ne = _truncate_span_at_line_break(text, start, end)
            if ne <= ns:
                continue
            trimmed.append((ns, ne, etype, text[ns:ne], pri))
        tagged = trimmed

    if text is not None:
        tagged = _extend_person_lookahead(tagged, text)

    non_person = [t for t in tagged if t[2] != "PERSON"]
    person = [t for t in tagged if t[2] == "PERSON"]

    accepted_np = _merge_non_person(non_person)
    accepted_p = _merge_person_widest(person, accepted_np)
    accepted_np = _drop_non_person_subsumed_by_person(accepted_np, accepted_p)

    result = [(s[0], s[1], s[2], s[3]) for s in accepted_np + accepted_p]
    result.sort(key=lambda x: x[0])

    if text is not None:
        result = _merge_adjacent_persons(result, text)
        result = _extend_hyphenated_person_surnames(result, text)
        result = _merge_adjacent_orgs(result, text)
        result = _extend_org_polish_zoo(result, text)
        result = _coreference_person_first_names(result, text)

    return result
