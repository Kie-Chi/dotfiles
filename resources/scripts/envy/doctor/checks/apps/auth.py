"""Authentication and account-state checkers for apps.

These checks intentionally inspect only local marker presence and command
status. They must not print account names, emails, API keys, or tokens.
"""

import json
import os
from pathlib import Path
from typing import Any

from envy.doctor.model import CheckResult, info, ok, warn
from envy.doctor.probes import command, filesystem
from envy.schemas.apps import AppSpec
from envy.utils import HOME_DIR


CHROME_ROOT = HOME_DIR / "Library/Application Support/Google/Chrome"
CODEX_AUTH = HOME_DIR / ".codex/auth.json"


def check_chrome_account(spec: AppSpec) -> list[CheckResult]:
    """Check whether Chrome has at least one signed-in local profile marker."""
    local_state = _read_dict(CHROME_ROOT / "Local State")
    profiles = _chrome_profile_preferences(local_state)
    if not profiles:
        return [warn(
            "apps",
            f"{spec.name} account",
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
                "apps",
                f"{spec.name} account",
                "Chrome sign-in appears disabled and no signed-in profile marker was found",
                hint="Open Chrome settings and re-enable browser sign-in if this machine should use a Google account.",
            )]
        return [warn(
            "apps",
            f"{spec.name} account",
            "no signed-in Chrome profile marker found",
            hint="Open Chrome -> profile avatar -> sign in or turn on sync.",
        )]

    results: list[CheckResult] = [
        ok("apps", f"{spec.name} account", f"signed-in marker found in {signed_in} profile(s)"),
    ]
    if sync_ready:
        results.append(ok("apps", f"{spec.name} sync", f"sync marker found in {sync_ready} profile(s)"))
    else:
        results.append(info(
            "apps",
            f"{spec.name} sync",
            "signed-in profile found, but no Chrome sync completion marker was found",
            hint="Turn on Chrome Sync if bookmarks, passwords, and settings should follow this machine.",
        ))
    return results


def check_tailscale_auth(spec: AppSpec) -> list[CheckResult]:
    """Check Tailscale authentication via the CLI status API."""
    if not command.exists("tailscale"):
        return [warn(
            "apps",
            f"{spec.name} auth",
            "tailscale command not found; cannot verify node authentication",
            hint="Run: envy apply  # tailscale-app should install the CLI helper",
        )]

    result = command.run(["tailscale", "status", "--json"], timeout=3)
    if result.returncode == 124:
        return [warn(
            "apps",
            f"{spec.name} auth",
            "tailscale status timed out",
            hint="Open Tailscale, confirm the VPN service is responsive, then rerun envy doctor apps --only tailscale.",
        )]
    if result.returncode != 0:
        return [warn(
            "apps",
            f"{spec.name} auth",
            "could not read tailscale status",
            hint="Run: tailscale status  # or open Tailscale and sign in",
        )]

    try:
        state = json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        return [warn(
            "apps",
            f"{spec.name} auth",
            "tailscale status returned invalid JSON",
            hint="Run: tailscale status  # confirm the CLI is healthy",
        )]

    backend = state.get("BackendState")
    if backend == "Running" and state.get("Self"):
        return [ok("apps", f"{spec.name} auth", "node is authenticated and backend is running")]
    if backend == "NeedsLogin":
        return [warn(
            "apps",
            f"{spec.name} auth",
            "node is not authenticated",
            hint="Run: tailscale login  # or open Tailscale and sign in",
        )]
    return [warn(
        "apps",
        f"{spec.name} auth",
        f"backend state is {backend or 'unknown'}",
        hint="Open Tailscale and confirm the node is signed in and connected.",
    )]


def check_codex_auth(spec: AppSpec) -> list[CheckResult]:
    """Check whether Codex has a usable local authentication marker."""
    if os.environ.get("OPENAI_API_KEY"):
        return [ok("apps", f"{spec.name} auth", "OPENAI_API_KEY is set in the current environment")]

    if not CODEX_AUTH.exists():
        return [warn(
            "apps",
            f"{spec.name} auth",
            "Codex auth file is missing",
            hint="Run: codex login  # or configure OPENAI_API_KEY for API-key auth",
        )]

    auth = _read_dict(CODEX_AUTH)
    if _codex_has_auth_marker(auth):
        return [ok("apps", f"{spec.name} auth", "local Codex auth marker is present")]

    return [warn(
        "apps",
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
        return [ok("apps", f"{spec.name} auth", "GitHub CLI authentication is available")]
    if result.returncode == 124:
        return [warn(
            "apps",
            f"{spec.name} auth",
            "gh auth status timed out",
            hint="Run: gh auth status  # then rerun envy doctor apps --only gh",
        )]
    return [warn(
        "apps",
        f"{spec.name} auth",
        "GitHub CLI is not authenticated",
        hint="Run: gh auth login",
    )]


def _read_dict(path: Path) -> dict[str, Any]:
    value = filesystem.read_json(path)
    if isinstance(value, dict):
        return value
    return {}


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
