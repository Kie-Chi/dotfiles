"""Device-local sops label resolution backed by `.device-label`."""

from __future__ import annotations

import re

from envy.keys.storage import current_device_public_key, read_sops_yaml_keys
from envy.utils import (
    device_metadata_is_toml,
    read_device_metadata,
    run_cmd,
    write_device_metadata,
)


def sanitize_label(name: str) -> str:
    return re.sub(r"[^a-z0-9_]", "_", name.lower())


def get_sops_label() -> str:
    metadata = read_device_metadata()
    label = metadata.get("sops_label") or metadata.get("machine_id")
    if label:
        return sanitize_label(label)
    hostname = run_cmd(["hostname", "-s"], check=False, capture=True)
    return sanitize_label(hostname) if hostname else "unknown"


def set_sops_label(label: str) -> None:
    write_device_metadata(sops_label=sanitize_label(label) or "unknown")


def ensure_sops_label() -> str:
    """Return and persist a stable sops key label for the current device."""
    stored = read_device_metadata().get("sops_label", "")
    if stored:
        label = get_sops_label()
        if stored != label or not device_metadata_is_toml():
            set_sops_label(label)
        return label

    current_public_key = current_device_public_key()
    if current_public_key:
        matching_labels = [
            label
            for label, public_key in read_sops_yaml_keys().items()
            if label != "recovery"
            and public_key == current_public_key
            and sanitize_label(label) == label
        ]
        if matching_labels:
            set_sops_label(matching_labels[0])
            return matching_labels[0]

    label = get_sops_label()
    set_sops_label(label)
    return label
