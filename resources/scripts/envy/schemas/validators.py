"""Shared field validators for envy config schema.

Each validator takes a string value and returns None (valid) or an error
message string (invalid).
"""

import re
from typing import Optional


def non_empty(val: str) -> Optional[str]:
    if not val.strip():
        return "Value cannot be empty"
    return None


def is_email(val: str) -> Optional[str]:
    if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', val):
        return "Please enter a valid email address"
    return None


def is_url(val: str) -> Optional[str]:
    if val and not val.startswith("http://") and not val.startswith("https://"):
        return "URL must start with http:// or https://"
    return None


def is_machine_id(val: str) -> Optional[str]:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", val or ""):
        return "Machine ID may contain only letters, digits, underscores, and hyphens"
    return None
