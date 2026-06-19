"""Shared utilities for dtf CLI — path constants, subprocess helpers, sudo wrapper."""

import os
import re
import subprocess
from pathlib import Path
from typing import Optional

# ==========================================
# PATHS
# ==========================================

HOME_DIR = Path.home()
USER_CONFIG = HOME_DIR / ".config" / "dotfiles" / "config.nix"
SYSTEM_CONFIG = Path("/etc/dotfiles/config.nix")


def _resolve_dotfiles_dir() -> Path:
    env = os.environ.get("DOTFILES_DIR")
    if env:
        return Path(env)
    for config_path in (USER_CONFIG, SYSTEM_CONFIG):
        if config_path.exists():
            text = config_path.read_text()
            match = re.search(r'dotfiles\.path\s*=\s*"([^"]+)"', text)
            if match:
                return Path(match.group(1))
    return HOME_DIR / ".dotfiles"


DOTFILES_DIR = _resolve_dotfiles_dir()
AGE_KEY_DIR = HOME_DIR / ".config" / "sops" / "age"
AGE_KEY_FILE = AGE_KEY_DIR / "keys.txt"
SOPS_YAML = DOTFILES_DIR / ".sops.yaml"
SECRETS_DIR = DOTFILES_DIR / "secrets"
SECRETS_FILE = SECRETS_DIR / "secrets.yaml"
RECOVERY_KEY_FILE = SECRETS_DIR / "recovery-key.age"
DEVICE_LABEL_FILE = DOTFILES_DIR / ".device-label"
SETUP_SCRIPT = DOTFILES_DIR / "setup.sh"

# ==========================================
# COLOR HELPERS
# ==========================================

GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
CYAN = "\033[0;36m"
RED = "\033[0;31m"
NC = "\033[0m"

# ==========================================
# DEBUG MODE
# ==========================================


def is_debug() -> bool:
    return os.environ.get("DTF_DEBUG") == "1"

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

    if is_debug():
        print(f"{CYAN}[debug] running: {' '.join(cmd)} (cwd={effective_cwd}){NC}")

    if capture:
        result = subprocess.run(
            cmd, input=stdin_data, capture_output=True, text=True,
            check=check, env=env, cwd=effective_cwd,
        )

        if is_debug():
            if result.stdout:
                print(f"{CYAN}[debug] stdout: {result.stdout[:500]}{NC}")
            if result.stderr:
                print(f"{YELLOW}[debug] stderr: {result.stderr[:500]}{NC}")

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


def esudo(*args: str, capture: bool = False) -> None:
    """sudo with automatic password injection from sops.
    capture=False: stream output live (default, for long-running commands).
    capture=True:  capture output for return-value inspection."""
    passwd = _get_sudo_passwd()
    if passwd:
        # Try password-based sudo first
        result = subprocess.run(
            ["sudo", "-S", *args],
            input=passwd, text=True,
            capture_output=capture,
        )
        if result.returncode == 0:
            if capture and result.stdout:
                print(result.stdout)
            return
        # Fall through to interactive sudo
    subprocess.run(["sudo", *args])

# ==========================================
# HOME-MANAGER
# ==========================================


def run_hm(*args: str) -> None:
    """Run home-manager or fallback to nix run. Output streams live to terminal."""
    if _command_exists("home-manager"):
        run_cmd(["home-manager", *args], capture=False)
    else:
        print(f"{YELLOW}--> 'home-manager' not found. Using nix run fallback...{NC}")
        run_cmd(["nix", "run", "github:nix-community/home-manager", "--", *args], capture=False)


def _command_exists(name: str) -> bool:
    return subprocess.run(
        ["which", name], capture_output=True,
    ).returncode == 0

# ==========================================
# CONFIG LINKS
# ==========================================


def ensure_config_links() -> None:
    """Link config.nix to /etc/dotfiles if not already linked."""
    if not SYSTEM_CONFIG.exists() or not os.path.islink(str(SYSTEM_CONFIG)):
        print(f"{CYAN}--> Linking config.nix to /etc/dotfiles...{NC}")
        esudo("mkdir", "-p", "/etc/dotfiles", capture=True)
        esudo("ln", "-sf", str(USER_CONFIG), str(SYSTEM_CONFIG), capture=True)


def clean_config_links() -> None:
    """Remove /etc/dotfiles symlink."""
    if SYSTEM_CONFIG.exists() and os.path.islink(str(SYSTEM_CONFIG)):
        print(f"{CYAN}--> Cleaning up config link...{NC}")
        esudo("rm", "-f", str(SYSTEM_CONFIG), capture=True)