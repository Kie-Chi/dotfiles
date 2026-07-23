"""Shared logging helpers for envy commands."""

import os
from typing import Any

from rich.console import Console

console = Console()


def is_debug() -> bool:
    return os.environ.get("ENVY_DEBUG") == "1"


def _format_kv(values: dict[str, Any]) -> str:
    if not values:
        return ""
    return " " + " ".join(f"{key}={value}" for key, value in values.items())


def step(scope: str, message: str, **values: Any) -> None:
    console.print(f"[cyan]-->[/cyan] {scope}: {message}{_format_kv(values)}")


def info(scope: str, message: str, **values: Any) -> None:
    console.print(f"[white]--[/white] {scope}: {message}{_format_kv(values)}")


def ok(scope: str, message: str, **values: Any) -> None:
    console.print(f"[green]OK[/green] {scope}: {message}{_format_kv(values)}")


def fix(scope: str, message: str, **values: Any) -> None:
    console.print(f"[green]FIX[/green] {scope}: {message}{_format_kv(values)}")


def warn(scope: str, message: str, **values: Any) -> None:
    console.print(f"[yellow]WARN[/yellow] {scope}: {message}{_format_kv(values)}")


def error(scope: str, message: str, **values: Any) -> None:
    console.print(f"[red]ERR[/red] {scope}: {message}{_format_kv(values)}")


def hint(message: str) -> None:
    console.print(f"[dim]    {message}[/dim]")


def debug(scope: str, message: str, **values: Any) -> None:
    if is_debug():
        console.print(f"[dim]DBG {scope}: {message}{_format_kv(values)}[/dim]")
