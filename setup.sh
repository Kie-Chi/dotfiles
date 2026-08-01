#!/usr/bin/env bash

set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REQUIRES_SCRIPT="$BASE_DIR/requires.sh"
MIRROR_ENV_SCRIPT="$BASE_DIR/resources/scripts/mirror-env.sh"
export ENVY_ROOT="$BASE_DIR"

# Bootstrap-time mirrors make the first nix develop usable before a machine
# module has been evaluated and applied.
# shellcheck source=resources/scripts/mirror-env.sh
. "$MIRROR_ENV_SCRIPT"

# ==========================================
# STEP 1: Ensure Nix is available
# ==========================================

# Source Nix profile if not already in PATH (handles "nix installed but PATH not set" scenario)
if ! command -v nix >/dev/null 2>&1; then
    if [ -e '/nix/var/nix/profiles/default/etc/profile.d/nix-daemon.sh' ]; then
        # shellcheck source=/dev/null
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
            # shellcheck source=/dev/null
            . '/nix/var/nix/profiles/default/etc/profile.d/nix-daemon.sh'
        fi
    else
        echo "[ERROR] requires.sh not found and Nix is not installed!"
        exit 1
    fi
fi

# ==========================================
# STEP 2: Enter the minimal setup runtime
# ==========================================

if [ "${ENVY_DEV_SHELL:-0}" = "1" ] \
    || { python3 -c 'import typer, rich, prompt_toolkit, yaml' 2>/dev/null \
        && command -v sops >/dev/null 2>&1 \
        && command -v age >/dev/null 2>&1 \
        && command -v ssh-to-age >/dev/null 2>&1; }; then
    # Applied envY packages and the development shell already provide runtime dependencies.
    echo "[INFO] Using the available envY setup runtime..."
    export PYTHONPATH="$BASE_DIR/resources/scripts:${PYTHONPATH:-}"
    exec python3 "$BASE_DIR/setup.py"
else
    echo "[INFO] Preparing the envY setup runtime..."
    exec nix run "path:$BASE_DIR#setup"
fi
