import os
import subprocess
import sys
from pathlib import Path

import typer
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


def complete_git_remotes(ctx, incomplete):
    """Complete git remote names for envy push."""
    result = subprocess.run(
        ["git", "remote"], capture_output=True, text=True,
        cwd=str(DOTFILES_DIR), check=False,
    )
    remotes = result.stdout.strip().split() if result.stdout else []
    return [name for name in remotes if name.startswith(incomplete)]


def complete_git_branches(ctx, incomplete):
    """Complete local Git branch names for push/sync branch options."""
    result = subprocess.run(
        ["git", "for-each-ref", "--format=%(refname:short)", "refs/heads"],
        capture_output=True, text=True, cwd=str(DOTFILES_DIR), check=False,
    )
    branches = result.stdout.strip().splitlines() if result.stdout else []
    return [name for name in branches if name.startswith(incomplete)]


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


def _ordered_unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _selected_git_remotes(remote: str | None) -> list[str]:
    if remote:
        return [remote]
    remotes_raw = _git_output("remote")
    return remotes_raw.split() if remotes_raw else []


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


def _outgoing_impact(
    remotes: list[str], branch: str, new_branches: set[str],
) -> tuple[list[str], set[str], dict[str, int]]:
    """Collect paths and unique commits that would be sent to target remotes."""
    paths: list[str] = []
    commits: set[str] = set()
    counts: dict[str, int] = {}
    for remote in remotes:
        revision = "HEAD" if remote in new_branches else f"{remote}/{branch}..HEAD"
        remote_commits = [
            line.strip() for line in _git_output("rev-list", revision).splitlines()
            if line.strip()
        ]
        counts[remote] = len(remote_commits)
        commits.update(remote_commits)
        if not remote_commits:
            continue
        paths.extend(
            line.strip().strip('"')
            for line in _git_output("log", "--format=", "--name-only", revision).splitlines()
            if line.strip()
        )
    return _ordered_unique(paths), commits, counts


def _enforce_push_scope(
    paths: list[str], *, machine_only: bool, self_only: bool,
) -> tuple[list[str], bool]:
    """Validate optional machine scope guards and return impact classification."""
    affected, shared = _affected_machines(paths)
    if self_only:
        selected = current_machine_id()
        expected = f"hosts/machines/{selected}.nix"
        outside = [path for path in paths if path != expected]
        if outside:
            log.error(
                "git",
                "--self refuses changes outside the selected machine file",
                machine=selected,
            )
            for path in outside:
                log.hint(path)
            raise typer.Exit(code=1)
    elif machine_only and shared:
        log.error("git", "--machine-only refuses shared changes")
        for path in paths:
            if not (path.startswith("hosts/machines/") and path.endswith(".nix")):
                log.hint(path)
        raise typer.Exit(code=1)
    return affected, shared


def _show_push_impact(
    *,
    paths: list[str],
    worktree_paths: list[str],
    outgoing_commits: set[str],
    counts: dict[str, int],
    affected: list[str],
    shared: bool,
    branch: str,
) -> None:
    scope = "shared" if shared else ("machine-only" if paths else "history-only")
    log.info(
        "git",
        "push impact",
        scope=scope,
        files=len(paths),
        worktree=len(worktree_paths),
        outgoing_commits=len(outgoing_commits),
    )
    for remote, count in counts.items():
        log.info("git", "push destination", branch=f"{remote}/{branch}", commits=count)
    for path in paths:
        log.hint(path)
    if affected:
        log.info("host", "affected machine targets", machines=", ".join(affected))


def _confirm_push_scope(
    *,
    shared: bool,
    affected: list[str],
    remotes: list[str],
    branch: str,
    has_worktree_changes: bool,
) -> bool:
    action = "Commit and push" if has_worktree_changes else "Push"
    destinations = ", ".join(f"{remote}/{branch}" for remote in remotes)
    if shared:
        return typer.confirm(
            f"{action} SHARED changes affecting {len(affected)} machine(s) to {destinations}?",
            default=None,
        )
    machines = ", ".join(affected) if affected else "no machine files"
    return typer.confirm(
        f"{action} machine-only changes for {machines} to {destinations}?",
        default=None,
    )


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


def _git_is_ancestor(older: str, newer: str) -> bool:
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", older, newer],
        cwd=str(DOTFILES_DIR), capture_output=True, check=False,
    )
    if result.returncode == 0:
        return True
    if result.returncode == 1:
        return False
    log.error("git", "could not compare branch ancestry", older=older, newer=newer)
    raise typer.Exit(code=result.returncode)


def _select_sync_target(remote_refs: list[str]) -> str:
    """Choose the newest linearly compatible ref, or reject remote divergence."""
    target = "HEAD"
    for remote_ref in remote_refs:
        if _git_is_ancestor(remote_ref, target):
            continue
        if _git_is_ancestor(target, remote_ref):
            target = remote_ref
            continue
        log.error(
            "git",
            "remote branches have diverged; refusing to create a merge commit",
            left=target,
            right=remote_ref,
        )
        raise typer.Exit(code=1)
    return target


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
    remote: Optional[str] = typer.Option(
        None, "--remote", "-r", help="Synchronize one remote; omit to inspect all remotes",
        autocompletion=complete_git_remotes,
    ),
    branch: str = typer.Option(
        "darwin", "--branch", "-b", help="Shared branch to fast-forward",
        autocompletion=complete_git_branches,
    ),
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

    remotes = _selected_git_remotes(remote)
    if not remotes:
        log.error("git", "no Git remotes are configured")
        raise typer.Exit(code=1)

    remote_refs: list[str] = []
    for selected_remote in remotes:
        log.step("git", "fetching remote", remote=selected_remote)
        _run_checked_git(["fetch", selected_remote], "fetch")
        remote_ref = f"{selected_remote}/{branch}"
        verify = subprocess.run(
            ["git", "rev-parse", "--verify", remote_ref], cwd=str(DOTFILES_DIR),
            capture_output=True, check=False,
        )
        if verify.returncode != 0:
            if remote is not None:
                log.error("git", "remote branch does not exist", branch=remote_ref)
                raise typer.Exit(code=1)
            log.warn("git", "remote does not provide the shared branch", branch=remote_ref)
            continue
        remote_refs.append(remote_ref)

    if not remote_refs:
        log.error("git", "no remote provides the requested shared branch", branch=branch)
        raise typer.Exit(code=1)

    target = _select_sync_target(remote_refs)
    if target == "HEAD":
        log.info("git", "local branch already contains every compatible remote")
    else:
        log.step("git", "fast-forwarding shared branch", branch=target)
        _run_checked_git(["merge", "--ff-only", target], "fast-forward")
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
    target: str = typer.Argument(None, help="Generation number or 'list'", autocompletion=complete_rollback_target),
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
    remote: str = typer.Argument(None, help="Remote name (omit to push all)", autocompletion=complete_git_remotes),
    branch: str = typer.Option(
        "darwin", "--branch", "-b", help="Shared branch expected for the push",
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

    remotes = _selected_git_remotes(remote)
    if not remotes:
        log.error("git", "no Git remotes are configured")
        raise typer.Exit(code=1)

    # Fetch and compare every destination before creating a local commit. This
    # keeps a remote-ahead shared branch recoverable with a simple fast-forward.
    new_branches = _preflight_push_remotes(remotes, current_branch)

    worktree_paths = _git_changed_paths()
    outgoing_paths, outgoing_commits, counts = _outgoing_impact(
        remotes, current_branch, new_branches,
    )
    paths = _ordered_unique([*worktree_paths, *outgoing_paths])
    affected, shared = _enforce_push_scope(
        paths, machine_only=machine_only, self_only=self_only,
    )
    has_push_work = bool(worktree_paths or outgoing_commits)
    if has_push_work:
        _show_push_impact(
            paths=paths,
            worktree_paths=worktree_paths,
            outgoing_commits=outgoing_commits,
            counts=counts,
            affected=affected,
            shared=shared,
            branch=current_branch,
        )
        if not yes and not _confirm_push_scope(
            shared=shared,
            affected=affected,
            remotes=remotes,
            branch=current_branch,
            has_worktree_changes=bool(worktree_paths),
        ):
            raise typer.Abort()

    if worktree_paths:
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
