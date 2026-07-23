"""Filesystem probes."""

import json
from pathlib import Path
from typing import Iterable

from envy.utils import HOME_DIR, platform_name

APP_DIRS = (
    [
        Path("/Applications"),
        HOME_DIR / "Applications",
        HOME_DIR / "Applications" / "Home Manager Apps",
        Path("/Library/Input Methods"),
    ]
    if platform_name() == "darwin"
    else [
        HOME_DIR / ".local/share/applications",
        Path("/usr/share/applications"),
    ]
)


def first_existing(paths: Iterable[Path]) -> Path | None:
    for path in paths:
        if path.exists():
            return path
    return None


def app_bundle(bundle_names: Iterable[str]) -> Path | None:
    candidates: list[Path] = []
    for name in bundle_names:
        bundle_path = Path(name)
        if bundle_path.is_absolute():
            candidates.append(bundle_path)
            continue
        candidates.extend(app_dir / name for app_dir in APP_DIRS)
    return first_existing(candidates)


def read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}
