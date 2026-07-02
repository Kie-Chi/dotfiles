"""VS Code state probes."""

import shutil
import sqlite3
from pathlib import Path

from envy.doctor.probes.command import run
from envy.utils import HOME_DIR

STATE_DB = HOME_DIR / "Library/Application Support/Code/User/globalStorage/state.vscdb"


def state_db_exists() -> bool:
    return STATE_DB.exists()


def state_keys() -> set[str]:
    if not STATE_DB.exists():
        return set()
    try:
        with sqlite3.connect(f"file:{STATE_DB}?mode=ro", uri=True) as conn:
            return {row[0] for row in conn.execute("select key from ItemTable")}
    except sqlite3.Error:
        return set()


def code_command() -> str | None:
    for candidate in [
        shutil.which("code"),
        "/Applications/Visual Studio Code.app/Contents/Resources/app/bin/code",
    ]:
        if candidate and Path(candidate).exists():
            return candidate
    return None


def installed_extensions(command: str) -> set[str]:
    result = run([command, "--list-extensions"], timeout=20)
    if result.returncode != 0:
        return set()
    return {line.strip() for line in result.stdout.splitlines() if line.strip()}
