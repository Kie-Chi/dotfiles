# Optional for zsh

##########################################
# Aliases

if command -v copypath > /dev/null 2>&1; then
    alias cpd='copypath'
fi

# Prevent nvim nesting in terminal - use nvr to open files in outer instance
# Opens in right vertical split to avoid covering the terminal
if [ -n "$NVIM" ] || [ -n "$NVIM_LISTEN_ADDRESS" ]; then
    alias nvim="nvr --remote-wait -O"
    alias vim="nvr --remote-wait -O"
fi