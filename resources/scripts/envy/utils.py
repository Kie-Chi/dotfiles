"""Shared utilities for envy CLI — path constants, subprocess helpers, sudo wrapper."""

import json
import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Optional

from envy import log

# ==========================================
# PLATFORM
# ==========================================

PLATFORM = sys.platform  # "linux" | "darwin"

# ==========================================
# PATHS
# ==========================================

HOME_DIR = Path.home()
LEGACY_MACHINE_SELECTOR = HOME_DIR / ".config" / "envy" / "machine"
LEGACY_USER_CONFIG = HOME_DIR / ".config" / "dotfiles" / "config.nix"
LEGACY_SYSTEM_CONFIG = Path("/etc/dotfiles/config.nix")


def _resolve_dotfiles_dir() -> Path:
    env = os.environ.get("ENVY_DOTFILES") or os.environ.get("DOTFILES_DIR")
    if env:
        return Path(env)
    source_checkout = Path(__file__).resolve().parents[3]
    if (source_checkout / "flake.nix").exists():
        return source_checkout
    return HOME_DIR / ".dotfiles"


DOTFILES_DIR = _resolve_dotfiles_dir()

# Platform-specific age key directory:
#   Linux: ~/.config/sops/age
#   macOS: ~/Library/Application Support/sops/age
AGE_KEY_DIR = (
    HOME_DIR / "Library" / "Application Support" / "sops" / "age"
    if PLATFORM == "darwin"
    else HOME_DIR / ".config" / "sops" / "age"
)
AGE_KEY_FILE = AGE_KEY_DIR / "keys.txt"
SOPS_YAML = DOTFILES_DIR / ".sops.yaml"
SECRETS_DIR = DOTFILES_DIR / "secrets"
SECRETS_FILE = SECRETS_DIR / "secrets.yaml"
RECOVERY_KEY_FILE = SECRETS_DIR / "recovery-key.age"
DEVICE_LABEL_FILE = DOTFILES_DIR / ".device-label"
SETUP_SCRIPT = DOTFILES_DIR / "setup.sh"

# Platform-specific system profile. The flake target is resolved at runtime
# because each Darwin machine has its own hosts/machines/<id>.nix entry.
SYSTEM_PROFILE = Path("/nix/var/nix/profiles/system")


def read_device_metadata() -> dict[str, str]:
    """Read .device-label TOML, accepting the previous one-line label once."""
    if not DEVICE_LABEL_FILE.exists():
        return {}
    text = DEVICE_LABEL_FILE.read_text().strip()
    if not text:
        return {}
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", text):
            # Historically this file named only the sops key. Do not assume it
            # was also the selected machine when legacy config may disagree.
            return {"sops_label": text}
        raise ValueError(f"invalid TOML in {DEVICE_LABEL_FILE}: {exc}") from exc

    version = data.get("version", 1)
    if type(version) is not int or version != 1:
        raise ValueError(f"unsupported device metadata version: {version}")
    device = data.get("device", {})
    if not isinstance(device, dict):
        raise ValueError(f"[device] must be a TOML table in {DEVICE_LABEL_FILE}")
    result = {}
    for key in ("machine_id", "sops_label"):
        value = device.get(key)
        if value is not None:
            if not isinstance(value, str):
                raise ValueError(f"device.{key} must be a string in {DEVICE_LABEL_FILE}")
            result[key] = value.strip()
    return result


def device_metadata_is_toml() -> bool:
    if not DEVICE_LABEL_FILE.exists():
        return False
    try:
        data = tomllib.loads(DEVICE_LABEL_FILE.read_text())
    except (OSError, tomllib.TOMLDecodeError):
        return False
    return (
        type(data.get("version")) is int
        and data.get("version") == 1
        and isinstance(data.get("device"), dict)
    )


def write_device_metadata(
    *, machine_id: str | None = None, sops_label: str | None = None
) -> None:
    """Update device-local TOML while preserving the other identity field."""
    current = read_device_metadata()
    if machine_id is not None:
        current["machine_id"] = machine_id
    if sops_label is not None:
        current["sops_label"] = sops_label
    DEVICE_LABEL_FILE.parent.mkdir(parents=True, exist_ok=True)
    lines = ["version = 1\n", "\n", "[device]\n"]
    for key in ("machine_id", "sops_label"):
        value = current.get(key)
        if value:
            lines.append(f"{key} = {json.dumps(value)}\n")
    DEVICE_LABEL_FILE.write_text("".join(lines))


def current_machine_id() -> str:
    """Resolve the machine target from device metadata and legacy inputs."""
    env_machine = os.environ.get("ENVY_MACHINE", "").strip()
    candidates = [env_machine]
    metadata = read_device_metadata()
    candidates.append(metadata.get("machine_id", ""))

    if not metadata.get("machine_id"):
        # One-time upgrade paths are consulted only until TOML device metadata
        # has a machine ID; they are not part of the steady-state lookup.
        if LEGACY_MACHINE_SELECTOR.exists():
            try:
                candidates.append(LEGACY_MACHINE_SELECTOR.read_text().strip())
            except OSError:
                pass

        for config_path in (LEGACY_USER_CONFIG, DOTFILES_DIR / "config.nix", LEGACY_SYSTEM_CONFIG):
            if not config_path.exists():
                continue
            try:
                text = config_path.read_text()
            except OSError:
                continue
            match = re.search(r'^\s*envy\.machine\.id\s*=\s*"([A-Za-z0-9_-]+)"\s*;', text, re.MULTILINE)
            if match:
                candidates.append(match.group(1))

    candidates.append(metadata.get("sops_label", ""))

    hostname = subprocess.getoutput("hostname -s").strip() or "machine"
    candidates.append(re.sub(r"[^A-Za-z0-9_-]", "_", hostname))
    for candidate in candidates:
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", candidate or ""):
            return candidate
    return "machine"


def set_device_machine_id(machine_id: str) -> None:
    """Persist the machine target in device metadata; policy stays in Git."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", machine_id):
        raise ValueError("invalid machine ID")
    write_device_metadata(machine_id=machine_id)
    if LEGACY_MACHINE_SELECTOR.is_file() or LEGACY_MACHINE_SELECTOR.is_symlink():
        LEGACY_MACHINE_SELECTOR.unlink()
        try:
            LEGACY_MACHINE_SELECTOR.parent.rmdir()
        except OSError:
            pass


def flake_target() -> str:
    # Use an explicit path flake so a freshly created, not-yet-committed
    # hosts/machines/<id>.nix is visible during the first check/apply.
    return f"path:.#{current_machine_id()}" if PLATFORM == "darwin" else "path:.#default"


# ==========================================
# SUBPROCESS
# ==========================================


def run_cmd(
    cmd: list,
    stdin_data: str | None = None,
    check: bool = True,
    cwd: Path | None = None,
    capture: bool = True,
) -> str | None:
    """Run subprocess command. capture=True returns stdout as string; capture=False streams live."""
    env = os.environ.copy()
    if AGE_KEY_FILE.exists():
        env["SOPS_AGE_KEY_FILE"] = str(AGE_KEY_FILE)

    effective_cwd = str(cwd or DOTFILES_DIR)

    log.debug("cmd", "running", cmd=' '.join(cmd), cwd=effective_cwd)

    if capture:
        result = subprocess.run(
            cmd, input=stdin_data, capture_output=True, text=True,
            check=check, env=env, cwd=effective_cwd,
        )

        if log.is_debug():
            if result.stdout:
                log.debug("cmd", "stdout", output=result.stdout[:500])
            if result.stderr:
                log.debug("cmd", "stderr", output=result.stderr[:500])

        return result.stdout.strip()
    else:
        subprocess.run(
            cmd, input=stdin_data, text=True,
            check=check, env=env, cwd=effective_cwd,
        )
        return None

# ==========================================
# SUDO WRAPPER
# ==========================================


def _get_sudo_passwd() -> str | None:
    """Read password from sops-encrypted secrets if available."""
    if not SECRETS_FILE.exists() or not AGE_KEY_FILE.exists():
        return None
    try:
        result = subprocess.run(
            ["sops", "-d", "--extract", '["home"]["passwd"]', str(SECRETS_FILE)],
            capture_output=True, text=True,
            env={**os.environ, "SOPS_AGE_KEY_FILE": str(AGE_KEY_FILE)},
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass
    return None


def is_sops_encrypted(path: Path) -> bool:
    """Check whether a YAML file contains sops metadata."""
    if not path.exists():
        return False
    try:
        return any(line.startswith("sops:") for line in path.read_text().splitlines())
    except (OSError, UnicodeDecodeError):
        return False


def backup_sensitive_file(filepath: Path) -> Optional[Path]:
    """Create a .bak copy of a sensitive file before overwriting it.
    Returns the backup path, or None if the source doesn't exist."""
    if not filepath.exists():
        return None
    bak = filepath.with_suffix(filepath.suffix + ".bak")
    try:
        bak.write_bytes(filepath.read_bytes())
        return bak
    except OSError:
        return None


def esudo(*args: str, capture: bool = False, cwd: Path | None = None) -> None:
    """sudo with automatic password injection from sops.
    capture=False: stream output live (default, for long-running commands).
    capture=True:  capture output for return-value inspection."""
    effective_cwd = str(cwd or DOTFILES_DIR)
    passwd = _get_sudo_passwd()
    if passwd:
        # Try password-based sudo first
        result = subprocess.run(
            ["sudo", "-S", *args],
            input=passwd, text=True,
            capture_output=capture,
            cwd=effective_cwd,
        )
        if result.returncode == 0:
            if capture and result.stdout:
                print(result.stdout)
            return
        # Fall through to interactive sudo
    subprocess.run(["sudo", *args], cwd=effective_cwd)

# ==========================================
# APPLY ROUTING
# ==========================================


def run_hm(*args: str) -> None:
    """Run home-manager or fallback to nix run. Output streams live to terminal."""
    if _command_exists("home-manager"):
        run_cmd(["home-manager", *args], capture=False)
    else:
        log.warn("hm", "'home-manager' not found, using nix run fallback")
        run_cmd(["nix", "run", "github:nix-community/home-manager", "--", *args], capture=False)


def run_darwin_switch() -> None:
    """Run nix-darwin switch with sudo."""
    log.step("darwin", "running nix-darwin switch")
    esudo("--preserve-env=HOME", "nix", "run", "nix-darwin", "--", "switch",
          "--flake", flake_target(), "--impure", capture=False)
    log.ok("darwin", "system successfully updated")


def run_apply() -> None:
    """Apply configuration — routes to platform-appropriate method."""
    if PLATFORM == "darwin":
        run_darwin_switch()
    else:
        log.step("hm", "applying Home Manager configuration")
        run_hm("switch", "--flake", flake_target(), "--impure")
        log.ok("hm", "configuration applied, new generation created")


def _command_exists(name: str) -> bool:
    return subprocess.run(
        ["which", name], capture_output=True,
    ).returncode == 0
