{ config, pkgs, lib, ... }:

{
  programs.ssh = {
    enable = true;
    enableDefaultConfig = false;
    matchBlocks = {
        "*" = {
            compression = true;
        };
    
        "github.com" = {
            hostname = "ssh.github.com";
            port = 443;
            user = "git";
        };

        "nas" = {
            hostname = "nas.fl0wer.cn";
            port = 2222;
            user = "gitea";
            identityfile = "~/.ssh/id_ed25519"
        };

        "dell-1" = {
            hostname = "202.112.47.189";
            port = 22;
            user = "xiongxk";
        };
    };
  };

  home.activation.generateSSHKey = lib.hm.dag.entryAfter ["writeBoundary"] ''
    ssh_key="$HOME/.ssh/id_ed25519"
    email="${config.programs.git.settings.user.email}"
    
    if [ ! -f "$ssh_key" ]; then
      echo "Generating SSH Key for $email..."
      $DRY_RUN_CMD mkdir -p "$HOME/.ssh"
      $DRY_RUN_CMD chmod 700 "$HOME/.ssh"
      $DRY_RUN_CMD ${pkgs.openssh}/bin/ssh-keygen -t ed25519 -C "$email" -f "$ssh_key" -N ""
      
      echo "SSH Key generated at $ssh_key"
    fi
  '';
}