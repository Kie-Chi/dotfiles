"""Evaluate the selected Nix machine for Envy's read-only views."""

import json
import subprocess
from functools import lru_cache
from typing import Any, Iterator

from envy.utils import DOTFILES_DIR, current_machine_id


SELECTION_GROUPS = (
    ("packages", "home"),
    ("packages", "system"),
    ("packages", "fonts"),
    ("homebrew", "brews"),
    ("homebrew", "casks"),
    ("homebrew", "taps"),
)


@lru_cache(maxsize=1)
def machine_manifest() -> dict[str, Any] | None:
    """Return the evaluated manifest, including imported defaults and modules."""
    machine_id = current_machine_id()
    attr = f"path:.#darwinConfigurations.{machine_id}.config.envy.machine.manifest"
    try:
        result = subprocess.run(
            ["nix", "eval", "--impure", attr, "--json"],
            cwd=str(DOTFILES_DIR), capture_output=True, text=True,
            timeout=30, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def manifest_settings(manifest: dict[str, Any] | None) -> dict[str, str]:
    """Normalize evaluated scalar settings for the config editor/view."""
    if not manifest or not isinstance(manifest.get("settings"), dict):
        return {}
    values: dict[str, str] = {}
    for path, value in manifest["settings"].items():
        if isinstance(value, bool):
            values[str(path)] = "true" if value else "false"
        elif isinstance(value, (str, int, float)):
            values[str(path)] = str(value)
    return values


def manifest_selection_rows(
    manifest: dict[str, Any] | None,
) -> Iterator[tuple[str, list[str], list[str], list[str]]]:
    """Yield path plus evaluated include/exclude/effective selection lists."""
    if not manifest:
        return
    inclusions = manifest.get("inclusions", {})
    exclusions = manifest.get("exclusions", {})
    for domain, group in SELECTION_GROUPS:
        include = _string_list(_nested(inclusions, domain, group))
        exclude = _string_list(_nested(exclusions, domain, group))
        effective = _string_list(_nested(manifest, domain, group))
        yield f"envy.{domain}.{group}", include, exclude, effective


def _nested(data: Any, first: str, second: str) -> Any:
    if not isinstance(data, dict):
        return []
    section = data.get(first, {})
    return section.get(second, []) if isinstance(section, dict) else []


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]
