{ config, pkgs, lib, secrets, ... }:

let 
  isDesktop = (secrets.home.option or "desktop") == "desktop";
  isNiri = (secrets.home.option or "all") == "niri" || (secrets.home.option or "all") == "all";
in
{
  imports = [
    ./modules/cores
    ./modules/devps
    ./modules/libs
  ] ++ lib.optionals isDesktop [
    ./modules/desktops
  ];
  config = {
    home.username = secrets.home.user;
    home.homeDirectory = secrets.home.dir;
    home.stateVersion = "25.11";
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
      API_KEY = secrets.agent.apikey;
      DASHSCOPE_API_KEY = secrets.agent.apikey;

      # ANTHROPIC
      ANTHROPIC_BASE_URL = "https://dashscope.aliyuncs.com/apps/anthropic";
      ANTHROPIC_API_KEY = secrets.agent.apikey;
      ANTHROPIC_MODEL = "glm-5.1";

      # NPM
      npm_config_prefix = "$HOME/.npm-global";
      npm_config_cache = "$HOME/.cache/npm";
      npm_config_registry = "https://registry.npmmirror.com";
    };
    home.sessionPath = [
      "$npm_config_prefix/bin"
    ];
    _module.args.isDesktop = isDesktop;
    programs.home-manager.enable = true;
  };
}