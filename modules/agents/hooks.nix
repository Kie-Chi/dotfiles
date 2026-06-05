{ pkgs, lib, config, sys, ... }:

{
  # Register plugin MCP servers into agent clients (Claude Code, Codex, etc).
  # Runs after plugin install to ensure CLI binaries are available.
  home.activation.installCodegraphMCP = sys.task.activation {
    name = "codegraph-install";
    after = [ "installAgentPlugins" ];
    script = ''
      ${pkgs.nodejs_26}/bin/node $HOME/.npm-global/lib/node_modules/@colbymchenry/codegraph/npm-shim.js install -y
    '';
  };

  # rtk hook registration is NOT automated here.
  # Claude Code manages ~/.claude/settings.json directly.
  # To register the rtk hook, run: rtk init -g
}