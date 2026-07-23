"""App check registry — built automatically from ALL_APP_SPECS."""

from envy.doctor.checks.apps.checkers import run_app_checks
from envy.doctor.model import CheckResult
from envy.schemas.apps import ALL_APP_SPECS, APP_ALIASES


def run_single_app(key: str) -> list[CheckResult]:
    """Run all checkers for a single app by key."""
    results = run_app_checks(ALL_APP_SPECS[key])
    for result in results:
        result.details.setdefault("app", key)
    return results


def normalize_app_key(value: str) -> str:
    """Normalize user input to a canonical app key."""
    key = value.strip().lower().replace("_", "-")
    return APP_ALIASES.get(key, key)


def available_apps() -> list[str]:
    """Return sorted list of all known app keys."""
    return sorted(ALL_APP_SPECS)
