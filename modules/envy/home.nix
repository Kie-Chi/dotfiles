{ config, lib, machinePlatform, ... }:

let
  selection = config.envy.packages.home;
  homePackages = lib.filter
    (package: !(builtins.elem (lib.getName package) selection.exclude))
    (lib.unique selection.include);
in
{
  imports =
    [ ./options.nix ]
    ++ lib.optionals (machinePlatform == "darwin") [ ./darwin/options.nix ]
    ++ lib.optionals (machinePlatform == "linux") [ ./linux.nix ];

  config = {
    envy.packages.home.effective = homePackages;
    home.packages = homePackages;
  };
}
