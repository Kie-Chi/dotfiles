###################################
#
#
#   BASE PACKAGES FOR MYSYSTEM
#
#
###################################

{ pkgs, config, cfg, lib, sys, ... }:

let
  nixCustomConfig = {
    trusted-users = "root ${cfg.home.user}";
  };
in
{
    home.packages = with pkgs; [
    # base
    git
    git-lfs
    tmux
    git-filter-repo

    # crypt
    git-crypt
    gnupg
    sops
    age

    # network
    curl
    wget
    wireshark
    rclone

    # system
    btop
    htop
    ncdu

    # tools
    unzip
    jq
    javaPackages.compiler.openjdk21

    # opt
    ripgrep
    bat
    tree
    neovim-remote
  ];

  home.file.".config/nixpkgs/config.nix".text = ''
    {
      allowUnfree = true;
    }
  '';

  home.file.".config/nix/nix.conf".text = ''
    substituters = https://mirrors.ustc.edu.cn/nix-channels/store https://cache.nixos.org/
  '';

  home.activation.setupNixConfig = sys.config.activation {
    name = "nix.custom.conf";
    format = "kvEq";
    data = nixCustomConfig;
    target = "/etc/nix/nix.custom.conf";
    mode = "0644";
    post = ''
      esudo ${sys.cmds.systemctl} restart nix-daemon
    '';
  };
}