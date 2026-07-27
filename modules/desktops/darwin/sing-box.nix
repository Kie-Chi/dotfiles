{ pkgs, ... }:

{
  envy.software.nix.packages.include = [ pkgs.sing-box ];
  envy.software.nix.packages.references."sing-box" = "nix:sing-box";
}
