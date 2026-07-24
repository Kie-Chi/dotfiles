{ lib, ... }:

let
  inherit (lib) mkOption types;
  inherit (import ../selection-options.nix { inherit lib; }) packageSelection stringSelection;
in
{
  options.envy.darwin = {
    proxy = {
      mode = mkOption {
        type = types.enum [ "none" "manual" "keep" ];
        default = "none";
        description = "Darwin proxy service policy.";
      };
      tun = mkOption {
        type = types.bool;
        default = false;
        description = "Whether Darwin uses proxy TUN mode.";
      };
    };

    software = {
      nix = {
        systemPackages = packageSelection "Darwin system packages";
        fonts = packageSelection "Darwin font packages";
      };
      homebrew = {
        formulae = stringSelection "Darwin Homebrew formulae";
        casks = stringSelection "Darwin Homebrew casks";
        repositories = stringSelection "Darwin Homebrew repositories";
      };
    };
  };
}
