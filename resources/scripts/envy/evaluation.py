"""Evaluate and cache the selected Nix machine for Envy's read-only views."""

import hashlib
import json
import os
import stat
import subprocess
import tempfile
import time
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterator

from envy.utils import DOTFILES_DIR, current_machine_id, machine_manifest_attr, platform_name


SELECTION_GROUPS = (
    ("packages", "home", "envy.packages.home", None),
    ("packages", "system", "envy.darwin.packages.system", "darwin"),
    ("packages", "fonts", "envy.darwin.packages.fonts", "darwin"),
    ("homebrew", "brews", "envy.darwin.homebrew.brews", "darwin"),
    ("homebrew", "casks", "envy.darwin.homebrew.casks", "darwin"),
    ("homebrew", "taps", "envy.darwin.homebrew.taps", "darwin"),
)

CACHE_SCHEMA = 1
_CACHE_ENV = "ENVY_NO_CACHE"
_COMMAND_TIMEOUT = 5


def _cache_disabled() -> bool:
    value = os.environ.get(_CACHE_ENV, "").strip().casefold()
    return value not in {"", "0", "false", "no", "off"}


def _cache_path(machine_id: str) -> Path:
    root = os.environ.get("XDG_CACHE_HOME", "").strip()
    cache_root = Path(root).expanduser() if root else Path.home() / ".cache"
    return cache_root / "envy" / "manifests" / platform_name() / f"{machine_id}.json"


def _command_bytes(command: list[str]) -> bytes | None:
    try:
        result = subprocess.run(
            command,
            cwd=str(DOTFILES_DIR),
            capture_output=True,
            timeout=_COMMAND_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout if result.returncode == 0 else None


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _untracked_digest(raw_paths: bytes) -> str | None:
    """Hash untracked paths, file types, modes, and contents without Git filters."""
    digest = hashlib.sha256()
    for raw_path in sorted(path for path in raw_paths.split(b"\0") if path):
        path = DOTFILES_DIR / os.fsdecode(raw_path)
        try:
            metadata = path.lstat()
        except OSError:
            return None

        digest.update(len(raw_path).to_bytes(8, "big"))
        digest.update(raw_path)
        digest.update(stat.S_IFMT(metadata.st_mode).to_bytes(4, "big"))
        digest.update((metadata.st_mode & 0o777).to_bytes(2, "big"))

        try:
            if path.is_symlink():
                target = os.fsencode(os.readlink(path))
                digest.update(len(target).to_bytes(8, "big"))
                digest.update(target)
            elif path.is_file():
                with path.open("rb") as handle:
                    while chunk := handle.read(1024 * 1024):
                        digest.update(chunk)
            else:
                # Git normally reports files and symlinks here. Avoid caching
                # an unusual filesystem object that Nix may read differently.
                return None
        except OSError:
            return None
    return digest.hexdigest()


def _repository_fingerprint(machine_id: str) -> str | None:
    """Return a content fingerprint for every repository layer Nix can see."""
    head = _command_bytes(["git", "rev-parse", "--verify", "HEAD"])
    index = _command_bytes(["git", "ls-files", "--stage", "-z"])
    worktree = _command_bytes([
        "git", "diff", "--binary", "--full-index", "--no-ext-diff",
        "--no-textconv", "--no-color", "--no-renames", "--src-prefix=a/",
        "--dst-prefix=b/", "--",
    ])
    untracked = _command_bytes(["git", "ls-files", "--others", "--exclude-standard", "-z"])
    nix_version = _command_bytes(["nix", "--version"])
    if None in (head, index, worktree, untracked, nix_version):
        return None

    untracked_hash = _untracked_digest(untracked)
    if untracked_hash is None:
        return None
    inputs = {
        "schema": CACHE_SCHEMA,
        "machine": machine_id,
        "platform": platform_name(),
        "head": head.decode(errors="replace").strip(),
        # Hashing the staged entries is read-only, unlike `git write-tree`,
        # while still covering paths, modes, stages, and blob object IDs.
        "index": _digest(index),
        "worktree": _digest(worktree),
        "untracked": untracked_hash,
        "nix": nix_version.decode(errors="replace").strip(),
    }
    encoded = json.dumps(inputs, sort_keys=True, separators=(",", ":")).encode()
    return _digest(encoded)


def _read_cache(machine_id: str, fingerprint: str) -> dict[str, Any] | None:
    try:
        value = json.loads(_cache_path(machine_id).read_text())
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(value, dict):
        return None
    manifest = value.get("manifest")
    if (
        value.get("schema") != CACHE_SCHEMA
        or value.get("machine") != machine_id
        or value.get("fingerprint") != fingerprint
        or not isinstance(manifest, dict)
    ):
        return None
    return manifest


def _write_cache(machine_id: str, fingerprint: str, manifest: dict[str, Any]) -> None:
    """Atomically store a successful evaluation; cache failures are non-fatal."""
    path = _cache_path(machine_id)
    temporary: Path | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        payload = {
            "schema": CACHE_SCHEMA,
            "machine": machine_id,
            "fingerprint": fingerprint,
            "created_at": int(time.time()),
            "manifest": manifest,
        }
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
        ) as handle:
            temporary = Path(handle.name)
            json.dump(payload, handle, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            handle.flush()
            os.fsync(handle.fileno())
        temporary.chmod(0o600)
        os.replace(temporary, path)
    except OSError:
        pass
    finally:
        if temporary is not None and temporary.exists():
            try:
                temporary.unlink()
            except OSError:
                pass


def _evaluate_machine_manifest(machine_id: str) -> dict[str, Any] | None:
    attr = machine_manifest_attr(machine_id)
    try:
        result = subprocess.run(
            ["nix", "eval", "--impure", attr, "--json"],
            cwd=str(DOTFILES_DIR), capture_output=True, text=True,
            timeout=30, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def _load_machine_manifest(*, read_cache: bool, write_cache: bool) -> dict[str, Any] | None:
    machine_id = current_machine_id()
    fingerprint = _repository_fingerprint(machine_id) if (read_cache or write_cache) else None
    if read_cache and fingerprint is not None:
        cached = _read_cache(machine_id, fingerprint)
        if cached is not None:
            return cached

    manifest = _evaluate_machine_manifest(machine_id)
    if manifest is None or not write_cache or fingerprint is None:
        return manifest

    # Never associate an evaluation with a source snapshot that changed while
    # Nix was running. A later invocation will evaluate the new snapshot.
    if _repository_fingerprint(machine_id) == fingerprint:
        _write_cache(machine_id, fingerprint, manifest)
    return manifest


@lru_cache(maxsize=1)
def _memoized_machine_manifest() -> dict[str, Any] | None:
    return _load_machine_manifest(read_cache=True, write_cache=True)


def invalidate_machine_manifest() -> None:
    """Clear the current process' memoized manifest after a source write."""
    _memoized_machine_manifest.cache_clear()


def machine_manifest(*, refresh: bool = False) -> dict[str, Any] | None:
    """Return the evaluated manifest, reusing a Git-fingerprinted disk cache."""
    if refresh:
        invalidate_machine_manifest()
        return _load_machine_manifest(read_cache=False, write_cache=True)
    if _cache_disabled():
        invalidate_machine_manifest()
        return _load_machine_manifest(read_cache=False, write_cache=False)
    return _memoized_machine_manifest()


def manifest_settings(manifest: dict[str, Any] | None) -> dict[str, str]:
    """Normalize evaluated scalar settings for the config editor/view."""
    if not manifest or not isinstance(manifest.get("settings"), dict):
        return {}
    values: dict[str, str] = {}
    for path, value in manifest["settings"].items():
        if isinstance(value, bool):
            values[str(path)] = "true" if value else "false"
        elif isinstance(value, (str, int, float)):
            values[str(path)] = str(value)
    return values


def manifest_selection_rows(
    manifest: dict[str, Any] | None,
) -> Iterator[tuple[str, list[str], list[str], list[str]]]:
    """Yield path plus evaluated include/exclude/effective selection lists."""
    if not manifest:
        return
    inclusions = manifest.get("inclusions", {})
    exclusions = manifest.get("exclusions", {})
    platform = manifest.get("platform")
    for domain, group, path, required_platform in SELECTION_GROUPS:
        if required_platform is not None and platform != required_platform:
            continue
        include = _string_list(_nested(inclusions, domain, group))
        exclude = _string_list(_nested(exclusions, domain, group))
        effective = _string_list(_nested(manifest, domain, group))
        yield path, include, exclude, effective


def _nested(data: Any, first: str, second: str) -> Any:
    if not isinstance(data, dict):
        return []
    section = data.get(first, {})
    return section.get(second, []) if isinstance(section, dict) else []


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]
