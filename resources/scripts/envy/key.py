"""Key lifecycle management for sops/age encryption — Typer subgroup for envy key."""

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

import typer
from rich.prompt import Confirm
from rich.table import Table
from prompt_toolkit import prompt as pt_prompt
from prompt_toolkit.application import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.layout import Layout, Window, HSplit, FormattedTextControl
from prompt_toolkit.layout.controls import BufferControl
from prompt_toolkit.styles import Style as PtStyle
from prompt_toolkit.widgets import Frame

from envy import log
from envy.utils import (
    DOTFILES_DIR, HOME_DIR, AGE_KEY_DIR, AGE_KEY_FILE,
    SOPS_YAML, SECRETS_DIR, SECRETS_FILE, RECOVERY_KEY_FILE,
    DEVICE_LABEL_FILE, run_cmd, backup_sensitive_file,
    device_metadata_is_toml, is_sops_encrypted, read_device_metadata,
    write_device_metadata,
)

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


def complete_sops_labels(ctx, incomplete):
    """Complete key labels from .sops.yaml for envy key remove."""
    if not SOPS_YAML.exists():
        return []
    text = SOPS_YAML.read_text()
    pattern = re.compile(r'- &(\S+)\s+(age1\S+)')
    labels = [match.group(1) for match in pattern.finditer(text)]
    return [name for name in labels if name.startswith(incomplete)]

# ==========================================
# UTILITIES
# ==========================================


def sanitize_label(name: str) -> str:
    return re.sub(r'[^a-z0-9_]', '_', name.lower())


def confirm(prompt_text: str) -> bool:
    """Require explicit y/n confirmation. Auto-answer yes with --yes/-y."""
    if _yes_flag:
        log.hint(f"{prompt_text} → auto-yes")
        return True
    return Confirm.ask(prompt_text, console=log.console)

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
    backup_sensitive_file(SOPS_YAML)
    lines = ["keys:\n"]
    lines.append("  # Device keys - managed by envy key commands\n")
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


def get_sops_label() -> str:
    metadata = read_device_metadata()
    label = metadata.get("sops_label") or metadata.get("machine_id")
    if label:
        return sanitize_label(label)
    hostname = run_cmd(["hostname", "-s"], check=False, capture=True)
    return sanitize_label(hostname) if hostname else "unknown"


def set_sops_label(label: str) -> None:
    normalized = sanitize_label(label) or "unknown"
    write_device_metadata(sops_label=normalized)


def ensure_sops_label() -> str:
    """Return and persist a stable sops key label for the current device."""
    stored = read_device_metadata().get("sops_label", "")
    if stored:
        label = get_sops_label()
        if stored != label or not device_metadata_is_toml():
            set_sops_label(label)
        return label

    # Recover the label from .sops.yaml when the local marker was deleted.
    # This avoids replacing a deliberate label with the hostname on an
    # existing device.
    current_pub = get_current_device_public_key()
    if current_pub:
        matching_labels = [
            label for label, pubkey in read_sops_yaml_keys().items()
            if label != "recovery" and pubkey == current_pub and sanitize_label(label) == label
        ]
        if matching_labels:
            set_sops_label(matching_labels[0])
            return matching_labels[0]

    label = get_sops_label()
    set_sops_label(label)
    return label

# ==========================================
# KEY STATE
# ==========================================


def get_current_device_public_key() -> Optional[str]:
    if not AGE_KEY_FILE.exists():
        return None
    try:
        return run_cmd(["age-keygen", "-y", str(AGE_KEY_FILE)], capture=True)
    except subprocess.CalledProcessError:
        return None


def run_sops_updatekeys() -> None:
    if not SECRETS_FILE.exists():
        log.warn("key", "no secrets file to updatekeys")
        return
    if not is_sops_encrypted(SECRETS_FILE):
        log.warn("key", "secrets.yaml is not sops-encrypted")
        log.hint("To use sops-nix, secrets.yaml must be encrypted with your device keys.")
        if not confirm("Encrypt secrets.yaml now?"):
            log.hint("Skipping updatekeys — secrets.yaml remains unencrypted.")
            return
        log.step("key", "encrypting secrets.yaml")
        backup_sensitive_file(SECRETS_FILE)
        run_cmd(["sops", "--encrypt", "--in-place", str(SECRETS_FILE)], capture=True)
    backup_sensitive_file(SECRETS_FILE)
    run_cmd(["sops", "updatekeys", "--yes", str(SECRETS_FILE)], capture=True)
    log.ok("key", "secrets re-encrypted with updated key list")


def _stage_repo_files(files: list[Path]) -> list[str]:
    """Stage explicit repository files and return changed relative pathspecs."""
    if not (DOTFILES_DIR / ".git").exists():
        return []

    repository = DOTFILES_DIR.resolve()
    changed: list[str] = []
    seen: set[str] = set()
    for file in files:
        if not file.exists():
            continue
        try:
            relative = str(file.resolve().relative_to(repository))
        except ValueError:
            log.error("git", "refusing to stage a file outside the dotfiles repository", path=str(file))
            continue
        if relative in seen:
            continue
        seen.add(relative)

        stage = subprocess.run(
            ["git", "add", "--", relative],
            capture_output=True, text=True, check=False,
            cwd=str(DOTFILES_DIR),
        )
        if stage.returncode != 0:
            log.error("git", "failed to stage managed file", path=relative)
            continue
        diff = subprocess.run(
            ["git", "diff", "--cached", "--quiet", "--", relative],
            capture_output=True, text=True, check=False,
            cwd=str(DOTFILES_DIR),
        )
        if diff.returncode == 1:
            changed.append(relative)
        elif diff.returncode != 0:
            log.error("git", "failed to inspect staged managed file", path=relative)
    return changed


def _commit_staged_files(changed: list[str], message: str) -> None:
    display = ", ".join(changed)
    if not confirm(f"Commit {display} to git?"):
        log.warn("git", "managed changes staged but not committed")
        log.hint("Review with: envy git diff --cached")
        log.hint("Commit later with: envy git commit")
        return

    result = subprocess.run(
        ["git", "commit", "-m", message, "--", *changed],
        capture_output=True, text=True, check=False,
        cwd=str(DOTFILES_DIR),
    )
    if result.returncode != 0:
        log.error("git", "commit failed", exit_code=result.returncode)
        log.hint("The managed files remain staged; inspect them with: envy git diff --cached")
        return
    log.ok("git", "committed", files=display)


def git_commit_sops_files(operation: str = "") -> None:
    if not (DOTFILES_DIR / ".git").exists():
        return

    label = get_sops_label()
    scope = f"sops/{operation}" if operation else "sops"

    changed = _stage_repo_files([SOPS_YAML, SECRETS_FILE, RECOVERY_KEY_FILE])

    if not changed:
        log.hint("sops files: no changes to commit")
        return

    names = [Path(f).name for f in changed]
    msg = f"chore({scope}): update keys on {label} ({', '.join(names)})"
    _commit_staged_files(changed, msg)


def git_commit_setup_files(machine_path: Path) -> None:
    """Offer one scoped commit for files managed by an envy setup save."""
    if not (DOTFILES_DIR / ".git").exists():
        return

    changed = _stage_repo_files([
        machine_path,
        SOPS_YAML,
        SECRETS_FILE,
        RECOVERY_KEY_FILE,
    ])
    if not changed:
        log.hint("setup files: no changes to commit")
        return

    names = [Path(path).name for path in changed]
    message = (
        f"chore(setup): update {machine_path.stem} configuration "
        f"({', '.join(names)})"
    )
    _commit_staged_files(changed, message)

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

    recovery_priv = run_cmd(["age", "--decrypt", "-i", str(AGE_KEY_FILE), str(RECOVERY_KEY_FILE)], capture=True)

    recipients = list(keys.values())
    encrypt_args = ["age", "--encrypt"]
    for pub in recipients:
        encrypt_args.extend(["-r", pub])

    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".age", dir=str(SECRETS_DIR))
    try:
        os.close(tmp_fd)
        run_cmd(encrypt_args + ["-o", tmp_path], stdin_data=recovery_priv, capture=True)
        backup_sensitive_file(RECOVERY_KEY_FILE)
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
    current_label = get_sops_label()

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

    log.console.print(table)

    if current_pub and current_pub in keys.values():
        log.ok("key", "current device CAN decrypt secrets")
    elif current_pub:
        log.error("key", "current device key NOT in .sops.yaml — cannot decrypt")
        log.hint("Run: envy key import or envy key add")
    else:
        log.error("key", "no age key on this device")
        log.hint("Run: envy key import")


def key_status() -> None:
    current_pub = get_current_device_public_key()
    keys = read_sops_yaml_keys()
    label = get_sops_label()

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

    items.append(("Sops key label", label, str(DEVICE_LABEL_FILE)))

    has_recovery = "recovery" in keys
    items.append(("Recovery key", "[green]YES[/green]" if has_recovery else "[yellow]NO[/yellow]", ""))

    can_decrypt = False
    if SECRETS_FILE.exists() and current_pub and current_pub in keys.values():
        try:
            run_cmd(["sops", "--decrypt", str(SECRETS_FILE)], check=True, capture=True)
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
    log.console.print(table)


def key_add(pubkey: str, label: Optional[str] = None) -> None:
    if not pubkey.startswith("age1"):
        log.error("key", "invalid age public key (must start with 'age1')")
        return

    if len(pubkey) < 58:
        log.error("key", f"invalid age public key (too short: {len(pubkey)} chars, expected ~58-62)")
        return

    keys = read_sops_yaml_keys()
    if pubkey in keys.values():
        log.warn("key", "key already exists in .sops.yaml")
        return

    if label is None:
        label = f"device_{len(keys)}"
    label = sanitize_label(label)

    if label in keys:
        log.error("key", f"label '{label}' already used, choose a different label")
        return

    try:
        run_cmd(["age", "--encrypt", "-r", pubkey, "-o", "/dev/null"], stdin_data="test", capture=True)
    except subprocess.CalledProcessError:
        log.error("key", "key rejected by age — not a valid recipient")
        return

    new_keys = dict(keys)
    new_keys[label] = pubkey

    if RECOVERY_KEY_FILE.exists():
        try:
            _reencrypt_recovery_key_with(new_keys)
        except (subprocess.CalledProcessError, RuntimeError):
            log.warn("key", "recovery key reencryption failed with new key, key will still be added")
            log.hint("Run: envy key add-recovery")

    write_sops_yaml_keys(new_keys)

    if SECRETS_FILE.exists():
        try:
            run_sops_updatekeys()
        except subprocess.CalledProcessError:
            log.warn("key", "sops updatekeys failed — secrets may not be re-encrypted for the new key yet")

    git_commit_sops_files("add")
    log.ok("key", "key added", label=label)


def key_remove(label: str, force: bool = False) -> None:
    keys = read_sops_yaml_keys()
    current_pub = get_current_device_public_key()

    if label not in keys:
        log.error("key", f"label '{label}' not found in .sops.yaml")
        return

    if label == "recovery":
        log.error("key", "cannot remove the recovery key — it ensures decryptability during rotation")
        return

    if keys[label] == current_pub:
        if not force and not confirm("This is your CURRENT device key! Removing it will make secrets inaccessible here. Remove anyway?"):
            log.warn("key", "skipped")
            return

    remaining = len(keys) - 1
    if remaining < 2:
        log.error("key", "cannot remove — at least one device key and the recovery key must remain")
        return

    removed_pub = keys.pop(label)
    write_sops_yaml_keys(keys)

    reencrypt_recovery_key(keys)

    run_sops_updatekeys()
    git_commit_sops_files("remove")
    log.ok("key", "key removed", label=label, pubkey=removed_pub[:24] + "...")
    log.warn("key", "that device will NO LONGER be able to decrypt secrets")

    if removed_pub == current_pub:
        log.error("key", "WARNING: you removed your own key! Secrets inaccessible on this device until you import a new key")


def key_export(format: str = "age", output: Optional[str] = None) -> None:
    if not AGE_KEY_FILE.exists():
        log.error("key", "no age key on this device to export")
        return

    content = AGE_KEY_FILE.read_text().strip()
    pub = get_current_device_public_key()

    if format == "age":
        if output:
            Path(output).write_text(content + "\n")
            Path(output).chmod(0o600)
            log.ok("key", "age key exported", path=output)
        else:
            print(content)
    elif format == "ssh":
        ssh_key = HOME_DIR / ".ssh" / "id_ed25519"
        if ssh_key.exists():
            if output:
                Path(output).write_text(ssh_key.read_text())
                Path(output).chmod(0o600)
                log.ok("key", "SSH key exported", path=output)
            else:
                print(ssh_key.read_text().strip())
        else:
            log.warn("key", "no SSH key found, export as age format instead")
            return

    log.hint(f"Public key: {pub}")
    log.warn("key", "private keys are sensitive — transfer securely (USB, scp, encrypted channel)")


def key_import(
    age_path: Optional[str] = None,
    ssh_path: Optional[str] = None,
    generate: bool = False,
    label: Optional[str] = None,
) -> Optional[str]:
    """Import a key for the current device. Returns public key on success."""
    pub = None

    # If AGE_KEY_FILE already exists, confirm overwrite and backup before any write path
    if AGE_KEY_FILE.exists() and (age_path or ssh_path or generate):
        if not confirm(f"AGE_KEY_FILE already exists at {AGE_KEY_FILE}. Overwrite?"):
            log.warn("key", "import cancelled")
            return None
        backup_sensitive_file(AGE_KEY_FILE)

    if age_path:
        src = Path(age_path).expanduser()
        if not src.exists():
            log.error("key", "file not found", path=str(src))
            return None
        content = src.read_text().strip()
        if not content.startswith("AGE-SECRET-KEY"):
            log.error("key", "file does not appear to be an age key (missing AGE-SECRET-KEY prefix)")
            return None
        AGE_KEY_DIR.mkdir(parents=True, exist_ok=True)
        AGE_KEY_FILE.write_text(content + "\n")
        AGE_KEY_FILE.chmod(0o600)
        pub = run_cmd(["age-keygen", "-y", str(AGE_KEY_FILE)], capture=True)
        if pub:
            log.ok("key", "age key imported", pubkey=pub[:20] + "...")
    elif ssh_path:
        src = Path(ssh_path).expanduser()
        if not src.exists():
            log.error("key", "file not found", path=str(src))
            return None
        AGE_KEY_DIR.mkdir(parents=True, exist_ok=True)
        result = run_cmd(["ssh-to-age", "-private-key", "-i", str(src)], capture=True)
        AGE_KEY_FILE.write_text(result + "\n")
        pub_path = src.with_suffix(".pub")
        if pub_path.exists():
            pub_input = pub_path.read_text()
        else:
            log.warn("key", "no public key found, enter it manually", path=str(pub_path))
            pub_input = pt_prompt("SSH public key: ")
        pub = run_cmd(["ssh-to-age"], stdin_data=pub_input, capture=True)
        if pub:
            AGE_KEY_FILE.chmod(0o600)
            log.ok("key", "age key derived from SSH", pubkey=pub[:20] + "...")
    elif generate:
        AGE_KEY_DIR.mkdir(parents=True, exist_ok=True)
        run_cmd(["age-keygen", "-o", str(AGE_KEY_FILE)], capture=True)
        AGE_KEY_FILE.chmod(0o600)
        pub = run_cmd(["age-keygen", "-y", str(AGE_KEY_FILE)], capture=True)
        if pub:
            log.ok("key", "new age key generated", pubkey=pub[:20] + "...")
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
        log.error("key", "key import failed")
        return None

    # Set the sops key label in shared device metadata.
    if label:
        set_sops_label(sanitize_label(label))
    else:
        default_label = get_sops_label()
        try:
            user_label = pt_prompt(f"Sops key label [{default_label}]: ").strip()
        except (EOFError, KeyboardInterrupt):
            user_label = ""
        set_sops_label(sanitize_label(user_label) if user_label else default_label)

    # Add to .sops.yaml
    keys = read_sops_yaml_keys()
    current_label = get_sops_label()
    keys[current_label] = pub
    write_sops_yaml_keys(keys)

    # Re-encrypt recovery key to include new device
    reencrypt_recovery_key(keys)

    if SECRETS_FILE.exists():
        run_sops_updatekeys()
    git_commit_sops_files("import")

    log.ok("key", f"key imported and added to .sops.yaml as '{current_label}'")
    log.hint(f"Public key: {pub}")

    # Warn if recovery public key exists but recovery-key.age is missing
    if "recovery" in keys and not RECOVERY_KEY_FILE.exists():
        log.warn("key", "recovery key is in .sops.yaml but secrets/recovery-key.age is missing")
        log.hint("Without recovery-key.age, you cannot export (envy key rr) the recovery private key from this device.")

    # Warn if device key overlaps with recovery key
    keys = read_sops_yaml_keys()
    if "recovery" in keys and pub == keys["recovery"]:
        log.warn("key", "your device key is the same as the recovery key")
        log.hint("The recovery key should be kept separate for offline backup.")
        log.hint("It is recommended to rotate your device key to generate an independent one.")

        if not RECOVERY_KEY_FILE.exists():
            log.info("key", "the recovery private key needs to be sealed into secrets/recovery-key.age")
            log.hint("Sealing encrypts the recovery private key with all device public keys")
            log.warn("key", "if you skip sealing now, the recovery private key will be permanently lost after rotation")
            if confirm("Seal recovery key into recovery-key.age?"):
                key_seal_recovery()
            else:
                log.hint("Run: envy key seal-recovery")

        if confirm("Rotate device key now?"):
            key_rotate()
            new_pub = get_current_device_public_key()
            log.ok("key", "device key rotated", pubkey=new_pub)
            return new_pub

    return pub


def key_add_recovery() -> None:
    keys = read_sops_yaml_keys()
    if "recovery" in keys:
        log.warn("key", "recovery key already exists")
        log.hint("Run: envy key rotate --recovery")
        return

    recovery_priv = run_cmd(["age-keygen"], capture=True)
    priv_line = [l for l in recovery_priv.split("\n") if l.startswith("AGE-SECRET-KEY")][0]

    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', dir=str(SECRETS_DIR), delete=False) as tmp:
        tmp.write(priv_line + "\n")
        tmp_path = tmp.name
    try:
        os.chmod(tmp_path, 0o600)
        recovery_pub = run_cmd(["age-keygen", "-y", tmp_path], capture=True)
    finally:
        pass  # keep temp file for encryption step

    recipients = list(keys.values()) + [recovery_pub]
    encrypt_args = ["age", "--encrypt"]
    for pub in recipients:
        encrypt_args.extend(["-r", pub])
    encrypt_args.extend(["-o", str(RECOVERY_KEY_FILE), tmp_path])

    try:
        run_cmd(encrypt_args, capture=True)
    finally:
        os.unlink(tmp_path)

    keys["recovery"] = recovery_pub
    write_sops_yaml_keys(keys)

    if SECRETS_FILE.exists():
        run_sops_updatekeys()

    git_commit_sops_files("add_recovery")
    log.ok("key", "recovery key generated and added to .sops.yaml")
    log.hint(f"Recovery public key: {recovery_pub[:30]}...")
    log.info("key", "recovery private key is stored encrypted at secrets/recovery-key.age")
    log.warn("key", "IMPORTANT: also save the recovery key offline (USB/paper/password manager) as ultimate backup")


def key_seal_recovery(priv_path: Optional[str] = None) -> None:
    """Encrypt a recovery private key into secrets/recovery-key.age."""
    keys = read_sops_yaml_keys()
    if "recovery" not in keys:
        log.error("key", "no recovery key in .sops.yaml")
        log.hint("Run: envy key add-recovery")
        return

    if RECOVERY_KEY_FILE.exists():
        log.warn("key", "recovery-key.age already exists, re-encrypting with updated key list")
        reencrypt_recovery_key(keys)
        return

    if priv_path:
        src = Path(priv_path).expanduser()
        if not src.exists():
            log.error("key", "file not found", path=str(src))
            return
        recovery_priv = src.read_text().strip()
    else:
        current_pub = get_current_device_public_key()
        if not current_pub:
            log.error("key", "no current device key")
            log.hint("Run: envy key seal-recovery <path>")
            return
        if current_pub != keys["recovery"]:
            log.error("key", "current device key is not the recovery key")
            log.hint("Run: envy key seal-recovery <path>")
            return
        recovery_priv = AGE_KEY_FILE.read_text().strip()

    priv_lines = [l for l in recovery_priv.split("\n") if l.startswith("AGE-SECRET-KEY")]
    if not priv_lines:
        log.error("key", "provided key does not contain AGE-SECRET-KEY")
        return

    priv_line = priv_lines[0]
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', dir=str(SECRETS_DIR), delete=False) as tmp:
        tmp.write(priv_line + "\n")
        tmp_path = tmp.name
    try:
        os.chmod(tmp_path, 0o600)
        derived_pub = run_cmd(["age-keygen", "-y", tmp_path], capture=True)
    finally:
        os.unlink(tmp_path)

    if derived_pub != keys["recovery"]:
        log.error("key", "derived public key does not match recovery key in .sops.yaml")
        log.hint(f"Expected: {keys['recovery'][:30]}...")
        log.hint(f"Got:      {derived_pub[:30]}...")
        return

    recipients = list(keys.values())
    encrypt_args = ["age", "--encrypt"]
    for pub in recipients:
        encrypt_args.extend(["-r", pub])
    encrypt_args.extend(["-o", str(RECOVERY_KEY_FILE)])

    run_cmd(encrypt_args, stdin_data=priv_line + "\n", capture=True)

    if SECRETS_FILE.exists():
        run_sops_updatekeys()
    git_commit_sops_files("seal_recovery")
    log.ok("key", "recovery private key sealed into secrets/recovery-key.age")
    log.hint("Encrypted for all device keys in .sops.yaml")


def key_recover_recovery(output: Optional[str] = None) -> None:
    """Decrypt the stored recovery private key."""
    if not RECOVERY_KEY_FILE.exists():
        log.error("key", "no recovery-key.age file found in repo")
        return

    current_pub = get_current_device_public_key()
    if not current_pub:
        log.error("key", "no age key on this device to decrypt recovery key")
        return

    decrypted = run_cmd(["age", "--decrypt", "-i", str(AGE_KEY_FILE), str(RECOVERY_KEY_FILE)], capture=True)

    if output:
        Path(output).write_text(decrypted)
        Path(output).chmod(0o600)
        log.ok("key", "recovery key decrypted and saved", path=output)
    else:
        log.warn("key", "recovery private key:")
        print(decrypted)
        log.hint("Use --output to save to a file safely.")


def key_rotate(recovery: bool = False) -> None:
    """Rotate current device key or recovery key."""
    keys = read_sops_yaml_keys()

    if recovery:
        current_pub = get_current_device_public_key()
        if not current_pub or current_pub not in keys.values():
            log.error("key", "current device key must be in .sops.yaml to rotate recovery key")
            return

        old_recovery_pub = keys.get("recovery")
        if not old_recovery_pub:
            log.error("key", "no recovery key to rotate")
            log.hint("Run: envy key add-recovery")
            return

        log.step("key", "rotating recovery key")
        log.hint(f"Old recovery: {old_recovery_pub[:30]}...")

        recovery_priv = run_cmd(["age-keygen"], capture=True)
        priv_line = [l for l in recovery_priv.split("\n") if l.startswith("AGE-SECRET-KEY")][0]

        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', dir=str(SECRETS_DIR), delete=False) as tmp:
            tmp.write(priv_line + "\n")
            tmp_path = tmp.name
        try:
            os.chmod(tmp_path, 0o600)
            new_recovery_pub = run_cmd(["age-keygen", "-y", tmp_path], capture=True)
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
            run_cmd(encrypt_args, capture=True)
        finally:
            os.unlink(tmp_path)

        keys.pop("recovery")
        keys["recovery"] = new_recovery_pub
        keys.pop("recovery_new")
        write_sops_yaml_keys(keys)
        run_sops_updatekeys()
        git_commit_sops_files("rotate_recovery")

        log.ok("key", "recovery key rotated", pubkey=new_recovery_pub[:30] + "...")
        log.warn("key", "IMPORTANT: save the new recovery key offline (USB/paper/password manager)")
        return

    # Rotate device key
    current_pub = get_current_device_public_key()
    if not current_pub:
        log.error("key", "no current key to rotate")
        log.hint("Run: envy key import")
        return

    label = ensure_sops_label()
    if current_pub not in keys.values():
        log.error("key", "current device key not in .sops.yaml, cannot rotate")
        return

    if "recovery" not in keys:
        log.error("key", "no recovery key in .sops.yaml — rotation is unsafe without a recovery key")
        log.hint("Run: envy key add-recovery")
        return

    log.step("key", f"rotating key for device '{label}'")
    log.hint(f"Old public key: {current_pub[:30]}...")

    old_key_content = AGE_KEY_FILE.read_text().strip()

    import uuid
    tmp_path = str(AGE_KEY_DIR / f"rotate_{uuid.uuid4().hex[:8]}.txt")
    run_cmd(["age-keygen", "-o", tmp_path], capture=True)
    os.chmod(tmp_path, 0o600)
    new_pub = run_cmd(["age-keygen", "-y", tmp_path], capture=True)

    log.hint(f"New public key: {new_pub[:30]}...")

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

    backup_sensitive_file(AGE_KEY_FILE)
    AGE_KEY_FILE.write_text(new_key_content + "\n")
    AGE_KEY_FILE.chmod(0o600)

    if os.path.exists(tmp_path):
        os.unlink(tmp_path)

    git_commit_sops_files("rotate")

    log.ok("key", f"key rotation complete for '{label}'")
    log.hint(f"New public key: {new_pub}")


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
    label: str = typer.Argument(help="Label of key to remove", autocompletion=complete_sops_labels),
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
    label: Optional[str] = typer.Option(None, "--label", "-l", help="Sops key label"),
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
