{ pkgs, config, lib, secrets, sys, ... }:

{
  home.packages = with pkgs; [
    # lib dev

    # env management
    mamba-cpp

    # virtualenv


    # build or pkg manager
    go
    uv
    maven
    javaPackages.compiler.openjdk21
    nodejs_26
  ];

  programs.zsh = {
    initContent = ''
      # Mamba Initialization
      # This check prevents errors if mamba isn't in the PATH for some reason
      if command -v mamba &> /dev/null; then
        eval "$(mamba shell hook --shell zsh)"
      fi
    '';
  };

  home.file.".condarc".text = ''
    envs_dirs:
      - ~/.mamba/envs
    pkgs_dirs:
      - ~/.mamba/pkgs
    channels:
      - conda-forge
      - defaults
  '';

  home.activation.installNativeDocker = sys.task.root {
    guardDryRun = false;
    pre = ''
      esudo rm -rf $HOME/.config/dotfiles/docker.modified
    '';
    script = ''
      if [ ! -e $HOME/.config/dotfiles/docker.installed ]; then
        echo "No Docker found, installing..."
        echo "Password is $SUDO_PWD"
        $DRY_RUN_CMD ${pkgs.curl}/bin/curl -fsSL https://get.docker.com -o /tmp/get-docker.sh
        $DRY_RUN_CMD esudo ${sys.cmds.sh} /tmp/get-docker.sh --mirror Aliyun
        $DRY_RUN_CMD esudo ${sys.cmds.usermod} -aG docker ${secrets.home.user}
        if [ -z "$DRY_RUN_CMD" ]; then
          if id -nG "${secrets.home.user}" | ${sys.cmds.grep} -qw "docker"; then
              echo "To use Docker without sudo in this terminal, you must run: 'newgrp docker'"
          fi
        else
          echo "Docker installation and user modification dry-run completed."
        fi
        echo "Docker installed successfully!"
        $DRY_RUN_CMD ${sys.cmds.touch} $HOME/.config/dotfiles/docker.installed
        $DRY_RUN_CMD ${sys.cmds.touch} $HOME/.config/dotfiles/docker.modified
      else
        if [ -z "$DRY_RUN_CMD" ]; then
          if id -nG "${secrets.home.user}" | ${sys.cmds.grep} -qw "docker"; then
            echo "Docker All right."
          else
            esudo ${sys.cmds.usermod} -aG docker ${secrets.home.user}
            esudo ${sys.cmds.touch} $HOME/.config/dotfiles/docker.modified
          fi
        else
          echo "Docker installation and user modification dry-run completed."
        fi
        echo "Docker found, skipping installation."
      fi
    '';
    post = ''
      if [ -e $HOME/.config/dotfiles/docker.modified ]; then
        echo "Docker configuration modified."
        esudo ${sys.cmds.systemctl} restart docker
      fi
    '';
  };

}