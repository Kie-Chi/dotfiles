{ config, pkgs, ... }:

{
  imports = [
    ./pkg.nix
    ./net-pkg.nix
  ];
  envy.packages.home.include = with pkgs; [
    (pkgs.callPackage ./tod.nix {})
  ];
}
