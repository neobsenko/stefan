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

# Street name endings (Swedish) — suffix glued to the last word (e.g. Samuelsgatan).
# Separate "… väg" (two tokens) is handled by a second LOCATION pattern below.
_STREET_SUFFIX = (
    r"(?:vägen|gränden|gränd|gatan|torget|stigen|leden|platsen|backen|allén|kajen|bron)"
)
_STREET_TOKEN = rf"[A-ZÅÄÖ][{_ORG_LC}\-]*"
_STREET_OCCUPANCY = r"\d+[A-Za-z]?(?:-\d+[A-Za-z]?)?"
_MAJOR_SWEDISH_CITIES = r"(?:Stockholm|Göteborg|Uppsala)"

# Swedish payment routing: must not match reference IDs (BL-2026-…, RS-…, year-prefixed, etc.).
# Left context = line start or a separator (so not glued to letter-hyphen refs like "BL-2026-…").
_BANK_ROUTE_LEFT = r"(?:^|(?<=[,\s\n\r:;]))"
# Not immediately after single-letter + hyphen (BL-, F-, X- …); blocks ref codes like "RS-2026-…".
_BANK_ROUTE_NOT_AFTER_LETTER_HYPH = r"(?<![A-Za-zÀ-Öà-ö]-)"
# Not a calendar-year–prefixed reference segment (2026-, 2025-, …).
_BANK_ROUTE_NOT_YEAR = r"(?!20\d{2}-)"

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
    # Swedish OCR/payment reference labels. Must run before bank/phone/SSN patterns.
    (
        "PAYMENT_REF",
        re.compile(
            r"(?i)\b(?:OCR|OCR-nr|OCR-nummer|OCR\s+ref|Referens|Ref):?\s*(\d{6,25})\b"
        ),
        1,
    ),
    # Swedish Bankgiro (3–4 digits, hyphen, 4 digits) — before PHONE.
    # Exclude year-shaped refs (2026-9999); require separator/line-start (not BL-2026-…).
    (
        "BANKGIRO",
        re.compile(
            _BANK_ROUTE_LEFT
            + _BANK_ROUTE_NOT_AFTER_LETTER_HYPH
            + _BANK_ROUTE_NOT_YEAR
            + r"\d{3,4}-\d{4}\b"
        ),
        0,
    ),
    # Plusgiro: spaced groups (e.g. 47 11 47-9).
    (
        "PLUSGIRO",
        re.compile(
            _BANK_ROUTE_LEFT
            + _BANK_ROUTE_NOT_AFTER_LETTER_HYPH
            + r"\d{2}\s\d{2}\s\d{2}-\d\b"
        ),
        0,
    ),
    # Plusgiro: compact (ends with single check digit after hyphen).
    (
        "PLUSGIRO",
        re.compile(
            _BANK_ROUTE_LEFT
            + _BANK_ROUTE_NOT_AFTER_LETTER_HYPH
            + _BANK_ROUTE_NOT_YEAR
            + r"\d{1,8}-\d\b"
        ),
        0,
    ),
    # Swedish bank account — SEB-style clearing + account groups.
    (
        "BANK_ACCOUNT",
        re.compile(
            _BANK_ROUTE_LEFT
            + _BANK_ROUTE_NOT_AFTER_LETTER_HYPH
            + _BANK_ROUTE_NOT_YEAR
            + r"\d{4}-\d{2}\s\d{3}\s\d{2}\s\d{3}\b"
        ),
        0,
    ),
    # Nordea-style and similar short grouped formats.
    (
        "BANK_ACCOUNT",
        re.compile(
            _BANK_ROUTE_LEFT
            + _BANK_ROUTE_NOT_AFTER_LETTER_HYPH
            + r"(?!20\d{2})\d{4}\s\d{2}\s\d{4}\b"
        ),
        0,
    ),
    # General Swedish account (Swedbank, Handelsbanken, etc.).
    # Reject leading 00… so international dial prefixes (0046 …) are not bank accounts.
    # Reject year-prefixed refs (2026-04-1847). May match a suffix of an IBAN; merge keeps IBAN.
    (
        "BANK_ACCOUNT",
        re.compile(
            _BANK_ROUTE_LEFT
            + _BANK_ROUTE_NOT_AFTER_LETTER_HYPH
            + _BANK_ROUTE_NOT_YEAR
            + r"(?!00)\d{4,5}[-\s,]\d{1,3}[\s\d\-]{5,18}\b"
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
    # Social profile paths/domains without protocol, e.g. /in/name or linkedin.com/in/name.
    (
        "URL",
        re.compile(
            r"(?<!\w)(?:/in/[a-z0-9\-]+|"
            r"(?:linkedin\.com|facebook\.com|twitter\.com|x\.com|instagram\.com|tiktok\.com)"
            r"/[a-z0-9\.\-_/]+)\b",
            re.IGNORECASE,
        ),
        0,
    ),
    # Email addresses (supports non-ASCII local parts: å, ä, ö, ś, ń, etc.)
    (
        "EMAIL",
        re.compile(
            rf"\b[A-Za-z0-9._%+\-äåæøąćęłńóśźżçġißșüöčďěňřšťůžáéíóúýàèìòùâêîôûëïÿāēīōūķļņșțőű]+@[A-Za-z0-9.-]+\.[A-Za-z]{{2,}}{_END_DELIM}"
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
            r"7[0236789](?:[\s-]*\d){6,8}"
            r"|8(?:[\s-]*\d){7,8}"
            r"|[1-9]\d{1,2}(?:[\s-]*\d){5,8}"
            r")"
            r"|0(?:"
            r"7[0236789](?:[\s-]*\d){6,8}"
            r"|8(?:[\s-]*\d){7,8}"
            r"|[1-9]\d{1,2}(?:[\s-]*\d){5,8}"
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
            r"(?i)(?:org\.?\s*nr\.?:?|orgnr|organisationsnummer)\s*(\d{6}-\d{4})\b"
        ),
        1,
    ),
    # Labeled payment references such as OCR ref / OCR-nummer and KID.
    (
        "OCR",
        re.compile(
            r"(?i)\bOCR(?:[\s-]*(?:nr\.?|nummer|ref(?:erens)?\.?))?"
            r"\s*[:#-]?\s*(\d(?:[\d\s-]*\d){3,})\b"
        ),
        1,
    ),
    (
        "KID",
        re.compile(
            r"(?i)\bKID(?:[\s-]*(?:nr\.?|nummer|ref(?:erens)?\.?))?"
            r"\s*[:#-]?\s*(\d(?:[\d\s-]*\d){3,})\b"
        ),
        1,
    ),
    # Swedish personnummer — dash required (no bare digit runs).
    # Last four may be digits or a standard mask (XXXX / xxxx / ****).
    (
        "SSN",
        re.compile(
            r"\b(?:"
            r"(?:19|20)\d{6}-(?:\d{4}|[Xx\*]{4})"
            r"|\d{6}-(?:\d{4}|[Xx\*]{4})"
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
    # Major Swedish city names that commonly appear as standalone project locations.
    (
        "LOCATION",
        re.compile(rf"\b{_MAJOR_SWEDISH_CITIES}\b"),
        0,
    ),
    # Institutional and authority locations commonly used as project sites.
    (
        "LOCATION",
        re.compile(
            r"\b(?:"
            r"Karolinska\s+Universitetssjukhuset(?:\s+Solna)?"
            r"|Sahlgrenska\s+Universitetssjukhuset"
            r"|Boverket"
            r")\b"
        ),
        0,
    ),
    # Municipal areas/city authorities used as construction permitting locations.
    (
        "LOCATION",
        re.compile(
            rf"\b(?:"
            rf"[{_ORG_UC}][{_ORG_LC}]+s\s+Stadsdelsförvaltning(?:en)?"
            rf"|(?:{_MAJOR_SWEDISH_CITIES})s\s+Stad"
            rf")\b"
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
    # Advokatfirman + name (major law firms; complements dictionary list).
    (
        "ORG",
        re.compile(
            rf"\bAdvokatfirman\s+[{_ORG_UC}][{_ORG_LC}]+\b"
        ),
        0,
    ),
    # Advokatbyrån Name & Co. — full firm (avoids PERSON on the partner name alone).
    # No trailing \b after Co.: "." is non-word, so \b would not end the match at "Co.".
    (
        "ORG",
        re.compile(
            rf"(?i)\bAdvokatbyrån\s+(?:{_ORG_BODY_TOKEN}\s+){{1,3}}&\s+Co\.?(?=\s|[,.;:!?\)]|$)"
        ),
        0,
    ),
    # Polish sp. z o.o. after a company-style token (common in Swedish subcontractor lists).
    (
        "ORG",
        re.compile(
            rf"(?i)\b{_ORG_BODY_TOKEN}\s+z\s+o\.o\.(?=\s|[,.;:!?\)]|$)"
        ),
        0,
    ),
    # Swedish street address with optional apartment (lgh) and postal code + city.
    (
        "LOCATION",
        re.compile(
            r"\b"
            + rf"(?:{_STREET_TOKEN}\s+){{0,2}}"
            + rf"{_STREET_TOKEN}"
            + _STREET_SUFFIX
            + rf"\s+{_STREET_OCCUPANCY}"
            + r"(?:,?\s*lgh\.?\s+\d+)?"
            + r"(?:,?\s*\d{3}\s+\d{2}\s+[A-ZÅÄÖ][a-zåäö\-]+)?"
            + r"\b"
        ),
        0,
    ),
    # e.g. "Drottning Kristinas väg 14" — väg as its own token.
    (
        "LOCATION",
        re.compile(
            r"\b"
            + rf"(?:{_STREET_TOKEN}\s+){{1,3}}[Vv]äg\s+{_STREET_OCCUPANCY}"
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
    # Apartment / unit: lägenhet 1101, lägenhet LGH 1002, or lägenhet 1101, 1102 och 1201.
    (
        "LOCATION",
        re.compile(
            r"(?i)\blägenhet(?:en)?\s+"
            r"(?:lgh\.?\s+)?"
            r"(?:\d{1,4}[A-Za-z]?(?:\s*,\s*\d{1,4}[A-Za-z]?)*(?:\s+och\s+\d{1,4}[A-Za-z]?)?)"
            r"\b"
        ),
        0,
    ),
    # Hyresgäst i 1001 — apartment number without the word lägenhet.
    (
        "LOCATION",
        re.compile(r"(?i)\bhyresgäs(?:ten|t)\s+i\s+\d{1,4}\b"),
        0,
    ),
    # Standalone lgh (not only after a full street line).
    (
        "LOCATION",
        re.compile(r"(?i)\blgh\.?\s+\d{1,4}[A-Za-z]?\b"),
        0,
    ),
]

# First word of a LOCATION match is sometimes prose (e.g. "Besök Mäster Samuelsgatan …")
# before the actual street; strip these while a house number remains.
def _intervals_overlap(a0: int, a1: int, b0: int, b1: int) -> bool:
    return a0 < b1 and b0 < a1


_LOCATION_LEADING_TRASH = frozenset(
    {
        "besök",
        "ring",
        "skicka",
        "kontakta",
        "boka",
        "kom",
        "gå",
        "komma",
        "möt",
        "se",
        "fråga",
        "hitta",
        "passa",
        "titta",
        "kontor",
        "adress",
        "leverans",
    }
)

_ORG_PERSON_TO_LAW_FIRM_BRIDGE_RE = re.compile(
    r"\s+på\s+(?=Advokatfirman|Advokatbyrån)", re.IGNORECASE
)


def _trim_location_leading_prose(text: str, start: int, end: int) -> Tuple[int, int]:
    """Drop leading capitalized sentence words before multi-word street matches."""
    new_start = start
    while new_start < end:
        seg = text[new_start:end]
        parts = seg.split()
        if len(parts) < 3:
            break
        first = parts[0].lower().rstrip(".,;:!?")
        if first not in _LOCATION_LEADING_TRASH:
            break
        m = re.match(r"^\S+\s+", text[new_start:end])
        if not m:
            break
        new_start += m.end()
    if new_start == start:
        return start, end
    rest = text[new_start:end]
    if len(rest.split()) < 2 or not any(c.isdigit() for c in rest):
        return start, end
    return new_start, end


def _split_org_person_to_law_firm_bridge(
    text: str,
    start: int,
    end: int,
) -> List[Tuple[int, int]]:
    """Split over-broad ORGs like ``Person på Advokatfirman X AB``."""
    chunk = text[start:end]
    m = _ORG_PERSON_TO_LAW_FIRM_BRIDGE_RE.search(chunk)
    if not m:
        return [(start, end)]
    right_start = start + m.end()
    if right_start >= end:
        return [(start, end)]
    return [(right_start, end)]


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

    adjusted: List[Tuple[int, int, str, str]] = []
    for start, end, entity_type, matched in spans:
        if entity_type == "ORG":
            for ns, ne in _split_org_person_to_law_firm_bridge(text, start, end):
                adjusted.append((ns, ne, entity_type, text[ns:ne]))
            continue
        if entity_type != "LOCATION":
            adjusted.append((start, end, entity_type, matched))
            continue
        ns, ne = _trim_location_leading_prose(text, start, end)
        adjusted.append((ns, ne, entity_type, text[ns:ne]))
    spans = adjusted

    # IBAN and Swedish payment routing numbers must never be misclassified as PHONE.
    _PROTECT_PHONE = frozenset(
        {"IBAN", "PAYMENT_REF", "BANKGIRO", "PLUSGIRO", "BANK_ACCOUNT"}
    )
    protected_spans = {(s, e) for s, e, t, _ in spans if t in _PROTECT_PHONE}

    spans = [
        sp
        for sp in spans
        if not (
            sp[2] == "PHONE"
            and any(
                _intervals_overlap(sp[0], sp[1], i0, i1)
                for i0, i1 in protected_spans
            )
        )
    ]

    # Same digit span can match ORG_NR (labeled) and SSN (\d{6}-\d{4}); keep ORG_NR only.
    org_nr_spans = {(s, e) for s, e, t, _ in spans if t == "ORG_NR"}
    spans = [
        sp
        for sp in spans
        if not (sp[2] == "SSN" and (sp[0], sp[1]) in org_nr_spans)
    ]
    payment_ref_spans = {(s, e) for s, e, t, _ in spans if t == "PAYMENT_REF"}
    spans = [
        sp
        for sp in spans
        if not (
            sp[2] == "OCR"
            and any(
                _intervals_overlap(sp[0], sp[1], i0, i1)
                for i0, i1 in payment_ref_spans
            )
        )
    ]
    return spans
