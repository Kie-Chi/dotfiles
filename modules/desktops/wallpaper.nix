{ config, pkgs, cfg, lib, sys, ... }:

{

  home.file.".config/wallpapers/background.jpg".source = ../../resources/images/background.jpg;

  home.activation.linkWallPaper = sys.task.activation {
    name = "linkWallPaper";
    script = ''
      echo "Setting desktop wallpaper with desktoppr..."
      ${pkgs.desktoppr}/bin/desktoppr "${config.home.homeDirectory}/.config/wallpapers/background.jpg"
    '';
  };
}