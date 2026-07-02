"""Doctor orchestration and terminal rendering."""

from collections.abc import Callable

from rich.table import Table

from envy import log
from envy.doctor.checks import apps, config
from envy.doctor.model import CheckResult

CheckFn = Callable[[], list[CheckResult]]

CHECKS: dict[str, CheckFn] = {
    "config": config.run_checks,
    "apps": apps.run_checks,
}


def run_sections(sections: list[str]) -> list[CheckResult]:
    results: list[CheckResult] = []
    for section in sections:
        check = CHECKS[section]
        log.step("doctor", f"checking {section}")
        results.extend(check())
    return results


def render(results: list[CheckResult]) -> None:
    table = Table(title="envy doctor")
    table.add_column("Status", no_wrap=True)
    table.add_column("Section", no_wrap=True)
    table.add_column("Check", no_wrap=True)
    table.add_column("Result")

    style = {
        "ok": "green",
        "warn": "yellow",
        "error": "red",
        "info": "cyan",
    }

    for result in results:
        table.add_row(
            f"[{style[result.status]}]{result.status.upper()}[/{style[result.status]}]",
            result.section,
            result.name,
            result.message,
        )

    log.console.print(table)

    hints = [result for result in results if result.hint]
    if hints:
        log.console.print("[bold]Hints[/bold]")
        for result in hints:
            log.console.print(f"[dim]- {result.section}/{result.name}: {result.hint}[/dim]")

    errors = sum(1 for result in results if result.failed)
    warnings = sum(1 for result in results if result.warned)
    if errors:
        log.error("doctor", "completed with errors", errors=errors, warnings=warnings)
    elif warnings:
        log.warn("doctor", "completed with warnings", warnings=warnings)
    else:
        log.ok("doctor", "all checks passed")


def exit_code(results: list[CheckResult], *, strict: bool = False) -> int:
    if any(result.failed for result in results):
        return 1
    if strict and any(result.warned for result in results):
        return 1
    return 0
