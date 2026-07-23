"""Dotfiles machine policy and sops checks."""

from pathlib import Path

from envy import _source_info
from envy.config import machine_config_file, read_machine_nix, read_secrets_data
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
from envy.utils import (
    AGE_KEY_FILE,
    DEVICE_LABEL_FILE,
    DOTFILES_DIR,
    SECRETS_FILE,
    device_metadata_is_toml,
    is_sops_encrypted,
    read_device_metadata,
    platform_name,
)


def run_checks() -> list[CheckResult]:
    results: list[CheckResult] = []

    # Source and version info
    results.extend(_check_source())

    try:
        metadata = read_device_metadata()
    except (OSError, ValueError) as exc:
        results.append(error(
            SECTION_CONFIG,
            "device metadata",
            str(exc),
            hint="Fix .device-label or run: envy config refine",
        ))
        return results

    if not device_metadata_is_toml():
        results.append(error(
            SECTION_CONFIG,
            "device metadata",
            ".device-label is missing or uses the legacy one-line format",
            hint="Run: envy config refine",
        ))
        return results
    if not metadata.get("machine_id") or not metadata.get("sops_label"):
        results.append(error(
            SECTION_CONFIG,
            "device metadata",
            "device.machine_id or device.sops_label is missing",
            hint="Run: envy config refine",
        ))
        return results
    results.append(ok(SECTION_CONFIG, "device metadata", f"found {DEVICE_LABEL_FILE}"))

    config_path = machine_config_file()
    if config_path.exists():
        results.append(ok(SECTION_CONFIG, "machine file", f"found {config_path}"))
    else:
        results.append(error(
            SECTION_CONFIG,
            "machine file",
            "selected machine configuration is missing",
            hint="Run: envy host init",
        ))
        return results

    values = read_machine_nix()
    vscode_mode = values.get("envy.vscode.mode", "remote")
    if vscode_mode in {"remote", "local"}:
        results.append(ok(SECTION_CONFIG, "envy.vscode.mode", f"mode={vscode_mode}"))
    else:
        results.append(error(
            SECTION_CONFIG,
            "envy.vscode.mode",
            f"invalid mode={vscode_mode}",
            hint="Run: envy config set envy.vscode.mode remote  # or local",
        ))

    if platform_name() == "darwin":
        proxy_path = "envy.darwin.proxy.mode"
        proxy_status = values.get(proxy_path, "none")
        if proxy_status in {"none", "manual", "keep"}:
            results.append(info(SECTION_CONFIG, proxy_path, f"mode={proxy_status}"))
        else:
            results.append(error(
                SECTION_CONFIG,
                proxy_path,
                f"invalid mode={proxy_status}",
                hint=f"Run: envy config set {proxy_path} none  # or manual/keep",
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
