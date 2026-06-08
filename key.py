#!/usr/bin/env python3
"""Key lifecycle management for sops/age encryption.

Provides CLI subcommands: list, status, add, remove, export, import, rotate, add-recovery, recover-recovery
"""

import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

from rich.console import Console
from rich.table import Table
from prompt_toolkit import prompt as pt_prompt

# ==========================================
# PATHS
# ==========================================

BASE_DIR = Path(__file__).resolve().parent
HOME_DIR = Path.home()
AGE_KEY_DIR = HOME_DIR / "Library" / "Application Support" / "sops" / "age"
AGE_KEY_FILE = AGE_KEY_DIR / "keys.txt"
SOPS_YAML = BASE_DIR / ".sops.yaml"
SECRETS_DIR = BASE_DIR / "secrets"
SECRETS_FILE = SECRETS_DIR / "secrets.yaml"
RECOVERY_KEY_FILE = SECRETS_DIR / "recovery-key.age"
DEVICE_LABEL_FILE = BASE_DIR / ".device-label"

console = Console()


# ==========================================
# UTILITIES
# ==========================================

def run_cmd(cmd: List[str], stdin_data: Optional[str] = None, check: bool = True) -> str:
    # Ensure sops can find the age key at our non-standard path
    env = os.environ.copy()
    if AGE_KEY_FILE.exists():
        env["SOPS_AGE_KEY_FILE"] = str(AGE_KEY_FILE)
    result = subprocess.run(cmd, input=stdin_data, capture_output=True, text=True, check=check, env=env)
    return result.stdout.strip()


def sanitize_label(name: str) -> str:
    return re.sub(r'[^a-z0-9_]', '_', name.lower())


# ==========================================
# SOPS YAML I/O
# ==========================================

def read_sops_yaml_keys() -> Dict[str, str]:
    """Parse .sops.yaml for labeled age keys. Returns {label: public_key}.
    Uses regex on raw text since yaml.safe_load strips anchors."""
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
    run_cmd(["sops", "updatekeys", "--yes", str(SECRETS_FILE)])
    console.print("[green]Secrets re-encrypted with updated key list.[/green]")


def git_commit_sops_files() -> None:
    if not (BASE_DIR / ".git").exists():
        return
    files = [str(SOPS_YAML), str(SECRETS_FILE), str(RECOVERY_KEY_FILE)]
    committed = []
    for f in files:
        if not Path(f).exists():
            continue
        try:
            run_cmd(["git", "-C", str(BASE_DIR), "diff", "--quiet", f], check=False)
        except subprocess.CalledProcessError:
            run_cmd(["git", "-C", str(BASE_DIR), "add", f], check=False)
            committed.append(Path(f).name)
    if committed:
        msg = f"chore: update sops keys ({', '.join(committed)})"
        run_cmd(["git", "-C", str(BASE_DIR), "commit", "-m", msg], check=False)
        console.print(f"[green]{', '.join(committed)} committed[/green]")
    else:
        console.print("[dim]sops files: no changes to commit[/dim]")


# ==========================================
# RECOVERY KEY MANAGEMENT
# ==========================================

def _reencrypt_recovery_key_with(keys: Dict[str, str]) -> None:
    """Re-encrypt recovery-key.age with the given key set. Does NOT use current .sops.yaml."""
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
        # Keys were changed externally — use provided keys
        _reencrypt_recovery_key_with(keys)
    else:
        _reencrypt_recovery_key_with(current_keys)


def key_add_recovery() -> None:
    """Generate a recovery key. Private key encrypted at secrets/recovery-key.age."""
    keys = read_sops_yaml_keys()
    if "recovery" in keys:
        console.print("[yellow]Recovery key already exists. Use 'dtf key rotate --recovery' to replace it.[/yellow]")
        return

    recovery_priv = run_cmd(["age-keygen"])
    # recovery_priv: "# created: ...\nAGE-SECRET-KEY-..."
    priv_line = [l for l in recovery_priv.split("\n") if l.startswith("AGE-SECRET-KEY")][0]

    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', dir=str(SECRETS_DIR), delete=False) as tmp:
        tmp.write(priv_line + "\n")
        tmp_path = tmp.name
    try:
        os.chmod(tmp_path, 0o600)
        recovery_pub = run_cmd(["age-keygen", "-y", tmp_path])
    finally:
        pass  # keep temp file for encryption step

    # Encrypt recovery private key with all current device public keys + itself
    recipients = list(keys.values()) + [recovery_pub]
    encrypt_args = ["age", "--encrypt"]
    for pub in recipients:
        encrypt_args.extend(["-r", pub])
    encrypt_args.extend(["-o", str(RECOVERY_KEY_FILE), tmp_path])

    try:
        run_cmd(encrypt_args)
    finally:
        os.unlink(tmp_path)

    # Add recovery public key to .sops.yaml
    keys["recovery"] = recovery_pub
    write_sops_yaml_keys(keys)

    if SECRETS_FILE.exists():
        run_sops_updatekeys()

    git_commit_sops_files()
    console.print(f"[green]Recovery key generated and added to .sops.yaml.[/green]")
    console.print(f"[dim]Recovery public key: {recovery_pub[:30]}...[/dim]")
    console.print("[cyan]Recovery private key is stored encrypted at secrets/recovery-key.age[/cyan]")
    console.print("[yellow]IMPORTANT: Also save the recovery key offline (USB/paper/password manager) as ultimate backup.[/yellow]")


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


# ==========================================
# SUBCOMMANDS
# ==========================================

def key_list() -> None:
    keys = read_sops_yaml_keys()
    current_pub = get_current_device_public_key()
    current_label = get_device_label()

    table = Table(title="Age Keys in .sops.yaml")
    table.add_column("Label", style="cyan")
    table.add_column("Public Key (truncated)", style="white")
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

    # Age key file
    if AGE_KEY_FILE.exists():
        items.append(("Age key file", "[green]PRESENT[/green]", str(AGE_KEY_FILE)))
    else:
        items.append(("Age key file", "[red]MISSING[/red]", str(AGE_KEY_FILE)))

    # Public key
    if current_pub:
        items.append(("Public key", f"[green]{current_pub[:30]}...[/green]", ""))
        in_sops = current_pub in keys.values()
        items.append(("In .sops.yaml", "[green]YES[/green]" if in_sops else "[red]NO[/red]", ""))
    else:
        items.append(("Public key", "[red]NONE[/red]", ""))
        items.append(("In .sops.yaml", "[red]NO KEY[/red]", ""))

    # Device label
    items.append(("Device label", label, str(DEVICE_LABEL_FILE)))

    # Recovery key
    has_recovery = "recovery" in keys
    items.append(("Recovery key", "[green]YES[/green]" if has_recovery else "[yellow]NO[/yellow]", ""))

    # Decryption test
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

    # Basic format validation: age1 + Bech32, typically ~58-62 chars
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

    # Verify key is a valid age recipient by encrypting a test message
    try:
        run_cmd(["age", "--encrypt", "-r", pubkey, "-o", "/dev/null"], stdin_data="test")
    except subprocess.CalledProcessError:
        console.print("[red]Key rejected by age — not a valid recipient.[/red]")
        return

    new_keys = dict(keys)
    new_keys[label] = pubkey

    # Try recovery key reencryption BEFORE committing .sops.yaml changes
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
            console.print("[yellow]Verify the key is valid and run 'sops updatekeys --yes secrets/secrets.yaml' manually.[/yellow]")

    git_commit_sops_files()
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

    if keys[label] == current_pub and not force:
        console.print("[red]This is your CURRENT device key! Removing it will make secrets inaccessible here.[/red]")
        console.print("[yellow]Use --force if you really want to remove your own device's access.[/yellow]")
        return

    remaining = len(keys) - 1
    if remaining < 2:  # need at least 1 device key + recovery key
        console.print("[red]Cannot remove — at least one device key and the recovery key must remain.[/red]")
        return

    removed_pub = keys.pop(label)
    write_sops_yaml_keys(keys)

    # Re-encrypt recovery key without removed device
    reencrypt_recovery_key(keys)

    run_sops_updatekeys()
    git_commit_sops_files()
    console.print(f"[green]Key '{label}' ({removed_pub[:24]}...) removed.[/green]")
    console.print("[yellow]That device will NO LONGER be able to decrypt secrets.[/yellow]")

    if keys.get(label) == current_pub or removed_pub == current_pub:
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


def scan_usb_key_files() -> List[Path]:
    """Scan mounted USB drives for .age/.age.txt files.
    Priority: recovery/ subdirectory first, then root-level files.
    macOS: /Volumes, Linux: /media/$USER + /mnt."""
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

            # Priority 1: recovery/ subdirectory
            recovery_dir = volume / "recovery"
            if recovery_dir.exists() and recovery_dir.is_dir():
                for f in sorted(recovery_dir.iterdir()):
                    if f.is_file() and (f.name.endswith(".age") or f.name.endswith(".age.txt")):
                        candidates.append(f)

            # Priority 2: root-level .age/.age.txt files
            for f in sorted(volume.iterdir()):
                if f.is_file() and (f.name.endswith(".age") or f.name.endswith(".age.txt")):
                    candidates.append(f)

    return candidates


def key_import(age_path: Optional[str] = None, ssh_path: Optional[str] = None,
               generate: bool = False, label: Optional[str] = None) -> Optional[str]:
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
        # Interactive mode with USB scan
        usb_files = scan_usb_key_files()

        console.print("[bold]Import age key for this device:[/bold]")

        if usb_files:
            console.print(f"\n[cyan]Found {len(usb_files)} key file(s) on mounted USB drives:[/cyan]")
            for i, f in enumerate(usb_files, 1):
                marker = "[yellow]recovery/[/yellow]" if f.parent.name == "recovery" else ""
                console.print(f"  [cyan]{i}[/cyan]  {marker}{f}")
            console.print(f"  [cyan]{len(usb_files) + 1}[/cyan]  Import age key file (specify path manually)")
            console.print(f"  [cyan]{len(usb_files) + 2}[/cyan]  Import SSH key and derive age key")
            console.print(f"  [cyan]{len(usb_files) + 3}[/cyan]  Generate new age key (fresh device)")
            try:
                choice = pt_prompt(f"Choose [1-{len(usb_files) + 3}]: ").strip()
            except (EOFError, KeyboardInterrupt):
                return None

            idx = int(choice) if choice.isdigit() else 0
            if 1 <= idx <= len(usb_files):
                return key_import(age_path=str(usb_files[idx - 1]), label=label)
            elif idx == len(usb_files) + 1:
                default_path = "~/Library/Application Support/sops/age/keys.txt"
                try:
                    path = pt_prompt(f"Path to age key file [{default_path}]: ").strip()
                except (EOFError, KeyboardInterrupt):
                    return None
                if not path:
                    path = default_path
                return key_import(age_path=path, label=label)
            elif idx == len(usb_files) + 2:
                default_ssh = "~/.ssh/id_ed25519"
                try:
                    path = pt_prompt(f"Path to SSH private key [{default_ssh}]: ").strip()
                except (EOFError, KeyboardInterrupt):
                    return None
                if not path:
                    path = default_ssh
                return key_import(ssh_path=path, label=label)
            elif idx == len(usb_files) + 3:
                return key_import(generate=True, label=label)
            else:
                return None
        else:
            console.print("  [cyan]1[/cyan]  Import age key file (copy from another machine)")
            console.print("  [cyan]2[/cyan]  Import SSH key and derive age key")
            console.print("  [cyan]3[/cyan]  Generate new age key (fresh device)")
            try:
                choice = pt_prompt("Choose [1/2/3]: ").strip()
            except (EOFError, KeyboardInterrupt):
                return None

            if choice == "1":
                default_path = "~/Library/Application Support/sops/age/keys.txt"
                try:
                    path = pt_prompt(f"Path to age key file [{default_path}]: ").strip()
                except (EOFError, KeyboardInterrupt):
                    return None
                if not path:
                    path = default_path
                return key_import(age_path=path, label=label)
            elif choice == "2":
                default_ssh = "~/.ssh/id_ed25519"
                try:
                    path = pt_prompt(f"Path to SSH private key [{default_ssh}]: ").strip()
                except (EOFError, KeyboardInterrupt):
                    return None
                if not path:
                    path = default_ssh
                return key_import(ssh_path=path, label=label)
            elif choice == "3":
                return key_import(generate=True, label=label)
            else:
                return None

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
    git_commit_sops_files()

    console.print(f"[green]Key imported and added to .sops.yaml as '{current_label}'.[/green]")
    console.print(f"[green]Public key: {pub}[/green]")
    return pub


def key_rotate(recovery: bool = False) -> None:
    """Rotate current device key or recovery key using two-phase approach."""
    keys = read_sops_yaml_keys()

    if recovery:
        # Rotate recovery key
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

        # Generate new recovery key
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

        # Phase 1: add new recovery alongside old
        keys["recovery_new"] = new_recovery_pub
        write_sops_yaml_keys(keys)
        run_sops_updatekeys()

        # Encrypt new recovery key to all device keys + new recovery pub
        recipients = [v for k, v in keys.items() if k != "recovery"] + [new_recovery_pub]
        encrypt_args = ["age", "--encrypt"]
        for pub in recipients:
            encrypt_args.extend(["-r", pub])
        encrypt_args.extend(["-o", str(RECOVERY_KEY_FILE), tmp_path])

        try:
            run_cmd(encrypt_args)
        finally:
            os.unlink(tmp_path)

        # Phase 2: remove old recovery, rename new
        keys.pop("recovery")
        keys["recovery"] = new_recovery_pub
        keys.pop("recovery_new")
        write_sops_yaml_keys(keys)
        run_sops_updatekeys()
        git_commit_sops_files()

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

    # Backup old key content for appending
    old_key_content = AGE_KEY_FILE.read_text().strip()

    # Generate new key to temp file
    import uuid
    tmp_path = str(AGE_KEY_DIR / f"rotate_{uuid.uuid4().hex[:8]}.txt")
    run_cmd(["age-keygen", "-o", tmp_path])
    os.chmod(tmp_path, 0o600)
    new_pub = run_cmd(["age-keygen", "-y", tmp_path])

    console.print(f"[dim]New public key: {new_pub[:30]}...[/dim]")

    # Phase 1: append new key to keys.txt (keep old so sops can decrypt)
    new_key_content = Path(tmp_path).read_text().strip()
    AGE_KEY_FILE.write_text(old_key_content + "\n" + new_key_content + "\n")
    AGE_KEY_FILE.chmod(0o600)

    # Add new key alongside old in .sops.yaml
    old_label_temp = f"{label}_old"
    keys[old_label_temp] = current_pub
    keys[label] = new_pub
    write_sops_yaml_keys(keys)
    run_sops_updatekeys()

    # Re-encrypt recovery key with new device key included
    _reencrypt_recovery_key_with(keys)

    # Phase 2: remove old key from .sops.yaml
    keys.pop(old_label_temp)
    write_sops_yaml_keys(keys)
    run_sops_updatekeys()

    # Remove old key from keys.txt (keep only new key)
    AGE_KEY_FILE.write_text(new_key_content + "\n")
    AGE_KEY_FILE.chmod(0o600)

    # Clean up temp file
    if os.path.exists(tmp_path):
        os.unlink(tmp_path)

    git_commit_sops_files()

    console.print(f"[green]Key rotation complete for '{label}'.[/green]")
    console.print(f"[green]New public key: {new_pub}[/green]")


# ==========================================
# CLI ENTRY POINT
# ==========================================

def main():
    import argparse
    parser = argparse.ArgumentParser(prog="dtf key", description="Manage age keys for sops encryption")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", aliases=["ls"], help="Show keys in .sops.yaml + current device status")
    sub.add_parser("status", aliases=["st"], help="Check key status and decryptability")

    p_add = sub.add_parser("add", aliases=["a"], help="Add a device key to .sops.yaml")
    p_add.add_argument("pubkey", help="Age public key to add")
    p_add.add_argument("-l", "--label", help="Label for this key")

    p_remove = sub.add_parser("remove", aliases=["rm"], help="Remove a device key from .sops.yaml")
    p_remove.add_argument("label", help="Label of key to remove")
    p_remove.add_argument("-f", "--force", action="store_true", help="Allow removing current device key")

    p_export = sub.add_parser("export", aliases=["ex"], help="Export current device's key")
    p_export.add_argument("-F", "--format", choices=["age", "ssh"], default="age", help="Export format")
    p_export.add_argument("-o", "--output", help="Output file path")

    p_rotate = sub.add_parser("rotate", help="Rotate current device's age key")
    p_rotate.add_argument("-r", "--recovery", action="store_true", help="Rotate recovery key instead")

    p_import = sub.add_parser("import", aliases=["im"], help="Import a key for current device")
    p_import.add_argument("-a", "--age", help="Path to age key file")
    p_import.add_argument("-s", "--ssh", help="Path to SSH private key")
    p_import.add_argument("-g", "--generate", action="store_true", help="Generate a new age key")
    p_import.add_argument("-l", "--label", help="Device label")

    sub.add_parser("add-recovery", aliases=["ar"], help="Generate a recovery key")
    p_recover = sub.add_parser("recover-recovery", aliases=["rr"], help="Decrypt stored recovery key")
    p_recover.add_argument("-o", "--output", help="Save decrypted recovery key to file")

    args = parser.parse_args()

    dispatch = {
        "list": lambda: key_list(), "ls": lambda: key_list(),
        "status": lambda: key_status(), "st": lambda: key_status(),
        "add": lambda: key_add(args.pubkey, args.label), "a": lambda: key_add(args.pubkey, args.label),
        "remove": lambda: key_remove(args.label, args.force), "rm": lambda: key_remove(args.label, args.force),
        "export": lambda: key_export(args.format, args.output), "ex": lambda: key_export(args.format, args.output),
        "rotate": lambda: key_rotate(args.recovery),
        "import": lambda: key_import(args.age, args.ssh, args.generate, args.label), "im": lambda: key_import(args.age, args.ssh, args.generate, args.label),
        "add-recovery": lambda: key_add_recovery(), "ar": lambda: key_add_recovery(),
        "recover-recovery": lambda: key_recover_recovery(args.output), "rr": lambda: key_recover_recovery(args.output),
    }
    dispatch[args.command]()


if __name__ == "__main__":
    main()