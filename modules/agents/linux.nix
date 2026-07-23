{ config, lib, pkgs, sys, ... }:

let
  isDesktop = config.envy.linux.option == "desktop";
  npmPrefix = "$HOME/.npm-global";
  npmRegistry = "https://registry.npmmirror.com";
  rtk = pkgs.callPackage ./linux/rtk.nix { };

  agentPlugins = [
    { name = "@colbymchenry/codegraph"; version = "0.9.7"; tool = "node"; }
    { name = "headroom-ai"; tool = "python"; withs = [ "fastapi" ]; }
  ];

  installPlugin = plugin:
    if plugin.tool == "node" then
      let
        packageSpec = "${plugin.name}@${plugin.version}";
        checkPath = "$HOME/.npm-global/lib/node_modules/${plugin.name}";
      in ''
        if ! [ -d "${checkPath}" ]; then
          ${pkgs.nodejs_26}/bin/npm install -g ${packageSpec}
        fi
      ''
    else if plugin.tool == "python" then
      let
        withFlags = lib.concatStringsSep " " (map (dependency: "--with ${dependency}") plugin.withs);
        checkPath = "$HOME/.local/share/uv/tools/${plugin.name}";
      in ''
        if ! [ -d "${checkPath}" ]; then
          ${pkgs.uv}/bin/uv tool install ${plugin.name} ${withFlags}
        fi
      ''
    else
      throw "Unknown agent plugin tool: ${plugin.tool}";
in
{
  home.sessionVariables = {
    npm_config_prefix = npmPrefix;
    npm_config_cache = "$HOME/.cache/npm";
    npm_config_registry = npmRegistry;
  };

  home.sessionPath = [ "${npmPrefix}/bin" ];

  envy.packages.home.include = [
    pkgs.codex
    rtk
  ] ++ lib.optional isDesktop pkgs.code-cursor;

  home.activation.installAgentPlugins = sys.task.activation {
    name = "agent-plugins";
    script = ''
      mkdir -p ${npmPrefix}/bin ${npmPrefix}/lib/node_modules "$HOME/.cache/npm"
      export npm_config_prefix=${npmPrefix}
      export npm_config_cache="$HOME/.cache/npm"
      export npm_config_registry=${npmRegistry}

      ${lib.concatMapStringsSep "\n" installPlugin agentPlugins}
    '';
  };

  home.activation.installCodegraphMCP = sys.task.activation {
    name = "codegraph-install";
    after = [ "installAgentPlugins" ];
    script = ''
      ${pkgs.nodejs_26}/bin/node \
        "$HOME/.npm-global/lib/node_modules/@colbymchenry/codegraph/npm-shim.js" \
        install -y
    '';
  };
}
