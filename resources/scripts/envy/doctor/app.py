"""Typer app for `envy doctor`."""

import typer

from envy.doctor.checks import apps as app_checks
from envy.doctor.runner import CHECKS, exit_code, render, run_sections

app = typer.Typer(
    name="doctor",
    help="Check local dotfiles health, app state, login hints, and macOS permissions.",
    rich_markup_mode="rich",
    no_args_is_help=False,
)


@app.callback(invoke_without_command=True)
def cmd_doctor(
    ctx: typer.Context,
    strict: bool = typer.Option(False, "--strict", help="Exit non-zero when warnings are present."),
):
    """Run all doctor checks."""
    if ctx.invoked_subcommand is not None:
        return
    results = run_sections(list(CHECKS.keys()))
    render(results)
    raise typer.Exit(exit_code(results, strict=strict))


@app.command(name="all")
def cmd_all(
    strict: bool = typer.Option(False, "--strict", help="Exit non-zero when warnings are present."),
):
    """Run all doctor checks."""
    results = run_sections(list(CHECKS.keys()))
    render(results)
    raise typer.Exit(exit_code(results, strict=strict))


@app.command(name="config")
def cmd_config(
    strict: bool = typer.Option(False, "--strict", help="Exit non-zero when warnings are present."),
):
    """Check dotfiles config and secrets."""
    results = run_sections(["config"])
    render(results)
    raise typer.Exit(exit_code(results, strict=strict))


@app.command(name="apps")
def cmd_apps(
    only: list[str] = typer.Option(None, "--only", "-o", help="Only run selected app checks. Repeat or comma-separate values."),
    strict: bool = typer.Option(False, "--strict", help="Exit non-zero when warnings are present."),
):
    """Check app installation, running status, local state, and login hints."""
    results = app_checks.run_checks(only)
    render(results)
    raise typer.Exit(exit_code(results, strict=strict))


@app.command(name="permissions")
def cmd_permissions(
    strict: bool = typer.Option(False, "--strict", help="Exit non-zero when warnings are present."),
):
    """Check macOS TCC permissions for all apps that declare them."""
    from envy.doctor.checks.apps.checkers import check_permissions
    from envy.schemas.apps import ALL_APP_SPECS

    results = []
    for spec in ALL_APP_SPECS.values():
        if spec.permissions:
            results.extend(check_permissions(spec))
    render(results)
    raise typer.Exit(exit_code(results, strict=strict))
