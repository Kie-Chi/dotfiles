import os
import subprocess

import typer
from click.shell_completion import CompletionItem
from typing import Optional

from envy import log
from envy.config import app as config_app, refine_all
from envy.key import app as key_app
from envy.utils import (
    DOTFILES_DIR, SETUP_SCRIPT, PLATFORM,
    FLAKE_TARGET, SYSTEM_PROFILE,
    clean_config_links, ensure_config_links,
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


def _refine_before_apply() -> None:
    report = refine_all(write=True, strict=True, include_secrets=True)
    if not report.ok:
        raise typer.Exit(code=1)


# ==========================================
# SUBCOMMANDS
# ==========================================

@cli.command(name="apply")
@cli.command(name="a", rich_help_panel="Aliases")
@cli.command(name="switch", rich_help_panel="Aliases")
def cmd_apply():
    """Apply the configuration (home-manager on Linux, nix-darwin on macOS)."""
    _refine_before_apply()
    run_apply()


@cli.command(name="sync")
@cli.command(name="s", rich_help_panel="Aliases")
def cmd_sync():
    """Pull latest changes from git and then apply."""
    log.step("git", "pulling latest changes")
    subprocess.run(["git", "pull"], cwd=str(DOTFILES_DIR))
    cmd_apply()


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
    if PLATFORM == "darwin":
        run_apply()
    else:
        log.step("hm", "bootstrapping Home Manager from flake")
        run_hm("switch", "--flake", FLAKE_TARGET, "--impure")
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
):
    """Commit and push changes to all remotes, or a specified one."""
    current_branch = run_cmd(["git", "branch", "--show-current"], check=False, capture=True)

    # Determine which remotes to push to
    if remote is None:
        remotes_raw = run_cmd(["git", "remote"], check=False, capture=True)
        remotes = remotes_raw.split() if remotes_raw else []
    else:
        remotes = [remote]

    # Commit if there are uncommitted changes
    committed = False
    diff_result = subprocess.run(
        ["git", "diff-index", "--quiet", "HEAD", "--"],
        cwd=str(DOTFILES_DIR), capture_output=True,
    )
    if diff_result.returncode != 0:
        subprocess.run(["git", "add", "."], cwd=str(DOTFILES_DIR))
        log.step("git", "committing changes")
        subprocess.run(["git", "commit", "-m", msg], cwd=str(DOTFILES_DIR))
        committed = True

    # Push to each remote
    failed = 0
    for r in remotes:
        verify = subprocess.run(
            ["git", "rev-parse", "--verify", f"{r}/{current_branch}"],
            cwd=str(DOTFILES_DIR), capture_output=True,
        )
        if verify.returncode == 0:
            local_commits = run_cmd(
                ["git", "rev-list", "--count", f"{r}/{current_branch}..HEAD"],
                check=False, capture=True,
            )
            local_commits = int(local_commits) if local_commits and local_commits.isdigit() else 0
            if local_commits > 0 or committed:
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
    subprocess.run(["/bin/bash", str(SETUP_SCRIPT)])
    log.ok("setup", "configuration complete")


# Register config subgroup — "c" alias registered separately
cli.add_typer(config_app, name="config")
cli.add_typer(config_app, name="c", rich_help_panel="Aliases")

# Register key subgroup — "k" alias registered separately
cli.add_typer(key_app, name="key")
cli.add_typer(key_app, name="k", rich_help_panel="Aliases")
