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

  home.activation.setupNixConfig = lib.hm.dag.entryAfter ["userBoundary"] ''
    _LOG_CTX="setupNixConfig"
    if [ ! -f "${config.sops.secrets.home-passwd.path}" ]; then
      log_error "sops password file not found at ${config.sops.secrets.home-passwd.path}"
      exit 1
    fi
    SUDO_PWD=$(cat "${config.sops.secrets.home-passwd.path}")
    if [ -z "$SUDO_PWD" ]; then
      log_error "Failed to read password from ${config.sops.secrets.home-passwd.path}"
      exit 1
    fi
    CONTENT="trusted-users = root ${config.envy.user.name}"

    HOST_SUDO="/usr/bin/sudo"
    HOST_SH="/bin/sh"
    if [ -z $DRY_RUN_CMD ]; then
      if ${pkgs.gnugrep}/bin/grep -qF "$CONTENT" /etc/nix/nix.custom.conf; then
        log_debug "trusted-users already in /etc/nix/nix.custom.conf"
      else
        echo "$SUDO_PWD" | $HOST_SUDO -S $HOST_SH -c "echo '$CONTENT' >> /etc/nix/nix.custom.conf"
        log_info "Added trusted-users to /etc/nix/nix.custom.conf"
      fi
    fi
  '';
}
