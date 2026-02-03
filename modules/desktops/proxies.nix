{ config, pkgs, secrets, lib, ... }:

let
  proxyStatus = secrets.proxy.status or "manual";
in
{
  xdg.configFile."mihomo/config.yaml" = lib.mkIf (proxyStatus != "none") {
    text = ''
      ${builtins.readFile ../../files/proxies/mihomo.yaml}

      proxy-providers:
        my-sub:
          type: http
          url: "${secrets.proxy.url}"
          path: ./sub.yaml
          interval: 3600
          health-check:
            enable: true
            url: http://www.gstatic.com/generate_204
            interval: 300
    '';
  };
}