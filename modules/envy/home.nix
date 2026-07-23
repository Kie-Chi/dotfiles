{ config, lib, ... }:

let
  excluded = config.envy.packages.home.exclude;
  homePackages = lib.filter
    (package: !(builtins.elem (lib.getName package) excluded))
    (lib.unique config.envy.packages.home.include);
in
{
  imports = [ ./options.nix ];

  config = {
    envy.packages.home.effective = homePackages;
    home.packages = homePackages;
  };
}
