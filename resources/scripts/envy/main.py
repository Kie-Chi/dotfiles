import os
import subprocess
import sys
from pathlib import Path

import typer
from click.shell_completion import CompletionItem
from typing import Optional

from envy import log
from envy import _check_schema_api
from envy.config import app as config_app, refine_all
from envy.doctor import app as doctor_app
from envy.key import app as key_app
from envy.host import (
    app as host_app,
    current_machine_file,
    initialize_machine,
    machine_ids,
    require_current_machine_file,
)
from envy.utils import (
    DOTFILES_DIR, SETUP_SCRIPT, PLATFORM,
    SYSTEM_PROFILE, current_machine_id, flake_target,
    run_cmd, run_hm, run_apply, esudo,
)


# ==========================================
# COMPLETION CALLBACKS
# ==========================================


def complete_git_remotes(ctx, param, incomplete):
    """Complete git remote names for envy push."""
    result = subprocess.run(
        ["git", "remote"], capture_output=True, text=True,
        cwd=str(DOTFILES_DIR), check=False,
    )
    remotes = result.stdout.strip().split() if result.stdout else []
    return [CompletionItem(name) for name in remotes if name.startswith(incomplete)]


def complete_rollback_target(ctx, param, incomplete):
    """Complete rollback target: 'list' or generation numbers."""
    if "list".startswith(incomplete):
        return [CompletionItem("list", help="List all available generations")]
    return []


# ==========================================
# CLI APP
# ==========================================


cli = typer.Typer(
    name="envy",
    help="A friendly manager for your Nix dotfiles.",
    rich_markup_mode="rich",
    no_args_is_help=True,
)


@cli.callback()
def main_callback(
    debug: bool = typer.Option(False, "--debug", "-e", help="Enable debug mode"),
):
    """envy — dotfiles manager"""
    if debug:
        os.environ["ENVY_DEBUG"] = "1"
    _check_schema_api()


def _refine_before_apply() -> None:
    report = refine_all(write=True, strict=True, include_secrets=True)
    if not report.ok:
        raise typer.Exit(code=1)


def _git_output(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=str(DOTFILES_DIR),
        capture_output=True, text=True, check=False,
    )
    return result.stdout.strip()


def _git_changed_paths() -> list[str]:
    paths: list[str] = []
    for line in _git_output("status", "--porcelain=v1", "--untracked-files=all").splitlines():
        if len(line) < 4:
            continue
        path = line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        paths.append(path.strip('"'))
    return paths


def _affected_machines(paths: list[str]) -> tuple[list[str], bool]:
    known = machine_ids()
    affected: set[str] = set()
    shared = False
    prefix = "hosts/machines/"
    for path in paths:
        if path.startswith(prefix) and path.endswith(".nix"):
            affected.add(Path(path).stem)
        else:
            shared = True
    return (known if shared else sorted(affected), shared)


def _run_checked_git(args: list[str], action: str) -> None:
    result = subprocess.run(["git", *args], cwd=str(DOTFILES_DIR), check=False)
    if result.returncode != 0:
        log.error("git", f"{action} failed")
        raise typer.Exit(code=result.returncode)


def _preflight_push_remotes(remotes: list[str], branch: str) -> set[str]:
    """Fetch every destination and reject remote-ahead branches before committing."""
    new_branches: set[str] = set()
    for remote in remotes:
        log.step("git", "checking push destination", branch=f"{remote}/{branch}")
        fetch = subprocess.run(
            ["git", "fetch", remote], cwd=str(DOTFILES_DIR), check=False,
        )
        if fetch.returncode != 0:
            log.error("git", "remote preflight failed", remote=remote)
            raise typer.Exit(code=fetch.returncode)

        remote_ref = f"{remote}/{branch}"
        verify = subprocess.run(
            ["git", "rev-parse", "--verify", remote_ref],
            cwd=str(DOTFILES_DIR), capture_output=True, check=False,
        )
        if verify.returncode != 0:
            new_branches.add(remote)
            continue

        remote_ahead = _git_output("rev-list", "--count", f"HEAD..{remote_ref}")
        if not remote_ahead.isdigit():
            log.error("git", "could not compare the remote branch", branch=remote_ref)
            raise typer.Exit(code=1)
        if int(remote_ahead) > 0:
            log.error(
                "git",
                "remote branch is ahead; refusing to create a divergent local commit",
                branch=remote_ref,
            )
            log.hint("Stash or discard local work, then run envy sync before committing.")
            raise typer.Exit(code=1)
    return new_branches


# ==========================================
# SUBCOMMANDS
# ==========================================

@cli.command(name="apply")
@cli.command(name="a", rich_help_panel="Aliases")
@cli.command(name="switch", rich_help_panel="Aliases")
def cmd_apply():
    """Apply the configuration (home-manager on Linux, nix-darwin on macOS)."""
    _refine_before_apply()
    require_current_machine_file()
    run_apply()


@cli.command(name="sync")
@cli.command(name="s", rich_help_panel="Aliases")
def cmd_sync(
    remote: str = typer.Option("origin", "--remote", "-r", help="Remote to synchronize"),
    branch: str = typer.Option("darwin", "--branch", "-b", help="Shared branch to fast-forward"),
    no_apply: bool = typer.Option(False, "--no-apply", help="Synchronize Git without applying"),
    build_only: bool = typer.Option(False, "--build-only", help="Build the selected machine without applying"),
):
    """Fast-forward the shared branch and apply the selected machine."""
    if _git_changed_paths():
        log.error("git", "working tree is not clean; refusing to synchronize")
        log.hint("Commit or stash the changes first.")
        raise typer.Exit(code=1)

    current_branch = _git_output("branch", "--show-current")
    if current_branch != branch:
        log.error("git", "current branch is not the configured shared branch",
                  current=current_branch or "<detached>", expected=branch)
        raise typer.Exit(code=1)

    log.step("git", "fetching remote", remote=remote)
    _run_checked_git(["fetch", remote], "fetch")
    remote_ref = f"{remote}/{branch}"
    verify = subprocess.run(
        ["git", "rev-parse", "--verify", remote_ref], cwd=str(DOTFILES_DIR),
        capture_output=True, check=False,
    )
    if verify.returncode != 0:
        log.error("git", "remote branch does not exist", branch=remote_ref)
        raise typer.Exit(code=1)

    log.step("git", "fast-forwarding shared branch", branch=remote_ref)
    _run_checked_git(["merge", "--ff-only", remote_ref], "fast-forward")
    if no_apply:
        log.ok("sync", "repository synchronized; apply skipped")
        return

    _refine_before_apply()
    require_current_machine_file()
    if build_only:
        machine_id = current_machine_id()
        attr = f"path:.#darwinConfigurations.{machine_id}.config.system.build.toplevel"
        log.step("host", "building selected machine", machine=machine_id)
        result = subprocess.run(
            ["nix", "build", "--impure", "--no-link", attr],
            cwd=str(DOTFILES_DIR), check=False,
        )
        if result.returncode != 0:
            raise typer.Exit(code=result.returncode)
        log.ok("host", "machine build completed", machine=machine_id)
        return
    run_apply()


@cli.command(name="update")
@cli.command(name="u", rich_help_panel="Aliases")
def cmd_update():
    """Update flake inputs (nixpkgs, etc.)."""
    log.step("flake", "updating flake inputs")
    subprocess.run(["nix", "flake", "update"], cwd=str(DOTFILES_DIR))
    if PLATFORM == "darwin":
        subprocess.run(["brew", "update"])
    log.ok("flake", "flake inputs updated")
    log.hint("Run: envy apply")


@cli.command(name="init")
@cli.command(name="i", rich_help_panel="Aliases")
@cli.command(name="bootstrap", rich_help_panel="Aliases")
def cmd_init():
    """Bootstrap configuration (home-manager on Linux, nix-darwin on macOS)."""
    _refine_before_apply()
    require_current_machine_file()
    if PLATFORM == "darwin":
        run_apply()
    else:
        log.step("hm", "bootstrapping Home Manager from flake")
        run_hm("switch", "--flake", flake_target(), "--impure")
    log.ok("bootstrap", "bootstrap completed successfully")


@cli.command(name="rollback")
@cli.command(name="r", rich_help_panel="Aliases")
def cmd_rollback(
    target: str = typer.Argument(None, help="Generation number or 'list'", shell_complete=complete_rollback_target),
):
    """Rollback to a previous configuration generation."""
    if PLATFORM == "darwin":
        _rollback_darwin(target)
    else:
        _rollback_linux(target)


def _rollback_darwin(target: Optional[str] = None):
    """Darwin rollback via nix-env on system profile."""
    profile = str(SYSTEM_PROFILE)
    if target is None:
        log.step("rollback", "rolling back to previous generation")
        esudo("-H", "nix-env", "-p", profile, "--rollback", capture=True)
        log.step("rollback", "re-activating previous configuration")
        esudo("-H", profile + "/activate", capture=False)
        log.ok("rollback", "rollback complete")
    elif target == "list":
        log.step("rollback", "current system generations")
        esudo("-H", "nix-env", "-p", profile, "--list-generations", capture=True)
    else:
        try:
            gen_num = int(target)
        except ValueError:
            log.error("rollback", "invalid argument, must be a number or 'list'")
            raise typer.Exit(code=1)
        log.step("rollback", f"switching system profile to generation {gen_num}")
        esudo("-H", "nix-env", "-p", profile, "--set-generation", str(gen_num), capture=True)
        log.step("rollback", f"activating configuration {gen_num}")
        esudo("-H", profile + "/activate", capture=False)
        log.ok("rollback", f"switched to generation {gen_num} successfully")


def _rollback_linux(target: Optional[str] = None):
    """Linux rollback via home-manager."""
    if target is None:
        log.step("rollback", "rolling back to previous generation")
        run_hm("switch", "--rollback")
        log.ok("rollback", "rollback successful")
    elif target == "list":
        log.step("rollback", "available Home Manager generations")
        run_hm("generations")
    else:
        try:
            gen_num = int(target)
        except ValueError:
            log.error("rollback", "invalid argument, must be a number or 'list'")
            raise typer.Exit(code=1)
        log.step("rollback", f"switching to generation {gen_num}")
        run_hm("switch", "--generation", str(gen_num))
        log.ok("rollback", f"switched to generation {gen_num} successfully")


@cli.command(name="edit")
@cli.command(name="e", rich_help_panel="Aliases")
def cmd_edit():
    """Open the dotfiles directory in your default editor."""
    editor = os.environ.get("EDITOR", "vim")
    log.step("editor", f"opening dotfiles in $EDITOR ({editor})")
    subprocess.run([editor, str(DOTFILES_DIR)])


@cli.command(name="push")
@cli.command(name="p", rich_help_panel="Aliases")
def cmd_push(
    msg: str = typer.Argument("chore: update configuration", help="Commit message"),
    remote: str = typer.Argument(None, help="Remote name (omit to push all)", shell_complete=complete_git_remotes),
    branch: str = typer.Option("darwin", "--branch", "-b", help="Shared branch expected for the push"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Confirm the displayed commit and push"),
):
    """Commit and push changes to all remotes, or a specified one."""
    current_branch = _git_output("branch", "--show-current")
    if not current_branch:
        log.error("git", "cannot push from a detached HEAD")
        raise typer.Exit(code=1)
    if current_branch != branch:
        log.error(
            "git",
            "current branch is not the configured shared branch",
            current=current_branch,
            expected=branch,
        )
        log.hint(f"Switch to {branch}, or pass --branch {current_branch} for an intentional branch push.")
        raise typer.Exit(code=1)

    # Determine which remotes to push to
    if remote is None:
        remotes_raw = run_cmd(["git", "remote"], check=False, capture=True)
        remotes = remotes_raw.split() if remotes_raw else []
    else:
        remotes = [remote]

    # Fetch and compare every destination before creating a local commit. This
    # keeps a remote-ahead shared branch recoverable with a simple fast-forward.
    new_branches = _preflight_push_remotes(remotes, current_branch)

    paths = _git_changed_paths()
    if paths:
        affected, shared = _affected_machines(paths)
        log.info("git", "changes selected for commit", files=len(paths), scope="shared" if shared else "machine")
        for path in paths:
            log.hint(path)
        if affected:
            log.info("host", "affected machine targets", machines=", ".join(affected))
        if not yes and not typer.confirm(f"Commit these changes on {current_branch} and push?", default=None):
            raise typer.Abort()

        _run_checked_git(["add", "-A"], "staging")
        log.step("git", "committing changes")
        _run_checked_git(["commit", "-m", msg], "commit")

    # Push to each remote
    failed = 0
    for r in remotes:
        if r not in new_branches:
            local_commits = run_cmd(
                ["git", "rev-list", "--count", f"{r}/{current_branch}..HEAD"],
                check=False, capture=True,
            )
            local_commits = int(local_commits) if local_commits and local_commits.isdigit() else 0
            if local_commits > 0:
                log.step("git", f"pushing to {r}/{current_branch}")
                result = subprocess.run(
                    ["git", "push", r, current_branch],
                    cwd=str(DOTFILES_DIR),
                )
                if result.returncode == 0:
                    log.ok("git", f"pushed to {r} successfully")
                else:
                    log.error("git", f"failed to push to {r}")
                    failed += 1
            else:
                log.info("git", f"already up to date with {r}/{current_branch}")
        else:
            log.step("git", f"creating new branch on {r}/{current_branch}")
            result = subprocess.run(
                ["git", "push", "-u", r, current_branch],
                cwd=str(DOTFILES_DIR),
            )
            if result.returncode == 0:
                log.ok("git", f"branch pushed to {r} successfully")
            else:
                log.error("git", f"failed to push to {r}")
                failed += 1

    if failed > 0:
        log.error("git", f"{failed} remote(s) failed")
        raise typer.Exit(code=1)


@cli.command(name="status")
@cli.command(name="st", rich_help_panel="Aliases")
def cmd_status():
    """Show the git status of the dotfiles repository."""
    subprocess.run(["git", "status"], cwd=str(DOTFILES_DIR))


@cli.command(name="diff")
@cli.command(name="d", rich_help_panel="Aliases")
@cli.command(name="dif", rich_help_panel="Aliases")
def cmd_diff():
    """Show the git difference of the dotfiles repository."""
    subprocess.run(["git", "diff"], cwd=str(DOTFILES_DIR))


@cli.command(name="git")
def cmd_git(
    args: list[str] = typer.Argument(None, help="Git arguments"),
):
    """Execute git commands in the dotfiles directory."""
    git_args = args if args else []
    subprocess.run(["git", *git_args], cwd=str(DOTFILES_DIR))


@cli.command(name="clean")
@cli.command(name="gc", rich_help_panel="Aliases")
def cmd_clean():
    """Run Nix garbage collection to clean old generations."""
    log.step("nix", "cleaning up old generations")
    if PLATFORM == "darwin":
        esudo("-H", "nix-collect-garbage", "-d", capture=False)
        subprocess.run(["nix-collect-garbage", "-d"])
        subprocess.run(["nix-store", "--optimise"])
        subprocess.run(["brew", "cleanup"])
    else:
        subprocess.run(["nix-collect-garbage", "-d"])
    log.ok("nix", "cleanup complete")


@cli.command(name="setup")
@cli.command(name="configure", rich_help_panel="Aliases")
def cmd_setup():
    """Run the setup script to configure secrets."""
    log.step("setup", "running setup")
    result = subprocess.run(["/bin/bash", str(SETUP_SCRIPT)], check=False)
    if result.returncode != 0:
        log.error("setup", "configuration failed", exit_code=result.returncode)
        raise typer.Exit(code=result.returncode)
    machine_path = current_machine_file()
    if PLATFORM == "darwin" and not machine_path.exists():
        log.warn("host", "machine configuration is missing", path=str(machine_path))
        if sys.stdin.isatty() and typer.confirm("Create it from hosts/default.nix now?", default=None):
            mode = typer.prompt("Creation mode (import/copy)", default="import")
            initialize_machine(machine_path.stem, mode)
        else:
            log.hint("Run: envy host init")
    log.ok("setup", "configuration complete")


# Register config subgroup — "c" alias registered separately
cli.add_typer(config_app, name="config")
cli.add_typer(config_app, name="c", rich_help_panel="Aliases")

# Register key subgroup — "k" alias registered separately
cli.add_typer(key_app, name="key")
cli.add_typer(key_app, name="k", rich_help_panel="Aliases")

# Register host subgroup — "h" alias registered separately
cli.add_typer(host_app, name="host")
cli.add_typer(host_app, name="h", rich_help_panel="Aliases")

# Register doctor subgroup — "dr" alias registered separately
cli.add_typer(doctor_app, name="doctor")
cli.add_typer(doctor_app, name="dr", rich_help_panel="Aliases")
