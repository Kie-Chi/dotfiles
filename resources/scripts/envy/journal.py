"""Persistent operation journal for state-changing envy commands.

Records a compact, append-only JSONL history of apply/sync/push/update/rollback/
clean operations so the CLI and TUI can answer "what did I run, when, and did it
succeed" — something Nix generations alone do not capture.

Storage lives under the persistent state directory (see ``utils.state_dir``), not
the cache, so it survives cache clears and ``envy clean``.
"""

from __future__ import annotations

import contextlib
import functools
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterator

import typer
from rich.table import Table

from envy import log
from envy.process import CommandError
from envy.secure_io import ensure_private_directory
from envy.utils import current_machine_id, platform_name, state_dir

JOURNAL_SCHEMA_VERSION = 1


def journal_path() -> Path:
    return state_dir() / "journal.jsonl"


def append(record: dict[str, Any]) -> None:
    """Append one JSONL record durably.

    A single ``write`` of a sub-PIPE_BUF line is atomic against concurrent
    envy invocations on POSIX, which is sufficient for a low-concurrency CLI.
    Failures here must never break the wrapped operation, so I/O errors are
    swallowed after a debug note.
    """
    path = journal_path()
    try:
        ensure_private_directory(path.parent)
        line = json.dumps(record, ensure_ascii=False, default=str) + "\n"
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line)
            handle.flush()
            os.fsync(handle.fileno())
    except OSError as exc:
        log.debug("journal", "append failed", error=str(exc))


def read(
    *,
    limit: int | None = None,
    failed: bool = False,
    operation: str | None = None,
) -> list[dict[str, Any]]:
    """Return journal records newest-first, after optional filtering."""
    path = journal_path()
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    log.debug("journal", "skipped malformed line")
                    continue
                if not isinstance(record, dict):
                    continue
                if failed and record.get("result") != "fail":
                    continue
                if operation is not None and record.get("operation") != operation:
                    continue
                records.append(record)
    except OSError as exc:
        log.debug("journal", "read failed", error=str(exc))
        return []
    records.reverse()
    if limit is not None:
        return records[:limit]
    return records


@contextlib.contextmanager
def _span(operation: str, detail: dict[str, Any]) -> Iterator[None]:
    """Time a wrapped operation and record its outcome, re-raising everything."""
    started = time.monotonic()
    result = "fail"
    exit_code = 1
    try:
        yield
        result = "ok"
        exit_code = 0
    except typer.Exit as exc:
        code = getattr(exc, "exit_code", getattr(exc, "code", 0)) or 0
        result = "ok" if code == 0 else "fail"
        exit_code = code
        raise
    except typer.Abort:
        result = "fail"
        exit_code = 1
        raise
    except CommandError as exc:
        result = "fail"
        exit_code = exc.returncode
        raise
    except BaseException:
        result = "fail"
        exit_code = 1
        raise
    finally:
        duration_ms = int((time.monotonic() - started) * 1000)
        append(
            {
                "schemaVersion": JOURNAL_SCHEMA_VERSION,
                "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
                "operation": operation,
                "machine": current_machine_id(),
                "platform": platform_name(),
                "durationMs": duration_ms,
                "result": result,
                "exitCode": exit_code,
                "detail": detail or {},
            }
        )


def record_operation(
    operation: str,
    detail: Callable[..., dict[str, Any]] | None = None,
    skip: Callable[..., bool] | None = None,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorate a workflow entry point to record a journal entry for each run.

    ``detail`` receives the wrapped call's args/kwargs and returns a small dict;
    keep it defensive (absorb ``**kwargs``) so signature changes never raise at
    call time. ``skip`` receives the same args and, when it returns True, runs
    the wrapped function without journaling — used to exclude read-only paths
    (e.g. ``rollback --dry-run`` / ``rollback list``).
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                if skip is not None and skip(*args, **kwargs):
                    return func(*args, **kwargs)
            except Exception as exc:  # noqa: BLE001 - skip must never break the op
                log.debug("journal", "skip callback failed", error=str(exc))
            try:
                detail_dict = detail(*args, **kwargs) if detail is not None else {}
            except Exception as exc:  # noqa: BLE001 - detail must never break the op
                log.debug("journal", "detail callback failed", error=str(exc))
                detail_dict = {}
            with _span(operation, detail_dict):
                return func(*args, **kwargs)

        return wrapper

    return decorator


# ==========================================
# RENDERING (envy log)
# ==========================================


def _format_detail(detail: Any) -> str:
    if not isinstance(detail, dict) or not detail:
        return ""
    return " ".join(f"{key}={value}" for key, value in detail.items())


def _duration_text(duration_ms: Any) -> str:
    try:
        seconds = int(duration_ms) / 1000.0
    except (TypeError, ValueError):
        return "—"
    return f"{seconds:.1f}s"


def snapshot(
    *,
    limit: int | None = None,
    failed: bool = False,
    operation: str | None = None,
) -> dict[str, Any]:
    return {
        "schemaVersion": JOURNAL_SCHEMA_VERSION,
        "machine": current_machine_id(),
        "platform": platform_name(),
        "entries": read(limit=limit, failed=failed, operation=operation),
    }


def render(payload: dict[str, Any]) -> None:
    entries = payload.get("entries") or []
    if not entries:
        log.warn("journal", "no operations recorded yet")
        return
    table = Table(title="Envy operation journal", title_style="cyan", expand=False)
    table.add_column("Time", style="dim", no_wrap=True)
    table.add_column("Operation", style="cyan", no_wrap=True)
    table.add_column("Result", no_wrap=True)
    table.add_column("Duration", justify="right", no_wrap=True)
    table.add_column("Machine", no_wrap=True)
    table.add_column("Detail")
    for entry in entries:
        result = str(entry.get("result", ""))
        result_cell = (
            "[green]ok[/green]" if result == "ok" else f"[red]{result or 'fail'}[/red]"
        )
        table.add_row(
            str(entry.get("timestamp", "")),
            str(entry.get("operation", "")),
            result_cell,
            _duration_text(entry.get("durationMs")),
            str(entry.get("machine", "")),
            _format_detail(entry.get("detail")),
        )
    log.console.print(table)


def show_log(
    *,
    json_output: bool = False,
    limit: int | None = None,
    failed: bool = False,
    operation: str | None = None,
) -> None:
    payload = snapshot(limit=limit, failed=failed, operation=operation)
    if json_output:
        log.console.print_json(json.dumps(payload, ensure_ascii=False, default=str))
    else:
        render(payload)
