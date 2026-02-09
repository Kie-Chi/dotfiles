{ config, pkgs, secrets, lib, ... }:

let
  proxyStatus = secrets.proxy.status or "manual";
in
{
  xdg.configFile."mihomo/config.yaml" = lib.mkIf (proxyStatus != "none") {
    text = ''
      ${builtins.readFile ../../files/proxies/mihomo.yaml}
      tun:
        enable: ${secrets.proxy.tun or "true"}
        stack: gvisor
        auto-route: true
        auto-detect-interface: true
        dns-hijack:
          - "any:53"

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
    proxy = "proxychains4 -f ${secrets.home.dir}/.config/proxychains/proxychains.conf";
  };
}