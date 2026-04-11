"""Regex-based entity detection."""

import re
from typing import List, Tuple

# (entity_type, compiled_pattern, capture_group_index) — group 0 = full match; group 1+ = captured digits only.
# Order matters: PHONE and ORG_NR before SSN so phones and labeled org numbers are not misclassified.
PATTERNS: List[Tuple[str, re.Pattern, int]] = [
    # Email addresses
    (
        "EMAIL",
        re.compile(
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
        ),
        0,
    ),
    # URLs (http/https/www)
    (
        "URL",
        re.compile(
            r"\b(?:https?://|www\.)[^\s<>\"']+",
            re.IGNORECASE,
        ),
        0,
    ),
    # Swedish phone numbers: +46 or 0046 with optional (0), mobile prefixes 7[0236789],
    # Stockholm 08, and other domestic area codes.
    (
        "PHONE",
        re.compile(
            r"(?<!\w)(?:"
            r"(?:\+46|0046)[\s-]?(?:\(0\)[\s-]?)?"
            r"(?:"
            r"7[0236789](?:[\s-]?\d){7}"
            r"|8(?:[\s-]?\d){7,8}"
            r"|[1-9]\d{1,2}(?:[\s-]?\d){5,8}"
            r")"
            r"|0(?:"
            r"7[0236789](?:[\s-]?\d){7}"
            r"|8(?:[\s-]?\d){7,8}"
            r"|[1-9]\d{1,2}(?:[\s-]?\d){5,8}"
            r")"
            r")(?!\w)"
        ),
        0,
    ),
    # Generic international fallback, e.g. +358 50 1234567.
    (
        "PHONE",
        re.compile(
            r"(?<!\w)\+(?!46\b)\d{1,3}(?:[\s-]?\(?\d{1,4}\)?)?(?:[\s-]?\d){4,12}(?!\w)"
        ),
        0,
    ),
    # Swedish organisation number (label + digits); digits tagged ORG_NR, not SSN.
    (
        "ORG_NR",
        re.compile(
            r"(?i)(?:org\.?\s*nr|orgnr|organisationsnummer)\s*:?\s*(\d{6}-\d{4})\b"
        ),
        1,
    ),
    # Swedish personnummer — dash required (no bare digit runs).
    (
        "SSN",
        re.compile(
            r"\b(?:"
            r"(?:19|20)\d{6}-\d{4}"
            r"|\d{6}-\d{4}"
            r")\b"
        ),
        0,
    ),
    # IPv4 addresses
    (
        "IP",
        re.compile(
            r"\b(?:25[0-5]|2[0-4]\d|[01]?\d\d?)"
            r"(?:\.(?:25[0-5]|2[0-4]\d|[01]?\d\d?)){3}\b"
        ),
        0,
    ),
    # Swedish / Nordic company-style names with legal/org suffix.
    # Supports "och", "&", and "i" connectors inside names.
    (
        "ORG",
        re.compile(
            r"\b"
            r"(?:[A-ZÅÄÖ]+|[A-ZÅÄÖ][a-zåäö0-9]*)"
            r"(?:\s+(?:(?:och|&|i)\s+)?(?:[A-ZÅÄÖ]+|[A-ZÅÄÖ][a-zåäö0-9]*)){0,5}"
            r" +"
            r"(?:Aktiebolag|Förvaltning|Fastigheter|Entreprenad|Holdings|Holding|"
            r"Sverige +AB|ASA|Group|Invest|Konsult|Bygg|AB|AS|HB|KB)\b"
        ),
        0,
    ),
    # Swedish municipalities/city authorities, e.g. Solna Stad, Uppsala Kommun.
    (
        "ORG",
        re.compile(
            r"\b[A-ZÅÄÖ][a-zåäö]+s?\s+(?:Stad|Kommun)\b"
        ),
        0,
    ),
    # Swedish street address: …vägen/gatan/… + number [+ optional , postal city]
    (
        "LOCATION",
        re.compile(
            r"\b"
            r"[A-ZÅÄÖ][a-zåö0-9-]*"
            r"(?:vägen|gränden|gränd|gatan|torget|stigen|leden|platsen|backen|allén|kajen|bron)\b"
            r"\s+\d+[A-Za-z]?"
            r"(?:,\s*\d{3}\s+\d{2}(?:\s+[A-ZÅÄÖ][a-zåö]+)?)?"
            r"\b"
        ),
        0,
    ),
]


def detect_regex(text: str) -> List[Tuple[int, int, str, str]]:
    """Run all regex patterns on text.

    Returns a list of (start, end, entity_type, matched_text) tuples.
    """
    spans: List[Tuple[int, int, str, str]] = []
    for entity_type, pattern, group_i in PATTERNS:
        for match in pattern.finditer(text):
            if group_i:
                g = match.group(group_i)
                if not g:
                    continue
                start, end = match.span(group_i)
                matched = g
            else:
                start, end = match.span()
                matched = match.group(0)
            # Phone heuristic: must contain at least 7 digits to count
            if entity_type == "PHONE":
                digit_count = sum(1 for c in matched if c.isdigit())
                if digit_count < 7:
                    continue
            spans.append((start, end, entity_type, matched))

    # Same digit span can match ORG_NR (labeled) and SSN (\d{6}-\d{4}); keep ORG_NR only.
    org_nr_spans = {(s, e) for s, e, t, _ in spans if t == "ORG_NR"}
    spans = [
        sp
        for sp in spans
        if not (sp[2] == "SSN" and (sp[0], sp[1]) in org_nr_spans)
    ]
    return spans
