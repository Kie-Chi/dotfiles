"""Atomic filesystem helpers for Envy-managed public and sensitive files."""

from __future__ import annotations

import os
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


def ensure_private_directory(path: Path) -> None:
    """Create a private directory and remove group/other access if it exists."""
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.chmod(0o700)


def _fsync_directory(path: Path) -> None:
    """Best-effort directory sync so a completed replace survives a crash."""
    try:
        descriptor = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


def atomic_write_bytes(
    path: Path,
    data: bytes,
    *,
    mode: int | None = None,
    private_parent: bool = False,
) -> None:
    """Write bytes through a mode-safe temporary file and atomically replace path."""
    if private_parent:
        ensure_private_directory(path.parent)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)

    target_mode = mode
    if target_mode is None:
        try:
            target_mode = path.stat().st_mode & 0o777
        except OSError:
            target_mode = 0o644

    descriptor, temporary_name = tempfile.mkstemp(
        dir=str(path.parent), prefix=f".{path.name}.envy-"
    )
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, target_mode)
        with os.fdopen(descriptor, "wb") as handle:
            descriptor = -1
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        _fsync_directory(path.parent)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if temporary.exists():
            temporary.unlink()


def atomic_write_text(
    path: Path,
    text: str,
    *,
    mode: int | None = None,
    private_parent: bool = False,
) -> None:
    atomic_write_bytes(
        path,
        text.encode("utf-8"),
        mode=mode,
        private_parent=private_parent,
    )


def secure_copy(source: Path, destination: Path) -> None:
    """Copy sensitive bytes without ever creating a broadly readable target."""
    atomic_write_bytes(destination, source.read_bytes(), mode=0o600)


@contextmanager
def secure_temporary_path(
    directory: Path,
    *,
    prefix: str = ".envy-",
    suffix: str = "",
) -> Iterator[Path]:
    """Yield a same-filesystem 0600 temporary path and always remove it."""
    directory.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(dir=str(directory), prefix=prefix, suffix=suffix)
    path = Path(name)
    try:
        os.fchmod(descriptor, 0o600)
        os.close(descriptor)
        yield path
    finally:
        if path.exists():
            path.unlink()


def replace_prepared_file(source: Path, destination: Path, *, mode: int = 0o644) -> None:
    """Durably replace destination with an already prepared same-directory file."""
    source.chmod(mode)
    with source.open("rb") as handle:
        os.fsync(handle.fileno())
    os.replace(source, destination)
    _fsync_directory(destination.parent)
