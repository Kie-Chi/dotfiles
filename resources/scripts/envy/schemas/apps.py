"""Application schema definitions for doctor checks.

Defines AppSpec (app check descriptor), PermissionReq (TCC permission),
the unified registry of all known apps, aliases, and VS Code extensions.
"""

from dataclasses import dataclass, field
from pathlib import Path

from envy.utils import HOME_DIR


@dataclass
class PermissionReq:
    """A macOS TCC permission this app requires."""

    service: str  # e.g. "kTCCServiceAccessibility"
    label: str  # e.g. "Accessibility"
    reason: str  # e.g. "global hotkeys and automation"
    tcc_client: str | None = None  # override bundle_id for TCC lookup


@dataclass
class AppSpec:
    """Declarative description of an application for doctor checks."""

    name: str
    bundles: list[str]
    bundle_id: str | None = None
    processes: list[str] = field(default_factory=list)
    should_run: bool = False
    state_paths: list[Path] = field(default_factory=list)
    login_hint: str = ""
    permissions: list[PermissionReq] = field(default_factory=list)
    checkers: list[str] = field(default_factory=list)


ALL_APP_SPECS: dict[str, AppSpec] = {
    "raycast": AppSpec(
        name="Raycast",
        bundles=["Raycast.app"],
        bundle_id="com.raycast.macos",
        processes=["Raycast"],
        should_run=True,
        state_paths=[
            HOME_DIR / ".config/raycast/ai/providers.yaml",
            HOME_DIR / "Library/Application Support/com.raycast.macos/raycast-enc.sqlite",
        ],
        login_hint="Open Raycast and sign in if you use account sync, store extensions, or paid AI.",
        permissions=[
            PermissionReq("kTCCServiceAccessibility", "Accessibility", "global hotkeys and automation"),
        ],
    ),
    "iterm2": AppSpec(
        name="iTerm2",
        bundles=["iTerm.app", "iTerm2.app"],
        bundle_id="com.googlecode.iterm2",
        processes=["iTerm2"],
        should_run=True,
        state_paths=[HOME_DIR / "Library/Application Support/iTerm2/DynamicProfiles/Dracula.json"],
    ),
    "karabiner": AppSpec(
        name="Karabiner-Elements",
        bundles=["Karabiner-Elements.app"],
        bundle_id="org.pqrs.Karabiner-Elements",
        processes=[
            "Karabiner-Elements",
            "Karabiner-Core-Service",
            "Karabiner-Menu",
            "Karabiner-VirtualHIDDevice-Daemon",
            "karabiner_console_user_server",
            "karabiner_session_monitor",
        ],
        should_run=True,
        state_paths=[HOME_DIR / ".config/karabiner/karabiner.json"],
        permissions=[
            PermissionReq("kTCCServiceAccessibility", "Accessibility", "keyboard remapping",
                          tcc_client="org.pqrs.Karabiner-Core-Service"),
        ],
    ),
    "linearmouse": AppSpec(
        name="LinearMouse",
        bundles=["LinearMouse.app"],
        bundle_id="com.lujjjh.LinearMouse",
        processes=["LinearMouse"],
        should_run=True,
        state_paths=[HOME_DIR / ".config/linearmouse/linearmouse.json"],
        permissions=[
            PermissionReq("kTCCServiceAccessibility", "Accessibility", "mouse behavior control"),
        ],
    ),
    "snipaste": AppSpec(
        name="Snipaste",
        bundles=["Snipaste.app"],
        bundle_id="com.Snipaste",
        processes=["Snipaste"],
        permissions=[
            PermissionReq("kTCCServiceScreenCapture", "Screen Recording", "screenshot capture"),
        ],
    ),
    "clash-verge": AppSpec(
        name="Clash Verge Rev",
        bundles=["Clash Verge.app", "Clash Verge Rev.app"],
        bundle_id="io.github.clash-verge-rev.clash-verge-rev",
        processes=["clash-verge", "Clash Verge"],
        state_paths=[
            HOME_DIR / "Library/Application Support/io.github.clash-verge-rev.clash-verge-rev/verge.yaml",
            HOME_DIR / "Library/Application Support/io.github.clash-verge-rev.clash-verge-rev/config.yaml",
        ],
    ),
    "betterdisplay": AppSpec(
        name="BetterDisplay",
        bundles=["BetterDisplay.app"],
        bundle_id="pro.betterdisplay.BetterDisplay",
        processes=["BetterDisplay"],
        should_run=True,
        state_paths=[HOME_DIR / "Library/Application Support/BetterDisplay"],
    ),
    "feishu": AppSpec(
        name="Feishu",
        bundles=["Feishu.app", "Lark.app"],
        bundle_id="com.electron.lark",
        processes=["Feishu", "Lark"],
        state_paths=[HOME_DIR / "Library/Application Support/LarkShell/Default/Preferences"],
        login_hint="Open Feishu and confirm the account avatar/workspace is present.",
        permissions=[
            PermissionReq("kTCCServiceCamera", "Camera", "video meetings"),
            PermissionReq("kTCCServiceMicrophone", "Microphone", "video meetings"),
            PermissionReq("kTCCServiceScreenCapture", "Screen Recording", "screen sharing"),
        ],
    ),
    "tencent-meeting": AppSpec(
        name="Tencent Meeting",
        bundles=["TencentMeeting.app", "腾讯会议.app"],
        bundle_id="com.tencent.meeting",
        processes=["TencentMeeting", "腾讯会议"],
        state_paths=[HOME_DIR / "Library/Application Support/com.tencent.meeting"],
        login_hint="Open Tencent Meeting and confirm the account page is signed in.",
        permissions=[
            PermissionReq("kTCCServiceCamera", "Camera", "video meetings"),
            PermissionReq("kTCCServiceMicrophone", "Microphone", "video meetings"),
            PermissionReq("kTCCServiceScreenCapture", "Screen Recording", "screen sharing"),
        ],
    ),
    "chrome": AppSpec(
        name="Google Chrome",
        bundles=["Google Chrome.app"],
        bundle_id="com.google.Chrome",
        processes=["Google Chrome"],
        state_paths=[HOME_DIR / "Library/Application Support/Google/Chrome"],
    ),
    "tailscale": AppSpec(
        name="Tailscale",
        bundles=["Tailscale.app"],
        bundle_id="io.tailscale.ipn.macsys",
        processes=["Tailscale"],
        state_paths=[HOME_DIR / "Library/Preferences/io.tailscale.ipn.macsys.plist"],
        login_hint="Run tailscale status or open Tailscale to confirm the node is authenticated.",
    ),
    "orbstack": AppSpec(
        name="OrbStack",
        bundles=["OrbStack.app"],
        bundle_id="dev.orbstack.OrbStack",
        processes=["OrbStack"],
        state_paths=[HOME_DIR / ".orbstack"],
    ),
    "vscode": AppSpec(
        name="Visual Studio Code",
        bundles=["Visual Studio Code.app"],
        bundle_id="com.microsoft.VSCode",
        processes=["Code"],
        checkers=["vscode_sync", "vscode_extensions"],
    ),
}

APP_ALIASES: dict[str, str] = {
    "code": "vscode",
    "visual-studio-code": "vscode",
    "visual-studio": "vscode",
    "karabiner-elements": "karabiner",
    "linear-mouse": "linearmouse",
    "clash": "clash-verge",
    "clash-verge-rev": "clash-verge",
    "google-chrome": "chrome",
    "tencentmeeting": "tencent-meeting",
    "meeting": "tencent-meeting",
    "lark": "feishu",
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
