{ config, pkgs, cfg, lib, sys, ... }:

let
  user = cfg.home.user;
  proxyPort = "20122";
  mihomoBin = "/opt/homebrew/bin/mihomo";
  configDir = "/Users/${cfg.home.user}/.config/mihomo";
  proxyStatus = cfg.proxy.status or "manual";  
  isTunMode = (cfg.proxy.tun or "true") == "true";

  # --- Shared Shell Functions for Interface Detection ---
  detectionLogic = ''
    PHYS_IFACE=$(${sys.cmds.scutil} --nwi 2>/dev/null | ${sys.cmds.awk} '/Network interfaces:/ {print $3}' | ${sys.cmds.head} -n 1)
    
    TS_IFACE=$(${sys.cmds.ifconfig} 2>/dev/null | ${sys.cmds.awk} '/^[a-zA-Z0-9]/ {current_iface=$1} /inet 100\./ {print current_iface; exit}' | ${sys.cmds.sed} 's/://')

    echo "[mihomo-wrapper] Detected Physical Interface: $PHYS_IFACE"
    echo "[mihomo-wrapper] Detected Tailscale Interface: $TS_IFACE"

    PHYS_IFACE=''${PHYS_IFACE:-en0}
    TS_IFACE=''${TS_IFACE:-utun6}

    echo "[mihomo-wrapper] Decided Physical Interface Finally: $PHYS_IFACE"
    echo "[mihomo-wrapper] Decided Tailscale Interface Finally: $TS_IFACE"

    TARGET_CONFIG="${configDir}/config.yaml"
    ${sys.cmds.mkdir} -p "${configDir}"
    
    TEMPLATE_TMPL="${configDir}/config.yaml.tmpl"
    TARGET_CONFIG="${configDir}/config.yaml"
    
    if [ ! -f "$TEMPLATE_TMPL" ]; then
      echo "[mihomo-wrapper] Error: Template $TEMPLATE_TMPL not found yet. Waiting for Home Manager..."
      exit 1
    fi

    ${sys.cmds.mkdir} -p "${configDir}"
    ${sys.cmds.sed} -e "s/@PHYS_IFACE@/$PHYS_IFACE/g" \
                    -e "s/@TS_IFACE@/$TS_IFACE/g" \
                    "$TEMPLATE_TMPL" > "$TARGET_CONFIG"
  '';

  # --- Wrapper 1: Pure TUN Mode (Runs entirely as root to create utun device) ---
  mihomoTunWrapper = pkgs.writeShellScriptBin "mihomo-tun-service" ''
    set -e
    echo "[mihomo-tun] Initializing dynamic interfaces..."
    ${detectionLogic}
    
    echo "[mihomo-tun] Setting correct ownership for config directory..."
    ${sys.cmds.chown} -R ${user}:staff ${configDir}

    echo "[mihomo-tun] Starting Mihomo in TUN Mode as ROOT..."
    # TUN mode requires root permissions to create utun interface on macOS
    exec ${mihomoBin} -d ${configDir}
  '';

  # --- Wrapper 2: System Proxy Mode (Manages networksetup, drops privileges for core) ---
  mihomoSysProxyWrapper = pkgs.writeShellScriptBin "mihomo-sysproxy-service" ''
    set -e
    echo "[mihomo-sysproxy] Initializing dynamic interfaces..."
    ${detectionLogic}

    if [[ "$PHYS_IFACE" == utun* ]]; then
      echo "[mihomo] ERROR: Active interface is '$PHYS_IFACE' (VPN/Tailscale detected). Aborting."
      exit 1
    fi

    # Map the detected physical interface (e.g. en0) to macOS Service Name (e.g. "Wi-Fi")
    networkService=$(${sys.cmds.networksetup} -listnetworkserviceorder | \
      ${sys.cmds.grep} -B 1 "Device: $PHYS_IFACE" | \
      ${sys.cmds.head} -n 1 | \
      ${sys.cmds.sed} -E 's/^\([0-9]+\) //')

    if [ -z "$networkService" ]; then
      echo "[mihomo-sysproxy] Error: Could not map interface $PHYS_IFACE to macOS network service."
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
    ${sys.cmds.sudo} -u ${user} ${mihomoBin} -d ${configDir} &
    MIHOMO_PID=$!
    wait "$MIHOMO_PID"
  '';
in
{
  homebrew.brews = lib.optionals (proxyStatus != "none") [ "mihomo" ];

  launchd.daemons.mihomo = lib.mkIf (proxyStatus != "none") {
    script = if isTunMode 
             then "${mihomoTunWrapper}/bin/mihomo-tun-service"
             else "${mihomoSysProxyWrapper}/bin/mihomo-sysproxy-service";

    serviceConfig = {
      KeepAlive = (proxyStatus == "keep");
      RunAtLoad = (proxyStatus == "keep");
      StandardOutPath = "/Library/Logs/mihomo.log";
      StandardErrorPath = "/Library/Logs/mihomo.err.log";
      ProcessType = "Background";
    };
  };
}