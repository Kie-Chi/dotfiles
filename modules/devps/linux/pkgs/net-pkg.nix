{ pkgs, lib, config, sys, ... }:

let
  isDesktop = (config.envy.linux.option or "desktop") == "desktop";
  systempkgs = [
    # systempkgs both desktop and server use
  ] ++ lib.optionals isDesktop [
    {
      pkg = "wechat";
      url = "https://dldir1v6.qq.com/weixin/Universal/Linux/WeChatLinux_x86_64.deb";
      install = ''
        pkg_install_files "$target"
      '';
    }
  ];
  packageScripts = lib.concatStringsSep "\n" (map (obj: ''
      PKG="${obj.pkg}"
      URL="${obj.url}"

      if ! pkg_installed "$PKG"; then
        log_warn "'$PKG' not found, preparing download from $URL"
        MISSING_NET_PKGS="$MISSING_NET_PKGS $PKG"
        filename=$(basename "$URL")
        target="$TEMP_DIR/$filename"
        ${pkgs.curl}/bin/curl -L "$URL" -o "$target"
        ${obj.install}
      else
        log_info "'$PKG' already installed, skip."
      fi
    '') systempkgs);
in
{
  home.activation.installNetworkSystemPkgs = lib.mkIf isDesktop (sys.task.root {
    name = "network-pkgs";
    pre = ''
      MISSING_NET_PKGS=""
      log_debug "starting network package installation"
    '';
    script = ''
      PKG_MANAGER="$(detect_pkg_manager)"
      log_debug "detected package manager: $PKG_MANAGER"
      TEMP_DIR=$(mktemp -d)
      trap 'rm -rf "$TEMP_DIR"' EXIT

      if [ "$PKG_MANAGER" != "apt" ]; then
        log_warn "skip: current manager '$PKG_MANAGER' does not support .deb workflow"
      else
        log_debug "total managed network packages: ${toString (builtins.length systempkgs)}"
        ${packageScripts}

        if [ -n "$MISSING_NET_PKGS" ]; then
          log_error "missing network packages:$MISSING_NET_PKGS"
        else
          log_info "all network packages satisfied, nothing to install."
        fi
      fi
    '';
  });
}
