#!/bin/bash

set -e

handle_sigint() {
    echo -e "\n${RED}Setup cancelled by user.${NC}" >&2
    exit 130
}

trap 'handle_sigint' SIGINT

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
    local val=""
    if command_exists gum; then
        val=$(gum input --header "$prompt" --placeholder "$default")
        local gum_exit_status=$?
        if [ "$gum_exit_status" -ne 0 ]; then
            exit "$gum_exit_status"
        fi
    else
        read -p "$(echo -e "${GREEN}${prompt}${NC} [default: ${YELLOW}${default}${NC}]: ")" user_input < /dev/tty
        local read_exit_status=$?
        if [ "$read_exit_status" -ne 0 ]; then
            exit "$read_exit_status"
        fi
        val="${user_input:-$default}"
    fi
    echo "${val:-$default}"
}

ui_choose() {
    local prompt="$1" choices="$2" default="$3"
    local val=""
    if command_exists gum; then
        val=$(gum choose --header "$prompt" --selected "$default" ${choices})
        local gum_exit_status=$?
        if [ "$gum_exit_status" -ne 0 ]; then
            exit "$gum_exit_status"
        fi
    else
        echo -e "${GREEN}${prompt}${NC} (${choices}) [default: ${YELLOW}${default}${NC}]"
        read -p "> " user_input < /dev/tty
        local read_exit_status=$?
        if [ "$read_exit_status" -ne 0 ]; then
            exit "$read_exit_status"
        fi
        val="${user_input:-$default}"
    fi
    echo "$val"
}

ui_confirm() {
    local prompt="$1"
    if command_exists gum; then
        gum confirm "$prompt"
        local gum_exit_status=$?
        if [ "$gum_exit_status" -eq 130 ]; then
            exit "$gum_exit_status"
        fi
        return "$gum_exit_status"
    else
        read -p "$(echo -e "${YELLOW}${prompt} (y/N): ${NC}")" choice < /dev/tty
        local read_exit_status=$?
        if [ "$read_exit_status" -ne 0 ]; then
            exit "$read_exit_status"
        fi
        [[ "$choice" =~ ^[Yy]$ ]]
        return "$?"
    fi
}

ui_error() {
    local msg="$1"
    if command_exists gum; then
        gum style --foreground 196 --bold "✖ $msg"
    else
        echo -e "${RED}[ERROR] ${msg}${NC}"
    fi
}


get_val() {
    local key="$1"
    local safe_key="${key//./_}"
    local var_name="VALUES_${safe_key}"
    echo "${!var_name}"
}

set_val() {
    local key="$1"
    local val="$2"
    local safe_key="${key//./_}"
    printf -v "VALUES_${safe_key}" '%s' "$val"
}

# ==========================================
# CONFIG
# FORMAT: 
# {
#    "group": "GROUP_NAME",
#    "path": "nix.path.to.value",
#    "prompt": "Prompt to show user",
#    "defaultCmd": "command to get default value",
#    "condition": "optional bash condition to include this prompt",
#    "choices": ["optional", "list", "of", "choices"]
#    "validation": "optional bash command to validate input"
#    "errorMsg": "optional error message if validation fails"
# }
# ==========================================
read -r -d '' CONFIG_JSON << 'EOF' || true
[
  {
    "group": "BASE",
    "path": "home.user",
    "prompt": "System username",
    "defaultCmd": "whoami",
    "validation": "[[ -n \"$input_val\" ]]", 
    "errorMsg": "System username cannot be empty."
  },
  {
    "group": "BASE",
    "path": "home.dir",
    "prompt": "Home directory",
    "defaultCmd": "echo \"$HOME\"",
    "validation": "[[ -n \"$input_val\" ]]", 
    "errorMsg": "Home directory cannot be empty."
  },
  {
    "group": "GIT",
    "path": "git.name",
    "prompt": "Git user name",
    "defaultCmd": "whoami",
    "validation": "[[ -n \"$input_val\" ]]", 
    "errorMsg": "Git name cannot be empty."
  },
  {
    "group": "GIT",
    "path": "git.email",
    "prompt": "Git user email",
    "defaultCmd": "echo \"$(whoami)@$(hostname -f)\"",
    "validation": "python3 -c \"import re, sys; sys.exit(0) if re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$', sys.stdin.read().strip()) else sys.exit(1)\" <<< \"$input_val\"",    
    "errorMsg": "Please enter a valid email address."
  },
  {
    "group": "PROXY",
    "path": "proxy.status",
    "prompt": "Proxy status",
    "defaultCmd": "echo 'none'",
    "choices": ["none", "manual", "keep"]
  },
  {
    "group": "PROXY",
    "path": "proxy.url",
    "prompt": "Proxy URL",
    "defaultCmd": "echo ''",
    "condition": "[[ \"$(get_val proxy.status)\" != \"none\" ]]",
    "validation": "python3 -c \"import sys; url = sys.stdin.read().strip(); sys.exit(0) if url.startswith('http://') or url.startswith('https://') else sys.exit(1)\" <<< \"$input_val\"",
    "errorMsg": "Proxy URL must start with http:// or https://"
  }
]
EOF

gen() {
    if ! echo "$CONFIG_JSON" | jq . >/dev/null 2>&1; then
        echo -e "${RED}[ERROR] Invalid JSON syntax in CONFIG_JSON.${NC}"
        echo "$CONFIG_JSON" | jq . 
        exit 1
    fi

    ui_header "Configuration Wizard"
    ui_info "Please provide the following information."

    local file_content="{\n"
    local current_group=""
    
    while IFS=$'\t' read -u 3 -r group nix_path prompt default_cmd condition choices_str validation error_msg; do
        if [ -n "$condition" ] && [ "$condition" != "null" ]; then
            if ! eval "$condition"; then
                continue
            fi
        fi

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
        
        while true; do
            if [ -n "$choices_str" ] && [ "$choices_str" != "null" ]; then
                final_value=$(ui_choose "$prompt" "$choices_str" "$default_val")
            else
                final_value=$(ui_input "$prompt" "$default_val")
            fi

            if [ -n "$validation" ] && [ "$validation" != "null" ]; then
                input_val="$final_value"
                if eval "$validation"; then
                    break
                else
                    local show_err="${error_msg:-"Invalid input, please try again."}"
                    ui_error "$show_err"
                    default_val="$final_value" 
                fi
            else
                break
            fi
        done

        set_val "$nix_path" "$final_value"

        final_value="${final_value//\\/\\\\}"
        final_value="${final_value//\"/\\\"}"

        file_content+=$(printf "  %s = \"%s\";\n" "$nix_path" "$final_value")
    done 3< <(echo "$CONFIG_JSON" | jq -r '.[] | [
        .group, 
        .path, 
        .prompt, 
        .defaultCmd, 
        (.condition // "null"), 
        (.choices // [] | if length > 0 then join(" ") else "null" end),
        (.validation // "null"),
        (.errorMsg // "null")
    ] | @tsv')

    file_content+="\n}"

    printf '%b' "$file_content" > "$SECRETS_FILE"    
    local TARGET_DIR="$HOME/.config/dotfiles"
    mkdir -p "$TARGET_DIR"
    ln -sf "$SECRETS_FILE" "$TARGET_DIR/secrets.nix"
    
    if command_exists gum; then
        gum style --foreground 82 "✔ secrets.nix generated successfully!"
    else
        echo -e "${GREEN}[SUCCESS]${NC} Generated secrets.nix"
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

if ! command_exists jq; then
    echo -e "${RED}[ERROR]${NC} 'jq' is required for this script but not installed."
    exit 1
fi

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