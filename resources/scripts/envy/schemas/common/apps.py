"""Platform-neutral application schemas used by ``envy doctor``."""

from dataclasses import dataclass, field
from pathlib import Path

from envy.utils import HOME_DIR


@dataclass
class PermissionReq:
    """A Darwin TCC permission attached only by the Darwin schema."""

    service: str
    label: str
    reason: str
    tcc_client: str | None = None


@dataclass
class AppSpec:
    """Declarative description of an application check."""

    name: str
    bundles: list[str] = field(default_factory=list)
    bundle_id: str | None = None
    commands: list[str] = field(default_factory=list)
    processes: list[str] = field(default_factory=list)
    should_run: bool = False
    state_paths: list[Path] = field(default_factory=list)
    login_hint: str = ""
    permissions: list[PermissionReq] = field(default_factory=list)
    checkers: list[str] = field(default_factory=list)
    casks: list[str] = field(default_factory=list)
    brews: list[str] = field(default_factory=list)
    packages: list[str] = field(default_factory=list)


APP_SPECS: dict[str, AppSpec] = {
    "claude-code": AppSpec(
        name="Claude Code",
        packages=["claude"],
        commands=["claude"],
        processes=["claude"],
        state_paths=[HOME_DIR / ".claude.json", HOME_DIR / ".claude"],
        login_hint="Run claude once and complete login if this machine should use Claude Code.",
    ),
    "wireshark": AppSpec(
        name="Wireshark",
        packages=["wireshark-qt"],
        commands=["wireshark"],
        processes=["wireshark", "Wireshark"],
    ),
    "vscode": AppSpec(
        name="Visual Studio Code",
        commands=["code"],
        processes=["code", "Code"],
        checkers=["vscode_sync", "vscode_extensions"],
    ),
}

APP_ALIASES: dict[str, str] = {
    "claude": "claude-code",
    "claude-code-url-handler": "claude-code",
    "code": "vscode",
    "visual-studio-code": "vscode",
    "visual-studio": "vscode",
}

EXPECTED_EXTENSIONS: list[str] = [
    "anthropic.claude-code",
    "eamodio.gitlens",
    "formulahendry.code-runner",
    "github.copilot",
    "github.copilot-chat",
    "hediet.vscode-drawio",
    "ms-python.python",
    "ms-vscode.cpptools",
    "ms-vscode.hexeditor",
    "ms-vscode-remote.remote-containers",
    "ms-vscode-remote.remote-ssh",
    "redhat.vscode-yaml",
    "shd101wyy.markdown-preview-enhanced",
    "vscode-icons-team.vscode-icons",
]


__all__ = [
    "APP_ALIASES",
    "APP_SPECS",
    "AppSpec",
    "EXPECTED_EXTENSIONS",
    "PermissionReq",
]
