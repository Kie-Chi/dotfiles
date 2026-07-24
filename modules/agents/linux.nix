{ config, lib, pkgs, ... }:

let
  isDesktop = config.envy.linux.option == "desktop";
  rtk = pkgs.callPackage ./linux/rtk.nix { };
in
{
  envy.software.nix.packages.include = [
    pkgs.codex
    rtk
  ] ++ lib.optional isDesktop pkgs.code-cursor;

}
