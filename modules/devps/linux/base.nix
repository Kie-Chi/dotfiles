{ pkgs, config, lib, sys, ... }:

let
  mirrorProfile = (import ../../mirrors/catalog.nix).${config.envy.mirrors.mode};
  dockerMirrorArg = lib.optionalString
    (mirrorProfile.dockerInstallerMirror != null)
    "--mirror ${mirrorProfile.dockerInstallerMirror}";
in
{
  envy.software.nix.packages.include = with pkgs; [
    # env management
    mamba-cpp

    # build or pkg manager
    go
    uv
    maven
    javaPackages.compiler.openjdk21
    nodejs_26
  ];

  envy.software.nix.packages.references = {
    "mamba-cpp" = "nix:mamba-cpp";
    go = "nix:go";
    uv = "nix:uv";
    maven = "nix:maven";
    nodejs = "nix:nodejs_26";
  };

  programs.zsh = {
    initContent = ''
      # Mamba Initialization
      # This check prevents errors if mamba isn't in the PATH for some reason
      if command -v mamba &> /dev/null; then
        eval "$(mamba shell hook --shell zsh)"
      fi
    '';
  };

  home.activation.installNativeDocker = sys.task.root {
    name = "installNativeDocker";
    after = [ "configureAptMirror" ];
    script = ''
      if [ ! -e $HOME/.config/dotfiles/docker.installed ]; then
        log_info "No Docker found, installing..."
        $DRY_RUN_CMD ${pkgs.curl}/bin/curl -fsSL https://get.docker.com -o /tmp/get-docker.sh
        $DRY_RUN_CMD esudo ${sys.cmds.sh} /tmp/get-docker.sh ${dockerMirrorArg}
        $DRY_RUN_CMD esudo ${sys.cmds.usermod} -aG docker ${config.envy.user.name}
        if [ -z "$DRY_RUN_CMD" ]; then
          if id -nG "${config.envy.user.name}" | ${sys.cmds.grep} -qw "docker"; then
              log_info "To use Docker without sudo in this terminal, you must run: 'newgrp docker'"
          fi
        else
          log_info "Docker installation and user modification dry-run completed."
        fi
        log_info "Docker installed successfully!"
        $DRY_RUN_CMD ${sys.cmds.touch} $HOME/.config/dotfiles/docker.installed
        $DRY_RUN_CMD ${sys.cmds.touch} $HOME/.config/dotfiles/docker.modified
      else
        if [ -z "$DRY_RUN_CMD" ]; then
          if id -nG "${config.envy.user.name}" | ${sys.cmds.grep} -qw "docker"; then
            log_info "Docker All right."
          else
            esudo ${sys.cmds.usermod} -aG docker ${config.envy.user.name}
            esudo ${sys.cmds.touch} $HOME/.config/dotfiles/docker.modified
          fi
        else
          log_info "Docker installation and user modification dry-run completed."
        fi
        log_info "Docker found, skipping installation."
      fi
    '';
    post = ''
      if [ -e $HOME/.config/dotfiles/docker.modified ]; then
        log_info "Docker configuration modified."
        esudo ${sys.cmds.systemctl} restart docker
      fi
    '';
  };

}
