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

    local nix_installer_url="${ENVY_NIX_INSTALLER_URL:-https://install.determinate.systems/nix}"
    curl --proto '=https' --tlsv1.2 -sSf -L "$nix_installer_url" | sh -s -- install

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
