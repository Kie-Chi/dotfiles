#!/usr/bin/env bash

set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REQUIRES_SCRIPT="$BASE_DIR/requires.sh"
MIRROR_ENV_SCRIPT="$BASE_DIR/resources/scripts/mirror-env.sh"
NIX_PROFILE_SCRIPT='/nix/var/nix/profiles/default/etc/profile.d/nix-daemon.sh'
NIX_BIN_DIR='/nix/var/nix/profiles/default/bin'
NIX_SYSTEM_CONFIG='/etc/nix/nix.conf'
NIX_MIRROR_MARKER='# BEGIN ENVY MANAGED NIX MIRROR'
mirror="${ENVY_MIRROR:-china}"
export ENVY_ROOT="$BASE_DIR"

while [ "$#" -gt 0 ]; do
    case "$1" in
        --mirror)
            [ "$#" -ge 2 ] || { echo "[ERROR] --mirror requires a value" >&2; exit 2; }
            mirror="$2"
            shift 2
            ;;
        *)
            echo "[ERROR] unknown option: $1" >&2
            exit 2
            ;;
    esac
done

case "$mirror" in
    china|upstream)
        export ENVY_MIRROR="$mirror"
        ;;
    *)
        echo "[ERROR] --mirror must be 'china' or 'upstream'" >&2
        exit 2
        ;;
esac

load_nix_path() {
    if [ -e "$NIX_PROFILE_SCRIPT" ]; then
        # shellcheck source=/dev/null
        . "$NIX_PROFILE_SCRIPT"
    fi

    # The installer runs as a child process, so its PATH changes cannot be
    # inherited. Restore the stable profile locations explicitly as well.
    if [ -d "$NIX_BIN_DIR" ]; then
        PATH="$NIX_BIN_DIR:${PATH:-}"
    fi
    if [ -n "${HOME:-}" ] && [ -d "$HOME/.nix-profile/bin" ]; then
        PATH="$HOME/.nix-profile/bin:${PATH:-}"
    fi
    export PATH
}

configure_nix_mirror_trust() {
    [ "$ENVY_MIRROR" = "china" ] || return 0

    # Nix daemon mode rejects client-only substituter settings from ordinary
    # users. Trust the audited USTC endpoint while preserving existing daemon
    # substituters and keys. The block is static and idempotent.
    if [ -r "$NIX_SYSTEM_CONFIG" ] && grep -Fq "$NIX_MIRROR_MARKER" "$NIX_SYSTEM_CONFIG"; then
        return 0
    fi

    local nix_mirror_block
    local configured=0
    nix_mirror_block=$(cat <<'EOF'
# BEGIN ENVY MANAGED NIX MIRROR
extra-trusted-substituters = https://mirrors.ustc.edu.cn/nix-channels/store
extra-trusted-public-keys = cache.nixos.org-1:6NCHdD59X431o0gWypbMrAURkbJ16ZPMQFGspcDShjY=
# END ENVY MANAGED NIX MIRROR
EOF
)

    if [ "$(id -u)" -eq 0 ]; then
        if ! printf '%s\n' "$nix_mirror_block" >> "$NIX_SYSTEM_CONFIG"; then
            echo "[WARN] Could not update $NIX_SYSTEM_CONFIG; USTC may be ignored by the Nix daemon." >&2
        else
            configured=1
        fi
    elif command -v sudo >/dev/null 2>&1; then
        if ! printf '%s\n' "$nix_mirror_block" | sudo tee -a "$NIX_SYSTEM_CONFIG" >/dev/null; then
            echo "[WARN] Could not update $NIX_SYSTEM_CONFIG; USTC may be ignored by the Nix daemon." >&2
        else
            configured=1
        fi
    else
        echo "[WARN] sudo is unavailable; USTC cannot be trusted by the Nix daemon." >&2
    fi

    if [ "$configured" -eq 1 ] && command -v systemctl >/dev/null 2>&1; then
        local service
        for service in nix-daemon.service determinate-nixd.service; do
            if systemctl is-active --quiet "$service" 2>/dev/null; then
                if [ "$(id -u)" -eq 0 ]; then
                    systemctl restart "$service" || true
                elif command -v sudo >/dev/null 2>&1; then
                    sudo systemctl restart "$service" || true
                fi
                break
            fi
        done
    fi
}

# Bootstrap-time mirrors make the first nix develop usable before a machine
# module has been evaluated and applied.
# shellcheck source=resources/scripts/mirror-env.sh
. "$MIRROR_ENV_SCRIPT"

# ==========================================
# STEP 1: Ensure Nix is available
# ==========================================

# Source Nix profile if not already in PATH (handles "nix installed but PATH not set" scenario)
if ! command -v nix >/dev/null 2>&1; then
    load_nix_path
fi

if ! command -v nix >/dev/null 2>&1; then
    echo "[INFO] Nix not found. Installing..."
    if [ -f "$REQUIRES_SCRIPT" ]; then
        chmod +x "$REQUIRES_SCRIPT"
        "$REQUIRES_SCRIPT"
        # Source Nix profile again after fresh install (subprocess env doesn't propagate to parent)
        load_nix_path
    else
        echo "[ERROR] requires.sh not found and Nix is not installed!"
        exit 1
    fi
fi

command -v nix >/dev/null 2>&1 || {
    echo "[ERROR] Nix was installed but is not available on PATH. Expected: $NIX_BIN_DIR/nix" >&2
    exit 1
}

configure_nix_mirror_trust

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
