"""Command execution probes."""

import shutil
import subprocess


def run(cmd: list[str], timeout: int = 5) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=124,
            stdout=_output_text(exc.stdout),
            stderr=_output_text(exc.stderr) or f"timed out after {timeout}s",
        )


def exists(name: str) -> bool:
    return shutil.which(name) is not None


def _output_text(value: str | bytes | None) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode(errors="replace")
    return value
