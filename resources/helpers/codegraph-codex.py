#!/usr/bin/env python3
"""Normalize CodeGraph's MCP table without rewriting other Codex settings."""

from __future__ import annotations

import os
import re
import stat
import sys
import tempfile
from pathlib import Path


_TABLE_HEADER = re.compile(
    r"^[ \t]*\[(?!\[)(?P<name>[^\]\r\n]+)\][ \t]*(?:#.*)?(?:\r?\n)?$"
)
_CODEGRAPH_TABLE = ("mcp_servers", "codegraph")


def _table_name(line: str) -> tuple[str, ...] | None:
    match = _TABLE_HEADER.match(line)
    if match is None:
        return None
    return tuple(part.strip() for part in match.group("name").split("."))


def _is_codegraph_table(name: tuple[str, ...] | None) -> bool:
    return name is not None and name[:2] == _CODEGRAPH_TABLE


def normalize_codegraph_table(path: Path) -> bool:
    """Ensure one canonical CodeGraph table exists at end of file.

    Codex may indent nested MCP table headers while CodeGraph 0.9.7 only
    recognizes a header at column zero. Moving the table to the end also keeps
    CodeGraph's narrow text updater from consuming indented sibling MCP tables.
    Returns whether the file changed.
    """

    try:
        target = path.resolve(strict=True)
        content = target.read_text(encoding="utf-8")
    except FileNotFoundError:
        return False

    lines = content.splitlines(keepends=True)
    kept: list[str] = []
    index = 0

    while index < len(lines):
        name = _table_name(lines[index])
        if not _is_codegraph_table(name):
            kept.append(lines[index])
            index += 1
            continue

        index += 1
        while index < len(lines) and _table_name(lines[index]) is None:
            index += 1

    while kept and not kept[-1].strip():
        kept.pop()

    only_crlf = "\r\n" in content and "\n" not in content.replace("\r\n", "")
    newline = "\r\n" if only_crlf else "\n"
    prefix = "".join(kept)
    if prefix and not prefix.endswith(("\n", "\r")):
        prefix += newline
    if prefix:
        prefix += newline

    block = newline.join(
        (
            "[mcp_servers.codegraph]",
            'command = "codegraph"',
            'args = ["serve", "--mcp"]',
            "",
        )
    )
    normalized = prefix + block
    if normalized == content:
        return False

    _atomic_write(target, normalized)
    return True


def _atomic_write(path: Path, content: str) -> None:
    mode = stat.S_IMODE(path.stat().st_mode)
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=path.parent,
            prefix=f".{path.name}.",
            delete=False,
        ) as temporary:
            temporary_name = temporary.name
            os.fchmod(temporary.fileno(), mode)
            temporary.write(content)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_name, path)
    finally:
        if temporary_name is not None:
            try:
                os.unlink(temporary_name)
            except FileNotFoundError:
                pass


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(f"Usage: {argv[0]} CODEX_CONFIG_TOML", file=sys.stderr)
        return 2
    normalize_codegraph_table(Path(argv[1]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
