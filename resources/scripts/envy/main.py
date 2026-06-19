import os
import subprocess

import typer
from click.shell_completion import CompletionItem
from rich.console import Console
from typing import Optional

from envy.key import app as key_app
from envy.utils import (
    CYAN, GREEN, YELLOW, RED, NC,
    DOTFILES_DIR, SETUP_SCRIPT, PLATFORM,
    FLAKE_TARGET, SYSTEM_PROFILE,
    clean_config_links, ensure_config_links,
    is_debug, run_cmd, run_hm, run_apply, esudo,
)

console = Console()


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


# ==========================================
# SUBCOMMANDS
# ==========================================

@cli.command(name="apply")
@cli.command(name="a", rich_help_panel="Aliases")
@cli.command(name="switch", rich_help_panel="Aliases")
def cmd_apply():
    """Apply the configuration (home-manager on Linux, nix-darwin on macOS)."""
    run_apply()


@cli.command(name="sync")
@cli.command(name="s", rich_help_panel="Aliases")
def cmd_sync():
    """Pull latest changes from git and then apply."""
    print(f"{CYAN}--> Pulling from git...{NC}")
    subprocess.run(["git", "pull"], cwd=str(DOTFILES_DIR))
    cmd_apply()


@cli.command(name="update")
@cli.command(name="u", rich_help_panel="Aliases")
def cmd_update():
    """Update flake inputs (nixpkgs, etc.)."""
    print(f"{CYAN}--> Updating flake inputs (nixpkgs, etc.)...{NC}")
    subprocess.run(["nix", "flake", "update"], cwd=str(DOTFILES_DIR))
    if PLATFORM == "darwin":
        subprocess.run(["brew", "update"])
    print(f"{GREEN}--> Flake inputs updated. Run 'envy apply' to use them.{NC}")


@cli.command(name="init")
@cli.command(name="i", rich_help_panel="Aliases")
@cli.command(name="bootstrap", rich_help_panel="Aliases")
def cmd_init():
    """Bootstrap configuration (home-manager on Linux, nix-darwin on macOS)."""
    if PLATFORM == "darwin":
        run_apply()
    else:
        print(f"{CYAN}--> Bootstrapping Home Manager from flake...{NC}")
        run_hm("switch", "--flake", FLAKE_TARGET, "--impure")
    print(f"{GREEN}--> Bootstrap completed successfully!{NC}")


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
        print(f"{CYAN}--> Rolling back to the previous generation...{NC}")
        esudo("-H", "nix-env", "-p", profile, "--rollback", capture=True)
        print(f"{CYAN}--> Re-activating previous configuration...{NC}")
        esudo("-H", profile + "/activate", capture=False)
        print(f"{GREEN}--> Rollback complete.{NC}")
    elif target == "list":
        print(f"{CYAN}--> Current System Generations:{NC}")
        esudo("-H", "nix-env", "-p", profile, "--list-generations", capture=True)
    else:
        try:
            gen_num = int(target)
        except ValueError:
            print(f"{RED}Error: Invalid argument for rollback. Must be a number or 'list'.{NC}")
            raise typer.Exit(code=1)
        print(f"{CYAN}--> Switching system profile to generation {gen_num}...{NC}")
        esudo("-H", "nix-env", "-p", profile, "--set-generation", str(gen_num), capture=True)
        print(f"{CYAN}--> Activating configuration {gen_num}...{NC}")
        esudo("-H", profile + "/activate", capture=False)
        print(f"{GREEN}--> Switched to generation {gen_num} successfully.{NC}")


def _rollback_linux(target: Optional[str] = None):
    """Linux rollback via home-manager."""
    if target is None:
        print(f"{CYAN}--> Rolling back to the previous generation...{NC}")
        run_hm("switch", "--rollback")
        print(f"{GREEN}--> Rollback successful!{NC}")
    elif target == "list":
        print(f"{CYAN}--> Available Home Manager generations:{NC}")
        run_hm("generations")
    else:
        try:
            gen_num = int(target)
        except ValueError:
            print(f"{RED}Error: Invalid argument for rollback. Must be a number or 'list'.{NC}")
            raise typer.Exit(code=1)
        print(f"{CYAN}--> Switching to generation {gen_num}...{NC}")
        run_hm("switch", "--generation", str(gen_num))
        print(f"{GREEN}--> Switched to generation {gen_num} successfully!{NC}")


@cli.command(name="edit")
@cli.command(name="e", rich_help_panel="Aliases")
def cmd_edit():
    """Open the dotfiles directory in your default editor."""
    editor = os.environ.get("EDITOR", "vim")
    print(f"{CYAN}--> Opening dotfiles in $EDITOR ({editor})...{NC}")
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
        print(f"{CYAN}--> Committing changes...{NC}")
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
                print(f"{CYAN}--> Pushing to {r}/{current_branch}...{NC}")
                result = subprocess.run(
                    ["git", "push", r, current_branch],
                    cwd=str(DOTFILES_DIR),
                )
                if result.returncode == 0:
                    print(f"{GREEN}--> Pushed to {r} successfully.{NC}")
                else:
                    print(f"{RED}--> Failed to push to {r}.{NC}")
                    failed += 1
            else:
                print(f"{YELLOW}--> Already up to date with {r}/{current_branch}.{NC}")
        else:
            print(f"{CYAN}--> Creating new branch on {r}/{current_branch}...{NC}")
            result = subprocess.run(
                ["git", "push", "-u", r, current_branch],
                cwd=str(DOTFILES_DIR),
            )
            if result.returncode == 0:
                print(f"{GREEN}--> Branch pushed to {r} successfully.{NC}")
            else:
                print(f"{RED}--> Failed to push to {r}.{NC}")
                failed += 1

    if failed > 0:
        print(f"{RED}--> {failed} remote(s) failed.{NC}")


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
    print(f"{CYAN}--> Cleaning up old Nix generations...{NC}")
    if PLATFORM == "darwin":
        esudo("-H", "nix-collect-garbage", "-d", capture=False)
        subprocess.run(["nix-collect-garbage", "-d"])
        subprocess.run(["nix-store", "--optimise"])
        subprocess.run(["brew", "cleanup"])
    else:
        subprocess.run(["nix-collect-garbage", "-d"])
    print(f"{GREEN}--> Cleanup complete.{NC}")


@cli.command(name="config")
@cli.command(name="c", rich_help_panel="Aliases")
def cmd_config():
    """Run the setup script to configure secrets."""
    print(f"{CYAN}--> Running setup...{NC}")
    subprocess.run(["/bin/bash", str(SETUP_SCRIPT)])
    print(f"{GREEN}--> Configuration complete!{NC}")


# Register key subgroup — "k" alias registered separately
cli.add_typer(key_app, name="key")
cli.add_typer(key_app, name="k", rich_help_panel="Aliases")