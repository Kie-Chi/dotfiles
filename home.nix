{ config, pkgs, cfg, lib, ... }:

{
  imports = [
    ./modules/cores
    ./modules/devps
    ./modules/desktops
  ];
  config = {
    home.username = cfg.home.user;
    home.homeDirectory = lib.mkForce "${cfg.home.dir}";
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
    sops.secrets.llm-dashscope-apikey = {
      sopsFile = ./secrets/secrets.yaml;
      key = "llm/dashscope/apikey";
    };
    sops.secrets.llm-deepseek-apikey = {
      sopsFile = ./secrets/secrets.yaml;
      key = "llm/deepseek/apikey";
    };

    # --- sops templates for env vars ---
    sops.templates."env-secrets" = {
      content = ''
        API_KEY=${config.sops.placeholder.llm-dashscope-apikey}
        DASHSCOPE_API_KEY=${config.sops.placeholder.llm-dashscope-apikey}
        ANTHROPIC_API_KEY=${config.sops.placeholder.llm-dashscope-apikey}
      '';
    };

    # --- debug: show sops secret paths at activation ---
    home.activation.debugSopsPaths = lib.hm.dag.entryAfter ["writeBoundary"] ''
      echo "[DEBUG] sops secret paths:"
      echo "[DEBUG]   home-passwd: ${config.sops.secrets.home-passwd.path}"
      echo "[DEBUG]   proxy-url: ${config.sops.secrets.proxy-url.path}"
      echo "[DEBUG]   llm-dashscope-apikey: ${config.sops.secrets.llm-dashscope-apikey.path}"
      echo "[DEBUG]   llm-deepseek-apikey: ${config.sops.secrets.llm-deepseek-apikey.path}"
      echo "[DEBUG]   env-secrets template: ${config.sops.templates."env-secrets".path}"
      for p in ${config.sops.secrets.home-passwd.path} ${config.sops.secrets.proxy-url.path} ${config.sops.secrets.llm-dashscope-apikey.path} ${config.sops.secrets.llm-deepseek-apikey.path}; do
        if [ -f "$p" ]; then
          echo "[DEBUG]   $p EXISTS"
        else
          echo "[DEBUG]   $p MISSING!"
        fi
      done
    '';

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