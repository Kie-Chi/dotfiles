"""Generic and custom checker infrastructure for app doctor checks.

A checker is a function: (spec: AppSpec) -> list[CheckResult].
Generic checkers run for every app (skipping if not applicable).
Custom checkers are declared per-app via spec.checkers and looked up by name.
"""

from collections.abc import Callable

from envy.doctor.model import CheckResult, info, ok, warn
from envy.doctor.probes import filesystem, process, tcc
from envy.schemas.apps import AppSpec

# Checker protocol
CheckerFn = Callable[[AppSpec], list[CheckResult]]

# TCC probe cache (avoid repeated DB access and duplicate warnings)
_tcc_result: tuple[dict[tuple[str, str], int], bool] | None = None
_tcc_warned_flag = False


def _tcc_cache() -> tuple[dict[tuple[str, str], int], bool]:
    """Cached TCC probe — only hits the database once per session."""
    global _tcc_result
    if _tcc_result is None:
        _tcc_result = tcc.permission_records()
    return _tcc_result


def _tcc_already_warned() -> bool:
    """Return True if we already emitted the TCC unreadable warning (and mark it)."""
    global _tcc_warned_flag
    if _tcc_warned_flag:
        return True
    _tcc_warned_flag = True
    return False


# ==========================================
# GENERIC CHECKERS
# ==========================================


def check_installed(spec: AppSpec) -> list[CheckResult]:
    """Check if the app bundle is installed."""
    bundle = filesystem.app_bundle(spec.bundles)
    if bundle:
        return [ok("apps", spec.name, f"installed at {bundle}")]
    return [warn(
        "apps",
        spec.name,
        "app bundle not found",
        hint="Run: envy apply  # or check the Homebrew cask name",
    )]


def check_running(spec: AppSpec) -> list[CheckResult]:
    """Check if the app process is running."""
    running = process.app_running(spec.bundle_id, spec.processes)
    if running:
        return [ok("apps", f"{spec.name} running", "process is active")]
    if spec.should_run:
        return [warn(
            "apps",
            f"{spec.name} running",
            "expected background app is not running",
            hint=f"Open {spec.name} once and enable launch-at-login if needed.",
        )]
    return [info("apps", f"{spec.name} running", "not running")]


def check_state(spec: AppSpec) -> list[CheckResult]:
    """Check if expected state/config paths exist."""
    if not spec.state_paths:
        return []
    state_path = filesystem.first_existing(spec.state_paths)
    if state_path:
        return [ok("apps", f"{spec.name} state", f"found {state_path}")]
    return [warn(
        "apps",
        f"{spec.name} state",
        "expected state/config path is missing",
        hint=f"Open {spec.name} once, then rerun envy apply if the file is managed.",
    )]


def check_login(spec: AppSpec) -> list[CheckResult]:
    """Show login hint only when app is not running or state is missing."""
    if not spec.login_hint:
        return []
    # If app is running and state paths are satisfied, assume logged in
    running = process.app_running(spec.bundle_id, spec.processes)
    state_ok = (not spec.state_paths) or filesystem.first_existing(spec.state_paths)
    if running and state_ok:
        return []
    return [info(
        "apps",
        f"{spec.name} login",
        spec.login_hint,
    )]


def check_permissions(spec: AppSpec) -> list[CheckResult]:
    """Check macOS TCC permissions declared for this app."""
    if not spec.permissions:
        return []

    records, readable = _tcc_cache()
    if not readable:
        if _tcc_already_warned():
            return []
        return [warn(
            "permissions",
            "TCC database",
            "Full Disk Access required — cannot verify app permissions",
            hint="System Settings -> Privacy & Security -> Full Disk Access: enable your terminal app.",
        )]

    results: list[CheckResult] = []
    for perm in spec.permissions:
        check_name = f"{spec.name} {perm.label}"
        client = perm.tcc_client or spec.bundle_id
        value = records.get((perm.service, client))
        if value == 2:
            results.append(ok("permissions", check_name, f"allowed for {perm.reason}"))
        elif value is None:
            results.append(warn(
                "permissions",
                check_name,
                f"not yet granted — required for {perm.reason}",
                hint=f"System Settings -> Privacy & Security -> {perm.label}: enable {spec.name}.",
            ))
        else:
            results.append(warn(
                "permissions",
                check_name,
                f"permission denied (auth_value={value})",
                hint=f"System Settings -> Privacy & Security -> {perm.label}: re-enable {spec.name}.",
            ))
    return results


GENERIC_CHECKERS: list[CheckerFn] = [
    check_installed,
    check_running,
    check_state,
    check_login,
    check_permissions,
]


# ==========================================
# CUSTOM CHECKER REGISTRY
# ==========================================

# Lazy import to avoid circular dependencies at module load time
_custom_checkers_loaded = False
_CUSTOM_CHECKERS: dict[str, CheckerFn] = {}


def _load_custom_checkers() -> dict[str, CheckerFn]:
    global _custom_checkers_loaded, _CUSTOM_CHECKERS
    if not _custom_checkers_loaded:
        from envy.doctor.checks.apps import vscode as _vscode

        _CUSTOM_CHECKERS = {
            "vscode_sync": _vscode.check_sync,
            "vscode_extensions": _vscode.check_extensions,
        }
        _custom_checkers_loaded = True
    return _CUSTOM_CHECKERS


# ==========================================
# RUNNER
# ==========================================


def run_app_checks(spec: AppSpec) -> list[CheckResult]:
    """Run all applicable checkers for an app."""
    results: list[CheckResult] = []

    # Generic checkers (they skip internally if not applicable)
    for checker in GENERIC_CHECKERS:
        results.extend(checker(spec))

    # Custom checkers by name
    if spec.checkers:
        custom = _load_custom_checkers()
        for name in spec.checkers:
            fn = custom.get(name)
            if fn:
                results.extend(fn(spec))

    return results
