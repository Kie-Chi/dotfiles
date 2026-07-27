"""One subprocess boundary with consistent diagnostics and failure semantics."""

from __future__ import annotations

import os
import re
import shlex
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Mapping, Sequence
from urllib.parse import urlsplit, urlunsplit

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
    return shlex.join(_redacted_command(command))


def _redact_url(value: str) -> str:
    try:
        parsed = urlsplit(value)
    except ValueError:
        return value
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return value
    hostname = parsed.hostname or ""
    if parsed.port:
        hostname += f":{parsed.port}"
    if parsed.username or parsed.password:
        hostname = f"<redacted>@{hostname}"
    query = "<redacted>" if parsed.query else ""
    return urlunsplit((parsed.scheme, hostname, parsed.path, query, ""))


def _redacted_command(command: Sequence[str]) -> list[str]:
    """Keep diagnostics useful without echoing common secret-bearing arguments."""
    sensitive = re.compile(r"(?:pass(?:word)?|token|secret|api[-_]?key|credential)", re.I)
    result: list[str] = []
    redact_next = False
    for raw in command:
        value = str(raw)
        if redact_next:
            result.append("<redacted>")
            redact_next = False
            continue
        if value.startswith("-") and "=" in value:
            option, option_value = value.split("=", 1)
            if sensitive.search(option):
                result.append(f"{option}=<redacted>")
                continue
            value = f"{option}={_redact_url(option_value)}"
        elif value.startswith("-") and sensitive.search(value):
            result.append(value)
            redact_next = True
            continue
        else:
            value = _redact_url(value)
        result.append(value)
    return result


def _activity_label(command: Sequence[str]) -> str:
    names = [Path(str(part)).name for part in command]
    if not names:
        return "external command"
    executable = names[0]
    index = 1
    if executable == "sudo":
        while index < len(names) and names[index].startswith("-"):
            index += 1
        if index < len(names):
            executable = names[index]
            index += 1
    subcommand = next(
        (part for part in names[index:] if not part.startswith("-")),
        "",
    )
    return " ".join(part for part in (executable, subcommand) if part)[:80]


class _ActivityReporter:
    """Emit a low-noise heartbeat while a foreground command is silent."""

    def __init__(self, label: str):
        self.label = label
        self.started = time.monotonic()
        self.stop_event = threading.Event()
        self.announced = False
        self.thread: threading.Thread | None = None

    def start(self) -> None:
        enabled = os.environ.get("ENVY_ACTIVITY", "1").strip().casefold()
        if (
            enabled in {"0", "false", "no", "off"}
            or not sys.stderr.isatty()
            or threading.current_thread() is not threading.main_thread()
        ):
            return
        delay = 3.0 if log.is_debug() else 5.0
        interval = 5.0 if log.is_debug() else 10.0

        def report() -> None:
            if self.stop_event.wait(delay):
                return
            while not self.stop_event.is_set():
                self.announced = True
                elapsed = int(time.monotonic() - self.started)
                log.activity(
                    "command",
                    "still running; Ctrl-C cancels",
                    task=self.label,
                    elapsed=f"{elapsed}s",
                )
                if self.stop_event.wait(interval):
                    return

        self.thread = threading.Thread(target=report, name="envy-activity", daemon=True)
        self.thread.start()

    def stop(self) -> float:
        self.stop_event.set()
        if self.thread is not None:
            self.thread.join(timeout=0.2)
        return time.monotonic() - self.started


def run_process(
    command: Sequence[str],
    *,
    cwd: Path | str | None = None,
    env: Mapping[str, str] | None = None,
    stdin_data: str | None = None,
    capture: bool = False,
    check: bool = True,
    timeout: int | float | None = None,
    activity: str | None = None,
) -> subprocess.CompletedProcess[str]:
    argv = [str(part) for part in command]
    displayed = command_display(argv)
    reporter = _ActivityReporter(activity or _activity_label(argv))
    log.debug(
        "cmd", "start", command=displayed, cwd=str(cwd or Path.cwd()),
        capture=str(capture).lower(), timeout=timeout if timeout is not None else "none",
    )
    reporter.start()
    try:
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
    finally:
        duration = reporter.stop()

    if reporter.announced:
        log.activity(
            "command", "finished", task=reporter.label,
            elapsed=f"{duration:.1f}s", exit_code=result.returncode,
        )

    if log.is_debug():
        log.debug(
            "cmd", "finish", command=displayed,
            elapsed=f"{duration:.3f}s", exit_code=result.returncode,
            stdout_chars=len(result.stdout or ""), stderr_chars=len(result.stderr or ""),
        )
    if check and result.returncode != 0:
        raise CommandError(result)
    return result


def render_command_error(error: CommandError) -> None:
    command = error.cmd if isinstance(error.cmd, list) else [str(error.cmd)]
    log.error("command", "external command failed", exit_code=error.returncode)
    log.hint(command_display(command))
    if error.stderr:
        lines = [line.strip() for line in str(error.stderr).splitlines() if line.strip()]
        if log.is_debug():
            selected = lines[-12:]
        else:
            important = [
                line for line in lines
                if re.search(r"\b(?:error|failed|failure|denied|timed out)\b", line, re.I)
            ]
            selected = [*(important[-2:]), *(lines[-2:])]
        for line in dict.fromkeys(selected):
            log.hint(line[:500])


def environment_with(base: Mapping[str, str] | None = None, **values: str) -> dict[str, str]:
    result = dict(base or os.environ)
    result.update(values)
    return result
