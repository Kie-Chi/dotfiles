import os

import typer
from typing import Optional

from envy import log
from envy import _check_schema_api
from envy.config import app as config_app
from envy.doctor import app as doctor_app
from envy.key import app as key_app
from envy.mirror import app as mirror_app
from envy.host import app as host_app
from envy.software import app as software_app
from envy.process import run_process
from envy.workflows.check import check_or_exit
from envy.workflows.update import update_homebrew, update_inputs
from envy.workflows import system as system_workflow
from envy.workflows import git as git_workflow
from envy.utils import DOTFILES_DIR, PLATFORM


# ==========================================
# COMPLETION CALLBACKS
# ==========================================


def complete_git_remotes(ctx, incomplete):
    """Complete git remote names for envy push."""
    return git_workflow.complete_remotes(incomplete)


def complete_git_branches(ctx, incomplete):
    """Complete local Git branch names for push/sync branch options."""
    return git_workflow.complete_branches(incomplete)


def complete_rollback_target(ctx, incomplete):
    """Complete rollback target: 'list' or generation numbers."""
    if "list".startswith(incomplete):
        return [("list", "List all available generations")]
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

update_app = typer.Typer(
    name="update",
    help="Update flake inputs or Homebrew metadata with validation.",
    invoke_without_command=True,
    no_args_is_help=False,
)


@cli.callback()
def main_callback(
    debug: bool = typer.Option(False, "--debug", "-e", help="Enable debug mode"),
):
    """envy — dotfiles manager"""
    if debug:
        os.environ["ENVY_DEBUG"] = "1"
    _check_schema_api()


# ==========================================
# SUBCOMMANDS
# ==========================================

@cli.command(name="apply")
@cli.command(name="a", rich_help_panel="Aliases")
@cli.command(name="switch", rich_help_panel="Aliases")
def cmd_apply():
    """Apply the configuration (home-manager on Linux, nix-darwin on macOS)."""
    system_workflow.apply_configuration()


@cli.command(name="sync")
@cli.command(name="s", rich_help_panel="Aliases")
def cmd_sync(
    remote: Optional[str] = typer.Option(
        None, "--remote", "-r", help="Synchronize one remote; omit to inspect all remotes",
        autocompletion=complete_git_remotes,
    ),
    branch: str = typer.Option(
        "master", "--branch", "-b", help="Shared cross-platform branch to fast-forward",
        autocompletion=complete_git_branches,
    ),
    no_apply: bool = typer.Option(False, "--no-apply", help="Synchronize Git without applying"),
    build_only: bool = typer.Option(False, "--build-only", help="Build the selected machine without applying"),
):
    """Fast-forward the shared branch and apply the selected machine."""
    git_workflow.sync(
        remote=remote, branch=branch, no_apply=no_apply, build_only=build_only,
    )


@update_app.callback(invoke_without_command=True)
def cmd_update(ctx: typer.Context):
    """Update all flake inputs, validate every machine, then refresh Homebrew on Darwin."""
    if ctx.invoked_subcommand is not None:
        return
    update_inputs(validate=True)
    if PLATFORM == "darwin":
        update_homebrew()
    log.hint("Run: envy apply")


@update_app.command(name="inputs")
def cmd_update_inputs(
    input_name: Optional[str] = typer.Argument(None, help="One flake input; omit for all"),
    no_check: bool = typer.Option(False, "--no-check", help="Skip all-machine validation"),
):
    """Update one or all flake inputs and roll back flake.lock on validation failure."""
    update_inputs(input_name, validate=not no_check)


@update_app.command(name="brew")
def cmd_update_brew():
    """Refresh Homebrew metadata only."""
    if PLATFORM != "darwin":
        log.error("update", "Homebrew update is available only on Darwin")
        raise typer.Exit(code=1)
    update_homebrew()


@cli.command(name="check")
def cmd_check_all(
    all_machines: bool = typer.Option(False, "--all", help="Check every Darwin and Linux machine"),
    changed: bool = typer.Option(False, "--changed", help="Check machines affected by worktree changes"),
    selected_platform: Optional[str] = typer.Option(
        None, "--platform", help="Restrict checks to darwin or linux"
    ),
    build: bool = typer.Option(False, "--build", help="Build selected local-platform targets"),
):
    """Evaluate current, changed, or all cross-platform machine targets."""
    check_or_exit(
        all_machines=all_machines,
        changed=changed,
        selected_platform=selected_platform,
        build=build,
    )


@cli.command(name="init")
@cli.command(name="i", rich_help_panel="Aliases")
@cli.command(name="bootstrap", rich_help_panel="Aliases")
def cmd_init():
    """Bootstrap configuration (home-manager on Linux, nix-darwin on macOS)."""
    system_workflow.bootstrap_configuration()


@cli.command(name="rollback")
@cli.command(name="r", rich_help_panel="Aliases")
def cmd_rollback(
    target: str = typer.Argument(None, help="Generation number or 'list'", autocompletion=complete_rollback_target),
):
    """Rollback to a previous configuration generation."""
    system_workflow.rollback_configuration(target)


@cli.command(name="edit")
@cli.command(name="e", rich_help_panel="Aliases")
def cmd_edit():
    """Open the dotfiles directory in your default editor."""
    system_workflow.open_editor()


@cli.command(name="push")
@cli.command(name="p", rich_help_panel="Aliases")
def cmd_push(
    msg: str = typer.Argument("chore: update configuration", help="Commit message"),
    remote: str = typer.Argument(None, help="Remote name (omit to push all)", autocompletion=complete_git_remotes),
    branch: str = typer.Option(
        "master", "--branch", "-b", help="Shared cross-platform branch expected for the push",
        autocompletion=complete_git_branches,
    ),
    machine_only: bool = typer.Option(
        False, "--machine-only",
        help="Require every worktree and outgoing change to be a machine file",
    ),
    self_only: bool = typer.Option(
        False, "--self",
        help="Require every worktree and outgoing change to belong to the selected machine",
    ),
    yes: bool = typer.Option(
        False, "--yes", "-y", help="Skip confirmation; scope safety guards still apply",
    ),
):
    """Commit and push changes to all remotes, or a specified one."""
    git_workflow.push(
        msg=msg,
        remote=remote,
        branch=branch,
        machine_only=machine_only,
        self_only=self_only,
        yes=yes,
    )


@cli.command(name="status")
@cli.command(name="st", rich_help_panel="Aliases")
def cmd_status():
    """Show the git status of the dotfiles repository."""
    run_process(["git", "status"], cwd=DOTFILES_DIR, check=True)


@cli.command(name="diff")
@cli.command(name="d", rich_help_panel="Aliases")
@cli.command(name="dif", rich_help_panel="Aliases")
def cmd_diff():
    """Show the git difference of the dotfiles repository."""
    run_process(["git", "diff"], cwd=DOTFILES_DIR, check=True)


@cli.command(name="git")
def cmd_git(
    args: list[str] = typer.Argument(None, help="Git arguments"),
):
    """Execute git commands in the dotfiles directory."""
    git_args = args if args else []
    run_process(["git", *git_args], cwd=DOTFILES_DIR, check=True)


@cli.command(name="clean")
@cli.command(name="gc", rich_help_panel="Aliases")
def cmd_clean(
    yes: bool = typer.Option(False, "--yes", "-y", help="Confirm generation deletion"),
    older_than: Optional[str] = typer.Option(
        None, "--older-than", help="Delete only generations older than a Nix duration, e.g. 30d"
    ),
    brew: bool = typer.Option(
        True, "--brew/--no-brew", help="Run Homebrew cleanup on Darwin"
    ),
):
    """Run Nix garbage collection to clean old generations."""
    system_workflow.clean_generations(yes=yes, older_than=older_than, brew=brew)


@cli.command(name="setup")
@cli.command(name="configure", rich_help_panel="Aliases")
def cmd_setup():
    """Run the setup script to configure secrets."""
    system_workflow.run_setup()


# Register validated update workflow and alias.
cli.add_typer(update_app, name="update")
cli.add_typer(update_app, name="u", rich_help_panel="Aliases")

# Register config subgroup — "c" alias registered separately
cli.add_typer(config_app, name="config")
cli.add_typer(config_app, name="c", rich_help_panel="Aliases")

# Software policy and registry search are independent from scalar config.
cli.add_typer(software_app, name="software")
cli.add_typer(software_app, name="sw", rich_help_panel="Aliases")

# Register key subgroup — "k" alias registered separately
cli.add_typer(key_app, name="key")
cli.add_typer(key_app, name="k", rich_help_panel="Aliases")

# Register host subgroup — "h" alias registered separately
cli.add_typer(host_app, name="host")
cli.add_typer(host_app, name="h", rich_help_panel="Aliases")

# Register doctor subgroup — "dr" alias registered separately
cli.add_typer(doctor_app, name="doctor")
cli.add_typer(doctor_app, name="dr", rich_help_panel="Aliases")

# Mirror policy inspection is read-only; configuration remains machine-owned.
cli.add_typer(mirror_app, name="mirror")
