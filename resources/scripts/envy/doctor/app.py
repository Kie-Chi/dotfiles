"""Typer app for `envy doctor`."""

import typer

from envy.doctor.selection import ONLY_HELP
from envy.doctor.runner import CHECKS, exit_code, render, run_sections

app = typer.Typer(
    name="doctor",
    help="Check local dotfiles health, app state, login hints, and platform permissions.",
    rich_markup_mode="rich",
    no_args_is_help=False,
)


@app.callback(invoke_without_command=True)
def cmd_doctor(
    ctx: typer.Context,
    only: list[str] = typer.Option(None, "--only", "-o", help=ONLY_HELP),
    strict: bool = typer.Option(False, "--strict", help="Exit non-zero when warnings are present."),
):
    """Run all doctor checks."""
    if ctx.invoked_subcommand is not None:
        return
    results = run_sections(list(CHECKS.keys()), only)
    render(results)
    raise typer.Exit(exit_code(results, strict=strict))


@app.command(name="all")
def cmd_all(
    only: list[str] = typer.Option(None, "--only", "-o", help=ONLY_HELP),
    strict: bool = typer.Option(False, "--strict", help="Exit non-zero when warnings are present."),
):
    """Run all doctor checks."""
    results = run_sections(list(CHECKS.keys()), only)
    render(results)
    raise typer.Exit(exit_code(results, strict=strict))


@app.command(name="config")
def cmd_config(
    only: list[str] = typer.Option(None, "--only", "-o", help=ONLY_HELP),
    strict: bool = typer.Option(False, "--strict", help="Exit non-zero when warnings are present."),
):
    """Check dotfiles config and secrets."""
    results = run_sections(["config"], only)
    render(results)
    raise typer.Exit(exit_code(results, strict=strict))


@app.command(name="apps")
def cmd_apps(
    only: list[str] = typer.Option(None, "--only", "-o", help=ONLY_HELP),
    strict: bool = typer.Option(False, "--strict", help="Exit non-zero when warnings are present."),
):
    """Check app installation, running status, local state, and login hints."""
    results = run_sections(["apps"], only)
    render(results)
    raise typer.Exit(exit_code(results, strict=strict))
