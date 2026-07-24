"""One subprocess boundary with consistent diagnostics and failure semantics."""

from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path
from typing import Mapping, Sequence

from envy import log


class CommandError(subprocess.CalledProcessError):
    """A subprocess failure safe to render once at the CLI boundary."""

    def __init__(self, result: subprocess.CompletedProcess[str]):
        super().__init__(
            result.returncode,
            result.args,
            output=result.stdout,
            stderr=result.stderr,
        )


def command_display(command: Sequence[str]) -> str:
    return shlex.join(str(part) for part in command)


def run_process(
    command: Sequence[str],
    *,
    cwd: Path | str | None = None,
    env: Mapping[str, str] | None = None,
    stdin_data: str | None = None,
    capture: bool = False,
    check: bool = True,
    timeout: int | float | None = None,
) -> subprocess.CompletedProcess[str]:
    argv = [str(part) for part in command]
    log.debug("cmd", "running", cmd=command_display(argv), cwd=str(cwd or Path.cwd()))
    try:
        result = subprocess.run(
            argv,
            cwd=str(cwd) if cwd is not None else None,
            env=dict(env) if env is not None else None,
            input=stdin_data,
            text=True,
            capture_output=capture,
            check=False,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        result = subprocess.CompletedProcess(argv, 127, "" if capture else None, str(exc))
    except subprocess.TimeoutExpired as exc:
        stderr = f"command timed out after {timeout} seconds"
        result = subprocess.CompletedProcess(argv, 124, exc.stdout, stderr)

    if log.is_debug():
        if result.stdout:
            log.debug("cmd", "stdout", output=result.stdout[:500])
        if result.stderr:
            log.debug("cmd", "stderr", output=result.stderr[:500])
    if check and result.returncode != 0:
        raise CommandError(result)
    return result


def render_command_error(error: CommandError) -> None:
    command = error.cmd if isinstance(error.cmd, list) else [str(error.cmd)]
    log.error("command", "external command failed", exit_code=error.returncode)
    log.hint(command_display(command))
    if error.stderr:
        last_line = str(error.stderr).strip().splitlines()[-1:]
        if last_line:
            log.hint(last_line[0][:500])


def environment_with(base: Mapping[str, str] | None = None, **values: str) -> dict[str, str]:
    result = dict(base or os.environ)
    result.update(values)
    return result
