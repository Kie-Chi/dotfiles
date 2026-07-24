{ config, lib, ... }:

let
  proxyStatus = config.envy.darwin.proxy.mode;
  enabled = proxyStatus != "none"
    && !(builtins.elem "clash-verge-rev" config.envy.darwin.software.homebrew.casks.exclude);
  enableTun = config.envy.darwin.proxy.tun;
  renderYaml = lib.generators.toYAML {};
in
{
  home.file."Library/Application Support/io.github.clash-verge-rev.clash-verge-rev/verge.yaml" = lib.mkIf enabled {
    text = renderYaml {
      app_log_level = null;
      app_log_max_size = 128;
      app_log_max_count = 8;
      language = "zh";
      theme_mode = "system";
      start_page = "/";
      traffic_graph = true;
      enable_memory_usage = true;
      enable_group_icon = true;
      pause_render_traffic_stats_on_blur = true;
      common_tray_icon = false;
      tray_icon = "monochrome";
      menu_icon = "monochrome";
      notice_position = "top-right";
      collapse_navbar = false;
      sysproxy_tray_icon = false;
      tun_tray_icon = false;
      enable_tun_mode = enableTun;
      enable_auto_launch = false;
      enable_silent_start = false;
      enable_system_proxy = false;
      enable_proxy_guard = false;
      enable_bypass_check = true;
      enable_dns_settings = true;
      use_default_bypass = true;
      system_proxy_bypass = null;
      proxy_guard_duration = 30;
      proxy_auto_config = false;
      pac_file_content = ''
        function FindProxyForURL(url, host) {
          return "PROXY 127.0.0.1:%mixed-port%; SOCKS5 127.0.0.1:%mixed-port%; DIRECT;";
        }
      '';
      proxy_host = "127.0.0.1";
      clash_core = "verge-mihomo";
      enable_global_hotkey = true;
      auto_close_connection = true;
      auto_check_update = true;
      enable_builtin_enhanced = true;
      auto_log_clean = 2;
      enable_auto_backup_schedule = false;
      auto_backup_interval_hours = 24;
      auto_backup_on_change = true;
      verge_redir_port = 7895;
      verge_redir_enabled = false;
      verge_mixed_port = 7897;
      verge_socks_port = 7898;
      verge_socks_enabled = false;
      verge_port = 7899;
      verge_http_enabled = false;
      enable_tray_speed = false;
      tray_proxy_groups_display_mode = "default";
      tray_inline_outbound_modes = false;
      enable_auto_light_weight_mode = false;
      auto_light_weight_minutes = 10;
      enable_hover_jump_navigator = true;
      hover_jump_navigator_delay = 280;
      enable_external_controller = false;
    };
  };

  home.file."Library/Application Support/io.github.clash-verge-rev.clash-verge-rev/config.yaml" = lib.mkIf enabled {
    text = renderYaml {
      "redir-port" = 7895;
      "mixed-port" = 7897;
      "socks-port" = 7898;
      port = 7899;
      "log-level" = "info";
      "allow-lan" = true;
      ipv6 = true;
      mode = "rule";
      "external-controller" = "127.0.0.1:9097";
      "external-controller-unix" = "/tmp/verge/verge-mihomo.sock";
      tun = {
        "auto-detect-interface" = true;
        "auto-route" = true;
        device = "utun1024";
        "dns-hijack" = [ "any:53" ];
        mtu = 1500;
        "route-exclude-address" = [ ];
        stack = "mixed";
        "strict-route" = false;
      };
      secret = "set-your-secret";
      "external-controller-cors" = {
        "allow-private-network" = true;
        "allow-origins" = [
          "tauri://localhost"
          "http://tauri.localhost"
          "https://yacd.metacubex.one"
          "https://metacubex.github.io"
          "https://board.zash.run.place"
        ];
      };
      "unified-delay" = true;
    };
  };
}
