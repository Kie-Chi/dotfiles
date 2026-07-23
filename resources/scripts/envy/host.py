"""Per-machine host configuration commands for envy."""

import re
import shutil
import subprocess
from pathlib import Path
from typing import Optional

import typer
from rich.table import Table

from envy import log
from envy.utils import (
    DEVICE_LABEL_FILE,
    DOTFILES_DIR,
    current_machine_id,
    flake_target,
    machine_build_attr,
    machine_config_dir,
    platform_name,
    set_device_machine_id,
)


HOSTS_DIR = DOTFILES_DIR / "hosts"
MACHINES_DIR = machine_config_dir()
DEFAULT_MACHINE = HOSTS_DIR / "default.nix"
MACHINE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


app = typer.Typer(
    name="host",
    help="Create and inspect per-machine Nix configurations",
    rich_markup_mode="rich",
    no_args_is_help=True,
)


def machine_file(machine_id: str) -> Path:
    return MACHINES_DIR / f"{machine_id}.nix"


def machine_entries() -> list[tuple[str, str, Path]]:
    entries = []
    for platform in ("darwin", "linux"):
        directory = HOSTS_DIR / platform
        entries.extend(
            (platform, path.stem, path)
            for path in directory.glob("*.nix")
            if path.is_file()
        )
    return sorted(entries, key=lambda entry: (entry[0], entry[1]))


def validate_machine_id(machine_id: str) -> str:
    value = machine_id.strip()
    if not MACHINE_ID_PATTERN.fullmatch(value):
        raise typer.BadParameter(
            "machine ID may contain only letters, digits, underscores, and hyphens"
        )
    return value


def suggested_machine_id() -> str:
    return current_machine_id()


def current_machine_file() -> Path:
    return machine_file(current_machine_id())


def require_current_machine_file() -> Path:
    path = current_machine_file()
    if path.exists():
        return path
    log.error("host", "machine configuration is missing", path=str(path))
    log.hint("Run: envy host init")
    raise typer.Exit(code=1)


def initialize_machine(machine_id: str, mode: str, force: bool = False) -> Path:
    machine_id = validate_machine_id(machine_id)
    mode = mode.strip().lower()
    if mode not in {"import", "copy"}:
        raise typer.BadParameter("mode must be 'import' or 'copy'")
    if not DEFAULT_MACHINE.exists():
        log.error("host", "default machine configuration is missing", path=str(DEFAULT_MACHINE))
        raise typer.Exit(code=1)

    target = machine_file(machine_id)
    MACHINES_DIR.mkdir(parents=True, exist_ok=True)
    if target.exists() and not force:
        log.error("host", "machine configuration already exists", path=str(target))
        log.hint("Use --force to replace it after an explicit confirmation.")
        raise typer.Exit(code=1)

    if target.exists():
        if not typer.confirm(f"Replace {target}?", default=None):
            raise typer.Abort()
        backup = target.with_suffix(target.suffix + ".bak")
        shutil.copy2(target, backup)
        log.info("host", "backed up existing machine configuration", path=str(backup))

    if mode == "import":
        content = """{ ... }:

{
  imports = [ ../default.nix ];

  # `envy config refine` writes non-sensitive machine values here.
  # Add machine-specific envy.* overrides here.
}
"""
        target.write_text(content)
    else:
        source = DEFAULT_MACHINE.read_text()
        header = (
            "# Machine configuration copied from hosts/default.nix.\n"
            "# It does not inherit later default policy changes.\n\n"
        )
        target.write_text(header + source)

    set_device_machine_id(machine_id)
    log.ok("host", "machine configuration created and selected", path=str(target), mode=mode)
    log.hint(f"Edit the file, then run: envy host check {machine_id}")
    return target


@app.command(name="init")
def cmd_init(
    machine_id: Optional[str] = typer.Argument(None, help="Machine ID; defaults to the local device label"),
    mode: Optional[str] = typer.Option(None, "--mode", "-m", help="Creation mode: import or copy"),
    force: bool = typer.Option(False, "--force", "-f", help="Back up and replace an existing machine file"),
):
    """Create machine.nix by importing or copying hosts/default.nix."""
    selected_id = machine_id or typer.prompt("Machine ID", default=suggested_machine_id())
    selected_mode = mode or typer.prompt("Creation mode (import/copy)", default="import")
    initialize_machine(selected_id, selected_mode, force=force)


@app.command(name="list")
@app.command(name="ls", rich_help_panel="Aliases")
def cmd_list():
    """List machine configurations in the repository."""
    current = current_machine_id()
    table = Table(title="envy machines")
    table.add_column("Platform")
    table.add_column("Machine")
    table.add_column("Current")
    table.add_column("File")
    local_platform = platform_name()
    for platform, machine_id, path in machine_entries():
        table.add_row(
            platform,
            machine_id,
            "yes" if platform == local_platform and machine_id == current else "",
            str(path),
        )
    log.console.print(table)


@app.command(name="select")
def cmd_select(
    machine_id: str = typer.Argument(..., help="Existing machine ID to select locally"),
):
    """Select which versioned machine file local envy commands operate on."""
    selected = validate_machine_id(machine_id)
    path = machine_file(selected)
    if not path.exists():
        log.error("host", "machine configuration is missing", path=str(path))
        raise typer.Exit(code=1)
    set_device_machine_id(selected)
    log.ok("host", "machine selected locally", machine=selected, metadata=str(DEVICE_LABEL_FILE))


@app.command(name="status")
@app.command(name="st", rich_help_panel="Aliases")
def cmd_status():
    """Show the selected machine and flake target."""
    machine_id = current_machine_id()
    path = machine_file(machine_id)
    table = Table(title="envy host")
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("Machine ID", machine_id)
    table.add_row("Platform", platform_name())
    table.add_row("Device metadata", str(DEVICE_LABEL_FILE))
    table.add_row("Machine file", str(path))
    table.add_row("File exists", "yes" if path.exists() else "no")
    table.add_row("Flake target", flake_target())
    branch = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=str(DOTFILES_DIR), capture_output=True, text=True, check=False,
    ).stdout.strip()
    table.add_row("Git branch", branch or "<detached>")
    log.console.print(table)


@app.command(name="check")
def cmd_check(
    machine_id: Optional[str] = typer.Argument(None, help="Machine ID; defaults to the selected machine"),
):
    """Evaluate the selected platform's machine derivation without applying it."""
    selected = validate_machine_id(machine_id or current_machine_id())
    path = machine_file(selected)
    if not path.exists():
        log.error("host", "machine configuration is missing", path=str(path))
        raise typer.Exit(code=1)
    attr = machine_build_attr(selected, drv_path=True)
    log.step("host", "evaluating machine configuration", machine=selected)
    result = subprocess.run(
        ["nix", "eval", "--impure", attr, "--raw"],
        cwd=str(DOTFILES_DIR), check=False,
    )
    if result.returncode != 0:
        raise typer.Exit(code=result.returncode)
    log.ok("host", "machine configuration evaluates successfully", machine=selected)
