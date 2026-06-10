{ lib, cfg, ... }:
let
  desktop = cfg.home.desktop or "all";
in
{
  imports = [
    ./base.nix
    ./fcitx.nix
    ./rime.nix
    ./font.nix
    ./sunshine.nix
  ]
  ++ lib.optionals (desktop == "gnome" || desktop == "all") [
    ./gnome.nix
    ./terminal.nix
  ]
  ++ lib.optionals (desktop == "niri" || desktop == "all") [
    ./niri.nix
    ./niris
  ];
}