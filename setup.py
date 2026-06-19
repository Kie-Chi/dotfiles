#!/usr/bin/env python3
"""Dotfiles setup CLI — menuconfig-like UI for config.nix + sops secrets."""

import os
import re
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional

import yaml
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from prompt_toolkit.application import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout, Window, HSplit, FormattedTextControl, ConditionalContainer
from prompt_toolkit.layout.controls import BufferControl
from prompt_toolkit.filters import Condition
from prompt_toolkit.styles import Style as PtStyle
from prompt_toolkit.widgets import Frame
from prompt_toolkit import prompt as pt_prompt

from envy.key import (
    AGE_KEY_DIR, AGE_KEY_FILE, SOPS_YAML, SECRETS_FILE, SECRETS_DIR,
    run_cmd as key_run_cmd, console as key_console,
    read_sops_yaml_keys, write_sops_yaml_keys,
    get_current_device_public_key, get_device_label, set_device_label,
    run_sops_updatekeys, git_commit_sops_files, key_import,
)
from envy.utils import RECOVERY_KEY_FILE, backup_sensitive_file


# ==========================================
# PATHS (shared with key.py)
# ==========================================

BASE_DIR = Path(__file__).resolve().parent
HOME_DIR = Path.home()
CONFIG_FILE = BASE_DIR / "config.nix"

# SOPS paths imported from key.py: AGE_KEY_DIR, AGE_KEY_FILE, SOPS_YAML, SECRETS_DIR, SECRETS_FILE

console = Console()


# ==========================================
# FIELD DEFINITIONS
# ==========================================

def non_empty(val: str) -> Optional[str]:
    if not val.strip():
        return "Value cannot be empty"
    return None

def is_email(val: str) -> Optional[str]:
    if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', val):
        return "Please enter a valid email address"
    return None

def is_url(val: str) -> Optional[str]:
    if val and not val.startswith("http://") and not val.startswith("https://"):
        return "URL must start with http:// or https://"
    return None


@dataclass
class FieldDef:
    group: str
    dest: str
    path: str
    yaml_path: str = ""
    prompt: str = ""
    default_fn: Callable = field(default_factory=lambda: lambda: "")
    choices: List[str] = field(default_factory=list)
    condition: Optional[Callable] = None
    validators: List[Callable] = field(default_factory=list)
    error_msg: str = ""
    ignore: bool = False


CONFIG_FIELDS = [
    FieldDef(group="BASE", dest="config", path="home.option", prompt="System option",
             default_fn=lambda: "desktop", choices=["desktop", "server"]),
    FieldDef(group="BASE", dest="config", path="home.desktop", prompt="Desktop option",
             default_fn=lambda: "all", choices=["all", "gnome", "niri", "none"],
             condition=lambda v: v.get("home.option") != "server"),
    FieldDef(group="BASE", dest="config", path="home.user", prompt="System username",
             default_fn=lambda: os.getenv("USER", "chi"), validators=[non_empty]),
    FieldDef(group="BASE", dest="config", path="home.dir", prompt="Home directory",
             default_fn=lambda: str(HOME_DIR), validators=[non_empty]),
    FieldDef(group="GIT", dest="config", path="git.name", prompt="Git user name",
             default_fn=lambda: os.getenv("USER", "chi"), validators=[non_empty]),
    FieldDef(group="GIT", dest="config", path="git.email", prompt="Git user email",
             default_fn=lambda: f"{os.getenv('USER','chi')}@{subprocess.getoutput('hostname -f')}",
             validators=[is_email]),
    FieldDef(group="PROXY", dest="config", path="proxy.status", prompt="Proxy status",
             default_fn=lambda: "none", choices=["none", "manual", "keep"]),
    FieldDef(group="PROXY", dest="config", path="proxy.tun", prompt="Proxy TUN status",
             default_fn=lambda: "true", choices=["true", "false"],
             condition=lambda v: v.get("proxy.status") != "none"),
    FieldDef(group="ENV", dest="config", path="dotfiles.path", prompt="Dotfiles local path",
             default_fn=lambda: str(BASE_DIR), ignore=True),
    FieldDef(group="LLM", dest="config", path="llm.dashscope.url", prompt="DashScope API base URL",
             default_fn=lambda: "https://dashscope.aliyuncs.com/apps/anthropic"),
    FieldDef(group="LLM", dest="config", path="llm.dashscope.model", prompt="DashScope default model",
             default_fn=lambda: "glm-5.1"),
    FieldDef(group="LLM", dest="config", path="llm.deepseek.url", prompt="DeepSeek API base URL",
             default_fn=lambda: "https://api.deepseek.com/v1"),
    FieldDef(group="LLM", dest="config", path="llm.deepseek.model", prompt="DeepSeek default model",
             default_fn=lambda: "deepseek-v4-pro"),
]

SECRET_FIELDS = [
    FieldDef(group="SECRET", dest="secret", yaml_path="home/passwd", path="home_passwd",
             prompt="System password",
             default_fn=lambda: os.getenv("USER", ""), validators=[non_empty]),
    FieldDef(group="SECRET", dest="secret", yaml_path="proxy/url", path="proxy_url",
             prompt="Proxy URL", default_fn=lambda: "",
             condition=lambda v: v.get("proxy.status") != "none",
             validators=[is_url]),
    FieldDef(group="SECRET", dest="secret", yaml_path="llm/dashscope/apikey", path="llm_dashscope_apikey",
             prompt="DashScope API Key",
             default_fn=lambda: os.getenv("API_KEY", "")),
    FieldDef(group="SECRET", dest="secret", yaml_path="llm/deepseek/apikey", path="llm_deepseek_apikey",
             prompt="DeepSeek API Key",
             default_fn=lambda: ""),
]

ALL_FIELDS = CONFIG_FIELDS + SECRET_FIELDS


# ==========================================
# CRYPTO — age key + sops (delegated to key.py)
# ==========================================

def run_cmd(cmd: List[str], stdin_data: Optional[str] = None, check: bool = True) -> str:
    env = os.environ.copy()
    if AGE_KEY_FILE.exists():
        env["SOPS_AGE_KEY_FILE"] = str(AGE_KEY_FILE)
    result = subprocess.run(cmd, input=stdin_data, capture_output=True, text=True, check=check, env=env)
    return result.stdout.strip()


def setup_age_key() -> str:
    """Ensure the current device has an age key. Detects SSH rotation mismatches."""
    AGE_KEY_DIR.mkdir(parents=True, exist_ok=True)

    if AGE_KEY_FILE.exists():
        current_pub = get_current_device_public_key()
        if current_pub:
            keys = read_sops_yaml_keys()
            if current_pub in keys.values():
                return current_pub

            # Key exists but not in .sops.yaml — detect SSH rotation
            ssh_key = HOME_DIR / ".ssh" / "id_ed25519"
            if ssh_key.exists():
                try:
                    ssh_pub_input = ssh_key.with_suffix(".pub").read_text()
                    ssh_derived_pub = run_cmd(["ssh-to-age"], stdin_data=ssh_pub_input)
                    if ssh_derived_pub == current_pub:
                        console.print("[yellow]Your age key was derived from SSH and doesn't match .sops.yaml.[/yellow]")
                        console.print("[yellow]This usually means your SSH key was rotated on a new device.[/yellow]")
                except subprocess.CalledProcessError:
                    pass

            console.print("[yellow]Age key exists but is not in .sops.yaml for this device.[/yellow]")
            console.print("[yellow]It will be added during save.[/yellow]")
            return current_pub

    # No age key file — try SSH derivation or generate new
    ssh_key = HOME_DIR / ".ssh" / "id_ed25519"
    if ssh_key.exists():
        try:
            result = run_cmd(["ssh-to-age", "-private-key", "-i", str(ssh_key)])
            AGE_KEY_FILE.write_text(result + "\n")
            with open(str(ssh_key) + ".pub") as f:
                pub_input = f.read()
            public_key = run_cmd(["ssh-to-age"], stdin_data=pub_input)
            if public_key:
                AGE_KEY_FILE.chmod(0o600)
                return public_key
        except subprocess.CalledProcessError:
            pass

    backup_sensitive_file(AGE_KEY_FILE)
    run_cmd(["age-keygen", "-o", str(AGE_KEY_FILE)])
    public_key = run_cmd(["age-keygen", "-y", str(AGE_KEY_FILE)])
    AGE_KEY_FILE.chmod(0o600)
    return public_key


# ==========================================
# CONFIG I/O
# ==========================================

def read_config_nix() -> dict:
    values = {}
    if not CONFIG_FILE.exists():
        return values
    pattern = re.compile(r'(\S+)\s*=\s*"([^"]*)"')
    for line in CONFIG_FILE.read_text().splitlines():
        line = line.strip()
        if line.startswith("#") or not line:
            continue
        for key, val in pattern.findall(line):
            values[key] = val
    return values


def write_config_nix(values: dict) -> None:
    groups = sorted(set(f.group for f in CONFIG_FIELDS))
    lines = ["{\n"]
    for group in groups:
        lines.append(f"\n  # --- {group} CONFIG ---\n")
        for f in CONFIG_FIELDS:
            if f.group != group:
                continue
            val = values.get(f.path, "")
            val = val.replace("\\", "\\\\").replace('"', '\\"')
            lines.append(f"  {f.path} = \"{val}\";\n")
    lines.append("}\n")
    CONFIG_FILE.write_text("".join(lines))

    target_dir = HOME_DIR / ".config" / "dotfiles"
    target_dir.mkdir(parents=True, exist_ok=True)
    symlink = target_dir / "config.nix"
    if symlink.exists() or symlink.is_symlink():
        symlink.unlink()
    symlink.symlink_to(CONFIG_FILE)


def read_secrets_yaml() -> tuple:
    """Read secrets from sops-encrypted YAML.
    Returns (values_dict, decrypt_success_bool).
    """
    values = {}
    if not SECRETS_FILE.exists():
        return values, False
    # Try sops decryption first, fallback to plain YAML for unencrypted files
    data = None
    decrypt_ok = False
    try:
        plain = run_cmd(["sops", "--decrypt", str(SECRETS_FILE)])
        data = yaml.safe_load(plain)
        decrypt_ok = True
    except subprocess.CalledProcessError:
        try:
            data = yaml.safe_load(SECRETS_FILE.read_text())
            decrypt_ok = False  # plain YAML = not encrypted = new device can't use sops-nix
        except Exception:
            pass
    if data is None:
        return values, False
    for f in SECRET_FIELDS:
        if not f.yaml_path:
            continue
        parts = f.yaml_path.split("/")
        d = data
        try:
            for part in parts[:-1]:
                d = d[part]
            val = d.get(parts[-1], "")
            if val is not None:
                values[f.path] = str(val)
        except (KeyError, TypeError):
            pass
    return values, decrypt_ok


def write_secrets_yaml(values: dict) -> None:
    SECRETS_DIR.mkdir(parents=True, exist_ok=True)

    data = {}
    for f in SECRET_FIELDS:
        parts = f.yaml_path.split("/")
        d = data
        for part in parts[:-1]:
            d = d.setdefault(part, {})
        d[parts[-1]] = values.get(f.path, "")

    backup = SECRETS_FILE.with_suffix(".yaml.bak")
    had_existing = SECRETS_FILE.exists()

    # Backup existing encrypted secrets before any modification
    if had_existing:
        os.replace(str(SECRETS_FILE), str(backup))

    try:
        # Write unencrypted data to the real path (matches .sops.yaml path_regex)
        with open(SECRETS_FILE, "w") as fh:
            yaml.dump(data, fh, default_flow_style=False, allow_unicode=True)

        # Encrypt in-place; filename matches creation rules so sops can find config
        keys = read_sops_yaml_keys()
        age_recipients = ",".join(keys.values())
        run_cmd(["sops", "--encrypt", "--in-place", "--age", age_recipients, str(SECRETS_FILE)])
    except Exception:
        # Encryption failed — rollback to backup immediately
        console.print("[red]sops encryption failed[/red]")
        console.print("[red]ABORTING: secrets.yaml will NOT be written unencrypted.[/red]")
        if had_existing and backup.exists():
            os.replace(str(backup), str(SECRETS_FILE))
            console.print("[green]Rolled back to previous encrypted secrets.yaml[/green]")
        else:
            # No backup means secrets.yaml didn't exist before — remove the unencrypted file
            if SECRETS_FILE.exists():
                os.unlink(str(SECRETS_FILE))
            console.print("[yellow]No previous secrets.yaml to restore — unencrypted file removed.[/yellow]")
        raise RuntimeError("sops encryption failed — refusing to leave secrets unencrypted")

    # Success — discard backup
    if backup.exists():
        os.unlink(str(backup))


# git_commit_sops_files is imported from key.py


# ==========================================
# MENUCONFIG UI — single Application with mode switching
# ==========================================

class AppState:
    """State for the menuconfig Application."""
    def __init__(self, values: dict):
        self.values = values
        self.mode = "list"  # "list" | "edit_text" | "edit_choice"
        self.cursor = 0
        self.editing_field: Optional[FieldDef] = None
        self.edit_buffer = Buffer()
        self.choice_cursor = 0
        self.error_msg = ""
        self.result: Optional[dict] = None  # set on save/quit


def init_values() -> dict:
    existing_config = read_config_nix()
    existing_secrets, _ = read_secrets_yaml()
    values = {}
    for f in ALL_FIELDS:
        if f.condition and not f.condition(values):
            continue
        if f.dest == "config" and f.path in existing_config:
            values[f.path] = existing_config[f.path]
        elif f.dest == "secret" and f.path in existing_secrets:
            values[f.path] = existing_secrets[f.path]
        else:
            values[f.path] = f.default_fn()
    return values


def handle_decrypt_failure() -> dict:
    """Layered guidance when sops decryption fails on a new device.
    Delegates to key_import() interactive mode from key.py."""
    console.print(Panel(
        "[bold red]sops decryption failed[/bold red]\n\n"
        "This usually means you're on a [bold]new device[/bold] and the age key\n"
        "doesn't match the one that encrypted secrets.yaml.\n\n"
        "To restore your existing secrets, you need a key from another device.",
        title="New Device Detected", border_style="red"))

    pub = key_import()  # interactive mode — offers import SSH/age/generate
    if pub:
        secrets, ok = read_secrets_yaml()
        if ok:
            console.print("[bold green]Decryption successful! Existing secrets restored.[/bold green]")
            return secrets
        else:
            console.print("[yellow]Key imported but decryption still failed. Try another key.[/yellow]")

    console.print("[yellow]Proceeding with empty secrets — you must re-enter all values in the menuconfig UI.[/yellow]")
    return {}


def get_visible_fields(values: dict) -> list:
    items = []
    for f in ALL_FIELDS:
        if f.ignore:
            continue
        if f.condition and not f.condition(values):
            continue
        items.append(f)
    return items


def _list_text(state: AppState) -> list:
    items = get_visible_fields(state.values)
    if state.cursor >= len(items):
        state.cursor = max(0, len(items) - 1)

    lines = []
    current_group = None
    for i, f in enumerate(items):
        if f.group != current_group:
            current_group = f.group
            lines.append(("class:group", f"\n  ── {current_group} ──\n"))
        val = state.values.get(f.path, "")
        tag = "[S] " if f.dest == "secret" else ""
        if f.choices:
            tag += f"({','.join(f.choices)}) "
        if i == state.cursor:
            lines.append(("class:cursor", f"  ► {tag}{f.prompt}: {val}\n"))
        else:
            lines.append(("class:normal", f"    {tag}{f.prompt}: {val}\n"))
    return lines


def _edit_frame_title(state: AppState) -> list:
    """Frame title for edit_text mode — includes error if present."""
    f = state.editing_field
    if state.error_msg:
        return [("class:error", f"Edit: {f.prompt}  ✗ {state.error_msg}")]
    return [("class:title", f"Edit: {f.prompt}")]


def _edit_context(state: AppState) -> list:
    """Dim current value line shown inside the edit frame."""
    f = state.editing_field
    val = state.values.get(f.path, "")
    return [("class:dim", f"  Current: {val}")]


def _choice_frame_title(state: AppState) -> list:
    f = state.editing_field
    return [("class:title", f"Select: {f.prompt}")]

def _choice_text(state: AppState) -> list:
    f = state.editing_field
    choices = f.choices
    lines = []
    for i, c in enumerate(choices):
        if i == state.choice_cursor:
            lines.append(("class:cursor", f"  ► {c}\n"))
        else:
            lines.append(("class:normal", f"    {c}\n"))
    return lines


def build_application(state: AppState) -> Application:
    """Build a single Application with mode-switching layout."""
    is_list = Condition(lambda: state.mode == "list")
    is_edit_text = Condition(lambda: state.mode == "edit_text")
    is_edit_choice = Condition(lambda: state.mode == "edit_choice")

    # --- Title bar (always visible) ---
    title_content = FormattedTextControl(lambda: [("class:title", "  Dotfiles Setup — menuconfig")])
    title_window = Window(content=title_content, height=1)

    # --- List mode ---
    list_content = FormattedTextControl(lambda: _list_text(state))
    list_window = Window(content=list_content)
    list_container = ConditionalContainer(content=list_window, filter=is_list)

    # --- Edit text mode (framed) ---
    edit_context = FormattedTextControl(lambda: _edit_context(state))
    edit_context_window = Window(content=edit_context, height=1)
    edit_buffer_control = BufferControl(buffer=state.edit_buffer)
    edit_buffer_window = Window(content=edit_buffer_control, height=1)
    edit_text_container = ConditionalContainer(
        content=Frame(
            title=lambda: _edit_frame_title(state),
            body=HSplit([edit_context_window, edit_buffer_window]),
        ),
        filter=is_edit_text,
    )

    # --- Edit choice mode (framed) ---
    choice_content = FormattedTextControl(lambda: _choice_text(state))
    choice_window = Window(content=choice_content)
    choice_container = ConditionalContainer(
        content=Frame(
            title=lambda: _choice_frame_title(state),
            body=choice_window,
        ),
        filter=is_edit_choice,
    )

    # --- Bottom bar (always visible, context-sensitive) ---
    def bottom_text():
        if state.mode == "list":
            return [("class:bottom", "  Enter: edit  │  s: save & exit  │  q/Esc: quit  │  ↑↓: navigate")]
        elif state.mode == "edit_text":
            return [("class:bottom", "  Enter: confirm  │  Esc: cancel")]
        elif state.mode == "edit_choice":
            return [("class:bottom", "  Enter: select  │  Esc: cancel  │  ↑↓: navigate")]
        return []

    bottom_content = FormattedTextControl(bottom_text)
    bottom_window = Window(content=bottom_content, height=1)

    layout = Layout(HSplit([
        title_window,
        list_container,
        edit_text_container,
        choice_container,
        bottom_window,
    ]))

    # --- Key bindings ---
    kb = KeyBindings()

    # Navigation — only in list and choice modes
    @kb.add("up", filter=is_list | is_edit_choice)
    def _(event):
        if state.mode == "list":
            items = get_visible_fields(state.values)
            state.cursor = max(0, state.cursor - 1)
        elif state.mode == "edit_choice":
            choices = state.editing_field.choices
            state.choice_cursor = max(0, state.choice_cursor - 1)
        event.app.invalidate()

    @kb.add("down", filter=is_list | is_edit_choice)
    def _(event):
        if state.mode == "list":
            items = get_visible_fields(state.values)
            state.cursor = min(len(items) - 1, state.cursor + 1)
        elif state.mode == "edit_choice":
            choices = state.editing_field.choices
            state.choice_cursor = min(len(choices) - 1, state.choice_cursor + 1)
        event.app.invalidate()

    # Enter — mode-specific behavior
    @kb.add("enter", filter=is_list)
    def _(event):
        items = get_visible_fields(state.values)
        if not items:
            return
        f = items[state.cursor]
        state.editing_field = f
        state.error_msg = ""
        if f.choices:
            current_val = state.values.get(f.path, f.default_fn())
            state.choice_cursor = f.choices.index(current_val) if current_val in f.choices else 0
            state.mode = "edit_choice"
        else:
            current_val = state.values.get(f.path, f.default_fn())
            state.edit_buffer.text = current_val
            state.edit_buffer.cursor_position = len(current_val)
            state.mode = "edit_text"
            event.app.layout.focus(edit_buffer_window)
        event.app.invalidate()

    @kb.add("enter", filter=is_edit_text)
    def _(event):
        new_val = state.edit_buffer.text
        # Validate using field validators
        for v in state.editing_field.validators:
            error = v(new_val)
            if error:
                state.error_msg = error
                event.app.invalidate()
                return
        state.values[state.editing_field.path] = new_val
        state.error_msg = ""
        state.mode = "list"
        event.app.invalidate()

    @kb.add("enter", filter=is_edit_choice)
    def _(event):
        selected = state.editing_field.choices[state.choice_cursor]
        state.values[state.editing_field.path] = selected
        state.mode = "list"
        event.app.invalidate()

    # Escape — cancel edit or quit from list
    @kb.add("escape", filter=is_edit_text | is_edit_choice)
    def _(event):
        state.error_msg = ""
        state.mode = "list"
        event.app.invalidate()

    @kb.add("escape", filter=is_list)
    @kb.add("q", filter=is_list)
    def _(event):
        state.result = None
        event.app.exit()

    # Save — only from list mode
    @kb.add("s", filter=is_list)
    def _(event):
        state.result = state.values
        event.app.exit()

    style = PtStyle.from_dict({
        "title": "#ansicyan bold",
        "group": "#ansicyan bold",
        "cursor": "bg:#ansicyan #ansiblack bold",
        "normal": "",
        "dim": "#ansigray",
        "hint": "#ansigray",
        "error": "#ansired bold",
        "bottom": "#ansigray",
        "frame.border": "#ansigray",
        "frame.title": "#ansicyan bold",
    })

    return Application(layout=layout, key_bindings=kb, style=style, full_screen=True)


def menuconfig_loop(initial_values: dict) -> Optional[dict]:
    state = AppState(values=dict(initial_values))
    app = build_application(state)
    app.run()
    return state.result


def show_changes(old_values: dict, new_values: dict) -> bool:
    """Display changed fields — secrets shown in plain text for verification."""
    changes = []
    for f in ALL_FIELDS:
        if f.ignore:
            continue
        old = old_values.get(f.path, "")
        new = new_values.get(f.path, "")
        if old != new:
            tag = "SECRET" if f.dest == "secret" else "CONFIG"
            changes.append((f"{tag}: {f.prompt}", old, new))

    if not changes:
        console.print("[dim]No changes detected[/dim]")
        return False

    table = Table(show_header=True, box=None, padding=(0, 2))
    table.add_column("Field", style="cyan")
    table.add_column("Old", style="red")
    table.add_column("New", style="green")
    for row in changes:
        table.add_row(*row)

    console.print(Panel(table, title="Changes Summary", border_style="yellow"))
    return True


def confirm_save() -> bool:
    """Simple Y/N confirmation using prompt_toolkit."""
    try:
        answer = pt_prompt("? Apply changes and save? [y/N]: ")
        return answer.lower().startswith("y")
    except (EOFError, KeyboardInterrupt):
        return False


def save_all(values: dict) -> None:
    # Read existing secrets before any writes to detect changes
    existing_secrets, _ = read_secrets_yaml()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:

        t1 = progress.add_task("Setting up age key...", total=None)
        public_key = setup_age_key()
        progress.update(t1, completed=True, description=f"Age key: [green]{public_key[:20]}...[/green]")

        t2 = progress.add_task("Updating .sops.yaml...", total=None)
        keys = read_sops_yaml_keys()
        label = get_device_label()

        sops_updated = False  # track whether .sops.yaml was actually written

        if label in keys and keys[label] == public_key:
            # Key already correct — skip overwrite, only ensure recovery key exists
            if "recovery" not in keys:
                from envy.key import key_add_recovery
                progress.update(t2, completed=True,
                                description="[dim].sops.yaml up-to-date, adding recovery key...[/dim]")
                key_add_recovery()
            else:
                progress.update(t2, completed=True,
                                description="[dim].sops.yaml up-to-date (skipped)[/dim]")
        else:
            sops_updated = True
            keys[label] = public_key
            # Ensure recovery key exists
            if "recovery" not in keys:
                from envy.key import key_add_recovery
                write_sops_yaml_keys(keys)
                progress.update(t2, completed=True, description="[green].sops.yaml written[/green]")
                progress.add_task("Generating recovery key...", total=None)
                key_add_recovery()
            else:
                write_sops_yaml_keys(keys)
                progress.update(t2, completed=True, description="[green].sops.yaml updated[/green]")

        t3 = progress.add_task("Writing config.nix...", total=None)
        write_config_nix(values)
        progress.update(t3, completed=True, description="[green]config.nix saved[/green]")

        # Only re-encrypt secrets if values changed or key set changed
        secrets_changed = (
            not SECRETS_FILE.exists()
            or any(
                str(values.get(f.path, "")) != str(existing_secrets.get(f.path, ""))
                for f in SECRET_FIELDS
            )
        )

        if secrets_changed:
            t4 = progress.add_task("Encrypting secrets.yaml...", total=None)
            write_secrets_yaml(values)
            progress.update(t4, completed=True, description="[green]secrets.yaml encrypted[/green]")
        elif sops_updated:
            progress.add_task("[dim]secrets.yaml unchanged, re-encrypting with updated keys...[/dim]")
        else:
            progress.add_task("[dim]secrets.yaml unchanged (skipped)[/dim]")

        if secrets_changed or sops_updated:
            t5 = progress.add_task("Re-encrypting secrets with updated keys...", total=None)
            run_sops_updatekeys()
            progress.update(t5, completed=True)

    console.print("[cyan]Committing sops files...[/cyan]")
    git_commit_sops_files("setup")


# ==========================================
# MAIN
# ==========================================

def main():
    existing_config = read_config_nix()
    existing_secrets, decrypt_ok = read_secrets_yaml()

    # Layered guidance for new device: if decryption failed, try key import before menuconfig
    if not decrypt_ok and SECRETS_FILE.exists():
        restored_secrets = handle_decrypt_failure()
        if not restored_secrets and SECRETS_FILE.exists():
            # User chose to proceed with empty secrets — they'll re-enter in menuconfig
            pass
        elif restored_secrets:
            existing_secrets = restored_secrets

    # Build initial values from config + (possibly restored) secrets
    values = {}
    for f in ALL_FIELDS:
        if f.condition and not f.condition(values):
            continue
        if f.dest == "config" and f.path in existing_config:
            values[f.path] = existing_config[f.path]
        elif f.dest == "secret" and f.path in existing_secrets:
            values[f.path] = existing_secrets[f.path]
        else:
            values[f.path] = f.default_fn()
    old_values = dict(values)

    new_values = menuconfig_loop(old_values)

    if new_values is None:
        console.print("[dim]Quit without saving.[/dim]")
        return

    console.print()
    has_changes = show_changes(old_values, new_values)

    if not has_changes:
        console.print("[dim]No changes to apply.[/dim]")
        return

    if not confirm_save():
        console.print("[red]Changes aborted.[/red]")
        return

    console.print()
    save_all(new_values)
    console.print()
    console.print(Panel("[bold green]All files saved successfully![/bold green]", border_style="green"))

    # Ask if user wants to apply immediately
    try:
        answer = pt_prompt("? Apply configuration now (envy apply)? [y/N]: ")
        if answer.lower().startswith("y"):
            console.print("[cyan]Running envy apply...[/cyan]")
            from envy.main import cmd_apply
            cmd_apply()
    except (EOFError, KeyboardInterrupt):
        pass


if __name__ == "__main__":
    main()