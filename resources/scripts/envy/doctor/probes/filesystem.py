"""Filesystem probes."""

import json
from pathlib import Path
from typing import Iterable

from envy.utils import HOME_DIR


def first_existing(paths: Iterable[Path]) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None


def app_bundle(bundle_names: Iterable[str]) -> Path | None:
    candidates: list[Path] = []
    for name in bundle_names:
        candidates.extend([
            Path("/Applications") / name,
            HOME_DIR / "Applications" / name,
            HOME_DIR / "Applications" / "Home Manager Apps" / name,
        ])
    return first_existing(candidates)


def read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
