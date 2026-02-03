#!/bin/bash

set -e

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SECRETS_FILE="$BASE_DIR/secrets.nix"
REQUIRES_SCRIPT="$BASE_DIR/requires.sh"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m'

command_exists() { command -v "$1" >/dev/null 2>&1; }

ui_header() {
    local title="$1"
    if command_exists gum; then
        echo ""
        gum style --foreground 212 --border-foreground 212 --border double --align center --width 50 "$title"
    else
        echo -e "\n${CYAN}=== $title ===${NC}"
    fi
}

ui_info() {
    if command_exists gum; then
        gum style --foreground 39 "[INFO] $1"
    else
        echo -e "${CYAN}[INFO]${NC} $1"
    fi
}

ui_input() {
    local prompt="$1" default="$2"
    if command_exists gum; then
        gum input --header "$prompt" --value "$default"
    else
        read -p "$(echo -e "${GREEN}${prompt}${NC} [default: ${YELLOW}${default}${NC}]: ")" user_input < /dev/tty
        echo "${user_input:-$default}"
    fi
}

ui_choose() {
    local prompt="$1" choices="$2" default="$3"
    if command_exists gum; then
        gum choose --header "$prompt" --selected "$default" ${choices}
    else
        echo -e "${GREEN}${prompt}${NC} (${choices}) [default: ${YELLOW}${default}${NC}]"
        read -p "> " user_input < /dev/tty
        echo "${user_input:-$default}"
    fi
}

ui_confirm() {
    local prompt="$1"
    if command_exists gum; then
        gum confirm "$prompt"
    else
        read -p "$(echo -e "${YELLOW}${prompt} (y/N): ${NC}")" choice
        [[ "$choice" =~ ^[Yy]$ ]]
    fi
}

# ==========================================
# 配置字典
# 格式: Group | NixPath | Prompt | DefaultCmd | OptionalChoices
# ==========================================
read -r -d '' CONFIG_ITEMS << 'EOF' || true
BASE|home.user|System username|whoami|
BASE|home.dir|Home directory|echo "$HOME"|
GIT|git.name|Git user name|echo "Someone"|
GIT|git.email|Git email address|echo "someone@example.com"|
PROXY|proxy.status|Proxy status|echo "none"|none manual keep
PROXY|proxy.url|Proxy URL (blank for none)|echo ""|
EOF

gen() {
    ui_header "Configuration Wizard"
    ui_info "Please provide the following information."

    local file_content="{\n"
    local current_group=""
    
    while IFS='|' read -u 9 -r group nix_path prompt default_cmd choices; do
        [ -z "$group" ] && continue
        if [ "$group" != "$current_group" ]; then
            [ -n "$current_group" ] && file_content+="\n"
            file_content+="  ###################################\n"
            file_content+="  #  ${group} IDENTITY CONFIGURATION  #\n"
            file_content+="  ###################################\n"
            current_group="$group"
        fi

        local default_val
        default_val=$(eval "$default_cmd")
        local final_value=""
        
        if [ -n "$choices" ]; then
            final_value=$(ui_choose "$prompt" "$choices" "$default_val")
        else
            final_value=$(ui_input "$prompt" "$default_val")
        fi

        final_value="${final_value//\\/\\\\}"
        final_value="${final_value//\"/\\\"}"

        file_content+=$(printf "  %s = \"%s\";\n" "$nix_path" "$final_value")

    done 9<<< "$CONFIG_ITEMS"

    file_content+="\n}"

    file_content+="\n}"

    printf '%b' "$file_content" > "$SECRETS_FILE"
    local TARGET_DIR="$HOME/.config/dotfiles"
    mkdir -p "$TARGET_DIR"
    ln -sf "$SECRETS_FILE" "$TARGET_DIR/secrets.nix"
    
    if command_exists gum; then
        gum style --foreground 82 "✔ secrets.nix generated and linked successfully!"
    else
        echo -e "${GREEN}[SUCCESS]${NC} Generated and linked secrets.nix"
    fi
}

cold() {
    ui_info "Applying Home Manager configuration for the first time..."
    /bin/bash resources/scripts/dtf apply
}

if [ ! -f "$REQUIRES_SCRIPT" ]; then
    echo -e "${RED}[ERROR]${NC} 'requires.sh' not found!"
    exit 1
fi
chmod +x "$REQUIRES_SCRIPT"
"$REQUIRES_SCRIPT"

if [ -f "$SECRETS_FILE" ]; then
    if ui_confirm "secrets.nix already exists. Overwrite it?"; then
        gen
    fi
else
    gen
fi

if ui_confirm "Do you want to apply the configuration now?"; then
    cold
fi

ui_header "Setup Finished"
ui_info "Your dotfiles are ready. You may need to restart your shell."