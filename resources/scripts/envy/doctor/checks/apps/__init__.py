"""Application doctor checks.

The app layer runs generic checkers (installed, running, state, login,
permissions) and custom checkers (e.g. vscode_sync) for each app declared
in schemas.apps.ALL_APP_SPECS.
"""

from collections.abc import Iterable
from typing import Optional

from envy.doctor.checks.apps.registry import run_single_app
from envy.doctor.model import CheckResult
from envy.doctor.selection import DoctorSelection, app_keys_for_selection, parse_only


def run_checks(selected: Optional[Iterable[str]] = None, selection: DoctorSelection | None = None) -> list[CheckResult]:
    active_selection = selection or parse_only(selected)
    results: list[CheckResult] = []

    for key in app_keys_for_selection(active_selection):
        results.extend(run_single_app(key))

    return results
