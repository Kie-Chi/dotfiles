{ config, lib, machinePlatform, ... }:

let
  selection = config.envy.software.nix.packages;
  selectItems = itemSelection: lib.filter
    (item: !(builtins.elem item.id itemSelection.exclude))
    (lib.unique itemSelection.include);
  homePackages = lib.filter
    (package: !(builtins.elem (lib.getName package) selection.exclude))
    (lib.unique selection.include);
  compatiblePackages = packages:
    lib.all
      (values: builtins.length (lib.unique values) == 1)
      (builtins.attrValues (lib.groupBy lib.getName packages));
  compatibleItems = items:
    lib.all
      (values: builtins.length (lib.unique values) == 1)
      (builtins.attrValues (lib.groupBy (item: item.id) items));
in
{
  imports =
    [ ./options.nix ]
    ++ lib.optionals (machinePlatform == "darwin") [ ./darwin/options.nix ]
    ++ lib.optionals (machinePlatform == "linux") [ ./linux.nix ];

  config = {
    assertions = [
      {
        assertion = compatiblePackages selection.include;
        message = "envy.software.nix.packages contains the same stable ID with different derivations";
      }
      {
        assertion = compatibleItems config.envy.software.npm.tools.include;
        message = "envy.software.npm.tools contains the same stable ID with conflicting metadata";
      }
      {
        assertion = compatibleItems config.envy.software.pypi.tools.include;
        message = "envy.software.pypi.tools contains the same stable ID with conflicting metadata";
      }
    ];
    envy.software.nix.packages.effective = homePackages;
    envy.software.npm.tools.effective = selectItems config.envy.software.npm.tools;
    envy.software.pypi.tools.effective = selectItems config.envy.software.pypi.tools;
    home.packages = homePackages;
  };
}
