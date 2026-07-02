"""Config engine — read, write, validate, and refine config.nix and sops secrets."""

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

from envy import log
from envy.schemas.config import (
    ALL_FIELDS,
    CONFIG_FIELDS,
    FieldDef,
    OBSOLETE_CONFIG_KEYS,
    OBSOLETE_SECRET_PATHS,
    SECRET_FIELDS,
)
from envy.utils import (
    AGE_KEY_FILE,
    DOTFILES_DIR,
    HOME_DIR,
    SECRETS_DIR,
    SECRETS_FILE,
    USER_CONFIG,
    backup_sensitive_file,
    is_sops_encrypted,
    run_cmd,
)


CONFIG_FILE = DOTFILES_DIR / "config.nix"


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


def read_config_nix() -> dict:
    values = {}
    path = USER_CONFIG if USER_CONFIG.exists() else CONFIG_FILE
    if not path.exists():
        return values
    pattern = re.compile(r'^\s*([A-Za-z0-9_.-]+)\s*=\s*"((?:\\.|[^"])*)"\s*;')
    for line in path.read_text().splitlines():
        match = pattern.match(line)
        if match:
            values[match.group(1)] = _unescape_nix_string(match.group(2))
    return values


def write_config_nix(values: dict) -> None:
    groups = sorted(set(f.group for f in CONFIG_FIELDS))
    lines = ["{\n"]
    for group in groups:
        lines.append(f"\n  # --- {group} CONFIG ---\n")
        for f in CONFIG_FIELDS:
            if f.group != group:
                continue
            val = _escape_nix_string(values.get(f.path, ""))
            lines.append(f"  {f.path} = \"{val}\";\n")
    lines.append("}\n")

    CONFIG_FILE.write_text("".join(lines))
    ensure_config_link()


def ensure_config_link() -> None:
    target_dir = USER_CONFIG.parent
    target_dir.mkdir(parents=True, exist_ok=True)
    if USER_CONFIG.is_symlink() and USER_CONFIG.resolve() == CONFIG_FILE:
        return
    if USER_CONFIG.exists() or USER_CONFIG.is_symlink():
        backup_sensitive_file(USER_CONFIG)
        USER_CONFIG.unlink()
    USER_CONFIG.symlink_to(CONFIG_FILE)
    log.fix("config", "linked user config", path=str(USER_CONFIG))


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

    for validator in field_def.validators:
        err = validator(str(value))
        if err:
            target = field_def.yaml_path if field_def.dest == "secret" else field_def.path
            report.errors.append(target)
            log.error(scope, err, field=target)


def refine_config(*, write: bool = True, strict: bool = False) -> RefineReport:
    report = RefineReport()
    values = read_config_nix()
    original = dict(values)

    for key in OBSOLETE_CONFIG_KEYS:
        if key in values:
            values.pop(key)
            report.removed.append(key)
            log.fix("config", "removed obsolete field", field=key)

    for f in CONFIG_FIELDS:
        if f.path not in values:
            values[f.path] = f.default_fn()
            report.added.append(f.path)
            log.fix("config", "added missing field", field=f.path)

    for f in CONFIG_FIELDS:
        _validate_field(f, values.get(f.path, ""), report, "config")

    if write and values != original:
        write_config_nix(values)
        report.changed = True
        log.ok("config", "config.nix refined", added=len(report.added), removed=len(report.removed))
    elif not report.added and not report.removed:
        log.ok("config", "config paths are complete")

    if strict and report.errors:
        log.error("config", "config refinement blocked by invalid fields")
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

    config_values = read_config_nix()
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
    log.step("config", "checking local configuration")
    report = RefineReport()
    report.extend(refine_config(write=write, strict=strict))
    if include_secrets:
        report.extend(refine_secrets(write=write, strict=strict, prune=prune))
    if report.ok:
        log.ok("config", "refine completed")
    elif strict:
        log.error("config", "refine failed")
    return report


def set_config_value(path: str, value: str) -> None:
    values = read_config_nix()
    valid_paths = {f.path for f in CONFIG_FIELDS}
    if path not in valid_paths:
        log.warn("config", "setting unknown config field", field=path)
    values[path] = value
    write_config_nix(values)
    log.ok("config", "config value updated", field=path)


def set_secret_value(yaml_path: str, value: str) -> None:
    stdin_data = json.dumps(value)
    run_cmd(["sops", "set", "--value-stdin", str(SECRETS_FILE), _sops_index(yaml_path)], stdin_data=stdin_data)
    log.ok("secrets", "secret value updated", key=yaml_path)


app = typer.Typer(
    name="config",
    help="Check and refine config.nix and sops secrets",
    rich_markup_mode="rich",
    no_args_is_help=True,
)


@app.command(name="check")
def cmd_check():
    """Check config.nix and secrets.yaml without writing changes."""
    report = refine_all(write=False, strict=False, include_secrets=True)
    if not report.ok:
        raise typer.Exit(code=1)


@app.command(name="refine")
def cmd_refine(
    prune: bool = typer.Option(False, "--prune", help="Remove known obsolete config/secret paths"),
):
    """Refine local config.nix and secrets.yaml."""
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
    path: str = typer.Argument(..., help="Config path, for example llm.steps.url"),
    value: str = typer.Argument(..., help="Value to write"),
):
    """Set a non-secret config.nix value."""
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
def cmd_show():
    """Show config values and redacted secret status."""
    table = Table(title="envy config")
    table.add_column("Kind")
    table.add_column("Path")
    table.add_column("Value")

    config_values = read_config_nix()
    for f in CONFIG_FIELDS:
        table.add_row("config", f.path, config_values.get(f.path, ""))

    secret_values, _ = read_secrets_yaml()
    for f in SECRET_FIELDS:
        value = secret_values.get(f.path, "")
        status = "<set>" if value else "<empty>"
        table.add_row("secret", f.yaml_path, status)

    log.console.print(table)
