{ config, pkgs, lib, ... }:

{
  programs.ssh = {
    enable = true;
    enableDefaultConfig = false;
    settings = {
        "*" = {
            Compression = true;
        };
    
        "github.com" = {
            HostName = "ssh.github.com";
            Port = 443;
            User = "git";
        };

        "bitaction" = {
            HostName = "115.190.182.138";
            Port = 22;
            User = "root";
            IdentityFile = "${config.home.homeDirectory}/.ssh/bitaction.pem";
        };
        "dell-1" = {
            HostName = "202.112.47.189";
            Port = 22;
            User = "xiongxk";
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
