{ lib, ... }:

let
  inherit (lib) mkOption types;
in
{
  options.envy.linux = {
    desktop = mkOption {
      type = types.enum [ "gnome" "niri" "all" "none" ];
      default = "gnome";
      description = "Linux desktop environment selection.";
    };
    option = mkOption {
      type = types.enum [ "desktop" "server" ];
      default = "desktop";
      description = "Whether the Linux machine is a desktop or server.";
    };
  };
}
