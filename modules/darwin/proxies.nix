{ config, pkgs, cfg, lib, sys, ... }:

let
  user = cfg.home.user;
  proxyPort = "20122";
  mihomoBin = "/opt/homebrew/bin/mihomo";
  configDir = "/Users/${cfg.home.user}/.config/mihomo";
  proxyStatus = cfg.proxy.status or "manual";
  
  # Check if TUN mode is enabled (matches your desktops/proxies.nix logic)
  isTunMode = (cfg.proxy.tun or "true") == "true";

  # --- Wrapper 1: Pure TUN Mode (Runs entirely as root, no system proxy mess) ---
  mihomoTunWrapper = pkgs.writeShellScriptBin "mihomo-tun-service" ''
    set -e
    echo "[mihomo-tun] Creating config directory if not exists..."
    ${sys.cmds.mkdir} -p ${configDir}
    
    echo "[mihomo-tun] Starting Mihomo in TUN Mode as ROOT..."
    # TUN mode requires root permissions to create utun interface on macOS
    exec ${mihomoBin} -d ${configDir}
  '';

  # --- Wrapper 2: System Proxy Mode (Runs core as user, manages networksetup) ---
  mihomoSysProxyWrapper = pkgs.writeShellScriptBin "mihomo-sysproxy-service" ''
    set -e

    # 1. Get the active default network interface
    INTERFACE=$(${sys.cmds.route} -n get default 2>/dev/null | ${sys.cmds.awk} '/interface:/ {print $2}')
    if [ -z "$INTERFACE" ]; then
      echo "[mihomo] Error: No active network interface detected."
      exit 1
    fi

    # 2. Prevent conflicting with third-party VPNs
    if [[ "$INTERFACE" == utun* ]]; then
      echo "[mihomo] ERROR: Active interface is '$INTERFACE' (VPN/Tailscale detected). Aborting."
      exit 1
    fi

    # 3. Map interface to macOS Service Name
    networkService=$(${sys.cmds.networksetup} -listnetworkserviceorder | \
      ${sys.cmds.grep} -B 1 "Device: $INTERFACE" | \
      ${sys.cmds.head} -n 1 | \
      ${sys.cmds.sed} -E 's/^\([0-9]+\) //')

    if [ -z "$networkService" ]; then
      echo "[mihomo] Error: Could not map interface to macOS network service."
      exit 1
    fi

    cleanup() {
      echo "[mihomo] Disabling system proxy on ($networkService)..."
      ${sys.cmds.sudo} ${sys.cmds.networksetup} -setwebproxystate "$networkService" off
      ${sys.cmds.sudo} ${sys.cmds.networksetup} -setsecurewebproxystate "$networkService" off
    }
    trap cleanup TERM INT EXIT

    # 4. Enable system proxy (No sudo needed here since launchd running as root)
    echo "[mihomo] Enabling system proxy on $networkService..."
    ${sys.cmds.sudo} ${sys.cmds.networksetup} -setwebproxy "$networkService" 127.0.0.1 ${proxyPort}
    ${sys.cmds.sudo} ${sys.cmds.networksetup} -setsecurewebproxy "$networkService" 127.0.0.1 ${proxyPort}

    # 5. Start Mihomo core as unprivileged user
    echo "[mihomo] Starting mihomo core as user '${user}'..."
    exec ${sys.cmds.sudo} -u ${user} ${mihomoBin} -d ${configDir}
  '';
in
{
  homebrew.brews = lib.optionals (proxyStatus != "none") [ "mihomo" ];

  launchd.daemons.mihomo = lib.mkIf (proxyStatus != "none") {
    # Dynamically select which wrapper script to execute based on your TUN setting
    script = if isTunMode 
             then "exec ${mihomoTunWrapper}/bin/mihomo-tun-service"
             else "exec ${mihomoSysProxyWrapper}/bin/mihomo-sysproxy-service";

    serviceConfig = {
      KeepAlive = (proxyStatus == "keep");
      RunAtLoad = (proxyStatus == "keep");
      StandardOutPath = "/Library/Logs/mihomo.log";
      StandardErrorPath = "/Library/Logs/mihomo.err.log";
      ProcessType = "Background";
    };
  };
}