"""Process and app-running probes."""

import re
from pathlib import Path
from typing import Iterable

from envy.doctor.probes.command import run


def app_running(bundle_id: str | None = None, process_names: Iterable[str] = ()) -> bool:
    if bundle_id:
        script = f'tell application id "{bundle_id}" to if it is running then return "true"'
        result = run(["osascript", "-e", script])
        if result.returncode == 0 and result.stdout.strip() == "true":
            return True

    for process_name in process_names:
        result = run(["pgrep", "-x", process_name])
        if result.returncode == 0:
            return True

    running_names = names()
    return any(process_name in running_names for process_name in process_names)


def names() -> set[str]:
    result = run(["ps", "ax", "-o", "comm="])
    if result.returncode != 0:
        return set()

    values: set[str] = set()
    for line in result.stdout.splitlines():
        command = line.strip()
        if not command:
            continue
        basename = Path(command).name
        values.add(basename)
        # Electron helpers can appear as "App Helper (Renderer)"; keep the app stem too.
        values.add(re.sub(r" Helper.*$", "", basename))
    return values
