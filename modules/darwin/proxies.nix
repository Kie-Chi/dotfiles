{ config, pkgs, secrets, lib, ... }:

let
  user = secrets.home.user;
  mihomoBin = "/opt/homebrew/bin/mihomo";
  configDir = "/Users/${secrets.home.user}/.config/mihomo";
  proxyStatus = secrets.proxy.status or "manual";
in
{
  homebrew.brews = lib.optionals (proxyStatus != "none") [ "mihomo" ];

  launchd.daemons.mihomo = lib.mkIf (proxyStatus != "none") {
    script = ''
      mkdir -p ${configDir}
      chown -R ${user}:staff ${configDir}
      exec ${mihomoBin} -d ${configDir}
    '';

    serviceConfig = {
      KeepAlive = (proxyStatus == "keep");
      RunAtLoad = (proxyStatus == "keep");
      StandardOutPath = "/Library/Logs/mihomo.log";
      StandardErrorPath = "/Library/Logs/mihomo.err.log";
      ProcessType = "Background";
    };
  };
}