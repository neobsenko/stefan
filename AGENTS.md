# Stefan — Detection Pipeline & Architecture

This file is for developers working on Stefan. For user-facing documentation, see `README.md`.

---

## Detection Pipeline

Detection runs as a strict-priority pipeline of independent detectors. The pipeline order is critical: earlier detectors claim spans first and protect those spans from misclassification by later detectors. Each detector returns `(start, end, entity_type, matched_text)` tuples.

### Pipeline order

```
1. regex.py       (detect_regex)        ← highest priority
2. context_triggers.py (detect_context_triggers)
3. dictionary.py   (detect_dictionary)
4. dictionary_orgs.py (detect_dictionary_orgs)
5. name_morphology.py (detect_name_morphology)
6. nlp.py         (detect_spacy)         ← fallback only
7. merger.py      (merge_spans)          ← resolves overlaps, applies post-processing
```

Called from `redactor.py`:
```python
regex_spans = detect_regex(text) + detect_context_triggers(text)
dict_spans = detect_dictionary(text) + detect_dictionary_orgs(text) + detect_name_morphology(text)
spacy_spans = detect_spacy(text) if use_spacy else []
spans = merge_spans(regex_spans, dict_spans, spacy_spans, text=text)
```

---

## Detectors

### 1. regex.py (`detect_regex`)

Pattern-based extraction for structurally predictable entities. Priority is assigned in `merger.py` based on entity type: hard identifiers (`IBAN`, `BANKGIRO`, `EMAIL`, `PHONE`, `ORG_NR`, `SSN`, `PAYMENT_REF`, `BANK_ACCOUNT`, `PLUSGIRO`, `KID`, `OCR`, `IP`, `URL`) get `regex_hard`; `ORG` gets `regex_org`; everything else gets `regex`.

Patterns (in priority order):
- **IBAN** — Swedish `SE\d{2}(?:[ \t]?\d{4}){5}` then generic international fallback
- **PAYMENT_REF** — labeled OCR refs: `(?i)\b(?:OCR|OCR-nr|...):?\s*(\d{6,25})\b`
- **BANKGIRO** — `NNNN-NNNN` with context guards (not `BL-2026-…`, not year-prefixed)
- **PLUSGIRO** — spaced format `NN NN NN-N` and compact `N{1,8}-N`
- **BANK_ACCOUNT** — SEB clearing format (`XXXX-XX XXX XXX XXX`), Nordea short groups, generic Swedish accounts; guards against international dial prefixes (`0046`) and year-prefixed refs
- **URL** — `https?://|www\.` followed by non-space content
- **URL** — social profile paths without protocol: `/in/…`, `linkedin.com/in/…`, etc.
- **EMAIL** — standard `user@domain.tld` pattern
- **PHONE** — Swedish: `+46`/`0046` with area codes (`7X`, `08`, others); international fallback: `+CC` not `+46`
- **ORG_NR** — labeled: `org.nr.:? NNNNNN-NNNN`
- **OCR** / **KID** — labeled numeric references with digit-count guard
- **SSN** — Swedish personnummer: `YYYYMMDD-XXXX` or `YYMMDD-XXXX` (dash required; last 4 may be masked)
- **IP** — IPv4 addresses
- **ORG** — Swedish/international company names with legal suffixes (`AB`, `HB`, `KB`, `Holding`, `GmbH`, `Ltd`, etc.) and connectors (`och`, `&`, `i`, `på`, `av`)
- **ORG** — Swedish municipalities: `Stad`/`Kommun` patterns
- **ORG** — Swedish public sector: `Region X`, `X Förvaltning`, etc.
- **ORG** — Swedish institutions: `X Sjukhus`, `X Universitet`, `X Institutet`, etc.
- **ORG** — `Advokatfirman Name`, `Advokatbyrån Name & Co.`
- **ORG** — Polish `sp. z o.o.` after company-style token
- **LOCATION** — Swedish street addresses: `StreetNamegatan N`, optional `lgh.`, postal code, city
- **LOCATION** — `Väg N` variant
- **LOCATION** — PO box: `Box NNNN`
- **LOCATION** — apartment/unit: `lägenhet NNNN`, `hyresgäst i NNNN`
- **LOCATION** — standalone `lgh. NNNN`

Post-processing in `detect_regex`:
- **Phone protection**: IBAN/PAYMENT_REF/BANKGIRO/PLUSGIRO/BANK_ACCOUNT spans are protected from PHONE overlap
- **ORG_NR over SSN**: if a digit span matches both labeled ORG_NR and bare SSN, keep ORG_NR only
- **OCR over KID**: if OCR and KID overlap, keep OCR only
- **LOCATION leading prose trim**: drops sentence-openers before street addresses — `Besök`, `Ring`, `Skicka`, `Kontakta`, `Boka`, `Kom`, `Gå`, `Kommer`, `Möt`, `Se`, `Fråga`, `Hitta`, `Passa`, `Titta`, `Kontor`, `Adress`, `Leverans`

### 2. context_triggers.py (`detect_context_triggers`)

Detects names by surrounding linguistic context rather than the name itself. Returns `PERSON` spans.

Patterns:
- Email greeting: `Hej [Name],`
- Email sign-offs: `Mvh\n\n[Name]`, `Med vänlig hälsning [Name]`, `Bästa hälsningar\n[Name]`
- Email headers: `Från: [Name]`, `Till: [Name]`, `Kopia: [Name]`
- Role introduction: `kontaktperson är/heter [Name]`, `vår VD/chef/platschef/projektledare/koordinator [Name]`

### 3. dictionary.py (`detect_dictionary`)

Whole-word, case-sensitive lookup against curated name lists. Returns `PERSON` spans. Supports reloading at runtime for the custom names endpoint.

Files in `data/` (loaded at startup; missing files are silently skipped):
- `swedish_first_names.txt` — Swedish given names
- `swedish_surnames.txt` — Swedish surnames
- `polish_names.txt` — Polish names (male/female, morphologically aware)
- `finnish_names.txt` — Finnish names
- `arabic_names_transliterated.txt` — Arabic names (Latin transliteration)
- `slavic_names.txt` — Slavic names (Latin transliteration)
- `custom_names.txt` — user-managed additions (appended at runtime via `/api/dictionary/add`)

Reload function: `reload_name_dictionaries()` — re-reads all files from disk and rebuilds the lookup set.

### 4. dictionary_orgs.py (`detect_dictionary_orgs`)

Whole-word, case-sensitive lookup against curated org lists. Returns `ORG` spans. Supports reloading at runtime.

Files in `data/`:
- `swedish_org_acronyms.txt` — ABB, IKEA, SEB, NCC, etc.
- `construction_orgs.txt` — Ahlsell, Beijer, Optimera, Lindab, Saint-Gobain, Rexel, Hilti, Veidekke, etc.
- `swedish_insurance_finance.txt` — SEB, Handelsbanken, Swedbank, Nordea, Trygg-Hansa, Folksam, Länsförsäkringar, etc.
- `swedish_law_firms.txt` — Vinge, Mannheimer Swartling, Lindahl, Roschier, Setterwalls, etc.
- `staffing_companies.txt` — Manpower, Adecco, Randstad, etc.
- `swedish_municipal_departments.txt` — Stadsbyggnadskontoret, Miljöförvaltningen, etc.

Reload function: `reload_org_dictionaries()` — re-reads all files from disk.

### 5. name_morphology.py (`detect_name_morphology`)

Pattern-based detection for names from languages with predictable structural endings. Returns `PERSON` spans.

Patterns:
- **Polish surnames**: `-ski`, `-ska`, `-cki`, `-cka`, `-wicz`, `-czyk`
- **Slavic surnames**: `-enko`, `-ov`, `-ova`, `-ev`, `-eva`
- **Finnish surnames**: `-nen`, `-la`, `-lä`
- **Latvian surnames**: `-iņš`, `-iņa`, `-aņš`, `-iņi`
- **Turkish surnames**: hyphenated compound (e.g. `Yılmaz-Demir`)
- **Arabic patronymic**: `bin`, `ibn`, `Abu`, `Al-`, `al-`, `el-`, `El-`; also full chains (`Khalid bin Tariq`)
- **Germanic noble particles**: `von`, `van`, `van der`, `de`, `zu`
- **French apostrophe particles**: `d'`, `D'`, `l'`, `L'`, `de la`, `du`, `des`
- **Irish/Scottish**: `O'` (e.g. `O'Sullivan`)
- **Swedish family collectives**: `Familjen [surname]`
- **Hyphenated double surnames**: any combination of the above
- **Hyphenated compound first names**: `Lars-Erik`, `Anna-Karin`, `Per-Olof`, including with quoted nicknames between first name and surname

Token character classes extend to European capitals: `A-ZÄÖÅÆØĄĆĘŁŃÓŚŹŻÇĞIŞÜČĎĚŇŘŠŤŮŽÁÉÍÓÚÝÀÈÌÒÙÂÊÎÔÛËÏŸĀĒĪŌŪĶĻŅȘȚŐŰ`.

### 6. nlp.py (`detect_spacy`)

spaCy NER fallback using the Swedish `sv_core_news_md` model (or `sv_core_news_sm`/`sv_core_news_lg` depending on env vars). Returns `PERSON`, `ORG`, `LOC` spans. Priority is always lowest (`spacy: 1`).

Warm-up function: `warm_model_for_web(quiet)` — pre-loads the model before the first HTTP request so the UI doesn't hang.

---

## merger.py (`merge_spans`)

Takes spans from all detectors and produces a final sorted, non-overlapping list. Key stages:

### Priority system

| Source type | Priority |
|---|---|
| `regex_hard` (IBAN, PHONE, SSN, etc.) | 6 |
| `regex_org` | 5 |
| `dictionary_org` | 4 |
| `regex` (ORG from regex, LOCATION) | 3 |
| `dictionary` (PERSON from names) | 2 |
| `spacy` | 1 |

### Stopword filter

Loaded from `data/stopwords_construction.txt`. Runs after all spans are tagged but before overlap resolution. Removes:
- Swedish industry acronyms (ID06, KMA, BAS-U, BAS-P, ÄTA, AMA, ABT, AB04)
- Role abbreviations (HR, IT, VD, CFO, COO, CEO, CTO)
- Currency codes (SEK, EUR, USD, NOK, DKK)
- Unit abbreviations (KG, KM, CM, MM, KWH)
- Swedish prepositions (innan, sedan, efter, mellan, under, enligt)
- Swedish nationality adjectives (Norska, Polska, Finska, Tyska)
- Swedish quantity descriptors (Multipla, Olika, Flera, Många, Andra)
- Financial labels (Bankgiro, Plusgiro, IBAN, BIC, OCR, Konto, Faktura)
- Header labels (Datum, Från, Till, Kopia, Bcc, Ämne, Org.nr, Personnr)
- Greetings (Pozdrowienia, Tervetuloa, Grüße, Salutations)
- SaaS products (Sharepoint, Teams, Zoom, Slack, Microsoft, LinkedIn, WhatsApp, Klarna)
- Swedish imperative verbs at sentence-start (Skicka, Hör, Ring, Glöm, Hålla, Tack, Hej)
- Swedish auxiliary verbs (Kunna, Vilja, Skola, Måste)
- ALL CAPS heading words (BETALNINGSUPPGIFTER, KONTAKTUPPGIFTER, etc.)

### Non-PERSON overlap resolution (`_merge_non_person`)

Sorted by `(-priority, -length, start)`. Greedy: accept highest-priority span first, reject all overlapping lower-priority spans. Special case: a wider ORG span from any source can extend a locked dictionary ORG if the wider span is ORG-only and strictly contains it.

### PERSON overlap resolution (`_merge_person_widest`)

Sorted by `(-length, -priority, start)`. Among overlapping PERSON spans, keep the widest. spaCy LOCATION/ORG fully contained within a PERSON are subsumed (not rejected).

### Post-processing steps (all require `text`)

1. **Line-break truncation** — spans are cut at the first newline; entities never span lines
2. **PERSON lookahead extension** — extends a PERSON span by one following capitalized alpha token if it's not a stopword
3. **Non-PERSON subsumption check** — LOCATION/ORG/etc. fully inside a kept PERSON are dropped
4. **Adjacent PERSON merge** — merges PERSON spans separated only by whitespace, hyphen, or quoted nickname pattern (`"Nick"`)
5. **Hyphenated surname extension** — extends PERSON spans with trailing hyphenated surname segments
6. **Adjacent ORG merge** — merges ORG spans separated only by whitespace or linker words (`Fastigheter`, `Sverige`, `Holding`, `Holdings`, `Group`, `Bygg`, `Entreprenad`, `Konsult`, `Förvaltning`, `Invest`, `International`, `Nordic`, `Scandinavia`, `Construction`)
7. **Polish `z o.o.` extension** — extends ORG spans to include trailing `z o.o.`
8. **Coreference** — scans for standalone first-name mentions of already-tagged PERSONs; links them to the canonical full-name entity. Handles Swedish genitive forms (`Anna` → `Annas`). Suppressed when first names are ambiguous (multiple people share the same first name in the document)

### Type-lock rule

Entities matched via dictionary (`dictionary_org` or `dictionary`) cannot be reclassified by later passes (spaCy). This prevents known companies like `Veidekke` from being downgraded to LOCATION by spaCy's location classifier.

---

## Placeholder assignment

Each unique source value gets exactly one placeholder ID per type. Duplicate values reuse the same placeholder. A strict no-collision rule: two different real values can never share a placeholder ID.

Pattern: `\b(TYPE)_\d+\b` where TYPE is one of `PERSON`, `ORG`, `ORG_NR`, `LOCATION`, `EMAIL`, `PHONE`, `URL`, `SSN`, `IP`, `PAYMENT_REF`.

---

## Hydration (`hydrator.py`)

The reverse of redaction. Loads the saved mapping (stored in `localStorage` client-side and server-side audit DB) and replaces all placeholder tokens with their original values. Unknown placeholders are left untouched.

---

## Web server (`web.py`)

Flask app on port 80 (or 5000). Serves `static/index.html` as a single-page application.

Endpoints:
- `GET /` — serves the UI
- `POST /api/detect` — `{"text": "..."}` → `{"spans": [{"start", "end", "type", "value"}]}`
- `POST /api/dictionary/add` — add to custom dictionaries (`{"kind": "name"|"org", "text": "..."}`)
- `GET /admin/custom-names` — admin page for custom names
- `GET /api/_stefan/boot` — server boot ID for browser auto-refresh

Config env vars:
- `STEFAN_USE_SPACY=0` — disable spaCy
- `STEFAN_MAX_DETECT_CHARS=N` — max text length (default 100,000)
- `STEFAN_WEB_NO_SPACY=1` — alias for above

---

## Adding new detection patterns

**New regex pattern** → add to `PATTERNS` in `detectors/regex.py`:
```python
("MY_TYPE", re.compile(r"\bmy_pattern\b"), 0),
```

**New dictionary file** → add to `DETECTOR_FILES` in `detectors/dictionary.py` or `detectors/dictionary_orgs.py`, then add the file to `pyproject.toml` under `[tool.setuptools.package-data]`.

**New morphology pattern** → add to the relevant regex group in `detectors/name_morphology.py`.

**Important**: changes to one detector should never require changes to another. If a new pattern causes conflicts with an existing detector, address it at the merger/priority level, not by modifying the detector that produces correct output.

Every new rule must be justified by a real false positive or false negative observed in customer data. Speculative complexity is the enemy of maintainability and trust.

---

## Testing

```bash
pytest
```

---

## Repository structure

```
stefan/                     ← Python package
├── cli.py                  # stefan redact / serve / hydrate commands
├── redactor.py             # Core redaction logic
├── hydrator.py             # Placeholder rehydration
├── web.py                  # Flask web server
├── detectors/
│   ├── __init__.py
│   ├── context_triggers.py # Context-based PERSON detection
│   ├── dictionary.py       # Name dictionary lookup
│   ├── dictionary_orgs.py  # Org dictionary lookup
│   ├── merger.py           # Span merging + post-processing
│   ├── name_morphology.py  # Structural name patterns
│   ├── nlp.py              # spaCy NER fallback
│   └── regex.py            # Pattern-based detection
├── data/                   # Dictionary/thesaurus files
└── static/
    └── index.html          # Single-page web UI

tests/
    test_*.py               # Detector-specific tests
```
