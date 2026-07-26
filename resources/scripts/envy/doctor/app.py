"""Typer app for `envy doctor`."""

import typer

from envy.doctor.selection import ONLY_HELP
from envy.doctor.runner import CHECKS, DEFAULT_CHECKS, exit_code, render, render_json, run_sections


def _run(
    sections: list[str],
    only: list[str] | None,
    *,
    strict: bool,
    json_output: bool,
) -> None:
    results = run_sections(sections, only, log_progress=not json_output)
    if json_output:
        render_json(results, strict=strict)
    else:
        render(results)
    raise typer.Exit(exit_code(results, strict=strict))

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
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON."),
):
    """Run all doctor checks."""
    if ctx.invoked_subcommand is not None:
        return
    _run(DEFAULT_CHECKS, only, strict=strict, json_output=json_output)


@app.command(name="all")
def cmd_all(
    only: list[str] = typer.Option(None, "--only", "-o", help=ONLY_HELP),
    strict: bool = typer.Option(False, "--strict", help="Exit non-zero when warnings are present."),
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON."),
):
    """Run all doctor checks."""
    _run(list(CHECKS.keys()), only, strict=strict, json_output=json_output)


@app.command(name="config")
def cmd_config(
    only: list[str] = typer.Option(None, "--only", "-o", help=ONLY_HELP),
    strict: bool = typer.Option(False, "--strict", help="Exit non-zero when warnings are present."),
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON."),
):
    """Check dotfiles config and secrets."""
    _run(["config"], only, strict=strict, json_output=json_output)


@app.command(name="apps")
def cmd_apps(
    only: list[str] = typer.Option(None, "--only", "-o", help=ONLY_HELP),
    strict: bool = typer.Option(False, "--strict", help="Exit non-zero when warnings are present."),
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON."),
):
    """Check app installation, running status, local state, and login hints."""
    _run(["apps"], only, strict=strict, json_output=json_output)


@app.command(name="system")
def cmd_system(
    only: list[str] = typer.Option(None, "--only", "-o", help=ONLY_HELP),
    strict: bool = typer.Option(False, "--strict", help="Exit non-zero when warnings are present."),
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON."),
):
    """Check host prerequisites, apply runner, Git state, and workflow leftovers."""
    _run(["system"], only, strict=strict, json_output=json_output)


@app.command(name="network")
def cmd_network(
    strict: bool = typer.Option(False, "--strict", help="Exit non-zero when warnings are present."),
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON."),
):
    """Probe evaluated mirror endpoints without changing network configuration."""
    _run(["network"], None, strict=strict, json_output=json_output)
