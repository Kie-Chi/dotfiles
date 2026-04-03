###################################
#
#
#   BASE PACKAGES FOR MYSYSTEM
#
#
###################################

{ pkgs, config, secrets, lib, sys, ... }:

let
  nixCustomConfig = {
    trusted-users = "root ${secrets.home.user}";
  };
in
{
    home.packages = with pkgs; [
    # base
    git 
    tmux
    systemd

    # crypt
    git-crypt
    gnupg

    # network
    curl 
    wget 

    # system
    btop 
    htop
    
    # tools
    unzip 
    jq 

    # opt 
    fzf 
    ripgrep 
    bat
    tree
    chsrc

    # ai
    claude-code
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