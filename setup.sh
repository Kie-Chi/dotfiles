#!/bin/bash

# ==============================================================================
# setup.sh - Generic, Dictionary-Driven Installer for Nix-based Dotfiles
#
# The script will automatically handle user prompts and file generation.
# ==============================================================================

set -e

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SECRETS_FILE="$BASE_DIR/secrets.nix"
REQUIRES_SCRIPT="$BASE_DIR/requires.sh"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m'

msg_info() { echo -e "${CYAN}[INFO]${NC} $1"; }
msg_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
msg_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
msg_error() { echo -e "${RED}[ERROR]${NC} $1" >&2; exit 1; }

CONFIG_ITEMS="BASE|home.user|Enter your system username|whoami
BASE|home.dir|Enter your home directory path|echo \"$HOME\"
GIT|git.name|Enter your Git user name|echo \"Someone\"
GIT|git.email|Enter your Git email address|echo \"someone@example.com\"
PROXY|proxy.status|Enter your proxy status (keep/manual/none)|echo \"none\"
PROXY|proxy.url|Enter your proxy URL (leave blank for none)|echo \"\""

gen() {
    msg_info "Configuring user identity for secrets.nix..."
    echo "Please provide the following information. Press Enter to accept the default value."

    local file_content="{\n"
    local current_group=""
    while IFS='|' read -r group nix_path prompt default_cmd; do
        [ -z "$group" ] && continue

        if [ "$group" != "$current_group" ]; then
            if [ -n "$current_group" ]; then
                file_content+="\n"
            fi
            # Using literal newlines which is safer and clearer
            file_content+="  ###################################\n"
            file_content+="  #  ${group} IDENTITY CONFIGURATION  #\n"
            file_content+="  ###################################\n"
            current_group="$group"
        fi

        local default_val
        default_val=$(eval "$default_cmd")

        read -p "$(echo -e "${GREEN}${prompt}${NC} [default: ${YELLOW}${default_val}${NC}]: ")" user_input < /dev/tty
        local final_value="${user_input:-$default_val}"

        final_value="${final_value//\\/\\\\}"
        final_value="${final_value//\"/\\\"}"

        # Using printf to build the string piece by piece is robust
        file_content+=$(printf "  %s = \"%s\";\n" "$nix_path" "$final_value")

    done <<< "$CONFIG_ITEMS"

    file_content+="\n}"

    printf '%b' "$file_content" > "$SECRETS_FILE"

    msg_success "Generated secrets.nix at: $SECRETS_FILE"
    local TARGET_DIR="$HOME/.config/dotfiles"
    local TARGET_LINK="$TARGET_DIR/secrets.nix"
    msg_info "Creating symbolic link for Home Manager..."
    mkdir -p "$TARGET_DIR"
    ln -sf "$SECRETS_FILE" "$TARGET_LINK"
    msg_success "Linked $SECRETS_FILE to $TARGET_LINK"
    echo ""
}

cold() {
    msg_info "Applying Home Manager configuration for the first time..."
    /bin/bash resources/scripts/dtf apply
}

msg_info "Starting setup..."
msg_info "Running prerequisite installer (requires.sh)..."
if [ ! -f "$REQUIRES_SCRIPT" ]; then
    msg_error "'requires.sh' not found in the script directory: $BASE_DIR"
fi
chmod +x "$REQUIRES_SCRIPT"
if ! "$REQUIRES_SCRIPT"; then
    msg_error "The prerequisite ('requires.sh') failed. Please check the output above for errors."
fi
msg_success "Prerequisites check and installation completed successfully."
echo ""
if [ -f "$SECRETS_FILE" ]; then
    msg_warn "'secrets.nix' already exists. Your existing configuration will be lost if you continue."
    read -p "$(echo -e "${YELLOW}Do you want to overwrite it? (y/N): ${NC}")" OVERWRITE_CHOICE
    echo ""
    if [[ "$OVERWRITE_CHOICE" =~ ^[Yy]$ ]]; then
        msg_info "Proceeding with reconfiguration..."
        gen
    else
        msg_info "Skipping reconfiguration. Your existing 'secrets.nix' is preserved."
        echo ""
    fi
else
    gen
fi

msg_success "Initial setup process finished!"
cold
msg_info "Your dotfiles are ready to be applied."
msg_warn "You may need to log out and log back in for all changes to take effect."
