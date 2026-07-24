"""Scoped Git staging and commit primitives shared by setup and key workflows."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from envy import log
from envy.git_safety import assert_index_secret_encrypted, assert_worktree_secret_encrypted
from envy.process import run_process
from envy.utils import DOTFILES_DIR


def stage_repo_files(files: list[Path], *, repository: Path = DOTFILES_DIR) -> list[str]:
    if not (repository / ".git").exists():
        return []
    assert_worktree_secret_encrypted(repository / "secrets" / "secrets.yaml")
    root = repository.resolve()
    relatives: list[str] = []
    for file in files:
        if not file.exists():
            continue
        try:
            relative = str(file.resolve().relative_to(root))
        except ValueError as exc:
            raise RuntimeError(f"refusing to stage a file outside the repository: {file}") from exc
        if relative not in relatives:
            relatives.append(relative)
    if not relatives:
        return []

    run_process(["git", "add", "--", *relatives], cwd=repository, check=True)
    if repository.resolve() == DOTFILES_DIR.resolve():
        assert_index_secret_encrypted(repository=repository)

    changed: list[str] = []
    for relative in relatives:
        result = run_process(
            ["git", "diff", "--cached", "--quiet", "--", relative],
            cwd=repository, capture=True, check=False,
        )
        if result.returncode == 1:
            changed.append(relative)
        elif result.returncode != 0:
            raise RuntimeError(f"failed to inspect staged managed file: {relative}")
    return changed


def commit_staged_files(
    changed: list[str],
    message: str,
    *,
    confirm: Callable[[str], bool],
    repository: Path = DOTFILES_DIR,
) -> None:
    display = ", ".join(changed)
    if not confirm(f"Commit {display} to git?"):
        log.warn("git", "managed changes staged but not committed")
        log.hint("Review with: envy git diff --cached")
        log.hint("Commit later with: envy git commit")
        return
    run_process(
        ["git", "commit", "-m", message, "--", *changed],
        cwd=repository, check=True,
    )
    log.ok("git", "committed", files=display)
