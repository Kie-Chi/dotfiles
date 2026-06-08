{ config, pkgs, cfg, lib, ... }:

{

  home.file.".config/wallpapers/background.jpg".source = ../../resources/images/background.jpg;

  home.activation.linkWallPaper = lib.hm.dag.entryAfter ["writeBoundary"] ''
    echo "Setting desktop wallpaper with desktoppr..."
    ${pkgs.desktoppr}/bin/desktoppr "${config.home.homeDirectory}/.config/wallpapers/background.jpg"
  '';
}