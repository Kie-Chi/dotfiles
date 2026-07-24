"""Structural validation for sops-encrypted YAML without decrypting it."""

from __future__ import annotations

from typing import Any

import yaml


def _encrypted_leaf(value: Any, *, key: str, unencrypted_suffix: str) -> bool:
    if unencrypted_suffix and key.endswith(unencrypted_suffix):
        return True
    if isinstance(value, dict):
        return all(
            _encrypted_leaf(child, key=str(child_key), unencrypted_suffix=unencrypted_suffix)
            for child_key, child in value.items()
        )
    if isinstance(value, list):
        return all(
            _encrypted_leaf(child, key=key, unencrypted_suffix=unencrypted_suffix)
            for child in value
        )
    # sops intentionally leaves empty values empty. Every non-empty scalar
    # outside its metadata must otherwise be an ENC[...] envelope.
    return value is None or value == "" or (
        isinstance(value, str) and value.startswith("ENC[") and value.endswith("]")
    )


def content_is_sops_encrypted(content: str) -> bool:
    """Reject malformed or mixed plaintext/ciphertext sops YAML documents."""
    try:
        data = yaml.safe_load(content)
    except (yaml.YAMLError, UnicodeError):
        return False
    if not isinstance(data, dict):
        return False
    metadata = data.get("sops")
    if not isinstance(metadata, dict):
        return False
    mac = metadata.get("mac")
    age = metadata.get("age")
    if not (
        isinstance(mac, str)
        and mac.startswith("ENC[")
        and mac.endswith("]")
        and isinstance(age, list)
        and age
    ):
        return False
    suffix = metadata.get("unencrypted_suffix", "")
    unencrypted_suffix = suffix if isinstance(suffix, str) else ""
    return all(
        key == "sops"
        or _encrypted_leaf(value, key=str(key), unencrypted_suffix=unencrypted_suffix)
        for key, value in data.items()
    )
