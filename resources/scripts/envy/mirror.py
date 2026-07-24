"""Read-only mirror policy inspection and connectivity probes."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import Any, Iterator

import typer
from rich.table import Table

from envy import log
from envy.evaluation import machine_manifest


app = typer.Typer(
    name="mirror",
    help="Inspect and probe the evaluated network mirror policy.",
    rich_markup_mode="rich",
    no_args_is_help=True,
)


@dataclass(frozen=True)
class ProbeResult:
    name: str
    url: str
    ok: bool
    status: str
    elapsed_ms: int | None
    detail: str = ""


def mirror_entries(mirrors: dict[str, Any]) -> Iterator[tuple[str, str]]:
    """Flatten configured mirror values while hiding probe-only metadata."""

    def walk(prefix: str, value: Any) -> Iterator[tuple[str, str]]:
        if isinstance(value, dict):
            for key in sorted(value):
                if not prefix and key == "probes":
                    continue
                next_prefix = f"{prefix}.{key}" if prefix else str(key)
                yield from walk(next_prefix, value[key])
        elif isinstance(value, list):
            for index, item in enumerate(value):
                yield from walk(f"{prefix}[{index}]", item)
        elif value is None:
            yield prefix, "disabled"
        elif isinstance(value, bool):
            yield prefix, "true" if value else "false"
        else:
            yield prefix, str(value)

    if "mode" in mirrors:
        yield "mode", str(mirrors["mode"])
    for key in sorted(key for key in mirrors if key not in {"mode", "probes"}):
        yield from walk(key, mirrors[key])


def probe_specs(mirrors: dict[str, Any]) -> list[tuple[str, str]]:
    values = mirrors.get("probes", [])
    if not isinstance(values, list):
        return []
    specs: list[tuple[str, str]] = []
    for value in values:
        if not isinstance(value, dict):
            continue
        name = value.get("name")
        url = value.get("url")
        if isinstance(name, str) and isinstance(url, str):
            specs.append((name, url))
    return specs


def probe_endpoint(name: str, url: str, timeout: int = 15) -> ProbeResult:
    """Probe one catalog endpoint without changing any local settings."""
    try:
        result = subprocess.run(
            [
                "curl",
                "--head",
                "--location",
                "--silent",
                "--show-error",
                "--output", "/dev/null",
                "--connect-timeout", "5",
                "--max-time", str(timeout),
                "--write-out", "%{http_code}\t%{time_total}",
                url,
            ],
            capture_output=True,
            text=True,
            timeout=timeout + 2,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return ProbeResult(name, url, False, "error", None, str(exc))

    status, separator, elapsed = result.stdout.strip().partition("\t")
    try:
        status_code = int(status)
    except ValueError:
        status_code = 0
    try:
        elapsed_ms = round(float(elapsed) * 1000) if separator else None
    except ValueError:
        elapsed_ms = None
    ok = result.returncode == 0 and 200 <= status_code < 400
    detail = result.stderr.strip()
    return ProbeResult(name, url, ok, status or "error", elapsed_ms, detail)


def _manifest_or_exit(refresh: bool) -> dict[str, Any]:
    manifest = machine_manifest(refresh=refresh)
    mirrors = manifest.get("mirrors") if isinstance(manifest, dict) else None
    if not isinstance(mirrors, dict):
        log.error("mirror", "evaluated mirror policy is unavailable")
        log.hint("Run: envy config check")
        raise typer.Exit(code=1)
    return {"manifest": manifest, "mirrors": mirrors}


@app.command(name="status")
def cmd_status(
    refresh: bool = typer.Option(False, "--refresh", help="Ignore the saved manifest cache."),
):
    """Show the effective mirror endpoints for the selected machine."""
    evaluated = _manifest_or_exit(refresh)
    manifest = evaluated["manifest"]
    table = Table(title=f"Mirror policy - {manifest.get('id', 'current')}")
    table.add_column("Setting", style="cyan", no_wrap=True)
    table.add_column("Value")
    for path, value in mirror_entries(evaluated["mirrors"]):
        table.add_row(path, value)
    log.console.print(table)


@app.command(name="probe")
def cmd_probe(
    refresh: bool = typer.Option(False, "--refresh", help="Ignore the saved manifest cache."),
    timeout: int = typer.Option(15, "--timeout", min=1, max=120, help="Per-endpoint timeout in seconds."),
):
    """Test effective mirror endpoints without modifying configuration."""
    evaluated = _manifest_or_exit(refresh)
    specs = probe_specs(evaluated["mirrors"])
    if not specs:
        log.warn("mirror", "no probe endpoints are declared")
        return

    table = Table(title=f"Mirror probe - {evaluated['manifest'].get('id', 'current')}")
    table.add_column("State", no_wrap=True)
    table.add_column("Endpoint", style="cyan", no_wrap=True)
    table.add_column("HTTP", justify="right")
    table.add_column("Latency", justify="right")
    table.add_column("URL")
    failed = 0
    for name, url in specs:
        result = probe_endpoint(name, url, timeout=timeout)
        if not result.ok:
            failed += 1
        table.add_row(
            "[green]OK[/green]" if result.ok else "[red]FAIL[/red]",
            result.name,
            result.status,
            f"{result.elapsed_ms} ms" if result.elapsed_ms is not None else "-",
            result.url,
        )
        if result.detail:
            log.debug("mirror", "probe detail", endpoint=result.name, detail=result.detail)
    log.console.print(table)
    if failed:
        log.warn("mirror", "one or more endpoints failed", failed=failed, total=len(specs))
        raise typer.Exit(code=1)
