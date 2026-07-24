"""Search provider implementations with no policy or rendering."""

import html
import json
import os
import re
import shutil
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable

from envy.process import run_process
from envy.search.model import ProviderReport, SearchResult
from envy.utils import platform_name


Provider = Callable[[str, int, float], ProviderReport]


def available_providers() -> dict[str, Provider]:
    providers: dict[str, Provider] = {
        "pypi": search_pypi,
        "go": search_go,
    }
    if shutil.which("nix"):
        providers["nix"] = search_nix
    if shutil.which("npm"):
        providers["npm"] = search_npm
    if shutil.which("cargo"):
        providers["cargo"] = search_cargo
    if platform_name() == "darwin" and shutil.which("brew"):
        providers["homebrew"] = search_homebrew
    if platform_name() == "linux" and _native_manager() is not None:
        providers["native"] = search_native
    return providers


def search_nix(query: str, limit: int, timeout: float) -> ProviderReport:
    result = run_process(
        ["nix", "search", "nixpkgs", query, "--json"],
        capture=True, check=False, timeout=timeout,
    )
    if result.returncode != 0:
        return _failure("nix", result.stderr)
    try:
        values = json.loads(result.stdout or "{}")
    except json.JSONDecodeError as exc:
        return _failure("nix", str(exc))
    rows = []
    for attr, metadata in values.items():
        if not isinstance(metadata, dict):
            continue
        name = str(metadata.get("pname") or attr.rsplit(".", 1)[-1])
        rows.append(SearchResult(
            source="nix",
            ecosystem="nix",
            name=name,
            kind="package",
            version=_text(metadata.get("version")),
            description=_text(metadata.get("description")) or "",
            ref=f"nix:{attr}",
            homepage=_homepage(metadata.get("homepage")),
        ))
    return ProviderReport("nix", rows[:limit])


def search_homebrew(query: str, limit: int, timeout: float) -> ProviderReport:
    rows: list[SearchResult] = []
    errors = []
    for flag, kind, ref_kind in (
        ("--formula", "formula", "formula"),
        ("--cask", "cask", "cask"),
    ):
        result = run_process(
            ["brew", "search", flag, query],
            capture=True, check=False, timeout=timeout,
        )
        if result.returncode != 0:
            errors.append((result.stderr or "search failed").strip())
            continue
        for name in (result.stdout or "").split():
            rows.append(SearchResult(
                source="homebrew",
                ecosystem="homebrew",
                name=name,
                kind=kind,
                ref=f"homebrew:{ref_kind}/{name}",
            ))
    if not rows and errors:
        return _failure("homebrew", errors[0])
    return ProviderReport("homebrew", rows[:limit])


def search_native(query: str, limit: int, timeout: float) -> ProviderReport:
    manager = _native_manager()
    if manager == "apt":
        result = run_process(
            ["apt-cache", "search", "--names-only", query],
            capture=True, check=False, timeout=timeout,
        )
        if result.returncode != 0:
            return _failure("apt", result.stderr)
        rows = []
        for line in (result.stdout or "").splitlines():
            name, separator, description = line.partition(" - ")
            if separator:
                rows.append(SearchResult(
                    source="apt", ecosystem="native", name=name.strip(),
                    kind="package", description=description.strip(),
                    ref=f"native:{name.strip()}",
                ))
        return ProviderReport("apt", rows[:limit])
    if manager == "pacman":
        result = run_process(
            ["pacman", "-Ss", query], capture=True, check=False, timeout=timeout,
        )
        if result.returncode not in (0, 1):
            return _failure("pacman", result.stderr)
        rows = []
        lines = (result.stdout or "").splitlines()
        for index in range(0, len(lines), 2):
            header = lines[index].strip()
            match = re.match(r"[^/]+/([^ ]+)\s+([^ ]+)", header)
            if match:
                description = lines[index + 1].strip() if index + 1 < len(lines) else ""
                rows.append(SearchResult(
                    source="pacman", ecosystem="native", name=match.group(1),
                    kind="package", version=match.group(2), description=description,
                    ref=f"native:{match.group(1)}",
                ))
        return ProviderReport("pacman", rows[:limit])
    if manager in {"dnf", "zypper"}:
        command = [manager, "search", query]
        result = run_process(command, capture=True, check=False, timeout=timeout)
        if result.returncode not in (0, 1):
            return _failure(manager, result.stderr)
        rows = []
        pattern = re.compile(r"^([^\s:]+)(?:\.[^\s:]+)?\s*:\s*(.+)$")
        for line in (result.stdout or "").splitlines():
            match = pattern.match(line.strip())
            if match:
                rows.append(SearchResult(
                    source=manager, ecosystem="native", name=match.group(1),
                    kind="package", description=match.group(2),
                    ref=f"native:{match.group(1)}",
                ))
        return ProviderReport(manager, rows[:limit])
    return _failure("native", "no supported native package manager found")


def search_npm(query: str, limit: int, timeout: float) -> ProviderReport:
    result = run_process(
        ["npm", "search", query, "--json", f"--searchlimit={limit}"],
        capture=True, check=False, timeout=timeout,
    )
    if result.returncode != 0:
        return _failure("npm", result.stderr)
    try:
        values = json.loads(result.stdout or "[]")
    except json.JSONDecodeError as exc:
        return _failure("npm", str(exc))
    rows = []
    for item in values if isinstance(values, list) else []:
        if not isinstance(item, dict) or not isinstance(item.get("name"), str):
            continue
        links = item.get("links") if isinstance(item.get("links"), dict) else {}
        publisher = item.get("publisher") if isinstance(item.get("publisher"), dict) else {}
        rows.append(SearchResult(
            source="npm", ecosystem="npm", name=item["name"], kind="tool",
            version=_text(item.get("version")),
            description=_text(item.get("description")) or "",
            ref=f"npm:{item['name']}",
            homepage=_text(links.get("homepage") or links.get("repository")),
            publisher=_text(publisher.get("username")),
        ))
    return ProviderReport("npm", rows[:limit])


def search_pypi(query: str, limit: int, timeout: float) -> ProviderReport:
    del limit
    url = f"https://pypi.org/pypi/{urllib.parse.quote(query, safe='')}/json"
    try:
        payload = _get_json(url, timeout)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return ProviderReport("pypi", [])
        return _failure("pypi", str(exc))
    except (OSError, ValueError) as exc:
        return _failure("pypi", str(exc))
    info = payload.get("info") if isinstance(payload, dict) else None
    if not isinstance(info, dict) or not isinstance(info.get("name"), str):
        return ProviderReport("pypi", [])
    row = SearchResult(
        source="pypi", ecosystem="pypi", name=info["name"], kind="tool",
        version=_text(info.get("version")),
        description=_text(info.get("summary")) or "",
        ref=f"pypi:{info['name']}", homepage=_text(info.get("project_url") or info.get("home_page")),
        publisher=_text(info.get("author")),
    )
    return ProviderReport("pypi", [row])


def search_cargo(query: str, limit: int, timeout: float) -> ProviderReport:
    result = run_process(
        ["cargo", "search", query, "--limit", str(limit)],
        capture=True, check=False, timeout=timeout,
    )
    if result.returncode != 0:
        return _failure("cargo", result.stderr)
    rows = []
    pattern = re.compile(r'^([^\s=]+)\s*=\s*"([^"]+)"\s*(?:#\s*(.*))?$')
    for line in (result.stdout or "").splitlines():
        match = pattern.match(line.strip())
        if match:
            rows.append(SearchResult(
                source="cargo", ecosystem="cargo", name=match.group(1),
                kind="tool", version=match.group(2), description=match.group(3) or "",
                ref=f"cargo:{match.group(1)}",
            ))
    return ProviderReport("cargo", rows[:limit])


def search_go(query: str, limit: int, timeout: float) -> ProviderReport:
    url = "https://pkg.go.dev/search?" + urllib.parse.urlencode({"q": query, "limit": limit})
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "envy-software/1"})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
    except (OSError, urllib.error.URLError) as exc:
        return _failure("go", str(exc))
    paths = re.findall(r'href="/([^"?#]+)"[^>]*data-test-id="UnitHeader-path"', body)
    if not paths:
        paths = re.findall(r'data-test-id="UnitHeader-path"[^>]*>\s*<[^>]+>([^<]+)', body)
    rows = []
    for raw in dict.fromkeys(paths):
        name = html.unescape(raw).strip().lstrip("/")
        if name and "." in name:
            rows.append(SearchResult(
                source="go", ecosystem="go", name=name, kind="tool",
                ref=f"go:{name}", homepage=f"https://pkg.go.dev/{name}",
            ))
    return ProviderReport("go", rows[:limit])


def _native_manager() -> str | None:
    for manager, command in (
        ("apt", "apt-cache"), ("dnf", "dnf"), ("pacman", "pacman"), ("zypper", "zypper"),
    ):
        if shutil.which(command):
            return manager
    return None


def _get_json(url: str, timeout: float) -> object:
    request = urllib.request.Request(url, headers={"User-Agent": "envy-software/1"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read())


def _failure(source: str, error: object) -> ProviderReport:
    message = str(error or "search failed").strip().splitlines()[-1]
    return ProviderReport(source, [], message[:500])


def _text(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _homepage(value: object) -> str | None:
    if isinstance(value, list):
        value = value[0] if value else None
    return _text(value)
