"""Small recoverable file transactions for multi-file envY workflows."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from envy.secure_io import atomic_write_bytes


@dataclass(frozen=True)
class FileSnapshot:
    path: Path
    existed: bool
    data: bytes
    mode: int

    @classmethod
    def capture(cls, path: Path) -> "FileSnapshot":
        if not path.exists():
            return cls(path=path, existed=False, data=b"", mode=0o600)
        return cls(
            path=path,
            existed=True,
            data=path.read_bytes(),
            mode=path.stat().st_mode & 0o777,
        )

    def restore(self) -> None:
        if self.existed:
            atomic_write_bytes(self.path, self.data, mode=self.mode)
        elif self.path.exists():
            self.path.unlink()


class FileTransaction:
    """Restore captured paths unless commit() is reached without an exception."""

    def __init__(self, paths: list[Path]):
        self.snapshots = [FileSnapshot.capture(path) for path in paths]
        self._committed = False

    def __enter__(self) -> "FileTransaction":
        return self

    def commit(self) -> None:
        self._committed = True

    def rollback(self) -> None:
        errors: list[OSError] = []
        for snapshot in reversed(self.snapshots):
            try:
                snapshot.restore()
            except OSError as exc:
                errors.append(exc)
        if errors:
            raise RuntimeError(f"failed to restore {len(errors)} transaction file(s)") from errors[0]

    def __exit__(self, exc_type, exc, traceback) -> bool:
        if exc_type is not None or not self._committed:
            self.rollback()
        return False
