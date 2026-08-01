###################################
#
#
#   BASE PACKAGES FOR MYSYSTEM
#
#
###################################

{ pkgs, config, lib, machinePlatform, ... }:

{
  envy.software.nix.packages.include = with pkgs; [
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
  ] ++ lib.optionals (machinePlatform == "linux") [ rclone ];

  envy.software.nix.packages.references = {
    git = "nix:git";
    "git-lfs" = "nix:git-lfs";
    tmux = "nix:tmux";
    "git-filter-repo" = "nix:git-filter-repo";
    "git-crypt" = "nix:git-crypt";
    gnupg = "nix:gnupg";
    sops = "nix:sops";
    age = "nix:age";
    curl = "nix:curl";
    wget = "nix:wget";
    "wireshark-qt" = "nix:wireshark";
    btop = "nix:btop";
    htop = "nix:htop";
    ncdu = "nix:ncdu";
    unzip = "nix:unzip";
    jq = "nix:jq";
    ripgrep = "nix:ripgrep";
    bat = "nix:bat";
    tree = "nix:tree";
    "neovim-remote" = "nix:neovim-remote";
  } // lib.optionalAttrs (machinePlatform == "darwin") {
    "zulu-ca-jdk" = "nix:javaPackages.compiler.openjdk21";
  } // lib.optionalAttrs (machinePlatform == "linux") {
    openjdk = "nix:javaPackages.compiler.openjdk21";
    rclone = "nix:rclone";
  };

  home.file.".config/nixpkgs/config.nix".text = ''
    {
      allowUnfree = true;
    }
  '';

  home.sessionPath = [
    "${config.envy.user.home}/.local/bin"
  ];
}
