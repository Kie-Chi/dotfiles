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

get_existing_val() {
    local key="$1"
    if [ -f "$SECRETS_FILE" ]; then
        grep -w "$key" "$SECRETS_FILE" | sed -n "s/.*$key[[:space:]]*=[[:space:]]*\"\([^\"]*\)\".*/\1/p" | head -n 1
    fi
}

init_values() {
    ui_info "Initializing configuration..."
    local paths=$(echo "$CONFIG_JSON" | jq -r '.[].path')
    for p in $paths; do
        local existing=$(get_existing_val "$p")
        if [ -n "$existing" ]; then
            set_val "$p" "$existing"
        else
            local cmd=$(echo "$CONFIG_JSON" | jq -r ".[] | select(.path == \"$p\") | .defaultCmd")
            set_val "$p" "$(eval "$cmd")"
        fi
    done
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
#    "ignore": true/false - if true, skip user input and use defaultCmd directly
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
    "path": "home.passwd",
    "prompt": "System password",
    "defaultCmd": "whoami",
    "validation": "[[ -n \"$input_val\" ]]", 
    "errorMsg": "System password cannot be empty."
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
    "path": "proxy.tun",
    "prompt": "Proxy TUN status",
    "defaultCmd": "echo 'true'",
    "condition": "[[ \"$(get_val proxy.status)\" != \"none\" ]]",
    "choices": ["true", "false"]
  },
  {
    "group": "PROXY",
    "path": "proxy.url",
    "prompt": "Proxy URL",
    "defaultCmd": "echo ''",
    "condition": "[[ \"$(get_val proxy.status)\" != \"none\" ]]",
    "validation": "python3 -c \"import sys; url = sys.stdin.read().strip(); sys.exit(0) if url.startswith('http://') or url.startswith('https://') else sys.exit(1)\" <<< \"$input_val\"",
    "errorMsg": "Proxy URL must start with http:// or https://"
  },
  {
    "group": "ENV",
    "path": "dotfiles.path",
    "prompt": "Dotfiles local path",
    "defaultCmd": "echo \"$BASE_DIR\"",
    "ignore": true
  },
  {
    "group": "ENV",
    "path": "agent.apikey",
    "prompt": "Agent API Key",
    "defaultCmd": "echo \"$API_KEY\""
  }
]
EOF

# ===========================================
# 
#           LIST ITERM MODE
# 
# ===========================================

main() {
    if ! echo "$CONFIG_JSON" | jq . >/dev/null 2>&1; then
        echo -e "${RED}[ERROR] Invalid JSON syntax in CONFIG_JSON.${NC}"
        echo "$CONFIG_JSON" | jq . 
        exit 1
    fi

    ui_header "Configuration Wizard"
    ui_info "Please provide the following information."

    local file_content="{\n"
    local current_group=""
    
    while IFS=$'\t' read -u 3 -r group nix_path prompt default_cmd condition choices_str validation error_msg ignore; do
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

        local existing_val=$(get_existing_val "$nix_path")
        local default_val
        
        if [ -n "$existing_val" ]; then
            default_val="$existing_val"
        else
            default_val=$(eval "$default_cmd")
        fi
        local final_value=""
        
        if [ "$ignore" = "true" ]; then
            final_value="$default_val"
        else
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
                        local show_err="${error_msg:-\"Invalid input, please try again.\"}"
                        ui_error "$show_err"
                        default_val="$final_value" 
                    fi
                else
                    break
                fi
            done
        fi

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
        (.errorMsg // "null"),
        (if .ignore == true then "true" else "false" end)
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

# ===========================================
# 
#               TUI MODE
# 
# ===========================================
configure_group() {
    local group_name="$1"
    while true; do
        local map=$(echo "$CONFIG_JSON" | jq -r ".[] | select(.group == \"$group_name\") | \"\(.prompt)|\(.path)\"")        
        local options=""
        while read -r line; do
            local prompt="${line%|*}"
            local path="${line#*|}"
            local cur_val=$(get_val "$path")
            options+="$prompt: [$cur_val]\n"
        done <<< "$map"
        options+="BACK"

        ui_header "Editing $group_name"
        local choice=$(echo -e "$options" | gum choose --header "Select item to modify:")

        if [[ "$choice" == "BACK" || -z "$choice" ]]; then break; fi
        local selected_prompt="${choice%%:*}"
        local selected_path=$(echo "$CONFIG_JSON" | jq -r ".[] | select(.prompt == \"$selected_prompt\" and .group == \"$group_name\") | .path")        
        local item_json=$(echo "$CONFIG_JSON" | jq -c ".[] | select(.path == \"$selected_path\")")
        edit_item "$item_json"
    done
}

edit_item() {
    local json="$1"
    local path=$(echo "$json" | jq -r .path)
    local prompt=$(echo "$json" | jq -r .prompt)
    local choices=$(echo "$json" | jq -r '.choices // [] | join(" ")')
    local validation=$(echo "$json" | jq -r '.validation // "null"')
    local cur_val=$(get_val "$path")

    local new_val=""
    if [[ -n "$choices" && "$choices" != "null" ]]; then
        new_val=$(ui_choose "$prompt" "$choices" "$cur_val")
    else
        new_val=$(ui_input "$prompt" "$cur_val")
    fi

    if [[ "$validation" != "null" ]]; then
        input_val="$new_val"
        if ! eval "$validation"; then
            ui_error "Invalid input for $prompt"
            sleep 1
            return
        fi
    fi
    set_val "$path" "$new_val"
}

main_tui() {
    init_values
    
    while true; do
        local groups=$(echo "$CONFIG_JSON" | jq -r '.[].group' | sort -u)
        ui_header "NixOS Config TUI"        
        local choice=$(printf "APPLY_AND_SAVE\nEXIT_WITHOUT_SAVING\n---\n%s" "$groups" | gum choose --header "Main Menu")

        case "$choice" in
            APPLY_AND_SAVE)
                if ui_confirm "Save changes to $SECRETS_FILE?"; then
                    save_all_to_nix
                    break
                fi
                ;;
            EXIT_WITHOUT_SAVING)
                if ui_confirm "Exit without saving?"; then exit 0; fi
                ;;
            ---|"") continue ;;
            *)
                configure_group "$choice"
                ;;
        esac
    done
}

save_all_to_nix() {
    local file_content="{\n"
    local groups=$(echo "$CONFIG_JSON" | jq -r '.[].group' | sort -u)
    
    for g in $groups; do
        file_content+="\n  # --- $g CONFIG ---\n"
        local paths=$(echo "$CONFIG_JSON" | jq -r ".[] | select(.group == \"$g\") | .path")
        for p in $paths; do
            local val=$(get_val "$p")
            val="${val//\\/\\\\}"
            val="${val//\"/\\\"}"
            file_content+=$(printf "  %s = \"%s\";\n" "$p" "$val")
        done
    done
    file_content+="\n}"
    
    printf '%b' "$file_content" > "$SECRETS_FILE"
    ui_info "Secrets saved."
}

cold() {
    ui_info "Applying Home Manager configuration for the first time..."
    bash -c "source /nix/var/nix/profiles/default/etc/profile.d/nix-daemon.sh 2>/dev/null || true; bash $BASE_DIR/resources/scripts/dtf apply"
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
        main_tui
    fi
else
    main_tui
fi

if ui_confirm "Do you want to apply the configuration now?"; then
    cold
fi

login=$(ui_choose "Select a devops to login" "none github onedev" "none")

case "$login" in
  github)
    gh auth login
    ;;
  onedev)
    tod_url=$(ui_input "Enter your OneDev Server URL" "http://nas.fl0wer.cn:6610")
    tod_token=$(ui_input "Enter your OneDev Access Token" "")
    cat << EOF > ~/.todconfig
server-url=$tod_url
access-token=$tod_token
EOF
    echo "tod configured successfully at ~/.todconfig!"
    ;;
  none)
    echo "Skipped devops login."
    ;;
  *)
    echo "Invalid selection."
    ;;
esac

ui_header "Setup Finished"
ui_info "Your dotfiles are ready. You may need to restart your shell."