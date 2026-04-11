"""Regex-based entity detection."""

import re
from typing import List, Tuple

# Extended character class for Scandinavian + European capitalized tokens in ORG names.
_ORG_UC = r"A-ZÅÄÖÆØÜÇĞŞÉÈÁÀÓÒÚÙÂÊÎÔÛËÏŸŐŰ"
_ORG_LC = r"a-zåäöæøüçğışéèáàóòúùâêîôûëïÿőű0-9"
_ORG_CAP = rf"(?:[{_ORG_UC}]+|[{_ORG_UC}][{_ORG_LC}]*(?:[-'][{_ORG_UC}{_ORG_LC}]+)*)"
_ORG_CONN = r"(?:och|&|i|på|av)"
_END_DELIM = r"(?=$|[\s,;\)\]>\r\n\.\!\?:])"
_ORG_LEGAL_SHORT = r"(?:AB|HB|KB|AS|ASA|AG|Ltd|Inc|Corp|LLC|LLP|KG|Oy|Oyj)"
_ORG_BODY_TOKEN = rf"(?!(?:{_ORG_LEGAL_SHORT})\b){_ORG_CAP}"

# Company suffixes: Nordic + international.
_ORG_SUFFIX = (
    r"(?:Aktiebolag|Förvaltning|Fastigheter|Entreprenad|Holdings|Holding|"
    r"Sverige[ \t]+AB|ASA|Group|Invest|Konsult|Bygg|Construction|International|"
    r"Limited|Ltd|GmbH(?:\s*&\s*Co\.?\s*KG)?|SA|SAS|NV|BV|SpA|SRL|Plc|AG|"
    r"Inc|Corp|Corporation|LLC|LLP|Oy|Oyj|A/S|ApS|PJSC|JSC|"
    r"AB|AS|HB|KB|KG)"
)

# Street name endings (Swedish).
_STREET_SUFFIX = (
    r"(?:vägen|gränden|gränd|gatan|torget|stigen|leden|platsen|backen|allén|kajen|bron)"
)

# (entity_type, compiled_pattern, capture_group_index)
PATTERNS: List[Tuple[str, re.Pattern, int]] = [
    # IBAN (Swedish specific) — must run before phone detection.
    (
        "IBAN",
        re.compile(
            r"\bSE\d{2}(?:[ \t]?\d{4}){5}\b"
        ),
        0,
    ),
    # Generic IBAN fallback (DE/FR/etc).
    (
        "IBAN",
        re.compile(
            r"\b[A-Z]{2}\d{2}(?:[ \t]?[A-Z0-9]{4}){2,7}[ \t]?[A-Z0-9]{1,4}\b"
        ),
        0,
    ),
    # URLs (http/https/www)
    (
        "URL",
        re.compile(
            rf"\b(?:https?://|www\.)[^\s<>\"']+{_END_DELIM}",
            re.IGNORECASE,
        ),
        0,
    ),
    # Email addresses
    (
        "EMAIL",
        re.compile(
            rf"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{{2,}}{_END_DELIM}"
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
            r")"
            + _END_DELIM
        ),
        0,
    ),
    # Generic international phone fallback: +CC followed by digit groups (not +46).
    (
        "PHONE",
        re.compile(
            r"(?<!\w)\+(?!46(?:\D|$))\d{1,3}(?:[\s-]?\d{1,4}){2,7}"
            + _END_DELIM
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
    # Swedish / international company-style names with legal/org suffix.
    # Supports "och", "&", "i", "på", "av" connectors inside names.
    # Also handles apostrophe tokens (O'Brien, d'Aubigné).
    (
        "ORG",
        re.compile(
            r"\b"
            + rf"{_ORG_BODY_TOKEN}"
            + rf"(?:[ \t]+(?:{_ORG_CONN}[ \t]+)?{_ORG_BODY_TOKEN}){{0,5}}"
            + r"[ \t]+"
            + _ORG_SUFFIX
            + r"\b"
        ),
        0,
    ),
    # Swedish municipalities/city authorities, e.g. Solna Stad, Uppsala Kommun.
    (
        "ORG",
        re.compile(
            rf"\b[{_ORG_UC}][{_ORG_LC}]+s?\s+(?:Stad|Kommun)\b"
        ),
        0,
    ),
    # Swedish public sector: Region X, X Förvaltning, standalone compound words, etc.
    (
        "ORG",
        re.compile(
            r"\b(?:"
            r"Region\s+[A-ZÅÄÖ][a-zåäö\-]+"
            r"|Stadsdelsförvaltningen?\s+[A-ZÅÄÖ][a-zåäö\-]+"
            r"|[A-ZÅÄÖ][a-zåäö\-]+s?\s+(?:"
            r"Förvaltning(?:en)?|Kontor(?:et)?|Nämnd(?:en)?|Myndighet(?:en)?"
            r"|Distrikt|Stadsdel(?:sförvaltning(?:en)?)?"
            r"|Idrottsförvaltning(?:en)?|Utbildningsförvaltning(?:en)?"
            r"|Socialförvaltning(?:en)?|Miljöförvaltning(?:en)?"
            r"|Kulturförvaltning(?:en)?)"
            r"(?:\s+[A-ZÅÄÖ][a-zåäö\-]+)?"
            # Standalone compound words ending in -förvaltningen/-förvaltning + optional city
            r"|[A-ZÅÄÖ][a-zåäö]*(?:förvaltning|Förvaltning)(?:en)?"
            r"(?:\s+[A-ZÅÄÖ][a-zåäö\-]+)?"
            r")\b"
        ),
        0,
    ),
    # Swedish institutions: sjukhus, universitet, högskola, etc.
    (
        "ORG",
        re.compile(
            rf"\b[{_ORG_UC}][{_ORG_LC}]*"
            rf"(?:\s+[{_ORG_UC}][{_ORG_LC}]*){{0,3}}\s+"
            r"(?:Sjukhus(?:et)?|Universitetssjukhus(?:et)?|Universitet(?:et)?"
            r"|Högskola(?:n)?|Akademi(?:n)?|Institut(?:et)?"
            r"|Centrum|Centret|Stiftelse(?:n)?|Förbund(?:et)?)"
            rf"(?:\s+[{_ORG_UC}][{_ORG_LC}]+)?\b"
        ),
        0,
    ),
    # Swedish street address with optional apartment (lgh) and postal code + city.
    (
        "LOCATION",
        re.compile(
            r"\b"
            rf"[A-ZÅÄÖ][{_ORG_LC}\-]*"
            + _STREET_SUFFIX
            + r"\s+\d+[A-Za-z]?"
            + r"(?:,?\s*lgh\.?\s+\d+)?"
            + r"(?:,?\s*\d{3}\s+\d{2}\s+[A-ZÅÄÖ][a-zåäö\-]+)?"
            + r"\b"
        ),
        0,
    ),
    # PO box address: Box 1234, 123 45 Stockholm
    (
        "LOCATION",
        re.compile(
            r"\bBox\s+\d{1,5}"
            r"(?:[,\s]+\d{3}\s+\d{2}\s+[A-ZÅÄÖ][a-zåäö\-]+)?\b"
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

    # IBANs must never be misclassified as PHONE.
    iban_spans = {(s, e) for s, e, t, _ in spans if t == "IBAN"}
    spans = [
        sp
        for sp in spans
        if not (sp[2] == "PHONE" and any(sp[0] >= i0 and sp[1] <= i1 for i0, i1 in iban_spans))
    ]

    # Same digit span can match ORG_NR (labeled) and SSN (\d{6}-\d{4}); keep ORG_NR only.
    org_nr_spans = {(s, e) for s, e, t, _ in spans if t == "ORG_NR"}
    spans = [
        sp
        for sp in spans
        if not (sp[2] == "SSN" and (sp[0], sp[1]) in org_nr_spans)
    ]
    return spans
