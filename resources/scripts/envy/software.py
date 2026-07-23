"""Machine-local software exclusions and their managed Nix source block."""

import hashlib
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import typer
from rich.table import Table
from rich.text import Text

from envy import log
from envy.evaluation import (
    invalidate_machine_manifest,
    machine_manifest,
    manifest_selection_rows,
)
from envy.utils import current_machine_id, machine_config_file, platform_name


MANAGED_START = "  # BEGIN ENVY MANAGED EXCLUSIONS"
MANAGED_END = "  # END ENVY MANAGED EXCLUSIONS"


@dataclass(frozen=True)
class SelectionGroup:
    key: str
    option: str
    label: str


COMMON_GROUPS = (
    SelectionGroup("packages.home", "envy.packages.home", "Home packages"),
)
DARWIN_GROUPS = (
    SelectionGroup("packages.system", "envy.darwin.packages.system", "Darwin system packages"),
    SelectionGroup("packages.fonts", "envy.darwin.packages.fonts", "Darwin fonts"),
    SelectionGroup("homebrew.brews", "envy.darwin.homebrew.brews", "Homebrew brews"),
    SelectionGroup("homebrew.casks", "envy.darwin.homebrew.casks", "Homebrew casks"),
    SelectionGroup("homebrew.taps", "envy.darwin.homebrew.taps", "Homebrew taps"),
)


def groups_for_platform(platform: str) -> tuple[SelectionGroup, ...]:
    return COMMON_GROUPS + (DARWIN_GROUPS if platform == "darwin" else ())


GROUPS = groups_for_platform(platform_name())
GROUP_BY_KEY = {group.key: group for group in GROUPS}
GROUP_BY_OPTION = {group.option: group for group in GROUPS}
if platform_name() == "darwin":
    GROUP_BY_OPTION.update({
        "envy.packages.system": GROUP_BY_KEY["packages.system"],
        "envy.packages.fonts": GROUP_BY_KEY["packages.fonts"],
        "envy.homebrew.brews": GROUP_BY_KEY["homebrew.brews"],
        "envy.homebrew.casks": GROUP_BY_KEY["homebrew.casks"],
        "envy.homebrew.taps": GROUP_BY_KEY["homebrew.taps"],
    })


@dataclass(frozen=True)
class SoftwareItem:
    name: str
    included: bool
    checked: bool
    managed: bool
    locked: bool
    stale: bool
    changed: bool


class SoftwarePolicyError(ValueError):
    """Raised when the managed exclusion block cannot be safely handled."""


class ConcurrentMachineEdit(SoftwarePolicyError):
    """Raised when machine.nix changed while an editor session was open."""


def machine_file(machine_id: str | None = None) -> Path:
    return machine_config_file(machine_id)


def empty_exclusions(
    groups: tuple[SelectionGroup, ...] | None = None,
) -> dict[str, list[str]]:
    active_groups = groups if groups is not None else GROUPS
    return {group.key: [] for group in active_groups}


def normalize_exclusions(
    values: dict[str, list[str]] | None,
    groups: tuple[SelectionGroup, ...] | None = None,
) -> dict[str, list[str]]:
    active_groups = groups if groups is not None else GROUPS
    normalized = empty_exclusions(active_groups)
    for group in active_groups:
        seen: set[str] = set()
        for raw in (values or {}).get(group.key, []):
            name = str(raw)
            _validate_name(name)
            if name not in seen:
                seen.add(name)
                normalized[group.key].append(name)
    return normalized


def source_digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def read_managed_exclusions(path: Path | None = None) -> dict[str, list[str]]:
    target = path or machine_file()
    if not target.exists():
        raise SoftwarePolicyError(f"machine configuration is missing: {target}")
    text = target.read_text()
    match = _managed_match(text)
    if match is None:
        return empty_exclusions()
    return _parse_block(match.group(0))


def render_managed_exclusions(values: dict[str, list[str]]) -> str:
    normalized = normalize_exclusions(values)
    lines = [
        MANAGED_START + "\n",
        "  # `envy setup` owns only these machine-local exclusion lists.\n",
    ]
    for group in GROUPS:
        names = normalized[group.key]
        if not names:
            continue
        lines.append(f"\n  {group.option}.exclude = [\n")
        for name in names:
            lines.append(f'    "{_escape_nix_string(name)}"\n')
        lines.append("  ];\n")
    lines.append(MANAGED_END)
    return "".join(lines)


def update_machine_source(text: str, values: dict[str, list[str]]) -> str:
    normalized = normalize_exclusions(values)
    has_values = any(normalized[group.key] for group in GROUPS)
    match = _managed_match(text)

    if match is not None:
        if has_values:
            updated = text[:match.start()] + render_managed_exclusions(normalized) + text[match.end():]
        else:
            updated = text[:match.start()].rstrip() + "\n\n" + text[match.end():].lstrip("\n")
        return updated if updated.endswith("\n") else updated + "\n"

    if not has_values:
        return text

    anchor = "  # END ENVY MANAGED CONFIG"
    anchor_index = text.find(anchor)
    if anchor_index >= 0:
        insert_at = text.find("\n", anchor_index)
        if insert_at < 0:
            insert_at = len(text)
        else:
            insert_at += 1
    else:
        insert_at = text.rfind("\n}")
        if insert_at < 0:
            raise SoftwarePolicyError("cannot locate the top-level closing brace in machine configuration")
        insert_at += 1

    prefix = text[:insert_at].rstrip()
    suffix = text[insert_at:].lstrip("\n")
    updated = prefix + "\n\n" + render_managed_exclusions(normalized) + "\n\n" + suffix
    return updated if updated.endswith("\n") else updated + "\n"


def write_managed_exclusions(
    values: dict[str, list[str]],
    path: Path | None = None,
    *,
    expected_digest: str | None = None,
) -> None:
    target = path or machine_file()
    original = target.read_text()
    if expected_digest is not None and source_digest(original) != expected_digest:
        raise ConcurrentMachineEdit(f"machine configuration changed while setup was open: {target}")
    updated = update_machine_source(original, values)
    if updated != original:
        _atomic_write(target, updated)


def restore_machine_source(text: str, path: Path | None = None) -> None:
    """Atomically restore a previously captured machine source document."""
    _atomic_write(path or machine_file(), text)


def write_and_validate_exclusions(
    values: dict[str, list[str]],
    path: Path | None = None,
    *,
    expected_digest: str | None = None,
) -> dict[str, Any]:
    """Write exclusions, roll back when the selected Nix machine stops evaluating."""
    target = path or machine_file()
    original = target.read_text()
    if expected_digest is not None and source_digest(original) != expected_digest:
        raise ConcurrentMachineEdit(f"machine configuration changed while setup was open: {target}")

    updated = update_machine_source(original, values)
    if updated != original:
        _atomic_write(target, updated)
    manifest = machine_manifest(refresh=True)
    if manifest is None:
        if updated != original:
            _atomic_write(target, original)
        invalidate_machine_manifest()
        raise SoftwarePolicyError("Nix evaluation failed; restored the original machine configuration")
    return manifest


def build_software_items(
    manifest: dict[str, Any] | None,
    managed: dict[str, list[str]],
    original_managed: dict[str, list[str]] | None = None,
    query: str = "",
    *,
    groups: tuple[SelectionGroup, ...] | None = None,
) -> dict[str, list[SoftwareItem]]:
    """Build checkbox state from evaluated policy plus pending machine exclusions."""
    manifest_platform = manifest.get("platform") if isinstance(manifest, dict) else None
    active_groups = groups or groups_for_platform(str(manifest_platform or platform_name()))
    current = normalize_exclusions(managed, active_groups)
    original = normalize_exclusions(
        original_managed if original_managed is not None else managed,
        active_groups,
    )
    option_to_key = {group.option: group.key for group in active_groups}
    rows = {}
    for path, include, exclude, effective in manifest_selection_rows(manifest):
        group_key = option_to_key.get(path)
        if group_key is not None:
            rows[group_key] = (include, exclude, effective)
    result: dict[str, list[SoftwareItem]] = {}
    needle = query.casefold().strip()

    for group in active_groups:
        include, final_exclude, _ = rows.get(group.key, ([], [], []))
        include_set = set(include)
        original_set = set(original[group.key])
        current_set = set(current[group.key])
        external_set = set(final_exclude) - original_set
        predicted_excluded = external_set | current_set
        names = _ordered_unique([*include, *final_exclude, *original[group.key], *current[group.key]])
        items = []
        for name in names:
            if needle and needle not in name.casefold():
                continue
            included = name in include_set
            locked = name in external_set
            managed_here = name in current_set
            items.append(SoftwareItem(
                name=name,
                included=included,
                checked=included and name not in predicted_excluded,
                managed=managed_here,
                locked=locked,
                stale=not included and name in predicted_excluded,
                changed=(name in current_set) != (name in original_set),
            ))
        result[group.key] = items
    return result


def set_excluded(
    values: dict[str, list[str]],
    group_key: str,
    name: str,
    excluded: bool,
    groups: tuple[SelectionGroup, ...] | None = None,
) -> None:
    active_groups = groups if groups is not None else GROUPS
    group = require_group(group_key, active_groups)
    _validate_name(name)
    current = normalize_exclusions(values, active_groups)
    names = current[group.key]
    if excluded and name not in names:
        names.append(name)
    elif not excluded and name in names:
        names.remove(name)
    values.clear()
    values.update(current)


def require_group(
    value: str,
    groups: tuple[SelectionGroup, ...] | None = None,
) -> SelectionGroup:
    active_groups = groups if groups is not None else GROUPS
    group_by_key = {group.key: group for group in active_groups}
    group_by_option = {group.option: group for group in active_groups}
    for group in active_groups:
        if group.option.startswith("envy.darwin."):
            group_by_option[group.option.replace("envy.darwin.", "envy.", 1)] = group
    option = value.removesuffix(".exclude")
    key = option.removeprefix("envy.")
    group = group_by_option.get(option) or group_by_key.get(key)
    if group is None:
        allowed = ", ".join(item.key for item in active_groups)
        raise typer.BadParameter(f"unknown software group: {value}; choose one of: {allowed}")
    return group


def software_changes(
    original: dict[str, list[str]], current: dict[str, list[str]],
) -> list[tuple[str, list[str], list[str]]]:
    before = normalize_exclusions(original)
    after = normalize_exclusions(current)
    changes = []
    for group in GROUPS:
        disabled = [name for name in after[group.key] if name not in before[group.key]]
        enabled = [name for name in before[group.key] if name not in after[group.key]]
        if disabled or enabled:
            changes.append((group.label, disabled, enabled))
    return changes


def _managed_match(text: str) -> re.Match[str] | None:
    start_count = text.count(MANAGED_START)
    end_count = text.count(MANAGED_END)
    if start_count != end_count or start_count > 1:
        raise SoftwarePolicyError("managed exclusions block markers are missing or duplicated")
    if start_count == 0:
        return None
    pattern = re.compile(
        rf"(?ms)^{re.escape(MANAGED_START)}$.*?^{re.escape(MANAGED_END)}$"
    )
    match = pattern.search(text)
    if match is None:
        raise SoftwarePolicyError("cannot parse managed exclusions block")
    return match


def _parse_block(block: str) -> dict[str, list[str]]:
    values = empty_exclusions()
    seen: set[str] = set()
    body = block.split("\n", 1)[1].rsplit("\n", 1)[0]
    body = re.sub(r"(?m)^\s*#.*$", "", body)
    options = "|".join(re.escape(option) for option in GROUP_BY_OPTION)
    assignment = re.compile(
        rf"(?ms)^\s*({options})\.exclude\s*=\s*\[(.*?)\]\s*;[ \t]*(?:\n|$)"
    )
    cursor = 0
    for match in assignment.finditer(body):
        if body[cursor:match.start()].strip():
            raise SoftwarePolicyError("unsupported content in managed exclusions block")
        group = GROUP_BY_OPTION[match.group(1)]
        if group.key in seen:
            raise SoftwarePolicyError(f"duplicate exclusion assignment: {group.option}.exclude")
        seen.add(group.key)
        values[group.key] = _parse_string_list(match.group(2))
        cursor = match.end()
    if body[cursor:].strip():
        raise SoftwarePolicyError("unsupported content in managed exclusions block")
    return normalize_exclusions(values)


def _parse_string_list(body: str) -> list[str]:
    strings = re.compile(r'"((?:\\.|[^"\\])*)"')
    values = []
    cursor = 0
    for match in strings.finditer(body):
        if body[cursor:match.start()].strip():
            raise SoftwarePolicyError("exclusion lists may contain only quoted strings")
        values.append(_unescape_nix_string(match.group(1)))
        cursor = match.end()
    if body[cursor:].strip():
        raise SoftwarePolicyError("exclusion lists may contain only quoted strings")
    return values


def _validate_name(name: str) -> None:
    if not name or name != name.strip() or any(char in name for char in ('"', "\\", "\n", "\r", "\t")):
        raise SoftwarePolicyError(f"invalid software name: {name!r}")


def _escape_nix_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _unescape_nix_string(value: str) -> str:
    return value.replace('\\"', '"').replace("\\\\", "\\")


def _ordered_unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _atomic_write(path: Path, text: str) -> None:
    mode = path.stat().st_mode & 0o777
    handle = tempfile.NamedTemporaryFile(
        mode="w", dir=path.parent, prefix=f".{path.name}.envy-", delete=False
    )
    temporary = Path(handle.name)
    try:
        with handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.chmod(mode)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


app = typer.Typer(
    name="software",
    help="Inspect and manage machine-local software exclusions",
    invoke_without_command=True,
    no_args_is_help=False,
)


@app.callback()
def cmd_software(ctx: typer.Context):
    """List evaluated software policy when no subcommand is supplied."""
    if ctx.invoked_subcommand is not None:
        return
    _print_policy()


@app.command(name="list")
def cmd_list():
    """List checkbox state for all software groups."""
    _print_policy()


@app.command(name="disable")
def cmd_disable(group: str, name: str):
    """Exclude one contributed item on the selected machine."""
    _change_one(group, name, excluded=True)


@app.command(name="enable")
def cmd_enable(group: str, name: str):
    """Remove one machine-local exclusion."""
    _change_one(group, name, excluded=False)


def _change_one(group_value: str, name: str, *, excluded: bool) -> None:
    group = require_group(group_value)
    values = read_managed_exclusions()
    manifest = machine_manifest()
    if manifest is None:
        log.error("software", "cannot evaluate the selected machine")
        raise typer.Exit(code=1)
    items = {
        item.name: item
        for item in build_software_items(manifest, values)[group.key]
    }
    item = items.get(name)
    if excluded:
        if item is None or not item.included:
            log.error("software", "item is not contributed by the selected machine", group=group.key, name=name)
            raise typer.Exit(code=1)
        if item.locked:
            log.error("software", "item is already excluded outside the managed machine block", group=group.key, name=name)
            raise typer.Exit(code=1)
        if item.managed:
            log.ok("software", "already disabled", group=group.key, name=name)
            return
    elif name not in values[group.key]:
        log.error("software", "item is not excluded by the managed machine block", group=group.key, name=name)
        log.hint("External or hand-written exclusions must be edited at their source.")
        raise typer.Exit(code=1)

    set_excluded(values, group.key, name, excluded)
    try:
        manifest = write_and_validate_exclusions(values)
    except SoftwarePolicyError as exc:
        log.error("software", str(exc))
        raise typer.Exit(code=1) from exc
    action = "disabled" if excluded else "enabled"
    log.ok("software", action, group=group.key, name=name, machine=manifest.get("id", "current"))


def _print_policy() -> None:
    manifest = machine_manifest()
    if manifest is None:
        log.error("software", "cannot evaluate the selected machine")
        raise typer.Exit(code=1)
    managed = read_managed_exclusions()
    items_by_group = build_software_items(manifest, managed)
    table = Table(title=f"Machine software — {manifest.get('id', current_machine_id())}")
    table.add_column("Group")
    table.add_column("State")
    table.add_column("Name")
    table.add_column("Source")
    for group in GROUPS:
        for item in items_by_group[group.key]:
            state = Text("[x]" if item.checked else ("[-]" if item.locked else "[ ]"))
            source = "machine exclusion" if item.managed else ("external exclusion" if item.locked else "included")
            if item.stale:
                source = "stale exclusion"
            table.add_row(group.label, state, item.name, source)
    log.console.print(table)
