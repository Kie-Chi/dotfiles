#!/bin/bash

# ==============================================================================
# requires.sh - Prerequisite Installer for Dotfiles
#
# dependencies required *before* running Nix and Home Manager.
# This includes build tools, git, curl, uidmap, and Nix itself.
#
# ==============================================================================

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

msg_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

msg_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

msg_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

msg_error() {
    echo -e "${RED}[ERROR]${NC} $1" >&2
    exit 1
}

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

check_sudo() {
    if [[ $EUID -ne 0 ]]; then
        if ! command_exists sudo; then
            msg_error "'sudo' command not found. Please run this script as root or install sudo."
        fi
        msg_info "Requesting sudo access for system package installation..."
        sudo -v # Ask for sudo password upfront
        if [[ $? -ne 0 ]]; then
            msg_error "Sudo access denied. Please run the script again."
        fi
    fi
}

install_system_deps() {
    local PKG_MANAGER=""
    local INSTALL_CMD=""
    local UPDATE_CMD=""
    local DEPS=()
    local os_name=""

    # Detect OS
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        if [ -f /etc/os-release ]; then
            . /etc/os-release
            os_name=$ID
        else
            msg_error "Cannot detect Linux distribution."
        fi
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        os_name="macos"
    else
        msg_error "Unsupported OS: $OSTYPE"
    fi

    msg_info "Detected OS: $os_name"

    case "$os_name" in
        ubuntu|debian)
            check_sudo
            msg_info "Adding Charm (gum) repository for $os_name..."
            sudo mkdir -p /etc/apt/keyrings
            curl -fsSL https://repo.charm.sh/apt/gpg.key | sudo gpg --dearmor -o /etc/apt/keyrings/charm.gpg
            echo "deb [signed-by=/etc/apt/keyrings/charm.gpg] https://repo.charm.sh/apt/ * *" | sudo tee /etc/apt/sources.list.d/charm.list
            PKG_MANAGER="apt-get"
            UPDATE_CMD="sudo apt-get update"
            INSTALL_CMD="sudo apt-get install -y"
            DEPS=("curl" "git" "build-essential" "uidmap" "gum" "jq")
            ;;
        arch)
            PKG_MANAGER="pacman"
            # pacman's -Syu updates and installs
            INSTALL_CMD="sudo pacman -Syu --noconfirm"
            # base-devel for build tools, shadow for uidmap/newuidmap
            DEPS=("curl" "git" "base-devel" "shadow" "gum" "jq")
            ;;
        fedora)
            PKG_MANAGER="dnf"
            INSTALL_CMD="sudo dnf install -y"
            DEPS=("curl" "git" "@development-tools" "shadow-utils" "gum" "jq")
            ;;
        macos)
            if ! command_exists brew; then
                msg_info "Homebrew not found. Installing Homebrew..."
                /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
                if [ -f /opt/homebrew/bin/brew ]; then
                    eval "$(/opt/homebrew/bin/brew shellenv)"
                fi
            fi
            INSTALL_CMD="brew install"
            DEPS=("git" "curl" "gum" "jq")
            ;;
        *)
            msg_error "Distribution '$os_name' is not supported by this script."
            ;;
    esac

    local to_install=()
    for dep in "${DEPS[@]}"; do
        local check_cmd="${dep#@}"
        if [[ "$PKG_MANAGER" == "pacman" && "$dep" == "base-devel" ]]; then
            if ! pacman -Q a | grep -q "make"; then
                 to_install+=("$dep")
            fi
        elif ! command_exists "$check_cmd"; then
            to_install+=("$dep")
        fi
    done

    if [ ${#to_install[@]} -eq 0 ]; then
        msg_success "All system dependencies are already installed."
    else
        msg_info "The following system dependencies will be installed: ${to_install[*]}"
        check_sudo
        [ -n "$UPDATE_CMD" ] && $UPDATE_CMD
        $INSTALL_CMD "${to_install[@]}"
        msg_success "System dependencies installed successfully."
    fi
}

install_nix() {
    if command_exists nix; then
        msg_success "Nix package manager is already installed."
        return
    fi

    msg_info "Nix not found. Starting installation of the Nix package manager..."
    read -p "Press Enter to continue, or Ctrl+C to cancel."

    curl --proto '=https' --tlsv1.2 -sSf -L https://install.determinate.systems/nix | sh -s -- install
    if [ -e '/nix/var/nix/profiles/default/etc/profile.d/nix-daemon.sh' ]; then
        . '/nix/var/nix/profiles/default/etc/profile.d/nix-daemon.sh'
    fi

    msg_success "Nix installation complete."
    msg_warn "If erros met following, you can relogin and try again."
}


main() {
    msg_info "Starting prerequisite check for Nix dotfiles..."
    install_system_deps
    install_nix
    if [ -e '/nix/var/nix/profiles/default/etc/profile.d/nix-daemon.sh' ]; then
        . '/nix/var/nix/profiles/default/etc/profile.d/nix-daemon.sh'
    fi
    
    echo
    msg_success "All prerequisites are installed!"
}

main
if [ -e '/nix/var/nix/profiles/default/etc/profile.d/nix-daemon.sh' ]; then
    . '/nix/var/nix/profiles/default/etc/profile.d/nix-daemon.sh'
fi