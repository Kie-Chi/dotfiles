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
    ./modules/agents
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
    };
    home.sessionPath = [
      "/home/${secrets.home.user}/.local/bin"
    ];
    _module.args.isDesktop = isDesktop;
    programs.home-manager.enable = true;
  };
}