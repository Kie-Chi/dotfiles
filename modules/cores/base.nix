###################################
#
#
#   BASE PACKAGES FOR MYSYSTEM
#
#
###################################

{ pkgs, config, cfg, lib, ... }:

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
    SOPS_PWD_FILE="${config.sops.secrets.home-passwd.path}"
    echo "[DEBUG] sops password file path: $SOPS_PWD_FILE"
    if [ ! -f "$SOPS_PWD_FILE" ]; then
      echo "[ERROR] sops password file not found at $SOPS_PWD_FILE"
      exit 1
    fi
    SUDO_PWD=$(cat "$SOPS_PWD_FILE")
    if [ -z "$SUDO_PWD" ]; then
      echo "[ERROR] Failed to read password from $SOPS_PWD_FILE"
      exit 1
    fi
    CONTENT="trusted-users = root ${cfg.home.user}"

    HOST_SUDO="/usr/bin/sudo"
    HOST_SYSTEMCTL="/usr/bin/systemctl"
    HOST_SH="/bin/sh"
    if [ -z $DRY_RUN_CMD ]; then
      if ${pkgs.gnugrep}/bin/grep -qF "$CONTENT" /etc/nix/nix.custom.conf; then
        echo "[DEBUG] Content already exists in /etc/nix/nix.custom.conf"
      else
        echo "$SUDO_PWD" | $HOST_SUDO -S $HOST_SH -c "echo '$CONTENT' >> /etc/nix/nix.custom.conf"
        echo "[DEBUG] Added trusted-users to /etc/nix/nix.custom.conf"
      fi
    fi
  '';
}