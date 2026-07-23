{ pkgs, ... }:

{
  envy.packages.home.include = [ pkgs.sing-box ];
}
