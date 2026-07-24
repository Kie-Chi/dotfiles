#!/usr/bin/env bash

set -euo pipefail

repository_url="${ENVY_REPOSITORY_URL:-https://github.com/Kie-Chi/dotfiles.git}"
branch="${ENVY_BRANCH:-master}"
target="${ENVY_DOTFILES:-${HOME:?HOME is not set}/.dotfiles}"
run_setup=1
temporary_dir=""

usage() {
    cat <<'EOF'
Usage: install.sh [options]

Bootstrap the dotfiles repository, then run its setup.sh.

Options:
  --repo URL       Git repository URL
  --branch NAME    Branch to clone (default: master)
  --target PATH    Checkout path (default: $HOME/.dotfiles)
  --no-setup       Clone only; do not run setup.sh
  -h, --help       Show this help

Environment equivalents:
  ENVY_REPOSITORY_URL, ENVY_BRANCH, ENVY_DOTFILES
EOF
}

fail() {
    printf 'error: %s\n' "$1" >&2
    exit 1
}

# shellcheck disable=SC2329  # Invoked indirectly by trap.
cleanup() {
    if [ -n "$temporary_dir" ] && [ -d "$temporary_dir" ]; then
        rm -rf "$temporary_dir"
    fi
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --repo)
            [ "$#" -ge 2 ] || fail "--repo requires a value"
            repository_url="$2"
            shift 2
            ;;
        --branch)
            [ "$#" -ge 2 ] || fail "--branch requires a value"
            branch="$2"
            shift 2
            ;;
        --target)
            [ "$#" -ge 2 ] || fail "--target requires a value"
            target="$2"
            shift 2
            ;;
        --no-setup)
            run_setup=0
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

[ -n "$repository_url" ] || fail "repository URL cannot be empty"
[ -n "$branch" ] || fail "branch cannot be empty"
[ -n "$target" ] || fail "target cannot be empty"

case "$target" in
    /|"$HOME")
        fail "refusing to use a broad target path: $target"
        ;;
esac

command -v git >/dev/null 2>&1 || fail "git is required before bootstrapping"

if [ -d "$target/.git" ]; then
    printf 'Using existing checkout: %s\n' "$target"
elif [ -e "$target" ]; then
    fail "target exists but is not a Git checkout: $target"
else
    parent_dir="$(dirname "$target")"
    mkdir -p "$parent_dir"
    temporary_dir="$(mktemp -d "${TMPDIR:-/tmp}/envy-bootstrap.XXXXXX")"
    trap cleanup EXIT HUP INT TERM

    printf 'Cloning %s (%s)...\n' "$repository_url" "$branch"
    git clone --quiet --single-branch --branch "$branch" "$repository_url" "$temporary_dir/repository"
    [ ! -e "$target" ] || fail "target appeared while cloning: $target"
    mv "$temporary_dir/repository" "$target"
    rmdir "$temporary_dir"
    temporary_dir=""
    trap - EXIT HUP INT TERM
fi

[ -f "$target/setup.sh" ] || fail "setup.sh is missing from checkout: $target"

if [ "$run_setup" -eq 0 ]; then
    printf 'Checkout ready. Run: bash %s/setup.sh\n' "$target"
    exit 0
fi

export ENVY_DOTFILES="$target"
if [ -t 0 ]; then
    exec "$BASH" "$target/setup.sh"
fi

# `curl ... | bash` occupies stdin with the script body. Reattach the
# interactive setup to the controlling terminal after the clone completes.
if tty -s </dev/tty 2>/dev/null; then
    exec "$BASH" "$target/setup.sh" </dev/tty
fi

fail "interactive setup requires a terminal; rerun with --no-setup to clone only"
