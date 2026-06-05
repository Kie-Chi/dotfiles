{ pkgs, lib, config, sys, ... }:

let
  npmPrefix = "$HOME/.npm-global";
  npmRegistry = config.home.sessionVariables.npm_config_registry;

  # Declarative agent plugin list.
  # tool = "node"   → npm global install (check: npm-global/lib/node_modules/<name>)
  # tool = "python" → uv tool install     (check: .local/share/uv/tools/<name>)
  agentPlugins = [
    { name = "@colbymchenry/codegraph"; version = "0.9.7"; tool = "node"; }
    { name = "headroom-ai"; tool = "python"; }
  ];

  installScript = p:
    if p.tool == "node" then
      let
        pkgSpec = if p ? version then "${p.name}@${p.version}" else p.name;
        checkPath = "$HOME/.npm-global/lib/node_modules/${p.name}";
      in ''
        if ! [ -d "${checkPath}" ]; then
          ${pkgs.nodejs_26}/bin/npm install -g ${pkgSpec}
        fi
      ''
    else if p.tool == "python" then
      let
        pkgSpec = if p ? extras then "${p.name}[${p.extras}]" else p.name;
        checkPath = "$HOME/.local/share/uv/tools/${p.name}";
      in ''
        if ! [ -d "${checkPath}" ]; then
          ${pkgs.uv}/bin/uv tool install ${pkgSpec}
        fi
      ''
    else throw "Unknown agent plugin tool: ${p.tool}";

  hasNodePlugins = lib.any (p: p.tool == "node") agentPlugins;

  npmSetup = lib.optionalString hasNodePlugins ''
    mkdir -p ${npmPrefix}/bin
    mkdir -p ${npmPrefix}/lib/node_modules
    mkdir -p $HOME/.cache/npm

    export npm_config_prefix="${npmPrefix}"
    export npm_config_cache="$HOME/.cache/npm"
    export npm_config_registry="${npmRegistry}"
  '';

  pluginScripts = lib.concatStringsSep "\n" (map installScript agentPlugins);
in
{
  home.activation.installAgentPlugins = sys.task.activation {
    name = "agent-plugins";
    script = ''
      ${npmSetup}
      ${pluginScripts}
    '';
  };
}