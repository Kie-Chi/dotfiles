"""Dotfiles machine policy and sops checks."""

from pathlib import Path

from envy import _source_info
from envy.config import machine_config_file, read_machine_nix, read_secrets_data
from envy.evaluation import machine_manifest, manifest_settings
from envy.git_safety import (
    SecretSafetyError,
    assert_head_secret_encrypted,
    assert_index_secret_encrypted,
    assert_worktree_secret_encrypted,
)
from envy.schemas.config import MACHINE_FIELDS, SECRET_FIELDS
from envy.software import (
    SoftwarePolicyError,
    groups_for_manifest,
    read_managed_policy,
)
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
    AGE_KEY_DIR,
    DEVICE_LABEL_FILE,
    DOTFILES_DIR,
    SECRETS_FILE,
    device_metadata_is_toml,
    is_sops_encrypted,
    read_device_metadata,
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

    manifest = machine_manifest()
    values = manifest_settings(manifest) or read_machine_nix()
    results.extend(_check_fields(MACHINE_FIELDS, values, SECTION_CONFIG))
    if manifest is None:
        results.append(error(
            SECTION_CONFIG,
            "machine manifest",
            "selected machine manifest cannot be evaluated",
            hint="Run: envy host check",
        ))
    else:
        results.append(ok(SECTION_CONFIG, "machine manifest", "Nix evaluation succeeded"))

    try:
        read_managed_policy(
            config_path,
            groups_for_manifest(manifest, include_empty=True),
        )
        results.append(ok(SECTION_CONFIG, "software policy", "managed include/exclude assignments are valid"))
    except SoftwarePolicyError as exc:
        results.append(error(
            SECTION_CONFIG,
            "software policy",
            str(exc),
            hint="Fix the ENVY MANAGED SOFTWARE block or reopen envy setup.",
        ))

    results.extend(_check_secrets(values))
    return results


def _check_fields(fields, values: dict[str, str], section) -> list[CheckResult]:
    results: list[CheckResult] = []
    for field in fields:
        if field.condition and not field.condition(values):
            continue
        key = field.yaml_path if field.dest == "secret" else field.path
        value = str(values.get(field.path, ""))
        problems: list[str] = []
        if field.required and not value.strip():
            problems.append("required value is empty")
        if field.choices and value not in field.choices:
            problems.append("allowed values: " + ", ".join(field.choices))
        for validator in field.validators:
            validation = validator(value)
            if validation:
                problems.append(validation)
        if problems:
            results.append(error(section, key, "; ".join(dict.fromkeys(problems))))
        else:
            results.append(ok(section, key, "valid"))
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


def _check_secrets(machine_values: dict[str, str]) -> list[CheckResult]:
    results: list[CheckResult] = []

    if AGE_KEY_FILE.exists():
        results.append(ok(SECTION_SECRETS, "age key", f"found {AGE_KEY_FILE}"))
        results.extend(_check_private_permissions())
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
        secret_values = dict(machine_values)
        for field in SECRET_FIELDS:
            current = data
            for part in field.yaml_path.split("/"):
                current = current.get(part, {}) if isinstance(current, dict) else {}
            secret_values[field.path] = "" if isinstance(current, dict) else str(current or "")
        results.extend(_check_fields(SECRET_FIELDS, secret_values, SECTION_SECRETS))
    else:
        results.append(error(
            SECTION_SECRETS,
            "decrypt",
            "sops decrypt failed",
            hint=f"Check age key at {AGE_KEY_FILE}",
        ))

    try:
        assert_worktree_secret_encrypted()
        assert_index_secret_encrypted()
        assert_head_secret_encrypted()
        results.append(ok(
            SECTION_SECRETS,
            "Git safety",
            "worktree, index, and HEAD contain encrypted secrets",
        ))
    except SecretSafetyError as exc:
        results.append(error(
            SECTION_SECRETS,
            "Git safety",
            str(exc),
            hint="Encrypt secrets.yaml before any commit or push.",
        ))

    return results


def _check_private_permissions() -> list[CheckResult]:
    results: list[CheckResult] = []
    paths = [AGE_KEY_FILE, *AGE_KEY_FILE.parent.glob(AGE_KEY_FILE.name + ".bak*")]
    directory_mode = AGE_KEY_DIR.stat().st_mode & 0o777 if AGE_KEY_DIR.exists() else 0
    if directory_mode == 0o700:
        results.append(ok(SECTION_SECRETS, "age directory permissions", "0700"))
    else:
        results.append(error(
            SECTION_SECRETS,
            "age directory permissions",
            f"expected 0700, found {directory_mode:04o}",
            hint="Run: envy config refine",
        ))
    for path in paths:
        mode = path.stat().st_mode & 0o777
        if mode == 0o600:
            results.append(ok(SECTION_SECRETS, path.name + " permissions", "0600"))
        else:
            results.append(error(
                SECTION_SECRETS,
                path.name + " permissions",
                f"expected 0600, found {mode:04o}",
                hint="Run: envy config refine",
            ))
    return results
