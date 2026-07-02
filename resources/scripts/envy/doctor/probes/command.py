"""Command execution probes."""

import shutil
import subprocess


def run(cmd: list[str], timeout: int = 5) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def exists(name: str) -> bool:
    return shutil.which(name) is not None
