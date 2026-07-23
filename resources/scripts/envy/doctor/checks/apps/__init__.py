"""Application doctor checks.

The app layer runs generic checkers (installed, running, state, login,
permissions) and custom checkers (e.g. vscode_sync) for each app declared
in schemas.apps.ALL_APP_SPECS.
"""

from collections.abc import Iterable
from typing import Optional

from envy.doctor.checks.apps.registry import run_single_app
from envy.doctor.model import SECTION_INSTALL, CheckResult, info
from envy.doctor.policy import app_policy, machine_manifest
from envy.doctor.selection import DoctorSelection, app_keys_for_selection, parse_only
from envy.schemas.apps import ALL_APP_SPECS


def run_checks(selected: Optional[Iterable[str]] = None, selection: DoctorSelection | None = None) -> list[CheckResult]:
    active_selection = selection or parse_only(selected)
    results: list[CheckResult] = []

    for key in app_keys_for_selection(active_selection):
        enabled, reason = app_policy(ALL_APP_SPECS[key])
        if not enabled:
            result = info(
                SECTION_INSTALL,
                ALL_APP_SPECS[key].name,
                f"disabled for machine {(machine_manifest() or {}).get('id', 'current')}: {reason}",
            )
            result.details["app"] = key
            results.append(result)
            continue
        results.extend(run_single_app(key))

    return results
