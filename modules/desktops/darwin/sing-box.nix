{ pkgs, ... }:

{
  envy.software.nix.packages.include = [ pkgs.sing-box ];
}
