{ config, pkgs, lib, sys, ... }:

{
  imports = [
    ./modules/envy/home.nix
    ./modules/agents
    ./modules/cores
    ./modules/devps
    ./modules/desktops
    ./modules/libs
  ];
  config = {
    home.username = config.envy.user.name;
    home.homeDirectory = lib.mkForce config.envy.user.home;
    home.stateVersion = "25.11";

    # --- sops secrets declaration (nested YAML paths) ---
    sops.secrets.home-passwd = {
      sopsFile = ./secrets/secrets.yaml;
      key = "home/passwd";
    };
    sops.secrets.proxy-url = {
      sopsFile = ./secrets/secrets.yaml;
      key = "proxy/url";
    };
    sops.secrets.llm-steps-apikey = {
      sopsFile = ./secrets/secrets.yaml;
      key = "llm/steps/apikey";
    };
    sops.secrets.llm-deepseek-apikey = {
      sopsFile = ./secrets/secrets.yaml;
      key = "llm/deepseek/apikey";
    };

    # --- sops templates for env vars ---
    sops.templates."env-secrets" = {
      content = ''
        export STEPFUN_BASE_URL=${lib.escapeShellArg config.envy.llm.steps.url}
        export API_KEY=${lib.escapeShellArg config.sops.placeholder.llm-steps-apikey}
        export STEPFUN_API_KEY=${lib.escapeShellArg config.sops.placeholder.llm-steps-apikey}
        export ANTHROPIC_BASE_URL=${lib.escapeShellArg config.envy.llm.steps.url}
        export ANTHROPIC_API_KEY=${lib.escapeShellArg config.sops.placeholder.llm-steps-apikey}
        export ANTHROPIC_AUTH_TOKEN=${lib.escapeShellArg config.sops.placeholder.llm-steps-apikey}
        export ANTHROPIC_MODEL=${lib.escapeShellArg config.envy.llm.steps.model}
      '';
    };

    # --- debug: show sops secret paths at activation ---
    home.activation.debugSopsPaths = sys.task.activation {
      name = "debugSopsPaths";
      script = ''
        log_debug "sops secret paths:"
        log_debug "  home-passwd: ${config.sops.secrets.home-passwd.path}"
        log_debug "  proxy-url: ${config.sops.secrets.proxy-url.path}"
        log_debug "  llm-steps-apikey: ${config.sops.secrets.llm-steps-apikey.path}"
        log_debug "  llm-deepseek-apikey: ${config.sops.secrets.llm-deepseek-apikey.path}"
        log_debug "  env-secrets template: ${config.sops.templates."env-secrets".path}"
        for p in ${config.sops.secrets.home-passwd.path} ${config.sops.secrets.proxy-url.path} ${config.sops.secrets.llm-steps-apikey.path} ${config.sops.secrets.llm-deepseek-apikey.path}; do
          if [ -f "$p" ]; then
            log_debug "  $p EXISTS"
          else
            log_warn "  $p MISSING!"
          fi
        done
      '';
    };

    # --- source sops env template in shell ---
    programs.zsh.initContent = lib.mkAfter ''
      if [ -f "${config.sops.templates."env-secrets".path}" ]; then
        source "${config.sops.templates."env-secrets".path}"
      else
        echo "[WARN] sops env-secrets template not found at ${config.sops.templates."env-secrets".path}"
      fi
    '';

    programs.home-manager.enable = true;
  };
}
