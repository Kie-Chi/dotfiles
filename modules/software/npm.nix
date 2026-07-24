{ config, lib, pkgs, sys, ... }:

let
  tools = config.envy.software.npm.tools.effective;
  npmPrefix = "$HOME/.npm-global";
  installTool = tool:
    let
      packageSpec = if tool.version == null then tool.name else "${tool.name}@${tool.version}";
      checkPath = "$HOME/.npm-global/lib/node_modules/${tool.name}";
    in ''
      if ! [ -d "${checkPath}" ]; then
        ${pkgs.nodejs_26}/bin/npm install -g ${lib.escapeShellArg packageSpec}
      fi
    '';
in
{
  config = lib.mkIf (tools != [ ]) {
    home.sessionVariables = {
      npm_config_prefix = npmPrefix;
      npm_config_cache = "$HOME/.cache/npm";
    };
    home.sessionPath = [ "${npmPrefix}/bin" ];

    home.activation.installNpmTools = sys.task.activation {
      name = "npm-tools";
      script = ''
        mkdir -p ${npmPrefix}/bin ${npmPrefix}/lib/node_modules "$HOME/.cache/npm"
        export npm_config_prefix=${npmPrefix}
        export npm_config_cache="$HOME/.cache/npm"
        ${lib.concatMapStringsSep "\n" installTool tools}
      '';
    };
  };
}
