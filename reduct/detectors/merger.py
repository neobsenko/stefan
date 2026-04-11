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
    }
)

# Higher number = higher priority. Regex > dictionary > spaCy.
_PRIORITY = {
    "regex": 3,
    "dictionary": 2,
    "spacy": 1,
}

# Max run of whitespace-only gap when gluing adjacent PERSON spans.
_MAX_PERSON_WS_GAP = 48
_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_PERSON_HYPHEN_TAIL_RE = re.compile(
    r"-(?:[A-ZÀ-ÖØ-ÝÅÄÖ][A-Za-zÀ-ÖØ-öø-ÿÅÄÖåäö'’\-]*)"
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
    return [span for span in spans if span[3] not in stopwords]


def _overlaps(a: Tuple[int, int], b: Tuple[int, int]) -> bool:
    """Two half-open intervals overlap iff they share any positions."""
    return a[0] < b[1] and b[0] < a[1]


def _merge_adjacent_persons(
    spans: List[Tuple[int, int, str, str]],
    text: str,
) -> List[Tuple[int, int, str, str]]:
    """Merge adjacent PERSON spans separated only by whitespace (bounded length).

    Repeats until a full pass produces no further merges, so chains like
    "Erik Anders Andersson" collapse into a single span.
    """
    spans = sorted(spans, key=lambda s: s[0])
    while True:
        merged: List[Tuple[int, int, str, str]] = []
        changed = False
        i = 0
        while i < len(spans):
            if i + 1 < len(spans):
                a = spans[i]
                b = spans[i + 1]
                if a[2] == "PERSON" and b[2] == "PERSON":
                    gap = text[a[1] : b[0]]
                    if (
                        gap
                        and len(gap) <= _MAX_PERSON_WS_GAP
                        and re.fullmatch(r"(?:[ \t]+|[ \t]*-[ \t]*)", gap)
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
        m = _PERSON_HYPHEN_TAIL_RE.match(text[end:])
        if m is None:
            extended.append((start, end, entity_type, original))
            continue
        new_end = end + len(m.group(0))
        extended.append((start, new_end, entity_type, text[start:new_end]))

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
    """Merge adjacent ORG spans, or ORGs separated only by linker words (see _ORG_LINKER_WORDS)."""
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


def _merge_non_person(
    spans: List[Tuple[int, int, str, str, int]],
) -> List[Tuple[int, int, str, str, int]]:
    """Greedy non-overlap: higher priority wins; then longer span."""
    spans = sorted(spans, key=lambda x: (-x[4], -(x[1] - x[0]), x[0]))
    accepted: List[Tuple[int, int, str, str, int]] = []
    for span in spans:
        start, end = span[0], span[1]
        if any(_overlaps((start, end), (a[0], a[1])) for a in accepted):
            continue
        accepted.append(span)
    return accepted


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
        words = re.findall(r"\b\w+\b", text[start:end], re.UNICODE)
        if len(words) < 2:
            continue
        first = words[0]
        if len(first) < 3:
            continue
        if not first[0].isupper():
            continue
        if first in stopwords:
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

    out.sort(key=lambda s: s[0])
    return out


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
        if any(_overlaps((start, end), (b[0], b[1])) for b in blocked):
            continue
        if any(_overlaps((start, end), (a[0], a[1])) for a in accepted):
            continue
        accepted.append(span)
    return accepted


def merge_spans(
    regex_spans: List[Tuple[int, int, str, str]],
    dict_spans: List[Tuple[int, int, str, str]],
    spacy_spans: List[Tuple[int, int, str, str]],
    text: Optional[str] = None,
) -> List[Tuple[int, int, str, str]]:
    """Merge spans from multiple sources, resolving overlaps by priority.

    Non-PERSON entities use source priority (regex > dictionary > spaCy), then length.

    Overlapping PERSON spans from any source: keep the **widest** span; tie-break by
    source priority.

    Returns a list of non-overlapping spans, sorted by start position.
    """
    tagged: List[Tuple[int, int, str, str, int]] = []
    for s in regex_spans:
        tagged.append((*s, _PRIORITY["regex"]))
    for s in dict_spans:
        tagged.append((*s, _PRIORITY["dictionary"]))
    for s in spacy_spans:
        tagged.append((*s, _PRIORITY["spacy"]))
    tagged = _filter_stopword_spans(tagged)

    non_person = [t for t in tagged if t[2] != "PERSON"]
    person = [t for t in tagged if t[2] == "PERSON"]

    accepted_np = _merge_non_person(non_person)
    accepted_p = _merge_person_widest(person, accepted_np)

    result = [(s[0], s[1], s[2], s[3]) for s in accepted_np + accepted_p]
    result.sort(key=lambda x: x[0])

    if text is not None:
        result = _merge_adjacent_persons(result, text)
        result = _extend_hyphenated_person_surnames(result, text)
        result = _merge_adjacent_orgs(result, text)
        result = _coreference_person_first_names(result, text)

    return result
