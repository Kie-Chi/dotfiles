{ config, pkgs, cfg, lib, ... }:

let
  user = cfg.home.user;
  mihomoBin = "/opt/homebrew/bin/mihomo";
  configDir = "/Users/${cfg.home.user}/.config/mihomo";
  proxyStatus = cfg.proxy.status or "manual";
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