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
    bundles: list[str] = field(default_factory=list)
    bundle_id: str | None = None
    commands: list[str] = field(default_factory=list)
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
    "codex": AppSpec(
        name="Codex",
        bundles=["Codex.app"],
        bundle_id="com.openai.codex",
        commands=["codex"],
        processes=["Codex", "codex"],
        state_paths=[
            HOME_DIR / ".codex",
            HOME_DIR / "Library/Application Support/Codex",
        ],
        checkers=["codex_auth"],
    ),
    "claude-code": AppSpec(
        name="Claude Code",
        bundles=["Claude Code URL Handler.app"],
        bundle_id="com.anthropic.claude-code-url-handler",
        commands=["claude"],
        processes=["claude"],
        state_paths=[
            HOME_DIR / ".claude.json",
            HOME_DIR / ".claude",
        ],
        login_hint="Run claude once and complete login if this machine should use Claude Code.",
    ),
    "github-cli": AppSpec(
        name="GitHub CLI",
        commands=["gh"],
        checkers=["github_cli_auth"],
    ),
    "lark-cli": AppSpec(
        name="Lark CLI",
        commands=["lark-cli"],
        checkers=["lark_cli_auth"],
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
    "squirrel": AppSpec(
        name="Squirrel",
        bundles=["Squirrel.app"],
        bundle_id="im.rime.inputmethod.Squirrel",
        processes=["Squirrel"],
        should_run=True,
        state_paths=[
            HOME_DIR / "Library/Rime/squirrel.yaml",
            HOME_DIR / "Library/Preferences/im.rime.inputmethod.Squirrel.plist",
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
    "cyberduck": AppSpec(
        name="Cyberduck",
        bundles=["Cyberduck.app"],
        bundle_id="ch.sudo.cyberduck",
        processes=["Cyberduck"],
    ),
    "wps-office": AppSpec(
        name="WPS Office",
        bundles=["wpsoffice.app", "WPS Office.app"],
        bundle_id="com.kingsoft.wpsoffice.mac",
        processes=["wpsoffice", "WPS Office"],
        login_hint="Open WPS Office and sign in if you use WPS Cloud or account sync.",
    ),
    "iina": AppSpec(
        name="IINA",
        bundles=["IINA.app"],
        bundle_id="com.colliderli.iina",
        commands=["iina"],
        processes=["IINA"],
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
        checkers=["chrome_account"],
    ),
    "tailscale": AppSpec(
        name="Tailscale",
        bundles=["Tailscale.app"],
        bundle_id="io.tailscale.ipn.macsys",
        processes=["Tailscale"],
        state_paths=[HOME_DIR / "Library/Preferences/io.tailscale.ipn.macsys.plist"],
        checkers=["tailscale_auth"],
    ),
    "orbstack": AppSpec(
        name="OrbStack",
        bundles=["OrbStack.app"],
        bundle_id="dev.orbstack.OrbStack",
        processes=["OrbStack"],
        state_paths=[HOME_DIR / ".orbstack"],
    ),
    "okular": AppSpec(
        name="Okular",
        bundles=["okular.app", "Okular.app"],
        bundle_id="org.kde.okular",
        processes=["okular", "Okular"],
    ),
    "wireguard": AppSpec(
        name="WireGuard",
        bundles=["WireGuard.app"],
        bundle_id="com.wireguard.macos",
        processes=["WireGuard"],
    ),
    "wireshark": AppSpec(
        name="Wireshark",
        bundles=["Wireshark.app"],
        bundle_id="org.wireshark.Wireshark",
        commands=["wireshark"],
        processes=["Wireshark"],
    ),
    "sing-box": AppSpec(
        name="sing-box",
        commands=["sing-box"],
    ),
    "vscode": AppSpec(
        name="Visual Studio Code",
        bundles=["Visual Studio Code.app"],
        bundle_id="com.microsoft.VSCode",
        commands=["code"],
        processes=["Code"],
        checkers=["vscode_sync", "vscode_extensions"],
    ),
}

APP_ALIASES: dict[str, str] = {
    "codex-app": "codex",
    "codex-desktop": "codex",
    "openai-codex": "codex",
    "claude": "claude-code",
    "claude-code-url-handler": "claude-code",
    "gh": "github-cli",
    "github": "github-cli",
    "feishu-cli": "lark-cli",
    "larkcli": "lark-cli",
    "larksuite-cli": "lark-cli",
    "code": "vscode",
    "visual-studio-code": "vscode",
    "visual-studio": "vscode",
    "karabiner-elements": "karabiner",
    "linear-mouse": "linearmouse",
    "squirrel-app": "squirrel",
    "rime": "squirrel",
    "clash": "clash-verge",
    "clash-verge-rev": "clash-verge",
    "google-chrome": "chrome",
    "tailscale-app": "tailscale",
    "tencentmeeting": "tencent-meeting",
    "meeting": "tencent-meeting",
    "lark": "feishu",
    "wps": "wps-office",
    "wpsoffice": "wps-office",
    "wpsoffice-cn": "wps-office",
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
