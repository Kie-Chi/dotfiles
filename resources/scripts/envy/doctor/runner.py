"""Doctor orchestration and terminal rendering."""

from collections.abc import Callable, Iterable

from rich.table import Table

from envy import log
from envy.doctor.checks import apps, config
from envy.doctor.model import (
    SECTION_AUTH,
    SECTION_CONFIG,
    SECTION_DOCTOR,
    SECTION_INSTALL,
    SECTION_PRIVACY,
    SECTION_RUNTIME,
    SECTION_SECRETS,
    SECTION_STATE,
    SECTION_SYNC,
    SECTION_SYSTEM,
    CheckResult,
    DoctorSection,
)
from envy.doctor.selection import DoctorSelection, filter_results, parse_only, selection_errors

CheckFn = Callable[[], list[CheckResult]]

CHECKS: dict[str, CheckFn] = {
    "config": config.run_checks,
    "apps": apps.run_checks,
}


CONFIG_RESULT_SECTIONS: set[DoctorSection] = {
    SECTION_DOCTOR,
    SECTION_CONFIG,
    SECTION_SECRETS,
}

APP_RESULT_SECTIONS: set[DoctorSection] = {
    SECTION_INSTALL,
    SECTION_RUNTIME,
    SECTION_STATE,
    SECTION_AUTH,
    SECTION_SYNC,
    SECTION_PRIVACY,
    SECTION_SYSTEM,
}


def run_sections(sections: list[str], selected: Iterable[str] | None = None) -> list[CheckResult]:
    selection = parse_only(selected)
    allow_apps = "apps" in sections
    errors = selection_errors(selection, allow_apps=allow_apps)
    if selection.has_parse_errors:
        return errors

    results: list[CheckResult] = []
    for section in sections:
        if not _scope_needed(section, selection):
            continue
        check = CHECKS[section]
        log.step("doctor", f"checking {section}")
        if section == "apps":
            results.extend(apps.run_checks(selection=selection))
        else:
            results.extend(check())
    return errors + filter_results(results, selection)


def _scope_needed(section: str, selection: DoctorSelection) -> bool:
    if selection.apps and section != "apps":
        return False
    if not selection.sections:
        return True
    if section == "config":
        return bool(selection.sections & CONFIG_RESULT_SECTIONS)
    if section == "apps":
        return bool(selection.sections & APP_RESULT_SECTIONS)
    return True


def render(results: list[CheckResult]) -> None:
    table = Table(title="envy doctor", expand=True)
    table.add_column("Status", width=6, no_wrap=True)
    table.add_column("Section", width=11, no_wrap=True)
    table.add_column("Check", min_width=18, max_width=28, no_wrap=True, overflow="ellipsis")
    table.add_column("Result", min_width=24, no_wrap=True, overflow="ellipsis", ratio=1)

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
