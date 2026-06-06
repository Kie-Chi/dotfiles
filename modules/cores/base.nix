###################################
#
#
#   BASE PACKAGES FOR MYSYSTEM
#
#
###################################

{ pkgs, config, secrets, lib, ... }:

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
  ];

  home.file.".config/nixpkgs/config.nix".text = ''
    {
      allowUnfree = true;
    }
  '';

  home.activation.setupNixConfig = lib.hm.dag.entryAfter ["writeBoundary"] ''
    SECRET_FILE="$HOME/.config/dotfiles/secrets.nix"
    if [ ! -f "$SECRET_FILE" ]; then
      echo "No password file found at $SECRET_FILE."
      exit 0
    fi
    SUDO_PWD=$(${pkgs.gnugrep}/bin/grep -w "home\.passwd" "$SECRET_FILE" | sed -n "s/.*home\.passwd[[:space:]]*=[[:space:]]*\"\([^\"]*\)\".*/\1/p" | head -n 1)
    if [ -z "$SUDO_PWD" ]; then
      echo "Failed to extract password from $SECRET_FILE."
      exit 1
    fi
    CONTENT="trusted-users = root ${secrets.home.user}"

    HOST_SUDO="/usr/bin/sudo"
    HOST_SYSTEMCTL="/usr/bin/systemctl"
    HOST_SH="/bin/sh"
    if [ -z $DRY_RUN_CMD ]; then
      if ${pkgs.gnugrep}/bin/grep -qF "$CONTENT" /etc/nix/nix.custom.conf; then
        echo "Content already exists in /etc/nix/nix.custom.conf"
      else
        echo "$SUDO_PWD" | $HOST_SUDO -S $HOST_SH -c "echo '$CONTENT' >> /etc/nix/nix.custom.conf"
      fi
    fi
  '';
}