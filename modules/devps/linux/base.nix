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
      envy_state_dir="$HOME/.config/envy"
      legacy_state_dir="$HOME/.config/dotfiles"
      if [ -e "$legacy_state_dir/docker.installed" ] && [ ! -e "$envy_state_dir/docker.installed" ]; then
        $DRY_RUN_CMD ${sys.cmds.mkdir} -p "$envy_state_dir"
        $DRY_RUN_CMD ${sys.cmds.cp} -p "$legacy_state_dir/docker.installed" "$envy_state_dir/docker.installed"
        if [ -e "$legacy_state_dir/docker.modified" ]; then
          $DRY_RUN_CMD ${sys.cmds.cp} -p "$legacy_state_dir/docker.modified" "$envy_state_dir/docker.modified"
        fi
        $DRY_RUN_CMD ${sys.cmds.rm} -f "$legacy_state_dir/docker.installed" "$legacy_state_dir/docker.modified"
      fi

      if [ ! -e "$envy_state_dir/docker.installed" ] && [ ! -e "$legacy_state_dir/docker.installed" ]; then
        log_info "No Docker found, installing..."
        $DRY_RUN_CMD ${sys.cmds.mkdir} -p "$envy_state_dir"
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
        $DRY_RUN_CMD ${sys.cmds.touch} "$envy_state_dir/docker.installed"
        $DRY_RUN_CMD ${sys.cmds.touch} "$envy_state_dir/docker.modified"
      else
        if [ -z "$DRY_RUN_CMD" ]; then
          if id -nG "${config.envy.user.name}" | ${sys.cmds.grep} -qw "docker"; then
            log_info "Docker All right."
          else
            esudo ${sys.cmds.usermod} -aG docker ${config.envy.user.name}
            esudo ${sys.cmds.mkdir} -p "$envy_state_dir"
            esudo ${sys.cmds.touch} "$envy_state_dir/docker.modified"
          fi
        else
          log_info "Docker installation and user modification dry-run completed."
        fi
        log_info "Docker found, skipping installation."
      fi
    '';
    post = ''
      if [ -e "$HOME/.config/envy/docker.modified" ]; then
        log_info "Docker configuration modified."
        esudo ${sys.cmds.systemctl} restart docker
      fi
    '';
  };

}
