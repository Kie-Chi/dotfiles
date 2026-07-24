"""Fail-closed Git guards for the repository's encrypted secret document."""

from __future__ import annotations

import subprocess
from collections.abc import Iterable
from pathlib import Path

from envy.sops_format import content_is_sops_encrypted
from envy.utils import DOTFILES_DIR, SECRETS_FILE, is_sops_encrypted


SECRET_PATH = "secrets/secrets.yaml"


class SecretSafetyError(RuntimeError):
    """Raised when plaintext secret material could enter Git history."""


def _encrypted_content(content: str) -> bool:
    return content_is_sops_encrypted(content)


def assert_worktree_secret_encrypted(path: Path | None = None) -> None:
    path = path or SECRETS_FILE
    if not path.exists():
        raise SecretSafetyError(f"refusing Git operation: {SECRET_PATH} is missing from worktree")
    if not is_sops_encrypted(path):
        raise SecretSafetyError(f"refusing Git operation: {SECRET_PATH} is not sops-encrypted")


def _git_file(revision: str, *, repository: Path | None = None) -> tuple[bool, str]:
    root = repository or DOTFILES_DIR
    object_name = f":{SECRET_PATH}" if revision == ":" else f"{revision}:{SECRET_PATH}"
    result = subprocess.run(
        ["git", "show", object_name],
        cwd=str(root), capture_output=True, text=True, check=False,
    )
    if result.returncode == 0:
        return True, result.stdout
    missing = subprocess.run(
        ["git", "cat-file", "-e", object_name],
        cwd=str(root), capture_output=True, check=False,
    )
    if missing.returncode != 0:
        return False, ""
    raise SecretSafetyError(f"cannot inspect {SECRET_PATH} in Git revision {revision}")


def assert_index_secret_encrypted(*, repository: Path | None = None) -> None:
    present, content = _git_file(":", repository=repository)
    if not present:
        raise SecretSafetyError(f"refusing Git operation: staged {SECRET_PATH} is missing")
    if not _encrypted_content(content):
        raise SecretSafetyError(f"refusing Git operation: staged {SECRET_PATH} is not sops-encrypted")


def assert_head_secret_encrypted(*, repository: Path | None = None) -> None:
    """Require the pushed repository tip to retain an encrypted secret document."""
    present, content = _git_file("HEAD", repository=repository)
    if not present:
        raise SecretSafetyError(f"refusing push: {SECRET_PATH} is missing from HEAD")
    if not _encrypted_content(content):
        raise SecretSafetyError(f"refusing push: {SECRET_PATH} in HEAD is not sops-encrypted")


def assert_outgoing_secrets_encrypted(
    commits: Iterable[str], *, repository: Path | None = None,
) -> None:
    unsafe: list[str] = []
    for commit in sorted(set(commits)):
        present, content = _git_file(commit, repository=repository)
        if present and not _encrypted_content(content):
            unsafe.append(commit[:12])
    if unsafe:
        revisions = ", ".join(unsafe)
        raise SecretSafetyError(
            f"refusing push: plaintext {SECRET_PATH} exists in outgoing commit(s): {revisions}"
        )


def assert_git_secret_safety(
    *, outgoing_commits: Iterable[str] = (), repository: Path | None = None,
) -> None:
    root = repository or DOTFILES_DIR
    assert_worktree_secret_encrypted(root / SECRET_PATH)
    assert_index_secret_encrypted(repository=root)
    assert_head_secret_encrypted(repository=root)
    assert_outgoing_secrets_encrypted(outgoing_commits, repository=root)
