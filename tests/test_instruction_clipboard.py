"""
Mirror clipboard wrap + hydrate strip logic from stefan/static/index.html.
Keep regex and string literals in sync when changing the UI.
"""

import re
from typing import Optional

# --- sync with index.html (CLIPBOARD_INSTRUCTION_*) ---
CLIPBOARD_INSTRUCTION_OPEN = (
    "[The following text has been automatically redacted for privacy. Placeholders like PERSON_1, ORG_2, EMAIL_1, LOCATION_1, PHONE_1, SSN_1, URL_1 represent real names, companies, emails, addresses, phone numbers, personal IDs, and URLs. Treat each placeholder as a consistent entity — the same placeholder always refers to the same real value. Respond using the placeholders as-is; they will be automatically restored afterward. Do not ask what the placeholders mean. Format your entire answer for copy-paste: it should look good when pasted into email, Word, Notion, or plain notes — clear section breaks, simple bullet lines, and plain-text-friendly tables (pipes/spaces) where tables are used. No chat-only fluff or decorative framing that would look wrong outside this window.]"
)
CLIPBOARD_INSTRUCTION_CLOSE = (
    "[End of redacted text. Keep all placeholders exactly as written. The reply must be ready to select-all, copy, and paste elsewhere without cleanup.]"
)

# --- sync with index.html (CLIPBOARD_SUMMARIZE_SV) ---
CLIPBOARD_SUMMARIZE_SV = (
    "Du är en assistent för svenska byggföretag. Sammanfatta följande mejl/dokument i punktform på svenska. Strukturen ska vara:\n\n"
    "Huvudbudskap: (1-2 meningar)\n\n"
    "Vad som måste göras:\n"
    "- [konkreta åtgärder med ansvarig och deadline om angivet]\n\n"
    "Viktiga datum & deadlines:\n"
    "- [alla datum, möten, frister]\n\n"
    "Personer att kontakta:\n"
    "- [namn/roll → vad de vill]\n\n"
    "Pengar/fakturor som nämns:\n"
    "- [belopp och vad det gäller]\n\n"
    "Risker eller varningar:\n"
    "- [det som kan gå fel om inget görs]\n\n"
    "Var konkret. Hoppa över artighetsfraser. Använd platshållarna (PERSON_1, ORG_2 etc) exakt som de står — de återställs automatiskt efteråt. Formatera så att användaren kan kopiera hela svaret och klistra in det i mejl, dokument eller anteckningar utan att behöva fixa radbrytningar eller struktur."
)

# --- sync with index.html (CLIPBOARD_DEADLINES_SV) ---
CLIPBOARD_DEADLINES_SV = (
    "Du är en assistent för svenska byggföretag. Läs följande text och extrahera ENBART deadlines, datum och tidskritiska saker. Strukturen ska vara:\n\n"
    "AKUT (inom 24 timmar):\n"
    "- [datum/tid] — [vad som måste göras] — [vem som ansvarar]\n\n"
    "DENNA VECKA:\n"
    "- [datum] — [vad som måste göras] — [vem som ansvarar]\n\n"
    "KOMMANDE:\n"
    "- [datum] — [vad som måste göras] — [vem som ansvarar]\n\n"
    "Möten:\n"
    "- [datum, tid, plats, deltagare]\n\n"
    "Lagstadgade frister (GDPR, AI Act, Arbetsmiljöverket, Boverket etc):\n"
    "- [vilken lag/myndighet] — [frist] — [konsekvens om missad]\n\n"
    'Sortera kronologiskt inom varje kategori. Om en deadline saknas men borde finnas, flagga det med "Deadline saknas". Använd platshållarna exakt som de står. Formatera så att listorna och rubrikerna går att kopiera och klistra in någon annanstans med bibehållen läsbarhet.'
)

# --- sync with index.html (CLIPBOARD_COSTS_SV) ---
CLIPBOARD_COSTS_SV = (
    "Du är en ekonomiassistent för svenska byggföretag. Läs följande text och extrahera all ekonomisk information. Strukturen ska vara:\n\n"
    "Fakturor att skicka:\n"
    "| Mottagare | Belopp (exkl. moms) | Belopp inkl. moms (25%) | Referens | Förfallodag |\n"
    "|---|---|---|---|---|\n\n"
    "Fakturor att betala:\n"
    "| Avsändare | Belopp | Förfallodag | Status |\n"
    "|---|---|---|---|\n\n"
    "Betalningsuppgifter som nämns:\n"
    "- [bankgiro/plusgiro/IBAN/konto + till vem]\n\n"
    "Total exponering:\n"
    "- Att fakturera ut: [summa] SEK\n"
    "- Att betala ut: [summa] SEK\n"
    "- Netto: [summa] SEK\n\n"
    "Ekonomiska risker:\n"
    "- [innehållna betalningar, tvister, ÄTA-arbeten utanför kontrakt, försenade fakturor, kontraktsbrott enligt AB04]\n\n"
    "Saknas:\n"
    "- [fakturor som borde nämnts men inte är, momsberäkningar, OCR-nummer]\n\n"
    "Räkna ut moms (25%) automatiskt om bara nettobelopp anges. Använd platshållarna exakt som de står. Tabeller ska vara enkla texttabeller (pipe-tecken) som klistras in läsbart; hela svaret ska gå att kopiera rakt av till kalkylark, mejl eller dokument."
)

HYDRATE_STRIP_LEAD = re.compile(
    r"^\s*\[[^\]]*(?:redacted|placeholder)[^\]]*\]\s*",
    re.IGNORECASE,
)
HYDRATE_STRIP_TAIL = re.compile(
    r"\s*\[[^\]]*End of redacted[^\]]*\]\s*$",
    re.IGNORECASE,
)


def wrap_redacted_for_clipboard(
    redacted: str, selected_preset: Optional[str] = None
) -> str:
    out = CLIPBOARD_INSTRUCTION_OPEN + "\n\n" + redacted + "\n\n"
    if selected_preset == "summarize":
        out += CLIPBOARD_SUMMARIZE_SV + "\n\n"
    elif selected_preset == "deadlines":
        out += CLIPBOARD_DEADLINES_SV + "\n\n"
    elif selected_preset == "costs":
        out += CLIPBOARD_COSTS_SV + "\n\n"
    out += CLIPBOARD_INSTRUCTION_CLOSE
    return out


def strip_hydration_wrappers(raw: str) -> str:
    t = raw
    for _ in range(32):
        n = HYDRATE_STRIP_LEAD.sub("", t, count=1)
        if n == t:
            break
        t = n
    for _ in range(32):
        n = HYDRATE_STRIP_TAIL.sub("", t, count=1)
        if n == t:
            break
        t = n
    return t.strip()


def test_clipboard_wrap_contains_instruction_blocks_and_body():
    body = "Please reply to EMAIL_1 about ORG_1."
    wrapped = wrap_redacted_for_clipboard(body)
    assert wrapped.startswith(CLIPBOARD_INSTRUCTION_OPEN)
    assert wrapped.endswith(CLIPBOARD_INSTRUCTION_CLOSE)
    assert "\n\n" + body + "\n\n" in wrapped
    assert "redacted for privacy" in wrapped
    assert "End of redacted text" in wrapped
    assert "copy-paste" in wrapped.lower()


def test_summarize_preset_inserts_swedish_instruction_after_redacted_body():
    body = "Mejl PERSON_1."
    wrapped = wrap_redacted_for_clipboard(body, selected_preset="summarize")
    assert CLIPBOARD_SUMMARIZE_SV in wrapped
    assert wrapped.index(body) < wrapped.index(CLIPBOARD_SUMMARIZE_SV)
    assert "Huvudbudskap:" in wrapped
    assert "**" not in CLIPBOARD_SUMMARIZE_SV
    assert "Sammanfatta följande mejl" in wrapped


def test_summarize_preset_off_matches_default_wrap():
    body = "X"
    assert wrap_redacted_for_clipboard(body) == wrap_redacted_for_clipboard(
        body, selected_preset=None
    )


def test_deadlines_preset_inserts_swedish_instruction_after_redacted_body():
    body = "Möte PERSON_1 imorgon."
    wrapped = wrap_redacted_for_clipboard(body, selected_preset="deadlines")
    assert CLIPBOARD_DEADLINES_SV in wrapped
    assert wrapped.index(body) < wrapped.index(CLIPBOARD_DEADLINES_SV)
    assert "AKUT (inom 24 timmar):" in wrapped
    assert "extrahera ENBART deadlines" in wrapped
    assert "Deadline saknas" in wrapped
    assert "**" not in CLIPBOARD_DEADLINES_SV


def test_costs_preset_inserts_swedish_instruction_after_redacted_body():
    body = "Faktura ORG_1 10 000 kr."
    wrapped = wrap_redacted_for_clipboard(body, selected_preset="costs")
    assert CLIPBOARD_COSTS_SV in wrapped
    assert wrapped.index(body) < wrapped.index(CLIPBOARD_COSTS_SV)
    assert "Fakturor att skicka:" in wrapped
    assert "ekonomiassistent" in wrapped
    assert "| Mottagare | Belopp (exkl. moms)" in wrapped
    assert "**" not in CLIPBOARD_COSTS_SV


def test_strip_removes_echoed_wrappers_before_hydrate():
    """Paste that mimics AI echoing our opening block; strip leaves redacted body."""
    inner = "Thanks, I will contact EMAIL_1."
    pasted = CLIPBOARD_INSTRUCTION_OPEN + "\n\n" + inner + "\n\n" + CLIPBOARD_INSTRUCTION_CLOSE
    assert strip_hydration_wrappers(pasted) == inner


def test_strip_placeholder_only_leading_bracket_block():
    """Alternate leading block mentioning 'placeholder'."""
    block = "[Note: use placeholder tokens like EMAIL_1.]\n\nReal body PERSON_1."
    assert strip_hydration_wrappers(block) == "Real body PERSON_1."


def test_strip_multiple_leading_blocks():
    t = "[Something redacted here]\n[Another placeholder note]\n\nFinal EMAIL_1."
    assert strip_hydration_wrappers(t) == "Final EMAIL_1."
