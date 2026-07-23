"""Authentication and account-state checkers for apps.

These checks intentionally inspect only local marker presence and command
status. They must not print account names, emails, API keys, or tokens.
"""

import json
import os
from pathlib import Path
from typing import Any

from envy.doctor.model import (
    SECTION_AUTH,
    SECTION_INSTALL,
    SECTION_STATE,
    SECTION_SYNC,
    CheckResult,
    info,
    ok,
    warn,
)
from envy.doctor.probes import command, filesystem
from envy.schemas.apps import AppSpec
from envy.utils import HOME_DIR, platform_name


CHROME_ROOT = (
    HOME_DIR / "Library/Application Support/Google/Chrome"
    if platform_name() == "darwin"
    else HOME_DIR / ".config/google-chrome"
)
CODEX_AUTH = HOME_DIR / ".codex/auth.json"


def check_chrome_account(spec: AppSpec) -> list[CheckResult]:
    """Check whether Chrome has at least one signed-in local profile marker."""
    local_state = _read_dict(CHROME_ROOT / "Local State")
    profiles = _chrome_profile_preferences(local_state)
    if not profiles:
        return [warn(
            SECTION_STATE,
            f"{spec.name} profile state",
            "Chrome profile preferences are missing",
            hint="Open Chrome once, sign in from the profile avatar, then rerun envy doctor apps --only chrome.",
        )]

    signed_in = 0
    sync_ready = 0
    signin_disabled = 0
    for profile_name, pref_path in profiles:
        prefs = _read_dict(pref_path)
        if not prefs:
            continue
        if _chrome_signin_disabled(prefs):
            signin_disabled += 1
        if _chrome_pref_has_account(prefs) or _chrome_local_state_has_account(local_state, profile_name):
            signed_in += 1
        if _chrome_sync_ready(prefs):
            sync_ready += 1

    if signed_in == 0:
        if signin_disabled:
            return [warn(
                SECTION_AUTH,
                f"{spec.name} account",
                "Chrome sign-in appears disabled and no signed-in profile marker was found",
                hint="Open Chrome settings and re-enable browser sign-in if this machine should use a Google account.",
            )]
        return [warn(
            SECTION_AUTH,
            f"{spec.name} account",
            "no signed-in Chrome profile marker found",
            hint="Open Chrome -> profile avatar -> sign in or turn on sync.",
        )]

    results: list[CheckResult] = [
        ok(SECTION_AUTH, f"{spec.name} account", f"signed-in marker found in {signed_in} profile(s)"),
    ]
    if sync_ready:
        results.append(ok(SECTION_SYNC, f"{spec.name} sync", f"sync marker found in {sync_ready} profile(s)"))
    else:
        results.append(info(
            SECTION_SYNC,
            f"{spec.name} sync",
            "signed-in profile found, but no Chrome sync completion marker was found",
            hint="Turn on Chrome Sync if bookmarks, passwords, and settings should follow this machine.",
        ))
    return results


def check_tailscale_auth(spec: AppSpec) -> list[CheckResult]:
    """Check Tailscale authentication via the CLI status API."""
    if not command.exists("tailscale"):
        return [warn(
            SECTION_INSTALL,
            f"{spec.name} commands",
            "tailscale command not found; cannot verify node authentication",
            hint="Run: envy apply  # tailscale-app should install the CLI helper",
        )]

    result = command.run(["tailscale", "status", "--json"], timeout=3)
    if result.returncode == 124:
        return [warn(
            SECTION_AUTH,
            f"{spec.name} auth",
            "could not verify auth: tailscale status timed out",
            hint="Open Tailscale, confirm the VPN service is responsive, then rerun envy doctor apps --only tailscale.",
        )]
    if result.returncode != 0:
        return [warn(
            SECTION_AUTH,
            f"{spec.name} auth",
            "could not verify auth: could not read tailscale status",
            hint="Run: tailscale status  # or open Tailscale and sign in",
        )]

    try:
        state = json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        return [warn(
            SECTION_AUTH,
            f"{spec.name} auth",
            "could not verify auth: tailscale status returned invalid JSON",
            hint="Run: tailscale status  # confirm the CLI is healthy",
        )]

    backend = state.get("BackendState")
    if backend == "Running" and state.get("Self"):
        return [ok(SECTION_AUTH, f"{spec.name} auth", "node is authenticated")]
    if backend == "NeedsLogin":
        return [warn(
            SECTION_AUTH,
            f"{spec.name} auth",
            "node is not authenticated",
            hint="Run: tailscale login  # or open Tailscale and sign in",
        )]
    if backend == "Running":
        return [warn(
            SECTION_AUTH,
            f"{spec.name} auth",
            "backend is running, but node identity is missing",
            hint="Run: tailscale status  # or open Tailscale and sign in",
        )]
    return [warn(
        SECTION_AUTH,
        f"{spec.name} auth",
        f"could not verify auth: backend state is {backend or 'unknown'}",
        hint="Open Tailscale and confirm the backend service is running, then sign in if needed.",
    )]


def check_codex_auth(spec: AppSpec) -> list[CheckResult]:
    """Check whether Codex has a usable local authentication marker."""
    if os.environ.get("OPENAI_API_KEY"):
        return [ok(SECTION_AUTH, f"{spec.name} auth", "OPENAI_API_KEY is set in the current environment")]

    if not CODEX_AUTH.exists():
        return [warn(
            SECTION_AUTH,
            f"{spec.name} auth",
            "Codex auth file is missing",
            hint="Run: codex login  # or configure OPENAI_API_KEY for API-key auth",
        )]

    auth = _read_dict(CODEX_AUTH)
    if _codex_has_auth_marker(auth):
        return [ok(SECTION_AUTH, f"{spec.name} auth", "local Codex auth marker is present")]

    return [warn(
        SECTION_AUTH,
        f"{spec.name} auth",
        "Codex auth file has no known auth marker",
        hint="Run: codex login  # or refresh the Codex desktop login",
    )]


def check_github_cli_auth(spec: AppSpec) -> list[CheckResult]:
    """Check GitHub CLI authentication without printing account details."""
    if not command.exists("gh"):
        return []

    result = command.run(["gh", "auth", "status"], timeout=5)
    if result.returncode == 0:
        return [ok(SECTION_AUTH, f"{spec.name} auth", "GitHub CLI authentication is available")]
    if result.returncode == 124:
        return [warn(
            SECTION_AUTH,
            f"{spec.name} auth",
            "gh auth status timed out",
            hint="Run: gh auth status  # then rerun envy doctor apps --only gh",
        )]
    return [warn(
        SECTION_AUTH,
        f"{spec.name} auth",
        "GitHub CLI is not authenticated",
        hint="Run: gh auth login",
    )]


def check_lark_cli_auth(spec: AppSpec) -> list[CheckResult]:
    """Check Lark CLI configuration and identity state without printing account details."""
    if not command.exists("lark-cli"):
        return []

    config_result = command.run(["lark-cli", "config", "show"], timeout=5)
    config_data = _parse_command_json(config_result)
    if config_result.returncode == 124:
        return [warn(
            SECTION_STATE,
            f"{spec.name} config",
            "lark-cli config check timed out",
            hint="Run: lark-cli config show  # then rerun envy doctor apps --only lark-cli",
        )]
    if config_result.returncode != 0:
        return [_lark_cli_config_warning(spec, config_data)]
    if not _truthy(config_data.get("appId")):
        return [warn(
            SECTION_STATE,
            f"{spec.name} config",
            "active app configuration is missing or incomplete",
            hint="Run: lark-cli config init --new",
        )]

    results: list[CheckResult] = [
        ok(SECTION_STATE, f"{spec.name} config", "active app configuration is present"),
    ]

    auth_result = command.run(["lark-cli", "auth", "status"], timeout=5)
    auth_data = _parse_command_json(auth_result)
    if auth_result.returncode == 124:
        results.append(warn(
            SECTION_AUTH,
            f"{spec.name} auth",
            "lark-cli auth status timed out",
            hint="Run: lark-cli auth status  # then rerun envy doctor apps --only lark-cli",
        ))
        return results
    if auth_result.returncode != 0:
        results.append(_lark_cli_auth_warning(spec, auth_data))
        return results

    identity = str(auth_data.get("identity") or "none")
    if identity in {"user", "bot"}:
        results.append(ok(SECTION_AUTH, f"{spec.name} auth", f"usable {identity} identity is available"))
        return results

    results.append(warn(
        SECTION_AUTH,
        f"{spec.name} auth",
        "no usable identity is available",
        hint="Run: lark-cli auth login  # or configure bot credentials for bot-only API calls",
    ))
    return results


def _read_dict(path: Path) -> dict[str, Any]:
    value = filesystem.read_json(path)
    if isinstance(value, dict):
        return value
    return {}


def _parse_json_object(text: str) -> dict[str, Any]:
    try:
        value = json.loads(text or "{}")
    except json.JSONDecodeError:
        return {}
    if isinstance(value, dict):
        return value
    return {}


def _parse_command_json(result: Any) -> dict[str, Any]:
    for text in (getattr(result, "stdout", ""), getattr(result, "stderr", "")):
        data = _parse_json_object(text)
        if data:
            return data
    return {}


def _lark_cli_config_warning(spec: AppSpec, data: dict[str, Any]) -> CheckResult:
    if _typed_error(data) == ("config", "not_configured"):
        return warn(
            SECTION_STATE,
            f"{spec.name} config",
            "lark-cli is not configured",
            hint="Run: lark-cli config init --new",
        )
    return warn(
        SECTION_STATE,
        f"{spec.name} config",
        "could not read lark-cli configuration",
        hint="Run: lark-cli config show",
    )


def _lark_cli_auth_warning(spec: AppSpec, data: dict[str, Any]) -> CheckResult:
    if _typed_error(data) == ("config", "not_configured"):
        return warn(
            SECTION_AUTH,
            f"{spec.name} auth",
            "cannot check auth before lark-cli is configured",
            hint="Run: lark-cli config init --new",
        )
    return warn(
        SECTION_AUTH,
        f"{spec.name} auth",
        "could not read lark-cli auth status",
        hint="Run: lark-cli auth status  # or refresh with lark-cli auth login",
    )


def _typed_error(data: dict[str, Any]) -> tuple[str, str]:
    error = data.get("error")
    if not isinstance(error, dict):
        return ("", "")
    return (str(error.get("type") or ""), str(error.get("subtype") or ""))


def _chrome_profile_preferences(local_state: dict[str, Any]) -> list[tuple[str, Path]]:
    names: list[str] = []
    profile = local_state.get("profile")
    if isinstance(profile, dict):
        for key in ("profiles_order", "last_active_profiles"):
            value = profile.get(key)
            if isinstance(value, list):
                names.extend(str(item) for item in value)
        info_cache = profile.get("info_cache")
        if isinstance(info_cache, dict):
            names.extend(str(name) for name in info_cache)

    names.append("Default")

    seen: set[str] = set()
    profiles: list[tuple[str, Path]] = []
    for name in names:
        if name in seen:
            continue
        seen.add(name)
        pref_path = CHROME_ROOT / name / "Preferences"
        if pref_path.exists():
            profiles.append((name, pref_path))

    for pref_path in CHROME_ROOT.glob("*/Preferences"):
        name = pref_path.parent.name
        if name in seen or name in {"Guest Profile", "System Profile"}:
            continue
        profiles.append((name, pref_path))
        seen.add(name)

    return profiles


def _chrome_pref_has_account(prefs: dict[str, Any]) -> bool:
    account_info = prefs.get("account_info")
    if isinstance(account_info, list) and len(account_info) > 0:
        return True

    sync = prefs.get("sync")
    if isinstance(sync, dict):
        if _truthy(sync.get("gaia_id")):
            return True
        transport = sync.get("transport_data_per_account")
        if isinstance(transport, dict) and len(transport) > 0:
            return True

    return False


def _chrome_local_state_has_account(local_state: dict[str, Any], profile_name: str) -> bool:
    profile = local_state.get("profile")
    if not isinstance(profile, dict):
        return False
    info_cache = profile.get("info_cache")
    if not isinstance(info_cache, dict):
        return False
    metadata = info_cache.get(profile_name)
    if not isinstance(metadata, dict):
        return False

    return (
        _truthy(metadata.get("gaia_id"))
        or _truthy(metadata.get("user_name"))
        or metadata.get("is_consented_primary_account") is True
    )


def _chrome_sync_ready(prefs: dict[str, Any]) -> bool:
    sync = prefs.get("sync")
    if not isinstance(sync, dict):
        return False
    if sync.get("has_setup_completed") is True:
        return True
    if _truthy(sync.get("last_synced_time")):
        return True
    transport = sync.get("transport_data_per_account")
    return isinstance(transport, dict) and len(transport) > 0


def _chrome_signin_disabled(prefs: dict[str, Any]) -> bool:
    signin = prefs.get("signin")
    return isinstance(signin, dict) and signin.get("allowed") is False


def _codex_has_auth_marker(auth: dict[str, Any]) -> bool:
    if _truthy(auth.get("OPENAI_API_KEY")):
        return True
    if _truthy(auth.get("access_token")) or _truthy(auth.get("refresh_token")):
        return True
    tokens = auth.get("tokens")
    return isinstance(tokens, dict) and any(_truthy(value) for value in tokens.values())


def _truthy(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return bool(value)
