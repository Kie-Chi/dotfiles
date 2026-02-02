{ config, pkgs, secrets, lib, ... }:

{
  imports = [
    ./modules/cores
    ./modules/devps
  ];
  config = {
    home.username = secrets.home.user;
    home.homeDirectory = lib.mkForce "${secrets.home.dir}";
    home.stateVersion = "25.11";
    programs.home-manager.enable = true;
  };
}
