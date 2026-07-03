"""Dotfiles, config.nix, and sops checks."""

from pathlib import Path

from envy import _source_info
from envy.config import read_config_nix, read_secrets_data
from envy.doctor.model import (
    SECTION_CONFIG,
    SECTION_DOCTOR,
    SECTION_SECRETS,
    CheckResult,
    error,
    info,
    ok,
    warn,
)
from envy.schemas import __version__ as envy_version, CONFIG_SCHEMA_VERSION
from envy.utils import AGE_KEY_FILE, DOTFILES_DIR, SECRETS_FILE, USER_CONFIG, is_sops_encrypted

CONFIG_FILE = DOTFILES_DIR / "config.nix"


def run_checks() -> list[CheckResult]:
    results: list[CheckResult] = []

    # Source and version info
    results.extend(_check_source())

    config_path = USER_CONFIG if USER_CONFIG.exists() else CONFIG_FILE
    if config_path.exists():
        results.append(ok(SECTION_CONFIG, "config.nix", f"found {config_path}"))
    else:
        results.append(error(
            SECTION_CONFIG,
            "config.nix",
            "config.nix is missing",
            hint="Run: envy config refine",
        ))
        return results

    values = read_config_nix()
    vscode_mode = values.get("vscode.mode", "remote")
    if vscode_mode in {"remote", "local"}:
        results.append(ok(SECTION_CONFIG, "vscode.mode", f"mode={vscode_mode}"))
    else:
        results.append(error(
            SECTION_CONFIG,
            "vscode.mode",
            f"invalid mode={vscode_mode}",
            hint="Run: envy config set vscode.mode remote  # or local",
        ))

    proxy_status = values.get("proxy.status", "none")
    if proxy_status in {"none", "manual", "keep"}:
        results.append(info(SECTION_CONFIG, "proxy.status", f"mode={proxy_status}"))
    else:
        results.append(error(
            SECTION_CONFIG,
            "proxy.status",
            f"invalid mode={proxy_status}",
            hint="Run: envy config set proxy.status none  # or manual/keep",
        ))

    results.extend(_check_secrets())
    return results


def _check_source() -> list[CheckResult]:
    """Check envy source location and version info."""
    results: list[CheckResult] = []
    source = _source_info()

    results.append(info(SECTION_DOCTOR, "envy version", f"v{envy_version} (schema={CONFIG_SCHEMA_VERSION})"))
    results.append(info(SECTION_DOCTOR, "envy source", source["source_dir"]))

    if source["in_nix_store"]:
        repo_source = DOTFILES_DIR / "resources" / "scripts" / "envy"
        if repo_source.exists():
            results.append(warn(
                SECTION_DOCTOR,
                "source priority",
                "using bundled Nix store source while repo source exists",
                hint="Use ./envy or unset ENVY_USE_BUNDLED to prefer repo source.",
            ))

    return results


def _check_secrets() -> list[CheckResult]:
    results: list[CheckResult] = []

    if AGE_KEY_FILE.exists():
        results.append(ok(SECTION_SECRETS, "age key", f"found {AGE_KEY_FILE}"))
    else:
        results.append(error(
            SECTION_SECRETS,
            "age key",
            "age key is missing",
            hint="Run: envy key import",
        ))

    if not Path(SECRETS_FILE).exists():
        results.append(error(
            SECTION_SECRETS,
            "secrets.yaml",
            "secrets file is missing",
            hint="Run: envy config refine",
        ))
        return results

    if is_sops_encrypted(SECRETS_FILE):
        results.append(ok(SECTION_SECRETS, "secrets.yaml", "file is sops-encrypted"))
    else:
        results.append(error(
            SECTION_SECRETS,
            "secrets.yaml",
            "file is not encrypted",
            hint="Encrypt it with setup.py or sops before applying the system",
        ))

    data, decrypt_ok = read_secrets_data()
    if data is not None and decrypt_ok:
        results.append(ok(SECTION_SECRETS, "decrypt", "sops decrypt succeeded"))
    else:
        results.append(error(
            SECTION_SECRETS,
            "decrypt",
            "sops decrypt failed",
            hint=f"Check age key at {AGE_KEY_FILE}",
        ))

    return results
