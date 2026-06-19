{ config, pkgs, cfg, lib, sys, ... }:

let
  proxyStatus = cfg.proxy.status or "manual";
in
{
  # --- sops template: mihomo config with encrypted proxy URL ---
  sops.templates."mihomo-config" = lib.mkIf (proxyStatus != "none") {
    content = ''
      ${builtins.readFile ../../files/proxies/mihomo_tailscale.yaml}
      tun:
        enable: ${cfg.proxy.tun or "true"}
        stack: mixed
        auto-route: true
        strict-route: false
        auto-detect-interface: true
        dns-hijack:
          - "any:53"
        external-controller-cors:
          allow-private-network: true
          allow-origins:
            - '*'
        route-exclude-address:
          - 100.64.0.0/10
          - 192.168.255.0/24

      proxy-providers:
        my-sub:
          type: http
          url: ${config.sops.placeholder.proxy-url}
          path: ./sub.yaml
          interval: 3600
          health-check:
            enable: true
            url: http://www.gstatic.com/generate_204
            interval: 300
    '';
  };

  home.activation.deployMihomoConfig = lib.mkIf (proxyStatus != "none") (sys.task.activation {
    name = "deployMihomoConfig";
    script = ''
      TARGET="$HOME/.config/mihomo/config.yaml"
      ${sys.cmds.mkdir} -p "$(dirname "$TARGET")"
      esudo ${sys.cmds.install} -m 0644 "${config.sops.templates."mihomo-config".path}" "$TARGET"
    '';
  });

  xdg.configFile."proxychains/proxychains.conf" = lib.mkIf (proxyStatus != "none") {
    text = ''
      strict_chain
      proxy_dns
      remote_dns_subnet 224

      [ProxyList]
      socks5 127.0.0.1 20122
    '';
  };

  programs.zsh.shellAliases = {
    proxy = "proxychains4 -f ${cfg.home.dir}/.config/proxychains/proxychains.conf";
  };
}