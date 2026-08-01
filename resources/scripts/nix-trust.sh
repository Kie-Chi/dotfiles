#!/usr/bin/env bash

set -euo pipefail

BEGIN_MARKER='# BEGIN ENVY MANAGED NIX MIRROR'
END_MARKER='# END ENVY MANAGED NIX MIRROR'
THALHEIM_URL='https://cache.thalheim.io'
THALHEIM_KEY='cache.thalheim.io-1:R7msbosLEZKrxk/lKxf9BTjOOH7Ax3H0Qj0/6wiHOgc='
USTC_URL='https://mirrors.ustc.edu.cn/nix-channels/store'
NIXOS_KEY='cache.nixos.org-1:6NCHdD59X431o0gWypbMrAURkbJ16ZPMQFGspcDShjY='

command_name="${1:-status}"
if [ "$#" -gt 0 ]; then
    shift
fi

mirror_mode="${ENVY_MIRROR:-china}"
managed_user="${SUDO_USER:-${USER:-}}"
custom_config="${ENVY_NIX_CUSTOM_CONFIG:-/etc/nix/nix.custom.conf}"
system_config="${ENVY_NIX_SYSTEM_CONFIG:-/etc/nix/nix.conf}"
systemctl_command="${ENVY_NIX_TRUST_SYSTEMCTL:-systemctl}"
sudo_command="${ENVY_NIX_TRUST_SUDO:-sudo}"
elevated=0
quiet=0
temporary_file=""

usage() {
    cat <<'EOF'
Usage: nix-trust.sh status|repair [options]

Options:
  --mode MODE           Mirror profile: upstream or china
  --user NAME           User trusted to submit restricted daemon settings
  --custom-config PATH  Managed nix.custom.conf path
  --system-config PATH  Parent nix.conf path that includes nix.custom.conf
  --quiet               Suppress successful/status output
EOF
}

fail() {
    printf '[ERROR] %s\n' "$1" >&2
    exit 2
}

say() {
    if [ "$quiet" -eq 0 ]; then
        printf '%s\n' "$1"
    fi
}

cleanup() {
    if [ -n "$temporary_file" ]; then
        rm -f "$temporary_file"
    fi
}
trap cleanup EXIT HUP INT TERM

while [ "$#" -gt 0 ]; do
    case "$1" in
        --mode)
            [ "$#" -ge 2 ] || fail "--mode requires a value"
            mirror_mode="$2"
            shift 2
            ;;
        --user)
            [ "$#" -ge 2 ] || fail "--user requires a value"
            managed_user="$2"
            shift 2
            ;;
        --custom-config)
            [ "$#" -ge 2 ] || fail "--custom-config requires a value"
            custom_config="$2"
            shift 2
            ;;
        --system-config)
            [ "$#" -ge 2 ] || fail "--system-config requires a value"
            system_config="$2"
            shift 2
            ;;
        --systemctl)
            [ "$#" -ge 2 ] || fail "--systemctl requires a value"
            systemctl_command="$2"
            shift 2
            ;;
        --elevated)
            elevated=1
            shift
            ;;
        --quiet)
            quiet=1
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            fail "unknown option: $1"
            ;;
    esac
done

case "$command_name" in
    status|repair)
        ;;
    *)
        usage >&2
        fail "command must be 'status' or 'repair'"
        ;;
esac

case "$mirror_mode" in
    upstream|china)
        ;;
    *)
        fail "mirror mode must be 'upstream' or 'china'"
        ;;
esac

case "$managed_user" in
    ''|*[!A-Za-z0-9._-]*)
        fail "managed user is empty or contains unsupported characters"
        ;;
esac

case "$custom_config:$system_config" in
    /*:/*)
        ;;
    *)
        fail "Nix configuration paths must be absolute"
        ;;
esac

render_block() {
    local substituters="$THALHEIM_URL"
    local keys="$THALHEIM_KEY"
    if [ "$mirror_mode" = "china" ]; then
        substituters="$substituters $USTC_URL"
        keys="$keys $NIXOS_KEY"
    fi

    printf '%s\n' \
        "$BEGIN_MARKER" \
        "extra-substituters = $substituters" \
        "extra-trusted-substituters = $substituters" \
        "extra-trusted-public-keys = $keys" \
        "extra-trusted-users = $managed_user" \
        'download-attempts = 3' \
        "$END_MARKER"
}

validate_parent_include() {
    if [ ! -r "$system_config" ]; then
        fail "$system_config is not readable; cannot verify the nix.custom.conf include"
    fi
    if ! grep -Eq '^[[:space:]]*!include[[:space:]]+(/etc/nix/)?nix\.custom\.conf[[:space:]]*$' "$system_config"; then
        fail "$system_config does not include nix.custom.conf; refusing to edit an inactive file"
    fi
}

marker_count() {
    local marker="$1"
    local count
    if [ ! -e "$custom_config" ]; then
        printf '0\n'
        return
    fi
    count="$(grep -Fxc "$marker" "$custom_config" || true)"
    printf '%s\n' "$count"
}

validate_markers() {
    local begin_count end_count begin_line end_line
    begin_count="$(marker_count "$BEGIN_MARKER")"
    end_count="$(marker_count "$END_MARKER")"
    if [ "$begin_count" -ne "$end_count" ] || [ "$begin_count" -gt 1 ]; then
        fail "$custom_config contains malformed or duplicate envY mirror markers"
    fi
    if [ "$begin_count" -eq 1 ]; then
        begin_line="$(grep -Fnx "$BEGIN_MARKER" "$custom_config" | cut -d: -f1)"
        end_line="$(grep -Fnx "$END_MARKER" "$custom_config" | cut -d: -f1)"
        if [ "$begin_line" -ge "$end_line" ]; then
            fail "$custom_config contains envY mirror markers in the wrong order"
        fi
    fi
}

render_candidate() {
    local output="$1"
    local begin_count
    begin_count="$(marker_count "$BEGIN_MARKER")"
    : > "$output"

    if [ "$begin_count" -eq 1 ]; then
        {
            awk -v marker="$BEGIN_MARKER" '$0 == marker { exit } { print }' \
                "$custom_config"
            render_block
            awk -v marker="$END_MARKER" \
                'found { print } $0 == marker { found = 1; next }' \
                "$custom_config"
        } >> "$output"
        return
    fi

    {
        if [ -e "$custom_config" ]; then
            cat "$custom_config"
            if [ -s "$custom_config" ] && [ "$(tail -c 1 "$custom_config" | wc -l | tr -d ' ')" -eq 0 ]; then
                printf '\n'
            fi
        fi
        render_block
    } >> "$output"
}

make_candidate() {
    temporary_file="$(mktemp "${TMPDIR:-/tmp}/envy-nix-trust.XXXXXX")"
    render_candidate "$temporary_file"
}

is_ready() {
    validate_parent_include
    validate_markers
    make_candidate
    if [ -f "$custom_config" ] && cmp -s "$temporary_file" "$custom_config"; then
        rm -f "$temporary_file"
        temporary_file=""
        return 0
    fi
    rm -f "$temporary_file"
    temporary_file=""
    return 1
}

restart_active_daemon() {
    local service
    if ! command -v "$systemctl_command" >/dev/null 2>&1; then
        return
    fi
    for service in nix-daemon.service determinate-nixd.service; do
        if "$systemctl_command" is-active --quiet "$service" 2>/dev/null; then
            "$systemctl_command" restart "$service"
            say "[OK] Restarted $service after updating Nix daemon trust."
            return
        fi
    done
}

repair_as_current_user() {
    local config_dir
    config_dir="$(dirname "$custom_config")"
    mkdir -p "$config_dir"
    temporary_file="$(mktemp "$config_dir/.envy-nix-custom.XXXXXX")"
    render_candidate "$temporary_file"

    if [ -f "$custom_config" ] && cmp -s "$temporary_file" "$custom_config"; then
        rm -f "$temporary_file"
        temporary_file=""
        say "[OK] Nix daemon trust is already ready: $custom_config"
        return
    fi

    chmod 0644 "$temporary_file"
    mv -f "$temporary_file" "$custom_config"
    temporary_file=""
    say "[OK] Updated Nix daemon trust: $custom_config"
    restart_active_daemon
}

if is_ready; then
    say "[OK] Nix daemon trust is ready: $custom_config"
    exit 0
fi

if [ "$command_name" = "status" ]; then
    say "[INFO] Nix daemon trust requires repair: $custom_config"
    exit 1
fi

config_dir="$(dirname "$custom_config")"
if [ "$(id -u)" -eq 0 ] || { [ -d "$config_dir" ] && [ -w "$config_dir" ]; }; then
    repair_as_current_user
    exit 0
fi

if [ "$elevated" -eq 1 ]; then
    fail "elevated process still cannot write $config_dir"
fi
if ! command -v "$sudo_command" >/dev/null 2>&1; then
    fail "Nix daemon trust requires root access, but sudo is unavailable"
fi

bash_command="$(command -v bash)"
quiet_args=()
if [ "$quiet" -eq 1 ]; then
    quiet_args=(--quiet)
fi
exec "$sudo_command" -- "$bash_command" "$0" repair \
    --mode "$mirror_mode" \
    --user "$managed_user" \
    --custom-config "$custom_config" \
    --system-config "$system_config" \
    --systemctl "$systemctl_command" \
    "${quiet_args[@]}" \
    --elevated
