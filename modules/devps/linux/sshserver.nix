{ lib, pkgs, sys, ... }:

let
  sshdConfig = {
    PasswordAuthentication = "yes";
    PubkeyAuthentication = "yes";
  };

in
{
  home.activation.setupSshd = sys.task.activation {
    after = [ "userBoundary" ];
    asRoot = true;
    name = "setupSshd";
    script = ''
      ${sys.deploy {
        name = "sshd_config";
        format = "kv";
        data = sshdConfig;
        target = "/etc/ssh/sshd_config.d/99-dotfiles.conf";
        mode = "0644";
      }}

      esudo ${sys.cmds.systemctl} enable --now ssh
      esudo ${sys.cmds.systemctl} restart ssh
      log_info "sshd setup complete."
    '';
  };
}
