"""
Mirror clipboard wrap + hydrate strip logic from reduct/static/index.html.
Keep regex and string literals in sync when changing the UI.
"""

import re

# --- sync with index.html (CLIPBOARD_INSTRUCTION_*) ---
CLIPBOARD_INSTRUCTION_OPEN = (
    "[The following text has been automatically redacted for privacy. Placeholders like PERSON_1, ORG_2, EMAIL_1, LOCATION_1, PHONE_1, SSN_1, URL_1 represent real names, companies, emails, addresses, phone numbers, personal IDs, and URLs. Treat each placeholder as a consistent entity — the same placeholder always refers to the same real value. Respond normally using the placeholders as-is; they will be automatically restored afterward. Do not ask what the placeholders mean.]"
)
CLIPBOARD_INSTRUCTION_CLOSE = (
    "[End of redacted text. Please respond keeping all placeholders exactly as written.]"
)

HYDRATE_STRIP_LEAD = re.compile(
    r"^\s*\[[^\]]*(?:redacted|placeholder)[^\]]*\]\s*",
    re.IGNORECASE,
)
HYDRATE_STRIP_TAIL = re.compile(
    r"\s*\[[^\]]*End of redacted[^\]]*\]\s*$",
    re.IGNORECASE,
)


def wrap_redacted_for_clipboard(redacted: str) -> str:
    return (
        CLIPBOARD_INSTRUCTION_OPEN
        + "\n\n"
        + redacted
        + "\n\n"
        + CLIPBOARD_INSTRUCTION_CLOSE
    )


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
