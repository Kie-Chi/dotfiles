"""macOS TCC database probes."""

import sqlite3
from pathlib import Path

from envy.utils import HOME_DIR

USER_TCC_DB = HOME_DIR / "Library/Application Support/com.apple.TCC/TCC.db"
SYSTEM_TCC_DB = Path("/Library/Application Support/com.apple.TCC/TCC.db")


def permission_records() -> tuple[dict[tuple[str, str], int], bool]:
    records: dict[tuple[str, str], int] = {}
    readable = False
    for db in [USER_TCC_DB, SYSTEM_TCC_DB]:
        if not db.exists():
            continue
        try:
            with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as conn:
                rows = conn.execute("select service, client, auth_value from access").fetchall()
        except sqlite3.Error:
            continue
        readable = True
        for service, client, auth_value in rows:
            records[(service, client)] = int(auth_value)
    return records, readable
