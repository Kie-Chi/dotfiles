#!/bin/bash

set -e

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REQUIRES_SCRIPT="$BASE_DIR/requires.sh"

# ==========================================
# STEP 1: Ensure Nix is installed
# ==========================================

if ! command -v nix >/dev/null 2>&1; then
    echo "[INFO] Nix not found. Installing..."
    if [ -f "$REQUIRES_SCRIPT" ]; then
        chmod +x "$REQUIRES_SCRIPT"
        "$REQUIRES_SCRIPT"
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
    exec python3 "$BASE_DIR/setup.py"
else
    # Enter nix develop and re-exec
    echo "[INFO] Entering Nix dev shell for setup environment..."
    exec nix develop "$BASE_DIR" --command bash "$0"
fi