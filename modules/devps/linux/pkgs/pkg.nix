{ lib, sys, config, ... }:

let
  isDesktop = (config.envy.linux.option or "desktop") == "desktop";
  systempkgs = [
    "cifs-utils"
    "openssh-server"
    "linux-headers-$(uname -r)"
  ] ++ lib.optionals isDesktop [
  ];
  pkgStrings = lib.concatMapStringsSep " " (pkg: "\"${pkg}\"") systempkgs;
in
{
  home.activation.installSystemPkgs = sys.task.root {
    name = "system-pkgs";
    pre = ''
      RAW_PKGS=(${pkgStrings})
      MISSING_PKGS=""
      CURRENT_KERNEL="$(uname -r)"
      log_debug "starting system package installation"
    '';
    script = ''
      PKG_MANAGER="$(detect_pkg_manager)"
      log_debug "detected package manager: $PKG_MANAGER"
      log_debug "total managed packages: ''${#RAW_PKGS[@]}"

      resolve_pkg_name() {
        case "$1" in
          'linux-headers-$(uname -r)')
            echo "linux-headers-$CURRENT_KERNEL"
            ;;
          *)
            echo "$1"
            ;;
        esac
      }

      if [ ''${#RAW_PKGS[@]} -gt 0 ]; then
        for item in "''${RAW_PKGS[@]}"; do
          PKG="$(resolve_pkg_name "$item")"

          if pkg_installed "$PKG"; then
            log_info "'$PKG' already installed, skip."
            continue
          fi

          log_warn "'$PKG' not found, queued for install."
          MISSING_PKGS="$MISSING_PKGS $PKG"
        done

        if [ -n "$MISSING_PKGS" ]; then
          log_error "missing packages:$MISSING_PKGS"
          pkg_update || true
          pkg_install $MISSING_PKGS
        else
          log_info "all packages satisfied, nothing to install."
        fi
      fi
    '';
  };
}
