#!/bin/bash

set -e

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REQUIRES_SCRIPT="$BASE_DIR/requires.sh"
export ENVY_DOTFILES="$BASE_DIR"

# ==========================================
# STEP 1: Ensure Nix is available
# ==========================================

# Source Nix profile if not already in PATH (handles "nix installed but PATH not set" scenario)
if ! command -v nix >/dev/null 2>&1; then
    if [ -e '/nix/var/nix/profiles/default/etc/profile.d/nix-daemon.sh' ]; then
        . '/nix/var/nix/profiles/default/etc/profile.d/nix-daemon.sh'
    fi
fi

if ! command -v nix >/dev/null 2>&1; then
    echo "[INFO] Nix not found. Installing..."
    if [ -f "$REQUIRES_SCRIPT" ]; then
        chmod +x "$REQUIRES_SCRIPT"
        "$REQUIRES_SCRIPT"
        # Source Nix profile again after fresh install (subprocess env doesn't propagate to parent)
        if [ -e '/nix/var/nix/profiles/default/etc/profile.d/nix-daemon.sh' ]; then
            . '/nix/var/nix/profiles/default/etc/profile.d/nix-daemon.sh'
        fi
    else
        echo "[ERROR] requires.sh not found and Nix is not installed!"
        exit 1
    fi
fi

# ==========================================
# STEP 2: Enter devShell and run setup.py
# ==========================================

if [ -n "$IN_NIX_SHELL" ]; then
    # Already in devShell, just run setup.py
    echo "[DEBUG] Already in Nix dev shell"
    export PYTHONPATH="$BASE_DIR/resources/scripts:${PYTHONPATH:-}"
    exec python3 "$BASE_DIR/setup.py"
else
    # Enter nix develop and re-exec
    echo "[INFO] Entering Nix dev shell for setup environment..."
    exec nix develop "path:$BASE_DIR" --command bash "$BASE_DIR/setup.sh"
fi
