"""Config engine for versioned machine policy and sops secrets."""

import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from getpass import getpass
from pathlib import Path
from typing import Optional

import typer
import yaml
from rich.table import Table
from rich.text import Text

from envy import log
from envy.evaluation import machine_manifest, manifest_selection_rows, manifest_settings
from envy.schemas.config import (
    FieldDef,
    LEGACY_CONFIG_PATHS,
    MACHINE_FIELDS,
    OBSOLETE_MACHINE_KEYS,
    OBSOLETE_SECRET_PATHS,
    SECRET_FIELDS,
)
from envy.software import (
    MANAGED_START as SOFTWARE_MANAGED_START,
    SoftwarePolicyError,
    app as software_app,
    read_managed_exclusions,
)
from envy.utils import (
    AGE_KEY_FILE,
    DEVICE_LABEL_FILE,
    DOTFILES_DIR,
    LEGACY_MACHINE_SELECTOR,
    LEGACY_SYSTEM_CONFIG,
    LEGACY_USER_CONFIG,
    SECRETS_DIR,
    SECRETS_FILE,
    current_machine_id,
    device_metadata_is_toml,
    is_sops_encrypted,
    machine_config_file as versioned_machine_file,
    read_device_metadata,
    run_cmd,
    set_device_machine_id,
)


MANAGED_START = "  # BEGIN ENVY MANAGED CONFIG"
MANAGED_END = "  # END ENVY MANAGED CONFIG"


@dataclass
class RefineReport:
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    changed: bool = False

    @property
    def ok(self) -> bool:
        return not self.errors

    def extend(self, other: "RefineReport") -> None:
        self.added.extend(other.added)
        self.removed.extend(other.removed)
        self.warnings.extend(other.warnings)
        self.errors.extend(other.errors)
        self.changed = self.changed or other.changed


def _escape_nix_string(value: str) -> str:
    return str(value).replace("\\", "\\\\").replace('"', '\\"')


def _unescape_nix_string(value: str) -> str:
    return value.replace('\\"', '"').replace("\\\\", "\\")


_MISSING = object()


def _get_nested(data: dict, path: str, default=_MISSING):
    cur = data
    parts = path.split("/")
    for part in parts[:-1]:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(part, {})
    if not isinstance(cur, dict):
        return default
    if parts[-1] not in cur:
        return default
    value = cur[parts[-1]]
    return "" if value is None else str(value)


def _set_nested(data: dict, path: str, value: str) -> None:
    cur = data
    parts = path.split("/")
    for part in parts[:-1]:
        cur = cur.setdefault(part, {})
    cur[parts[-1]] = value


def _unset_nested(data: dict, path: str) -> bool:
    cur = data
    parts = path.split("/")
    parents = []
    for part in parts[:-1]:
        if not isinstance(cur, dict) or part not in cur:
            return False
        parents.append((cur, part))
        cur = cur[part]
    if not isinstance(cur, dict) or parts[-1] not in cur:
        return False
    del cur[parts[-1]]
    for parent, key in reversed(parents):
        child = parent.get(key)
        if isinstance(child, dict) and not child:
            del parent[key]
    return True


def _sops_index(yaml_path: str) -> str:
    return "".join(f"[{json.dumps(part)}]" for part in yaml_path.split("/"))


def _read_nix_assignments(path: Path) -> dict:
    values = {}
    if not path.exists():
        return values
    string_pattern = re.compile(r'^\s*([A-Za-z0-9_.-]+)\s*=\s*"((?:\\.|[^"])*)"\s*;')
    bool_pattern = re.compile(r'^\s*([A-Za-z0-9_.-]+)\s*=\s*(true|false)\s*;')
    for line in path.read_text().splitlines():
        string_match = string_pattern.match(line)
        if string_match:
            values[string_match.group(1)] = _unescape_nix_string(string_match.group(2))
            continue
        bool_match = bool_pattern.match(line)
        if bool_match:
            values[bool_match.group(1)] = bool_match.group(2)
    return values


def machine_config_file(machine_id: str | None = None) -> Path:
    return versioned_machine_file(machine_id)


def read_machine_nix(machine_id: str | None = None) -> dict:
    return _read_nix_assignments(machine_config_file(machine_id))


def read_legacy_config_nix() -> dict:
    """Read the old ignored config.nix only as an upgrade source."""
    for path in (LEGACY_USER_CONFIG, DOTFILES_DIR / "config.nix", LEGACY_SYSTEM_CONFIG):
        if path.exists():
            try:
                return _read_nix_assignments(path)
            except OSError:
                continue
    return {}


def _legacy_config_value(path: str, values: dict, legacy_values: dict) -> str:
    sources = LEGACY_CONFIG_PATHS.get(path, ())
    if isinstance(sources, str):
        sources = (sources,)
    for source in sources:
        value = values.get(source, legacy_values.get(source, ""))
        if str(value).strip():
            return value
    return ""


def _render_machine_block(values: dict) -> str:
    groups = sorted(set(f.group for f in MACHINE_FIELDS))
    lines = [MANAGED_START + "\n", "  # `envy config` updates only this block. Other machine policy stays intact.\n"]
    for group in groups:
        lines.append(f"\n  # --- {group} CONFIG ---\n")
        for f in MACHINE_FIELDS:
            if f.group != group:
                continue
            raw = str(values.get(f.path, f.default_fn()))
            if f.nix_type == "bool":
                if raw.lower() not in {"true", "false"}:
                    raise ValueError(f"{f.path} must be true or false")
                val = raw.lower()
                lines.append(f"  {f.path} = {val};\n")
            else:
                lines.append(f"  {f.path} = \"{_escape_nix_string(raw)}\";\n")
    lines.append(MANAGED_END)
    return "".join(lines)


def write_machine_nix(values: dict, machine_id: str | None = None) -> None:
    selected = machine_id or current_machine_id()
    path = machine_config_file(selected)
    if not path.exists():
        raise FileNotFoundError(f"machine configuration is missing: {path}")

    text = path.read_text()
    block = _render_machine_block(values)
    managed_pattern = re.compile(
        rf"(?ms)^{re.escape(MANAGED_START)}$.*?^{re.escape(MANAGED_END)}$"
    )
    if managed_pattern.search(text):
        updated = managed_pattern.sub(block, text, count=1)
    else:
        # Move legacy flat assignments for managed fields into the controlled
        # block while leaving imports and all other machine policy untouched.
        managed_paths = {field.path for field in MACHINE_FIELDS}
        assignment = re.compile(r"^\s*([A-Za-z0-9_.-]+)\s*=.*;\s*$")
        kept_lines = []
        for line in text.splitlines(keepends=True):
            match = assignment.match(line)
            if not match or match.group(1) not in managed_paths:
                kept_lines.append(line)
        text = "".join(kept_lines)
        closing = text.rfind("\n}")
        if closing < 0:
            raise ValueError(f"cannot locate the top-level closing brace in {path}")
        updated = text[:closing].rstrip() + "\n\n" + block + "\n" + text[closing:]

    path.write_text(updated if updated.endswith("\n") else updated + "\n")
    set_device_machine_id(selected)

def read_secrets_yaml() -> tuple[dict, bool]:
    values = {}
    data, ok = read_secrets_data()
    if data is None:
        return values, False
    if not ok and is_sops_encrypted(SECRETS_FILE):
        return values, False
    for f in SECRET_FIELDS:
        if f.yaml_path:
            value = _get_nested(data, f.yaml_path, "")
            values[f.path] = "" if value is _MISSING else value
    return values, ok


def read_secrets_data() -> tuple[dict | None, bool]:
    if not SECRETS_FILE.exists():
        return {}, False
    try:
        plain = run_cmd(["sops", "--decrypt", str(SECRETS_FILE)])
        return yaml.safe_load(plain) or {}, True
    except subprocess.CalledProcessError as exc:
        log.debug("secrets", "sops decrypt failed", stderr=(exc.stderr or "").strip())
        try:
            return yaml.safe_load(SECRETS_FILE.read_text()) or {}, False
        except Exception:
            return None, False


def write_secrets_yaml(values: dict) -> None:
    data = {}
    for f in SECRET_FIELDS:
        if f.yaml_path:
            _set_nested(data, f.yaml_path, values.get(f.path, ""))
    write_secrets_data(data)


def write_secrets_data(data: dict) -> None:
    SECRETS_DIR.mkdir(parents=True, exist_ok=True)
    backup = SECRETS_FILE.with_suffix(".yaml.bak")
    had_existing = SECRETS_FILE.exists()
    if had_existing:
        os.replace(str(SECRETS_FILE), str(backup))

    try:
        SECRETS_FILE.write_text(yaml.dump(data, default_flow_style=False, allow_unicode=True))
        from envy.key import read_sops_yaml_keys
        keys = read_sops_yaml_keys()
        age_recipients = ",".join(keys.values())
        if not age_recipients:
            raise RuntimeError("No age recipients in .sops.yaml")
        run_cmd(["sops", "--encrypt", "--in-place", "--age", age_recipients, str(SECRETS_FILE)])
    except Exception:
        log.error("secrets", "sops encryption failed; refusing to leave secrets unencrypted")
        if had_existing and backup.exists():
            os.replace(str(backup), str(SECRETS_FILE))
            log.fix("secrets", "rolled back to previous encrypted secrets.yaml")
        elif SECRETS_FILE.exists():
            SECRETS_FILE.unlink()
        raise

    if backup.exists():
        backup.unlink()


def _validate_field(field_def: FieldDef, value: str, report: RefineReport, scope: str) -> None:
    if field_def.required and not str(value).strip():
        target = field_def.yaml_path if field_def.dest == "secret" else field_def.path
        report.errors.append(target)
        log.error(scope, "required field is empty", field=target)
        if field_def.dest == "secret":
            log.hint(f"Run: envy config secret-set {target}")
        else:
            log.hint(f"Run: envy config set {target} <value>")
        return

    if field_def.choices and str(value) not in field_def.choices:
        target = field_def.yaml_path if field_def.dest == "secret" else field_def.path
        report.errors.append(target)
        log.error(scope, "value is not one of the allowed choices", field=target)
        log.hint(f"Allowed values: {', '.join(field_def.choices)}")
        return

    for validator in field_def.validators:
        err = validator(str(value))
        if err:
            target = field_def.yaml_path if field_def.dest == "secret" else field_def.path
            report.errors.append(target)
            log.error(scope, err, field=target)


def refine_device_metadata(*, write: bool = True, strict: bool = False) -> RefineReport:
    """Validate and migrate the device-local TOML identity document."""
    report = RefineReport()
    try:
        metadata = read_device_metadata()
    except (OSError, ValueError) as exc:
        report.errors.append(str(DEVICE_LABEL_FILE))
        log.error("device", str(exc))
        return report

    machine_id = metadata.get("machine_id", "")
    sops_label = metadata.get("sops_label", "")
    legacy_format = DEVICE_LABEL_FILE.exists() and not device_metadata_is_toml()
    legacy_selector = LEGACY_MACHINE_SELECTOR.exists()

    if not machine_id:
        machine_id = current_machine_id()
        if write:
            report.added.append("device.machine_id")
            log.fix("device", "added machine ID", machine=machine_id)
        else:
            report.errors.append("device.machine_id")
            log.error("device", "machine ID is missing", path=str(DEVICE_LABEL_FILE))
    if machine_id and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", machine_id):
        report.errors.append("device.machine_id")
        log.error("device", "machine ID has invalid characters", machine=machine_id)

    machine_path = machine_config_file(machine_id) if machine_id else None
    if machine_path is not None and not machine_path.exists():
        report.errors.append(str(machine_path))
        log.error("device", "selected machine configuration is missing", path=str(machine_path))
        log.hint(f"Run: envy host init {machine_id}")

    if sops_label and not re.fullmatch(r"[a-z0-9_]+", sops_label):
        if write:
            from envy.key import sanitize_label
            normalized = sanitize_label(sops_label) or "unknown"
            log.fix("device", "normalized sops label", old=sops_label, new=normalized)
            sops_label = normalized
            report.changed = True
        else:
            report.errors.append("device.sops_label")
            log.error("device", "sops label must contain only lowercase letters, digits, and underscores")

    if not sops_label and not write:
        report.errors.append("device.sops_label")
        log.error("device", "sops label is missing", path=str(DEVICE_LABEL_FILE))

    if legacy_format and not write:
        report.errors.append("device.version")
        log.error("device", "legacy one-line .device-label must be migrated to TOML")
        log.hint("Run: envy config refine")

    if legacy_selector and not write:
        report.errors.append(str(LEGACY_MACHINE_SELECTOR))
        log.error("device", "legacy machine selector still exists", path=str(LEGACY_MACHINE_SELECTOR))
        log.hint("Run: envy config refine")

    if write and report.ok:
        needs_write = legacy_format or legacy_selector or not device_metadata_is_toml()
        if needs_write or metadata.get("machine_id") != machine_id:
            set_device_machine_id(machine_id)
            report.changed = True

        from envy.key import ensure_sops_label, set_sops_label
        persisted = read_device_metadata()
        if sops_label:
            if persisted.get("sops_label") != sops_label:
                set_sops_label(sops_label)
                report.changed = True
        else:
            sops_label = ensure_sops_label()
            report.added.append("device.sops_label")
            report.changed = True

        updated = read_device_metadata()
        if updated.get("machine_id") != machine_id or updated.get("sops_label") != sops_label:
            report.errors.append(str(DEVICE_LABEL_FILE))
            log.error("device", "device metadata did not persist correctly")
        elif report.changed:
            log.ok("device", "device metadata refined", path=str(DEVICE_LABEL_FILE))
        else:
            log.ok("device", "device metadata is complete")
    elif report.ok:
        log.ok("device", "device metadata is valid")

    if strict and report.errors:
        log.error("device", "device metadata refinement blocked by invalid fields")
    return report


def refine_config(*, write: bool = True, strict: bool = False) -> RefineReport:
    report = RefineReport()
    path = machine_config_file()
    if not path.exists():
        report.errors.append(str(path))
        log.error("machine", "selected machine configuration is missing", path=str(path))
        log.hint(f"Run: envy host init {current_machine_id()}")
        return report

    values = read_machine_nix()
    original = dict(values)
    legacy_values = read_legacy_config_nix()

    for key in OBSOLETE_MACHINE_KEYS:
        if key in values:
            values.pop(key)
            report.removed.append(key)
            log.fix("machine", "removed obsolete managed field", field=key)

    for f in MACHINE_FIELDS:
        if f.path not in values:
            legacy_value = _legacy_config_value(f.path, values, legacy_values)
            values[f.path] = legacy_value if str(legacy_value).strip() else f.default_fn()
            report.added.append(f.path)
            action = "migrated legacy field" if str(legacy_value).strip() else "added missing field"
            log.fix("machine", action, field=f.path)

    for f in MACHINE_FIELDS:
        _validate_field(f, values.get(f.path, ""), report, "machine")

    needs_managed_block = MANAGED_START not in path.read_text()
    if write and (values != original or needs_managed_block):
        write_machine_nix(values)
        report.changed = True
        log.ok(
            "machine",
            "machine configuration refined",
            path=str(path),
            added=len(report.added),
            removed=len(report.removed),
        )
    elif not report.added and not report.removed:
        log.ok("machine", "managed machine fields are complete")

    if strict and report.errors:
        log.error("machine", "machine refinement blocked by invalid fields")
    return report


def refine_software_policy(*, strict: bool = False) -> RefineReport:
    """Validate the optional setup-owned machine exclusion block."""
    report = RefineReport()
    path = machine_config_file()
    try:
        values = read_managed_exclusions(path)
    except (OSError, SoftwarePolicyError) as exc:
        report.errors.append(str(path))
        log.error("software", str(exc))
        log.hint("Fix the managed exclusions block or remove it and reopen envy setup.")
        return report

    if SOFTWARE_MANAGED_START in path.read_text():
        count = sum(len(names) for names in values.values())
        log.ok("software", "managed machine exclusions are valid", excluded=count)
    if strict and report.errors:
        log.error("software", "software policy validation failed")
    return report


def refine_secrets(*, write: bool = True, strict: bool = False, prune: bool = False) -> RefineReport:
    report = RefineReport()
    data, decrypt_ok = read_secrets_data()
    if data is None:
        report.errors.append("secrets.yaml")
        log.error("secrets", "cannot read secrets.yaml")
        return report
    if SECRETS_FILE.exists() and not decrypt_ok and is_sops_encrypted(SECRETS_FILE):
        report.errors.append("secrets.yaml")
        log.error("secrets", "cannot decrypt secrets.yaml")
        log.hint(f"Expected age key file: {AGE_KEY_FILE}")
        log.hint("Run: envy key import")
        return report

    config_values = read_machine_nix()
    values = dict(config_values)
    original = yaml.dump(data, sort_keys=True)

    for f in SECRET_FIELDS:
        if f.condition and not f.condition(values):
            continue
        current = _get_nested(data, f.yaml_path)
        if current is _MISSING:
            _set_nested(data, f.yaml_path, f.default_fn())
            report.added.append(f.yaml_path)
            log.fix("secrets", "created missing secret path", key=f.yaml_path)
        current_value = _get_nested(data, f.yaml_path, "")
        values[f.path] = "" if current_value is _MISSING else current_value

    if prune:
        for path in OBSOLETE_SECRET_PATHS:
            if _unset_nested(data, path):
                report.removed.append(path)
                log.fix("secrets", "removed obsolete secret path", key=path)
    else:
        for path in OBSOLETE_SECRET_PATHS:
            if _get_nested(data, path) is not _MISSING:
                report.warnings.append(path)
                log.warn("secrets", "obsolete secret path present", key=path)
                log.hint("Run: envy config refine --prune to remove obsolete secret paths")

    for f in SECRET_FIELDS:
        if f.condition and not f.condition(values):
            continue
        _validate_field(f, values.get(f.path, ""), report, "secrets")

    changed = yaml.dump(data, sort_keys=True) != original
    if write and changed:
        write_secrets_data(data)
        report.changed = True
        log.ok("secrets", "secrets.yaml refined", added=len(report.added), removed=len(report.removed))
    elif not report.added and not report.removed:
        log.ok("secrets", "secret paths are complete")

    if strict and report.errors:
        log.error("secrets", "secret refinement blocked by invalid fields")
    return report


def refine_all(*, write: bool = True, strict: bool = False, include_secrets: bool = True,
               prune: bool = False) -> RefineReport:
    log.step("config", "checking device metadata, selected machine, and secrets")
    report = RefineReport()
    device_report = refine_device_metadata(write=write, strict=strict)
    report.extend(device_report)
    if not device_report.ok:
        if strict:
            log.error("config", "refine failed")
        return report
    report.extend(refine_config(write=write, strict=strict))
    report.extend(refine_software_policy(strict=strict))
    if include_secrets:
        report.extend(refine_secrets(write=write, strict=strict, prune=prune))
    if report.ok:
        log.ok("config", "refine completed")
    elif strict:
        log.error("config", "refine failed")
    return report


def set_config_value(path: str, value: str) -> None:
    values = read_machine_nix()
    valid_paths = {f.path for f in MACHINE_FIELDS}
    if path not in valid_paths:
        log.error("machine", "unknown managed machine field", field=path)
        log.hint("Edit the machine file directly for custom policy.")
        raise typer.BadParameter(f"unknown managed machine field: {path}")
    legacy_values = read_legacy_config_nix()
    for field in MACHINE_FIELDS:
        if field.path not in values:
            legacy_value = _legacy_config_value(field.path, values, legacy_values)
            values[field.path] = legacy_value if str(legacy_value).strip() else field.default_fn()
    values[path] = value
    field_def = next(field for field in MACHINE_FIELDS if field.path == path)
    validation = RefineReport()
    _validate_field(field_def, value, validation, "machine")
    if validation.errors:
        raise typer.BadParameter(f"invalid value for {path}")
    write_machine_nix(values)
    log.ok("machine", "machine value updated", field=path, machine=current_machine_id())


def set_secret_value(yaml_path: str, value: str) -> None:
    stdin_data = json.dumps(value)
    run_cmd(["sops", "set", "--value-stdin", str(SECRETS_FILE), _sops_index(yaml_path)], stdin_data=stdin_data)
    log.ok("secrets", "secret value updated", key=yaml_path)


app = typer.Typer(
    name="config",
    help="Validate device metadata and edit the selected machine configuration and sops secrets",
    rich_markup_mode="rich",
    no_args_is_help=True,
)
app.add_typer(software_app, name="software")


@app.command(name="check")
def cmd_check():
    """Check device metadata, the selected machine file, and secrets without writing."""
    report = refine_all(write=False, strict=False, include_secrets=True)
    if not report.ok:
        raise typer.Exit(code=1)


@app.command(name="refine")
def cmd_refine(
    prune: bool = typer.Option(False, "--prune", help="Remove known obsolete config/secret paths"),
):
    """Refine device metadata, the selected machine file, and secrets.yaml."""
    report = refine_all(write=True, strict=False, include_secrets=True, prune=prune)
    if not report.ok:
        raise typer.Exit(code=1)


@app.command(name="doctor")
def cmd_doctor():
    """Run a stricter local config and secrets diagnostic."""
    report = refine_all(write=False, strict=True, include_secrets=True)
    if not report.ok:
        raise typer.Exit(code=1)


@app.command(name="set")
def cmd_set(
    path: str = typer.Argument(..., help="Machine path, for example envy.llm.steps.url"),
    value: str = typer.Argument(..., help="Value to write"),
):
    """Set a managed non-secret value in the selected machine file."""
    set_config_value(path, value)


@app.command(name="secret-set")
def cmd_secret_set(
    yaml_path: str = typer.Argument(..., help="Secret path, for example llm/steps/apikey"),
    value: Optional[str] = typer.Argument(None, help="Secret value; prompts when omitted"),
):
    """Set a secret value via sops without printing it."""
    if value is None:
        value = getpass(f"{yaml_path}: ")
    set_secret_value(yaml_path, value)


@app.command(name="show")
def cmd_show(
    refresh: bool = typer.Option(False, "--refresh", help="Ignore the saved manifest cache"),
    details: bool = typer.Option(
        False, "--details", "-d", help="Show complete software include/exclude/effective lists"
    ),
):
    """Show the evaluated machine, its software policy, and secret status."""
    manifest = machine_manifest(refresh=refresh)
    evaluated_values = manifest_settings(manifest)
    config_values = evaluated_values or read_machine_nix()
    table = Table(title="envy config (evaluated)" if evaluated_values else "envy config (source fallback)")
    table.add_column("Kind")
    table.add_column("Path")
    table.add_column("Value")

    device_values = read_device_metadata()
    table.add_row("device", "device.machine_id", device_values.get("machine_id", ""))
    table.add_row("device", "device.sops_label", device_values.get("sops_label", ""))

    for f in MACHINE_FIELDS:
        table.add_row("value", f.path, config_values.get(f.path, ""))

    if manifest:
        for path, include, exclude, effective in manifest_selection_rows(manifest):
            if details:
                table.add_row("include", f"{path}.include", _format_list(include))
            if details or exclude:
                table.add_row("exclude", f"{path}.exclude", _format_list(exclude))
            if details:
                table.add_row("effective", f"{path}.effective", _format_list(effective))
    else:
        log.warn(
            "config",
            "Nix evaluation failed; showing direct machine assignments without imported defaults",
        )

    secret_values, _ = read_secrets_yaml()
    for f in SECRET_FIELDS:
        value = secret_values.get(f.path, "")
        status = "<set>" if value else "<empty>"
        table.add_row("secret", f.yaml_path, status)

    log.console.print(table)


def _format_list(values: list[str]) -> Text:
    # A plain Text renderable prevents Rich from treating package names inside
    # square brackets as markup tags.
    return Text("[" + ", ".join(values) + "]")


@app.command(name="edit")
def cmd_edit():
    """Open the selected versioned machine file in $EDITOR."""
    path = machine_config_file()
    if not path.exists():
        log.error("machine", "selected machine configuration is missing", path=str(path))
        raise typer.Exit(code=1)
    editor = os.environ.get("EDITOR", "vim")
    subprocess.run([editor, str(path)], check=False)
