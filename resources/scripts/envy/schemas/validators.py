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


def is_terminal_scratchpad_gesture(val: str) -> Optional[str]:
    if val not in {"F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "F10", "F12"}:
        return "Terminal scratchpad gesture must be one of F2 through F10, or F12"
    return None


def is_global_launcher_gesture(val: str) -> Optional[str]:
    if not re.fullmatch(
        r"Option\+(?:[A-Za-z0-9]|Space|Return|Tab|Escape|F(?:[1-9]|1[0-2]))",
        val or "",
    ):
        return "Global launcher gesture must use Option+<key>, for example Option+Space"
    return None


def is_machine_id(val: str) -> Optional[str]:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", val or ""):
        return "Machine ID may contain only letters, digits, underscores, and hyphens"
    return None
