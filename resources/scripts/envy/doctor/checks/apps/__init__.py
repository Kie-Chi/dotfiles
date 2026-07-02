"""Application doctor checks.

The app layer runs generic checkers (installed, running, state, login,
permissions) and custom checkers (e.g. vscode_sync) for each app declared
in schemas.apps.ALL_APP_SPECS.
"""

from collections.abc import Iterable
from typing import Optional

from envy.doctor.checks.apps.registry import available_apps, normalize_app_key, run_single_app
from envy.doctor.model import CheckResult, error
from envy.schemas.apps import ALL_APP_SPECS


def run_checks(selected: Optional[Iterable[str]] = None) -> list[CheckResult]:
    keys, unknown = _resolve_selection(selected)
    results: list[CheckResult] = []

    if unknown:
        results.append(error(
            "apps",
            "selection",
            "unknown app check(s): " + ", ".join(unknown),
            hint="Available app checks: " + ", ".join(available_apps()),
        ))

    for key in keys:
        results.extend(run_single_app(key))

    return results


def _resolve_selection(selected: Optional[Iterable[str]]) -> tuple[list[str], list[str]]:
    requested = _expand_selection(selected)
    if not requested:
        return list(ALL_APP_SPECS), []

    keys: list[str] = []
    unknown: list[str] = []
    seen: set[str] = set()
    for value in requested:
        key = normalize_app_key(value)
        if key not in ALL_APP_SPECS:
            unknown.append(value)
            continue
        if key not in seen:
            keys.append(key)
            seen.add(key)

    return keys, unknown


def _expand_selection(selected: Optional[Iterable[str]]) -> list[str]:
    if not selected:
        return []

    values: list[str] = []
    for item in selected:
        values.extend(part.strip() for part in item.split(",") if part.strip())
    return values
