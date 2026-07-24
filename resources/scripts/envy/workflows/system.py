"""Apply, rollback, cleanup, editor, and setup workflows."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import typer

from envy import log
from envy.config import refine_all
from envy.host import current_machine_file, initialize_machine, require_current_machine_file
from envy.process import run_process
from envy.utils import (
    DOTFILES_DIR,
    PLATFORM,
    SETUP_SCRIPT,
    SYSTEM_PROFILE,
    esudo,
    flake_target,
    run_apply,
    run_hm,
)


def refine_before_apply() -> None:
    machine_path = current_machine_file()
    if not machine_path.exists():
        log.warn("host", "machine configuration is missing", path=str(machine_path))
        if not sys.stdin.isatty():
            log.hint(f"Run: envy host init {machine_path.stem}")
            raise typer.Exit(code=1)
        if not typer.confirm("Create it from hosts/default.nix now?", default=None):
            raise typer.Abort()
        mode = typer.prompt("Creation mode (import/copy)", default="import")
        initialize_machine(machine_path.stem, mode)
    report = refine_all(write=True, strict=True, include_secrets=True)
    if not report.ok:
        raise typer.Exit(code=1)


def apply_configuration() -> None:
    refine_before_apply()
    require_current_machine_file()
    run_apply()


def bootstrap_configuration() -> None:
    refine_before_apply()
    require_current_machine_file()
    if PLATFORM == "darwin":
        run_apply()
    else:
        log.step("hm", "bootstrapping Home Manager from flake")
        run_hm("switch", "--flake", flake_target(), "--impure")
    log.ok("bootstrap", "bootstrap completed successfully")


def rollback_configuration(target: str | None = None) -> None:
    if PLATFORM == "darwin":
        rollback_darwin(target)
    else:
        rollback_linux(target)


def rollback_darwin(target: str | None = None) -> None:
    profile = str(SYSTEM_PROFILE)
    if target is None:
        log.step("rollback", "rolling back to previous generation")
        esudo("-H", "nix-env", "-p", profile, "--rollback", capture=True)
        log.step("rollback", "re-activating previous configuration")
        esudo("-H", profile + "/activate", capture=False)
        log.ok("rollback", "rollback complete")
        return
    if target == "list":
        log.step("rollback", "current system generations")
        esudo("-H", "nix-env", "-p", profile, "--list-generations", capture=True)
        return
    try:
        generation = int(target)
    except ValueError as exc:
        raise typer.BadParameter("generation must be a number or 'list'") from exc
    log.step("rollback", "switching system profile", generation=generation)
    esudo("-H", "nix-env", "-p", profile, "--set-generation", str(generation), capture=True)
    esudo("-H", profile + "/activate", capture=False)
    log.ok("rollback", "generation activated", generation=generation)


def rollback_linux(target: str | None = None) -> None:
    if target is None:
        log.step("rollback", "rolling back to previous generation")
        run_hm("switch", "--rollback")
        log.ok("rollback", "rollback successful")
        return
    if target == "list":
        log.step("rollback", "available Home Manager generations")
        run_hm("generations")
        return
    try:
        generation = int(target)
    except ValueError as exc:
        raise typer.BadParameter("generation must be a number or 'list'") from exc
    state_dir = Path(os.environ.get("NIX_STATE_DIR", "/nix/var/nix"))
    user = os.environ.get("USER", "")
    activation = state_dir / "profiles" / "per-user" / user / f"home-manager-{generation}-link" / "activate"
    if not activation.exists():
        log.error("rollback", "Home Manager generation does not exist", generation=generation)
        log.hint("Run: envy rollback list")
        raise typer.Exit(code=1)
    log.step("rollback", "activating Home Manager generation", generation=generation)
    run_process([str(activation)], check=True)
    log.ok("rollback", "generation activated", generation=generation)


def open_editor() -> None:
    editor = os.environ.get("EDITOR", "vim")
    log.step("editor", f"opening dotfiles in $EDITOR ({editor})")
    run_process([editor, str(DOTFILES_DIR)], check=True)


def clean_generations(*, yes: bool, older_than: str | None, brew: bool) -> None:
    policy = f"older than {older_than}" if older_than else "all old generations"
    log.warn("nix", "cleanup will permanently delete generations", policy=policy)
    if not yes:
        if not sys.stdin.isatty():
            log.error("nix", "non-interactive cleanup requires --yes")
            raise typer.Exit(code=1)
        if not typer.confirm("Continue with destructive cleanup?", default=None):
            raise typer.Abort()
    command = ["nix-collect-garbage"]
    command.extend(["--delete-older-than", older_than] if older_than else ["-d"])
    log.step("nix", "cleaning up old generations", policy=policy)
    if PLATFORM == "darwin":
        esudo("-H", *command, capture=False)
        run_process(command, check=True)
        run_process(["nix-store", "--optimise"], check=True)
        if brew:
            run_process(["brew", "cleanup"], check=True)
    else:
        run_process(command, check=True)
    log.ok("nix", "cleanup complete")


def run_setup() -> None:
    log.step("setup", "running setup")
    result = run_process(["/bin/bash", str(SETUP_SCRIPT)], check=False)
    if result.returncode == 2:
        log.warn("setup", "configuration cancelled")
        return
    if result.returncode != 0:
        log.error("setup", "configuration failed", exit_code=result.returncode)
        raise typer.Exit(code=result.returncode)
    log.ok("setup", "configuration complete")
