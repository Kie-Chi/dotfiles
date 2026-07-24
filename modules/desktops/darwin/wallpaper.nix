{ config, pkgs, lib, sys, ... }:

{
  envy.software.nix.packages.include =
    [ pkgs.desktoppr ];

  home.file.".config/wallpapers/background.jpg" =
    lib.mkIf (builtins.elem "desktoppr" (map lib.getName config.envy.software.nix.packages.effective)) {
      source = ../../../resources/images/background.jpg;
    };

  home.activation.linkWallPaper = lib.mkIf (
    builtins.elem "desktoppr" (map lib.getName config.envy.software.nix.packages.effective)
  ) (sys.task.activation {
    name = "linkWallPaper";
    script = ''
      echo "Setting desktop wallpaper with desktoppr..."
      ${pkgs.desktoppr}/bin/desktoppr "${config.home.homeDirectory}/.config/wallpapers/background.jpg"
    '';
  });
}
