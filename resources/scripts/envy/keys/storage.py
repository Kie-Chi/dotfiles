"""Atomic storage for .sops.yaml recipients and the local age private key."""

from __future__ import annotations

import re
import subprocess

from envy.secure_io import atomic_write_text, ensure_private_directory
from envy.utils import AGE_KEY_DIR, AGE_KEY_FILE, SOPS_YAML, backup_sensitive_file, run_cmd


def read_sops_yaml_keys() -> dict[str, str]:
    if not SOPS_YAML.exists():
        return {}
    pattern = re.compile(r"- &(\S+)\s+(age1\S+)")
    return {match.group(1): match.group(2) for match in pattern.finditer(SOPS_YAML.read_text())}


def write_sops_yaml_keys(keys: dict[str, str]) -> None:
    backup_sensitive_file(SOPS_YAML)
    lines = ["keys:\n", "  # Device keys - managed by envy key commands\n"]
    lines.extend(f"  - &{label} {public_key}\n" for label, public_key in keys.items())
    lines.extend([
        "\ncreation_rules:\n",
        "  - path_regex: secrets/secrets\\.yaml$\n",
        "    key_groups:\n",
        "      - age:\n",
    ])
    lines.extend(f"          - *{label}\n" for label in keys)
    atomic_write_text(SOPS_YAML, "".join(lines), mode=0o644)


def store_device_age_key(content: str) -> None:
    normalized = content.strip()
    if "AGE-SECRET-KEY" not in normalized:
        raise ValueError("age private key content is missing AGE-SECRET-KEY")
    ensure_private_directory(AGE_KEY_DIR)
    atomic_write_text(
        AGE_KEY_FILE,
        normalized + "\n",
        mode=0o600,
        private_parent=True,
    )


def generate_device_age_key() -> str:
    generated = run_cmd(["age-keygen"], capture=True)
    store_device_age_key(generated)
    return run_cmd(["age-keygen", "-y", str(AGE_KEY_FILE)], capture=True)


def current_device_public_key() -> str | None:
    """Derive the public recipient for the locally stored age identity."""
    if not AGE_KEY_FILE.exists():
        return None
    try:
        return run_cmd(["age-keygen", "-y", str(AGE_KEY_FILE)], capture=True)
    except subprocess.CalledProcessError:
        return None
