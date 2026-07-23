{ config, lib, pkgs, ... }:

let
  agentConfig = config.agents.claude;
  packageEnabled = !(builtins.elem "claude" config.envy.packages.home.exclude);
  promptFile = ".config/ccli/prompt";

  claudeWithDefaults = pkgs.writeShellApplication {
    name = "claude";
    text = ''
      system_prompt="''${CCLI_SYSTEM_PROMPT:-}"
      prompt_file="$HOME/${promptFile}"

      if [[ -z "$system_prompt" && -f "$prompt_file" ]]; then
        system_prompt=$(<"$prompt_file")
      fi

      # Call nixpkgs' wrapper by absolute path. It prepares Claude Code's
      # runtime before handing off to its internal .claude-wrapped binary.
      cmd=("${lib.getExe agentConfig.package}")
      ${lib.concatMapStringsSep "\n" (arg: "cmd+=(${lib.escapeShellArg arg})") agentConfig.extraArgs}

      if [[ -n "$system_prompt" ]]; then
        cmd+=(--system-prompt "$system_prompt")
      fi

      exec "''${cmd[@]}" "$@"
    '';
  };

  ccli = pkgs.writeShellScriptBin "ccli" ''
    exec claude "$@"
  '';
in
{
  options.agents.claude = {
    package = lib.mkPackageOption pkgs "claude-code" { };

    extraArgs = lib.mkOption {
      type = with lib.types; listOf str;
      default = [ ];
      description = "Arguments injected before caller-provided Claude arguments.";
    };

    ccliAlias = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Keep ccli as a compatibility command that delegates to claude.";
    };
  };

  config = lib.mkIf packageEnabled {
    envy.packages.home.include = [
      claudeWithDefaults
    ] ++ lib.optional agentConfig.ccliAlias ccli;

    home.file.${promptFile}.source = ../../files/ccli/prompt;
  };
}
