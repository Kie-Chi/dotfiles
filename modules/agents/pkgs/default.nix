{ pkgs, ... }:
{
  home.packages = [
    (pkgs.callPackage ./rtk.nix {})
  ];
}