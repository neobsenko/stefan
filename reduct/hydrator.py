"""Hydration: replace placeholders with their original values."""

import re
from typing import Dict

# Match any placeholder of the form TYPE_N where TYPE is one of our known types.
_PLACEHOLDER_RE = re.compile(
    r"\b(?:PERSON|ORG|ORG_NR|LOCATION|EMAIL|PHONE|URL|SSN|IP)_\d+\b"
)


def hydrate(text: str, mapping: Dict[str, str]) -> str:
    """Replace placeholders in text with their original values.

    Unknown placeholders (not in the mapping) are left untouched.
    """

    def _sub(match: re.Match) -> str:
        placeholder = match.group(0)
        return mapping.get(placeholder, placeholder)

    return _PLACEHOLDER_RE.sub(_sub, text)
