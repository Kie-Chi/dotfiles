###################################
#
#
#   BASE PACKAGES FOR MYSYSTEM
#
#
###################################

{ pkgs, config, ... }: 

{
    home.packages = with pkgs; [
    # base
    git 
    tmux

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
    ncdu
  ];
}
