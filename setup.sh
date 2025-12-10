#!/bin/bash
set -e

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOTB_BIN="$BASE_DIR/bin/dotb"
CONFIG_FILE="$BASE_DIR/configs/config.yml"
GREEN='\033[0;32m'
NC='\033[0m'

echo -e "${GREEN}-> Setting up environment from $BASE_DIR${NC}"
if [ -f "$DOTB_BIN" ]; then
    chmod +x "$DOTB_BIN"
else
    echo "Error: Binary not found at $DOTB_BIN"
    exit 1
fi

if [ ! -f "/usr/local/bin/dotb" ]; then
    echo "Creating symlink for dotb..."
    sudo ln -sf "$DOTB_BIN" /usr/local/bin/dotb || echo "Warning: Failed to link to /usr/local/bin, skipping."
fi
echo -e "${GREEN}-> Executing DotBuilder...${NC}"

# "$@" ./install.sh --debug
"$DOTB_BIN" -c "$CONFIG_FILE" "$@"
