{ config, pkgs, cfg, lib, sys, ... }:

let
  isDesktop = (cfg.home.option or "desktop") == "desktop";
in
{
  imports = [
    ./modules/cores
    ./modules/devps
    ./modules/libs
    ./modules/agents
  ] ++ lib.optionals isDesktop [
    ./modules/desktops
  ];
  config = {
    home.username = cfg.home.user;
    home.homeDirectory = cfg.home.dir;
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
    home.activation.debugSopsPaths = sys.task.activation {
      name = "debugSopsPaths";
      script = ''
        log_debug "sops secret paths:"
        log_debug "  home-passwd: ${config.sops.secrets.home-passwd.path}"
        log_debug "  proxy-url: ${config.sops.secrets.proxy-url.path}"
        log_debug "  llm-dashscope-apikey: ${config.sops.secrets.llm-dashscope-apikey.path}"
        log_debug "  llm-deepseek-apikey: ${config.sops.secrets.llm-deepseek-apikey.path}"
        log_debug "  env-secrets template: ${config.sops.templates."env-secrets".path}"
        for p in ${config.sops.secrets.home-passwd.path} ${config.sops.secrets.proxy-url.path} ${config.sops.secrets.llm-dashscope-apikey.path} ${config.sops.secrets.llm-deepseek-apikey.path}; do
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

    home.pointerCursor = lib.mkIf isDesktop {
      name = "Yaru";
      package = pkgs.yaru-theme;
      size = 24;
      x11.enable = true;
      gtk.enable = true;
    };

    home.sessionVariables = {
      GTK_IM_MODULE = "fcitx";
      QT_IM_MODULE = "fcitx";
      XMODIFIERS = "@im=fcitx";
      SDL_IM_MODULE = "fcitx";
      GLFW_IM_MODULE = "ibus";
      XDG_DATA_DIRS = "$GSETTINGS_SCHEMAS_PATH:$XDG_DATA_DIRS";
    };

    home.sessionPath = [
      "/home/${cfg.home.user}/.local/bin"
    ];

    programs.home-manager.enable = true;
  };
}