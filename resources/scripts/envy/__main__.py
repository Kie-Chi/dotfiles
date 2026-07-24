from envy.main import cli
from envy.process import CommandError, render_command_error

try:
    cli(prog_name="envy")
except CommandError as exc:
    render_command_error(exc)
    raise SystemExit(exc.returncode) from None
