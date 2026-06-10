{ pkgs, config, lib, cfg, ... }:

let
  npmPrefix = "$HOME/.npm-global";
in
{
  home.sessionVariables = {
    # Agent API keys (from sops env-secrets template, sourced in shell)
    # These are also set via sops.templates."env-secrets" in home.nix
    ANTHROPIC_BASE_URL = "https://dashscope.aliyuncs.com/apps/anthropic";
    ANTHROPIC_MODEL = "glm-5.1";

    # NPM global configuration (for agent npm tools: codegraph)
    npm_config_prefix = npmPrefix;
    npm_config_cache = "$HOME/.cache/npm";
    npm_config_registry = "https://registry.npmmirror.com";
  };

  home.sessionPath = [
    "${npmPrefix}/bin"
  ];

  home.packages = with pkgs; [
    # Agent CLIs
    claude-code
    codex
  ] ++ lib.optionals ((cfg.home.option or "desktop") == "desktop") [
    # Agent IDE (desktop only)
    code-cursor
  ];
}