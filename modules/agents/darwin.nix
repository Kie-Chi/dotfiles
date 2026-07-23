{ ... }:

{
  # Darwin distribution for agent applications. Agent configuration and
  # skills remain cross-platform in modules/agents/default.nix.
  envy.darwin.homebrew.casks.include = [
    "codex"
    "chatgpt"
  ];
}
