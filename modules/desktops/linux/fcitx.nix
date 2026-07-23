{ config
, pkgs
, lib
, ...
}:

let
  isDesktop = config.envy.linux.option == "desktop";
in
{
  config = lib.mkIf isDesktop {
  home.sessionVariables = {
    GTK_IM_MODULE = "fcitx";
    QT_IM_MODULE = "fcitx";
    XMODIFIERS = "@im=fcitx";
    SDL_IM_MODULE = "fcitx";
    GLFW_IM_MODULE = "ibus";
  };

  i18n.inputMethod = {
    enable = true;
    type = "fcitx5";

    fcitx5 = {
      # waylandFrontend = true;
      addons = with pkgs; [
        kdePackages.fcitx5-configtool
        fcitx5-gtk
        kdePackages.fcitx5-qt
        (fcitx5-rime.override { rimeDataPkgs = [ pkgs.rime-ice ]; })
      ];

      settings = {
        globalOptions = {
          "HotKey/TriggerKeys"."0" = "Ctrl+space";
        };
        inputMethod = {
          "Groups/0" = {
            Name = "Default";
            "Default Layout" = "us";
            DefaultIM = "keyboard-us";
          };
          "Groups/0/Items/0".Name = "keyboard-us";
          "Groups/0/Items/1".Name = "rime";
          GroupOrder."0" = "Default";
        };
      };
    };
  };

  #home.activation.kwinFcitx5 = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
  #  run ${pkgs.kdePackages.kconfig}/bin/kwriteconfig6 --file kwinrc --group Wayland --key InputMethod "/etc/profiles/per-user/${config.home.username}/share/applications/fcitx5-wayland-launcher.desktop"
  #  run ${pkgs.kdePackages.kconfig}/bin/kwriteconfig6 --file kwinrc --group Wayland --key VirtualKeyboardEnabled true
  #'';
  };
}
