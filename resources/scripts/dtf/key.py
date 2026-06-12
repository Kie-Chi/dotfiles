"""Key lifecycle management for sops/age encryption — Typer subgroup for dtf key."""

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

import typer
from click.shell_completion import CompletionItem
from rich.console import Console
from rich.table import Table
from prompt_toolkit import prompt as pt_prompt
from prompt_toolkit.application import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout, Window, HSplit, FormattedTextControl
from prompt_toolkit.layout.controls import BufferControl
from prompt_toolkit.styles import Style as PtStyle
from prompt_toolkit.widgets import Frame

from dtf.utils import (
    DOTFILES_DIR, HOME_DIR, AGE_KEY_DIR, AGE_KEY_FILE,
    SOPS_YAML, SECRETS_DIR, SECRETS_FILE, RECOVERY_KEY_FILE,
    DEVICE_LABEL_FILE, run_cmd, is_debug,
    CYAN, GREEN, YELLOW, RED, NC,
)

console = Console()

# Typer subgroup
app = typer.Typer(
    name="key",
    help="Manage age keys for sops encryption",
    rich_markup_mode="rich",
    no_args_is_help=True,
)

# --yes/-y global flag
_yes_flag = False


def _set_yes_flag(yes: bool):
    global _yes_flag
    _yes_flag = yes

# ==========================================
# COMPLETION CALLBACKS
# ==========================================


def complete_sops_labels(ctx, param, incomplete):
    """Complete key labels from .sops.yaml for dtf key remove."""
    if not SOPS_YAML.exists():
        return []
    text = SOPS_YAML.read_text()
    pattern = re.compile(r'- &(\S+)\s+(age1\S+)')
    labels = [match.group(1) for match in pattern.finditer(text)]
    return [CompletionItem(name) for name in labels if name.startswith(incomplete)]

# ==========================================
# UTILITIES
# ==========================================


def _is_sops_encrypted(path: Path) -> bool:
    """Check whether a YAML file contains sops metadata."""
    try:
        with open(path) as f:
            for line in f:
                if line.startswith("sops:"):
                    return True
    except (OSError, UnicodeDecodeError):
        return False
    return False


def sanitize_label(name: str) -> str:
    return re.sub(r'[^a-z0-9_]', '_', name.lower())


def confirm(prompt_text: str) -> bool:
    """Ask user for y/N confirmation. Auto-answers yes if --yes/-y was set."""
    if _yes_flag:
        console.print(f"[dim]{prompt_text} → auto-yes[/dim]")
        return True
    return typer.confirm(f"{prompt_text} [y/N]", default=False)

# ==========================================
# SOPS YAML I/O
# ==========================================


def read_sops_yaml_keys() -> Dict[str, str]:
    """Parse .sops.yaml for labeled age keys. Returns {label: public_key}."""
    if not SOPS_YAML.exists():
        return {}
    text = SOPS_YAML.read_text()
    pattern = re.compile(r'- &(\S+)\s+(age1\S+)')
    keys = {}
    for match in pattern.finditer(text):
        label, pubkey = match.group(1), match.group(2)
        keys[label] = pubkey
    return keys


def write_sops_yaml_keys(keys: Dict[str, str]) -> None:
    """Write .sops.yaml with labeled keys and creation rules."""
    lines = ["keys:\n"]
    lines.append("  # Device keys - managed by dtf key commands\n")
    for label, pubkey in keys.items():
        lines.append(f"  - &{label} {pubkey}\n")
    lines.append("\ncreation_rules:\n")
    lines.append("  - path_regex: secrets/secrets\\.yaml$\n")
    lines.append("    key_groups:\n")
    lines.append("      - age:\n")
    for label in keys:
        lines.append(f"          - *{label}\n")
    SOPS_YAML.write_text("".join(lines))

# ==========================================
# DEVICE IDENTITY
# ==========================================


def get_device_label() -> str:
    if DEVICE_LABEL_FILE.exists():
        return DEVICE_LABEL_FILE.read_text().strip()
    hostname = run_cmd(["hostname", "-s"], check=False)
    return sanitize_label(hostname) if hostname else "unknown"


def set_device_label(label: str) -> None:
    DEVICE_LABEL_FILE.write_text(label)

# ==========================================
# KEY STATE
# ==========================================


def get_current_device_public_key() -> Optional[str]:
    if not AGE_KEY_FILE.exists():
        return None
    try:
        return run_cmd(["age-keygen", "-y", str(AGE_KEY_FILE)])
    except subprocess.CalledProcessError:
        return None


def run_sops_updatekeys() -> None:
    if not SECRETS_FILE.exists():
        console.print("[yellow]No secrets file to updatekeys.[/yellow]")
        return
    if not _is_sops_encrypted(SECRETS_FILE):
        console.print("[yellow]secrets.yaml is not sops-encrypted.[/yellow]")
        console.print("To use sops-nix, secrets.yaml must be encrypted with your device keys.")
        if not confirm("Encrypt secrets.yaml now?"):
            console.print("[dim]Skipping updatekeys — secrets.yaml remains unencrypted.[/dim]")
            return
        console.print("[cyan]Encrypting secrets.yaml...[/cyan]")
        run_cmd(["sops", "--encrypt", "--in-place", str(SECRETS_FILE)])
    run_cmd(["sops", "updatekeys", "--yes", str(SECRETS_FILE)])
    console.print("[green]Secrets re-encrypted with updated key list.[/green]")


def git_commit_sops_files(operation: str = "") -> None:
    if not (DOTFILES_DIR / ".git").exists():
        return

    label = get_device_label()
    scope = f"sops/{operation}" if operation else "sops"

    files = [str(SOPS_YAML), str(SECRETS_FILE), str(RECOVERY_KEY_FILE)]
    changed = []

    for f in files:
        if not Path(f).exists():
            continue
        run_cmd(["git", "add", f], check=False)
        rc = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", f],
            capture_output=True, text=True, check=False,
            cwd=str(DOTFILES_DIR),
        ).returncode
        if rc == 1:
            changed.append(f)

    if not changed:
        console.print("[dim]sops files: no changes to commit[/dim]")
        return

    names = [Path(f).name for f in changed]
    msg = f"chore({scope}): update keys on {label} ({', '.join(names)})"
    if not confirm(f"Commit {', '.join(names)} to git?"):
        console.print("[yellow]Changes not committed. Run 'dtf git add . && dtf git commit' manually.[/yellow]")
        return
    run_cmd(["git", "commit", "-m", msg, "--"] + changed, check=False)
    console.print(f"[green]{', '.join(names)} committed[/green]")

# ==========================================
# RECOVERY KEY MANAGEMENT
# ==========================================


def _reencrypt_recovery_key_with(keys: Dict[str, str]) -> None:
    """Re-encrypt recovery-key.age with the given key set."""
    if not RECOVERY_KEY_FILE.exists():
        return
    current_pub = get_current_device_public_key()
    if not current_pub:
        raise RuntimeError("No current device key")

    recovery_priv = run_cmd(["age", "--decrypt", "-i", str(AGE_KEY_FILE), str(RECOVERY_KEY_FILE)])

    recipients = list(keys.values())
    encrypt_args = ["age", "--encrypt"]
    for pub in recipients:
        encrypt_args.extend(["-r", pub])

    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".age", dir=str(SECRETS_DIR))
    try:
        os.close(tmp_fd)
        run_cmd(encrypt_args + ["-o", tmp_path], stdin_data=recovery_priv)
        os.replace(tmp_path, str(RECOVERY_KEY_FILE))
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def reencrypt_recovery_key(keys: Dict[str, str]) -> None:
    """Re-encrypt recovery-key.age with all current device keys from .sops.yaml."""
    current_keys = read_sops_yaml_keys()
    if current_keys != keys:
        _reencrypt_recovery_key_with(keys)
    else:
        _reencrypt_recovery_key_with(current_keys)

# ==========================================
# INTERACTIVE MENU (prompt_toolkit)
# ==========================================


def _select_menu(items: list, title: str = "Select") -> Optional[tuple]:
    """Arrow-key navigation menu using prompt_toolkit Application.
    items: list of (fragments, action_type, data)
    Returns (action_type, data) on Enter, None on Esc/q."""

    class MenuState:
        cursor = 0
        result = None

    state = MenuState()

    def render():
        lines = [("class:title", f"  {title}\n")]
        for i, (fragments, action, data) in enumerate(items):
            base = "class:cursor" if i == state.cursor else "class:normal"
            prefix = "  ► " if i == state.cursor else "    "
            lines.append((base, prefix))
            for style_suffix, text in fragments:
                if style_suffix:
                    lines.append((f"class:{style_suffix}", text))
                else:
                    lines.append((base, text))
            lines.append((base, "\n"))
        lines.append(("class:bottom", "\n  Enter: confirm  │  Esc/q: cancel  │  ↑↓: navigate"))
        return lines

    kb = KeyBindings()

    @kb.add("up")
    def _(event):
        if state.cursor > 0:
            state.cursor -= 1
        event.app.invalidate()

    @kb.add("down")
    def _(event):
        if state.cursor < len(items) - 1:
            state.cursor += 1
        event.app.invalidate()

    @kb.add("enter")
    def _(event):
        _, action, data = items[state.cursor]
        state.result = (action, data)
        event.app.exit()

    @kb.add("escape")
    @kb.add("q")
    def _(event):
        state.result = None
        event.app.exit()

    content = FormattedTextControl(render)
    layout = Layout(Window(content=content))
    style = PtStyle.from_dict({
        "title": "#ansicyan bold",
        "cursor": "bg:#ansicyan #ansiblack bold",
        "normal": "",
        "usb": "#ansiyellow bold",
        "bottom": "#ansigray",
    })

    app_instance = Application(layout=layout, key_bindings=kb, style=style, full_screen=True)
    app_instance.run()
    return state.result

# ==========================================
# USB KEY SCANNING
# ==========================================


def scan_usb_key_files() -> List[Path]:
    """Scan mounted USB drives for .age/.age.txt files."""
    candidates = []
    mount_dirs = []

    if sys.platform == "darwin":
        mount_dirs = [Path("/Volumes")]
    else:
        mount_dirs = [Path(f"/media/{os.getenv('USER', '')}"), Path("/mnt")]

    for mount_dir in mount_dirs:
        if not mount_dir.exists():
            continue
        for volume in mount_dir.iterdir():
            if not volume.is_dir():
                continue

            recovery_dir = volume / "recovery"
            if recovery_dir.exists() and recovery_dir.is_dir():
                for f in sorted(recovery_dir.iterdir()):
                    if f.is_file() and (f.name.endswith(".age") or f.name.endswith(".age.txt")):
                        candidates.append(f)

            for f in sorted(volume.iterdir()):
                if f.is_file() and (f.name.endswith(".age") or f.name.endswith(".age.txt")):
                    candidates.append(f)

    return candidates

# ==========================================
# KEY SUBCOMMANDS
# ==========================================


def key_list() -> None:
    keys = read_sops_yaml_keys()
    current_pub = get_current_device_public_key()
    current_label = get_device_label()

    table = Table(title="Age Keys in .sops.yaml")
    table.add_column("Label", style="cyan")
    table.add_column("Public Key", style="white")
    table.add_column("Status")

    for label, pubkey in keys.items():
        is_current = pubkey == current_pub
        if label == "recovery":
            status = "[magenta]RECOVERY[/magenta]"
        elif is_current:
            status = "[green]THIS DEVICE[/green]"
        else:
            status = "[dim]remote[/dim]"
        table.add_row(label, pubkey[:24] + "...", status)

    console.print(table)

    if current_pub and current_pub in keys.values():
        console.print("[green]Current device CAN decrypt secrets.[/green]")
    elif current_pub:
        console.print("[red]Current device key NOT in .sops.yaml — cannot decrypt![/red]")
        console.print("[yellow]Run 'dtf key import' or 'dtf key add' to add this device's key.[/yellow]")
    else:
        console.print("[red]No age key on this device — run 'dtf key import' first.[/red]")


def key_status() -> None:
    current_pub = get_current_device_public_key()
    keys = read_sops_yaml_keys()
    label = get_device_label()

    items = []

    if AGE_KEY_FILE.exists():
        items.append(("Age key file", "[green]PRESENT[/green]", str(AGE_KEY_FILE)))
    else:
        items.append(("Age key file", "[red]MISSING[/red]", str(AGE_KEY_FILE)))

    if current_pub:
        items.append(("Public key", f"[green]{current_pub[:30]}...[/green]", ""))
        in_sops = current_pub in keys.values()
        items.append(("In .sops.yaml", "[green]YES[/green]" if in_sops else "[red]NO[/red]", ""))
    else:
        items.append(("Public key", "[red]NONE[/red]", ""))
        items.append(("In .sops.yaml", "[red]NO KEY[/red]", ""))

    items.append(("Device label", label, str(DEVICE_LABEL_FILE)))

    has_recovery = "recovery" in keys
    items.append(("Recovery key", "[green]YES[/green]" if has_recovery else "[yellow]NO[/yellow]", ""))

    can_decrypt = False
    if SECRETS_FILE.exists() and current_pub and current_pub in keys.values():
        try:
            run_cmd(["sops", "--decrypt", str(SECRETS_FILE)], check=True)
            can_decrypt = True
        except subprocess.CalledProcessError:
            can_decrypt = False
    status_str = "[green]YES[/green]" if can_decrypt else "[red]NO[/red]" if SECRETS_FILE.exists() else "[dim]N/A[/dim]"
    items.append(("Can decrypt", status_str, ""))

    items.append(("Total keys", str(len(keys)), ""))

    table = Table(title="Key Status")
    table.add_column("Property")
    table.add_column("Value")
    table.add_column("Detail")
    for prop, val, detail in items:
        table.add_row(prop, val, detail)
    console.print(table)


def key_add(pubkey: str, label: Optional[str] = None) -> None:
    if not pubkey.startswith("age1"):
        console.print("[red]Invalid age public key (must start with 'age1').[/red]")
        return

    if len(pubkey) < 58:
        console.print(f"[red]Invalid age public key (too short: {len(pubkey)} chars, expected ~58-62).[/red]")
        return

    keys = read_sops_yaml_keys()
    if pubkey in keys.values():
        console.print("[yellow]Key already exists in .sops.yaml.[/yellow]")
        return

    if label is None:
        label = f"device_{len(keys)}"
    label = sanitize_label(label)

    if label in keys:
        console.print(f"[red]Label '{label}' already used. Choose a different label.[/red]")
        return

    try:
        run_cmd(["age", "--encrypt", "-r", pubkey, "-o", "/dev/null"], stdin_data="test")
    except subprocess.CalledProcessError:
        console.print("[red]Key rejected by age — not a valid recipient.[/red]")
        return

    new_keys = dict(keys)
    new_keys[label] = pubkey

    if RECOVERY_KEY_FILE.exists():
        try:
            _reencrypt_recovery_key_with(new_keys)
        except (subprocess.CalledProcessError, RuntimeError):
            console.print("[yellow]Recovery key reencryption failed with new key. Key will still be added.[/yellow]")
            console.print("[yellow]Run 'dtf key add-recovery' to regenerate the recovery key after adding.[/yellow]")

    write_sops_yaml_keys(new_keys)

    if SECRETS_FILE.exists():
        try:
            run_sops_updatekeys()
        except subprocess.CalledProcessError:
            console.print("[yellow]sops updatekeys failed — secrets may not be re-encrypted for the new key yet.[/yellow]")

    git_commit_sops_files("add")
    console.print(f"[green]Key '{label}' added.[/green]")


def key_remove(label: str, force: bool = False) -> None:
    keys = read_sops_yaml_keys()
    current_pub = get_current_device_public_key()

    if label not in keys:
        console.print(f"[red]Label '{label}' not found in .sops.yaml.[/red]")
        return

    if label == "recovery":
        console.print("[red]Cannot remove the recovery key. It ensures decryptability during rotation.[/red]")
        return

    if keys[label] == current_pub:
        if not force and not confirm("This is your CURRENT device key! Removing it will make secrets inaccessible here. Remove anyway?"):
            console.print("[yellow]Skipped.[/yellow]")
            return

    remaining = len(keys) - 1
    if remaining < 2:
        console.print("[red]Cannot remove — at least one device key and the recovery key must remain.[/red]")
        return

    removed_pub = keys.pop(label)
    write_sops_yaml_keys(keys)

    reencrypt_recovery_key(keys)

    run_sops_updatekeys()
    git_commit_sops_files("remove")
    console.print(f"[green]Key '{label}' ({removed_pub[:24]}...) removed.[/green]")
    console.print("[yellow]That device will NO LONGER be able to decrypt secrets.[/yellow]")

    if removed_pub == current_pub:
        console.print("[bold red]WARNING: You removed your own key! Secrets inaccessible on this device until you import a new key.[/bold red]")


def key_export(format: str = "age", output: Optional[str] = None) -> None:
    if not AGE_KEY_FILE.exists():
        console.print("[red]No age key on this device to export.[/red]")
        return

    content = AGE_KEY_FILE.read_text().strip()
    pub = get_current_device_public_key()

    if format == "age":
        if output:
            Path(output).write_text(content + "\n")
            Path(output).chmod(0o600)
            console.print(f"[green]Age key exported to {output}[/green]")
        else:
            print(content)
    elif format == "ssh":
        ssh_key = HOME_DIR / ".ssh" / "id_ed25519"
        if ssh_key.exists():
            if output:
                Path(output).write_text(ssh_key.read_text())
                Path(output).chmod(0o600)
                console.print(f"[green]SSH key exported to {output}[/green]")
            else:
                print(ssh_key.read_text().strip())
        else:
            console.print("[yellow]No SSH key found. Export as age format instead.[/yellow]")
            return

    console.print(f"[dim]Public key: {pub}[/dim]")
    console.print("[yellow]WARNING: Private keys are sensitive. Transfer securely (USB, scp, encrypted channel).[/yellow]")


def key_import(
    age_path: Optional[str] = None,
    ssh_path: Optional[str] = None,
    generate: bool = False,
    label: Optional[str] = None,
) -> Optional[str]:
    """Import a key for the current device. Returns public key on success."""
    pub = None

    if age_path:
        src = Path(age_path).expanduser()
        if not src.exists():
            console.print(f"[red]File not found: {src}[/red]")
            return None
        content = src.read_text().strip()
        if not content.startswith("AGE-SECRET-KEY"):
            console.print("[red]File does not appear to be an age key (missing AGE-SECRET-KEY prefix)[/red]")
            return None
        AGE_KEY_DIR.mkdir(parents=True, exist_ok=True)
        AGE_KEY_FILE.write_text(content + "\n")
        AGE_KEY_FILE.chmod(0o600)
        pub = run_cmd(["age-keygen", "-y", str(AGE_KEY_FILE)])
        if pub:
            console.print(f"[green]Age key imported: {pub[:20]}...[/green]")
    elif ssh_path:
        src = Path(ssh_path).expanduser()
        if not src.exists():
            console.print(f"[red]File not found: {src}[/red]")
            return None
        AGE_KEY_DIR.mkdir(parents=True, exist_ok=True)
        with open(AGE_KEY_FILE, "w") as f:
            run_cmd(["ssh-to-age", "-private-key", "-i", str(src)])
        pub_path = src.with_suffix(".pub")
        if pub_path.exists():
            pub_input = pub_path.read_text()
        else:
            console.print(f"[yellow]No public key found at {pub_path}, enter it manually:[/yellow]")
            pub_input = pt_prompt("SSH public key: ")
        pub = run_cmd(["ssh-to-age"], stdin_data=pub_input)
        if pub:
            AGE_KEY_FILE.chmod(0o600)
            console.print(f"[green]Age key derived from SSH: {pub[:20]}...[/green]")
    elif generate:
        AGE_KEY_DIR.mkdir(parents=True, exist_ok=True)
        run_cmd(["age-keygen", "-o", str(AGE_KEY_FILE)])
        AGE_KEY_FILE.chmod(0o600)
        pub = run_cmd(["age-keygen", "-y", str(AGE_KEY_FILE)])
        if pub:
            console.print(f"[green]New age key generated: {pub[:20]}...[/green]")
    else:
        # Interactive mode — arrow-key navigation menu
        usb_files = scan_usb_key_files()

        items = []
        for f in usb_files:
            tag_text = "USB " if f.parent.name == "recovery" else "USB "
            path_text = str(f)
            items.append(([("usb", tag_text), ("", path_text)], "usb", str(f)))
        items.append(([("", "Import age key file (specify path)")], "age_manual", ""))
        items.append(([("", "Import SSH key and derive age key")], "ssh_manual", ""))
        items.append(([("", "Generate new age key")], "generate", ""))
        items.append(([("", "Quit")], "quit", ""))

        result = _select_menu(items, title="Import age key for this device")
        if result is None or result[0] == "quit":
            return None

        action, data = result
        if action == "usb":
            return key_import(age_path=data, label=label)
        elif action == "age_manual":
            default_path = "~/Library/Application Support/sops/age/keys.txt"
            try:
                path = pt_prompt(f"Path to age key file [{default_path}]: ").strip()
            except (EOFError, KeyboardInterrupt):
                return None
            if not path:
                path = default_path
            return key_import(age_path=path, label=label)
        elif action == "ssh_manual":
            default_ssh = "~/.ssh/id_ed25519"
            try:
                path = pt_prompt(f"Path to SSH private key [{default_ssh}]: ").strip()
            except (EOFError, KeyboardInterrupt):
                return None
            if not path:
                path = default_ssh
            return key_import(ssh_path=path, label=label)
        elif action == "generate":
            return key_import(generate=True, label=label)

    if not pub:
        console.print("[red]Key import failed.[/red]")
        return None

    # Set device label
    if label:
        set_device_label(sanitize_label(label))
    else:
        default_label = get_device_label()
        try:
            user_label = pt_prompt(f"Device label [{default_label}]: ").strip()
        except (EOFError, KeyboardInterrupt):
            user_label = ""
        set_device_label(sanitize_label(user_label) if user_label else default_label)

    # Add to .sops.yaml
    keys = read_sops_yaml_keys()
    current_label = get_device_label()
    keys[current_label] = pub
    write_sops_yaml_keys(keys)

    # Re-encrypt recovery key to include new device
    reencrypt_recovery_key(keys)

    if SECRETS_FILE.exists():
        run_sops_updatekeys()
    git_commit_sops_files("import")

    console.print(f"[green]Key imported and added to .sops.yaml as '{current_label}'.[/green]")
    console.print(f"[green]Public key: {pub}[/green]")

    # Warn if recovery public key exists but recovery-key.age is missing
    if "recovery" in keys and not RECOVERY_KEY_FILE.exists():
        console.print("[bold yellow]WARNING: Recovery key is in .sops.yaml but secrets/recovery-key.age is missing.[/bold yellow]")
        console.print("[yellow]Without recovery-key.age, you cannot export (dtf key rr) the recovery private key from this device.[/yellow]")

    # Warn if device key overlaps with recovery key
    keys = read_sops_yaml_keys()
    if "recovery" in keys and pub == keys["recovery"]:
        console.print("[bold yellow]WARNING: Your device key is the same as the recovery key.[/bold yellow]")
        console.print("The recovery key should be kept separate for offline backup.")
        console.print("It is recommended to rotate your device key to generate an independent one.")

        if not RECOVERY_KEY_FILE.exists():
            console.print("[cyan]The recovery private key needs to be sealed into secrets/recovery-key.age.[/cyan]")
            console.print("[dim]Sealing encrypts the recovery private key with all device public keys[/dim]")
            console.print("[yellow]If you skip sealing now, the recovery private key will be permanently lost after rotation,[/yellow]")
            if confirm("Seal recovery key into recovery-key.age?"):
                key_seal_recovery()
            else:
                console.print("[yellow]Skipping seal. Run 'dtf key seal-recovery' manually before rotating.[/yellow]")

        if confirm("Rotate device key now?"):
            key_rotate()
            new_pub = get_current_device_public_key()
            console.print(f"[green]Device key rotated. New public key: {new_pub}[/green]")
            return new_pub

    return pub


def key_add_recovery() -> None:
    keys = read_sops_yaml_keys()
    if "recovery" in keys:
        console.print("[yellow]Recovery key already exists. Use 'dtf key rotate --recovery' to replace it.[/yellow]")
        return

    recovery_priv = run_cmd(["age-keygen"])
    priv_line = [l for l in recovery_priv.split("\n") if l.startswith("AGE-SECRET-KEY")][0]

    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', dir=str(SECRETS_DIR), delete=False) as tmp:
        tmp.write(priv_line + "\n")
        tmp_path = tmp.name
    try:
        os.chmod(tmp_path, 0o600)
        recovery_pub = run_cmd(["age-keygen", "-y", tmp_path])
    finally:
        pass  # keep temp file for encryption step

    recipients = list(keys.values()) + [recovery_pub]
    encrypt_args = ["age", "--encrypt"]
    for pub in recipients:
        encrypt_args.extend(["-r", pub])
    encrypt_args.extend(["-o", str(RECOVERY_KEY_FILE), tmp_path])

    try:
        run_cmd(encrypt_args)
    finally:
        os.unlink(tmp_path)

    keys["recovery"] = recovery_pub
    write_sops_yaml_keys(keys)

    if SECRETS_FILE.exists():
        run_sops_updatekeys()

    git_commit_sops_files("add_recovery")
    console.print(f"[green]Recovery key generated and added to .sops.yaml.[/green]")
    console.print(f"[dim]Recovery public key: {recovery_pub[:30]}...[/dim]")
    console.print("[cyan]Recovery private key is stored encrypted at secrets/recovery-key.age[/cyan]")
    console.print("[yellow]IMPORTANT: Also save the recovery key offline (USB/paper/password manager) as ultimate backup.[/yellow]")


def key_seal_recovery(priv_path: Optional[str] = None) -> None:
    """Encrypt a recovery private key into secrets/recovery-key.age."""
    keys = read_sops_yaml_keys()
    if "recovery" not in keys:
        console.print("[red]No recovery key in .sops.yaml. Run 'dtf key add-recovery' first.[/red]")
        return

    if RECOVERY_KEY_FILE.exists():
        console.print("[yellow]recovery-key.age already exists. Re-encrypting with updated key list...[/yellow]")
        reencrypt_recovery_key(keys)
        return

    if priv_path:
        src = Path(priv_path).expanduser()
        if not src.exists():
            console.print(f"[red]File not found: {src}[/red]")
            return
        recovery_priv = src.read_text().strip()
    else:
        current_pub = get_current_device_public_key()
        if not current_pub:
            console.print("[red]No current device key.[/red]")
            console.print("[yellow]Provide recovery private key path: dtf key seal-recovery <path>[/yellow]")
            return
        if current_pub != keys["recovery"]:
            console.print("[red]Current device key is not the recovery key.[/red]")
            console.print("[yellow]Provide recovery private key path: dtf key seal-recovery <path>[/yellow]")
            return
        recovery_priv = AGE_KEY_FILE.read_text().strip()

    priv_lines = [l for l in recovery_priv.split("\n") if l.startswith("AGE-SECRET-KEY")]
    if not priv_lines:
        console.print("[red]Provided key does not contain AGE-SECRET-KEY.[/red]")
        return

    priv_line = priv_lines[0]
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', dir=str(SECRETS_DIR), delete=False) as tmp:
        tmp.write(priv_line + "\n")
        tmp_path = tmp.name
    try:
        os.chmod(tmp_path, 0o600)
        derived_pub = run_cmd(["age-keygen", "-y", tmp_path])
    finally:
        os.unlink(tmp_path)

    if derived_pub != keys["recovery"]:
        console.print("[red]Derived public key does not match recovery key in .sops.yaml.[/red]")
        console.print(f"[dim]Expected: {keys['recovery'][:30]}...[/dim]")
        console.print(f"[dim]Got:      {derived_pub[:30]}...[/dim]")
        return

    recipients = list(keys.values())
    encrypt_args = ["age", "--encrypt"]
    for pub in recipients:
        encrypt_args.extend(["-r", pub])
    encrypt_args.extend(["-o", str(RECOVERY_KEY_FILE)])

    run_cmd(encrypt_args, stdin_data=priv_line + "\n")

    if SECRETS_FILE.exists():
        run_sops_updatekeys()
    git_commit_sops_files("seal_recovery")
    console.print("[green]Recovery private key sealed into secrets/recovery-key.age[/green]")
    console.print("[dim]Encrypted for all device keys in .sops.yaml[/dim]")


def key_recover_recovery(output: Optional[str] = None) -> None:
    """Decrypt the stored recovery private key."""
    if not RECOVERY_KEY_FILE.exists():
        console.print("[red]No recovery-key.age file found in repo.[/red]")
        return

    current_pub = get_current_device_public_key()
    if not current_pub:
        console.print("[red]No age key on this device to decrypt recovery key.[/red]")
        return

    decrypted = run_cmd(["age", "--decrypt", "-i", str(AGE_KEY_FILE), str(RECOVERY_KEY_FILE)])

    if output:
        Path(output).write_text(decrypted)
        Path(output).chmod(0o600)
        console.print(f"[green]Recovery key decrypted and saved to {output}[/green]")
    else:
        console.print("[yellow]Recovery private key:[/yellow]")
        console.print(decrypted)
        console.print("[yellow]Use --output to save to a file safely.[/yellow]")


def key_rotate(recovery: bool = False) -> None:
    """Rotate current device key or recovery key."""
    keys = read_sops_yaml_keys()

    if recovery:
        current_pub = get_current_device_public_key()
        if not current_pub or current_pub not in keys.values():
            console.print("[red]Current device key must be in .sops.yaml to rotate recovery key.[/red]")
            return

        old_recovery_pub = keys.get("recovery")
        if not old_recovery_pub:
            console.print("[red]No recovery key to rotate. Run 'dtf key add-recovery' first.[/red]")
            return

        console.print("[cyan]Rotating recovery key...[/cyan]")
        console.print(f"[dim]Old recovery: {old_recovery_pub[:30]}...[/dim]")

        recovery_priv = run_cmd(["age-keygen"])
        priv_line = [l for l in recovery_priv.split("\n") if l.startswith("AGE-SECRET-KEY")][0]

        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', dir=str(SECRETS_DIR), delete=False) as tmp:
            tmp.write(priv_line + "\n")
            tmp_path = tmp.name
        try:
            os.chmod(tmp_path, 0o600)
            new_recovery_pub = run_cmd(["age-keygen", "-y", tmp_path])
        finally:
            pass

        keys["recovery_new"] = new_recovery_pub
        write_sops_yaml_keys(keys)
        run_sops_updatekeys()

        recipients = [v for k, v in keys.items() if k != "recovery"] + [new_recovery_pub]
        encrypt_args = ["age", "--encrypt"]
        for pub in recipients:
            encrypt_args.extend(["-r", pub])
        encrypt_args.extend(["-o", str(RECOVERY_KEY_FILE), tmp_path])

        try:
            run_cmd(encrypt_args)
        finally:
            os.unlink(tmp_path)

        keys.pop("recovery")
        keys["recovery"] = new_recovery_pub
        keys.pop("recovery_new")
        write_sops_yaml_keys(keys)
        run_sops_updatekeys()
        git_commit_sops_files("rotate_recovery")

        console.print(f"[green]Recovery key rotated. New: {new_recovery_pub[:30]}...[/green]")
        console.print("[yellow]IMPORTANT: Save the new recovery key offline (USB/paper/password manager).[/yellow]")
        return

    # Rotate device key
    current_pub = get_current_device_public_key()
    if not current_pub:
        console.print("[red]No current key to rotate. Run 'dtf key import' first.[/red]")
        return

    label = get_device_label()
    if current_pub not in keys.values():
        console.print("[red]Current device key not in .sops.yaml. Cannot rotate.[/red]")
        return

    if "recovery" not in keys:
        console.print("[red]No recovery key in .sops.yaml! Rotation is unsafe without a recovery key.[/red]")
        console.print("[yellow]Generate a recovery key first: dtf key add-recovery[/yellow]")
        return

    console.print(f"[cyan]Rotating key for device '{label}'...[/cyan]")
    console.print(f"[dim]Old public key: {current_pub[:30]}...[/dim]")

    old_key_content = AGE_KEY_FILE.read_text().strip()

    import uuid
    tmp_path = str(AGE_KEY_DIR / f"rotate_{uuid.uuid4().hex[:8]}.txt")
    run_cmd(["age-keygen", "-o", tmp_path])
    os.chmod(tmp_path, 0o600)
    new_pub = run_cmd(["age-keygen", "-y", tmp_path])

    console.print(f"[dim]New public key: {new_pub[:30]}...[/dim]")

    new_key_content = Path(tmp_path).read_text().strip()
    AGE_KEY_FILE.write_text(old_key_content + "\n" + new_key_content + "\n")
    AGE_KEY_FILE.chmod(0o600)

    old_label_temp = f"{label}_old"
    keys[old_label_temp] = current_pub
    keys[label] = new_pub
    write_sops_yaml_keys(keys)
    run_sops_updatekeys()

    _reencrypt_recovery_key_with(keys)

    keys.pop(old_label_temp)
    write_sops_yaml_keys(keys)
    run_sops_updatekeys()

    AGE_KEY_FILE.write_text(new_key_content + "\n")
    AGE_KEY_FILE.chmod(0o600)

    if os.path.exists(tmp_path):
        os.unlink(tmp_path)

    git_commit_sops_files("rotate")

    console.print(f"[green]Key rotation complete for '{label}'.[/green]")
    console.print(f"[green]New public key: {new_pub}[/green]")


# ==========================================
# TYPER COMMAND REGISTRATION
# ==========================================

# Global -y/--yes flag handler
@app.callback()
def key_callback(
    yes: bool = typer.Option(False, "--yes", "-y", help="Auto-answer yes to all confirmations"),
):
    """Manage age keys for sops encryption."""
    _set_yes_flag(yes)
    # Also treat --force as auto-yes
    global _yes_flag


@app.command(name="list")
@app.command(name="ls", rich_help_panel="Aliases")
def cmd_list():
    """Show keys in .sops.yaml + current device status."""
    key_list()


@app.command(name="status")
@app.command(name="st", rich_help_panel="Aliases")
def cmd_status():
    """Check key status and decryptability."""
    key_status()


@app.command(name="add")
@app.command(name="a", rich_help_panel="Aliases")
def cmd_add(
    pubkey: str = typer.Argument(help="Age public key to add"),
    label: Optional[str] = typer.Option(None, "--label", "-l", help="Label for this key"),
):
    """Add a device key to .sops.yaml."""
    key_add(pubkey, label)


@app.command(name="remove")
@app.command(name="rm", rich_help_panel="Aliases")
def cmd_remove(
    label: str = typer.Argument(help="Label of key to remove", shell_complete=complete_sops_labels),
    force: bool = typer.Option(False, "--force", "-f", help="Allow removing current device key"),
):
    """Remove a device key from .sops.yaml."""
    key_remove(label, force)


@app.command(name="export")
@app.command(name="ex", rich_help_panel="Aliases")
def cmd_export(
    format: str = typer.Option("age", "--format", "-F", help="Export format (age, ssh)"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Output file path"),
):
    """Export current device key for transfer."""
    key_export(format, output)


@app.command(name="rotate")
def cmd_rotate(
    recovery: bool = typer.Option(False, "--recovery", "-r", help="Rotate recovery key instead"),
):
    """Rotate current device age key."""
    key_rotate(recovery)


@app.command(name="import")
@app.command(name="im", rich_help_panel="Aliases")
def cmd_import(
    age: Optional[str] = typer.Option(None, "--age", "-a", help="Path to age key file"),
    ssh: Optional[str] = typer.Option(None, "--ssh", "-s", help="Path to SSH private key"),
    generate: bool = typer.Option(False, "--generate", "-g", help="Generate a new age key"),
    label: Optional[str] = typer.Option(None, "--label", "-l", help="Device label"),
):
    """Import a key for current device."""
    result = key_import(age_path=age, ssh_path=ssh, generate=generate, label=label)
    if result is None and not age and not ssh and not generate:
        # Interactive mode returned None (user quit)
        raise typer.Exit()


@app.command(name="add-recovery")
@app.command(name="ar", rich_help_panel="Aliases")
def cmd_add_recovery():
    """Generate a recovery key."""
    key_add_recovery()


@app.command(name="seal-recovery")
@app.command(name="sr", rich_help_panel="Aliases")
def cmd_seal_recovery(
    priv_path: Optional[str] = typer.Argument(None, help="Path to recovery private key file"),
):
    """Encrypt recovery private key into recovery-key.age."""
    key_seal_recovery(priv_path)


@app.command(name="recover-recovery")
@app.command(name="rr", rich_help_panel="Aliases")
def cmd_recover_recovery(
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Save decrypted recovery key to file"),
):
    """Decrypt stored recovery key."""
    key_recover_recovery(output)