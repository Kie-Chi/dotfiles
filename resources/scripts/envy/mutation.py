"""Consistent scoped Git follow-up for commands that mutate versioned files."""

from __future__ import annotations

import sys
from pathlib import Path

import typer

from envy import log
from envy.git_safety import assert_index_secret_encrypted, assert_worktree_secret_encrypted
from envy.process import run_process
from envy.utils import DOTFILES_DIR


def changed_repo_paths(paths: list[Path]) -> list[str]:
    repository = DOTFILES_DIR.resolve()
    changed: list[str] = []
    for path in dict.fromkeys(paths):
        if not path.exists():
            continue
        try:
            relative = str(path.resolve().relative_to(repository))
        except ValueError:
            continue
        result = run_process(
            ["git", "status", "--porcelain=v1", "--", relative],
            cwd=DOTFILES_DIR, capture=True, check=True,
        )
        if (result.stdout or "").strip():
            changed.append(relative)
    return changed


def offer_mutation_commit(paths: list[Path], message: str) -> None:
    """Offer one explicit-path commit in a TTY; print guidance otherwise."""
    assert_worktree_secret_encrypted()
    changed = changed_repo_paths(paths)
    if not changed:
        return
    if not sys.stdin.isatty():
        log.info("git", "versioned mutation is not committed", files=", ".join(changed))
        log.hint("Review and commit with: envy push \"<message>\"")
        return
    for relative in changed:
        run_process(["git", "add", "--", relative], cwd=DOTFILES_DIR, check=True)
    assert_index_secret_encrypted()
    if not typer.confirm(f"Commit {', '.join(changed)}?", default=None):
        log.warn("git", "managed changes remain staged")
        log.hint("Review with: envy git diff --cached")
        return
    run_process(["git", "commit", "-m", message, "--", *changed], cwd=DOTFILES_DIR, check=True)
    log.ok("git", "committed managed mutation", files=", ".join(changed))
