#!/usr/bin/env bash

# ==============================================================================
# requires.sh - Install Nix if not present
#
# Only installs Nix itself. All other dependencies (jq, sops, age, Python, etc.)
# are provided by the devShell defined in flake.nix.
# ==============================================================================

set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m'

msg_info() { echo -e "${CYAN}[INFO]${NC} $1"; }
msg_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
msg_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
msg_error() { echo -e "${RED}[ERROR]${NC} $1" >&2; exit 1; }

command_exists() { command -v "$1" >/dev/null 2>&1; }

install_nix() {
    if command_exists nix; then
        msg_success "Nix is already installed."
        return 0
    fi

    msg_info "Nix not found. Installing Nix package manager..."
    read -r -p "Press Enter to continue, or Ctrl+C to cancel." </dev/tty

    command_exists curl || msg_error "curl is required to install Nix"

    local nix_installer_url
    local nix_installer_args
    local -a installer_args=()
    if [ -n "${ENVY_NIX_INSTALLER_URL:-}" ]; then
        # Keep the historical Determinate invocation for explicitly supplied
        # installer endpoints. A standard Nix installer can opt into its
        # daemon mode with ENVY_NIX_INSTALLER_ARGS.
        nix_installer_url="$ENVY_NIX_INSTALLER_URL"
        nix_installer_args="${ENVY_NIX_INSTALLER_ARGS:-install}"
    elif [ "${ENVY_MIRROR:-china}" = "china" ]; then
        # TUNA mirrors the official Nix binary installer and its tarballs. The
        # script verifies the tarball hash before running the embedded install.
        nix_installer_url="https://mirrors.tuna.tsinghua.edu.cn/nix/latest/install"
        nix_installer_args="${ENVY_NIX_INSTALLER_ARGS:---daemon}"
    else
        nix_installer_url="https://install.determinate.systems/nix"
        nix_installer_args="${ENVY_NIX_INSTALLER_ARGS:-install}"
    fi

    # Split only the explicitly documented argument string; this avoids eval
    # while still allowing flags such as `--daemon --no-channel`. Word
    # splitting is intentional here and is scoped to installer arguments.
    read -r -a installer_args <<< "$nix_installer_args"
    curl --proto '=https' --tlsv1.2 -sSf -L "$nix_installer_url" \
        | sh -s -- "${installer_args[@]}"

    msg_success "Nix installation complete."
    msg_warn "You may need to re-login or restart your shell for Nix to be available."

    # Source Nix profile in this process so subsequent function calls can use nix
    if [ -e '/nix/var/nix/profiles/default/etc/profile.d/nix-daemon.sh' ]; then
        # shellcheck source=/dev/null
        . '/nix/var/nix/profiles/default/etc/profile.d/nix-daemon.sh'
    fi
}

main() {
    msg_info "Checking prerequisites..."
    install_nix
    msg_success "Prerequisites ready!"
}

main
