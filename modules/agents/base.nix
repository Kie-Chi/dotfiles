{ pkgs, config, lib, secrets, isDesktop, sys, ... }:

let
  npmPrefix = "$HOME/.npm-global";
in
{
  home.sessionVariables = {
    # Agent API keys
    API_KEY = secrets.agent.apikey;
    DASHSCOPE_API_KEY = secrets.agent.apikey;

    # Anthropic proxy configuration
    ANTHROPIC_BASE_URL = "https://dashscope.aliyuncs.com/apps/anthropic";
    ANTHROPIC_API_KEY = secrets.agent.apikey;
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
  ] ++ lib.optionals isDesktop [
    # Agent IDE (desktop only)
    code-cursor
  ];
}