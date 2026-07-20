{ config, lib, pkgs, ... }:

let
  cfg = config.agents.claude;

  claudeWithDefaults = pkgs.writeShellApplication {
    name = "claude";
    text = ''
      system_prompt="''${CCLI_SYSTEM_PROMPT:-}"
      prompt_file="$HOME/${cfg.systemPromptFile}"

      if [[ -z "$system_prompt" && -f "$prompt_file" ]]; then
        system_prompt=$(<"$prompt_file")
      fi

      # Call nixpkgs' wrapper by absolute path. It prepares Claude Code's
      # runtime before handing off to its internal .claude-wrapped binary.
      cmd=("${lib.getExe cfg.package}")
      ${lib.concatMapStringsSep "\n" (arg: "cmd+=(${lib.escapeShellArg arg})") cfg.extraArgs}

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
    enable = lib.mkEnableOption "the managed Claude Code command";

    package = lib.mkPackageOption pkgs "claude-code" { };

    wrap = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Wrap claude with the configured prompt and extra arguments.";
    };

    systemPromptFile = lib.mkOption {
      type = lib.types.str;
      default = ".config/ccli/prompt";
      description = "System prompt path relative to the user's home directory.";
    };

    extraArgs = lib.mkOption {
      type = with lib.types; listOf str;
      default = [ "--dangerously-skip-permissions" ];
      description = "Arguments injected before caller-provided Claude arguments.";
    };

    ccliAlias = lib.mkOption {
      type = lib.types.bool;
      default = true;
      description = "Keep ccli as a compatibility command that delegates to claude.";
    };
  };

  config = lib.mkIf cfg.enable {
    home.packages = [
      (if cfg.wrap then claudeWithDefaults else cfg.package)
    ] ++ lib.optional cfg.ccliAlias ccli;

    home.file.${cfg.systemPromptFile}.source = ../../files/ccli/prompt;
  };
}
