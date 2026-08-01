{ config, lib, pkgs, sys, ... }:

let
  profile = (import ./resolve.nix { inherit lib; })
    (import ./catalog.nix).${config.envy.mirrors.mode}
    config.envy.mirrors.overrides;
  sourcePath = "/etc/apt/sources.list.d/envy-mirror.sources";
  nixTrustSource = ../../resources/scripts/nix-trust.sh;
  nixTrust = pkgs.writeShellApplication {
    name = "envy-nix-trust";
    runtimeInputs = with pkgs; [
      coreutils
      diffutils
      gawk
      gnugrep
    ];
    text = ''
      exec ${pkgs.bash}/bin/bash "${nixTrustSource}" "$@"
    '';
  };
  nixTrustCommand = "${nixTrust}/bin/envy-nix-trust";
  removeManagedMirrorFile = ''
    remove_envy_apt_mirror() {
      if [ -e "${sourcePath}" ]; then
        esudo ${sys.cmds.rm} -f "${sourcePath}"
      fi
    }
  '';
  configureChinaMirror = ''
    ${removeManagedMirrorFile}
    if [ "$(detect_pkg_manager)" != "apt" ]; then
      log_info "APT mirror is not applicable on this host."
      remove_envy_apt_mirror
    elif [ ! -r /etc/os-release ]; then
      log_warn "Cannot configure the APT mirror: /etc/os-release is unavailable."
      remove_envy_apt_mirror
    else
      # shellcheck disable=SC1091
      . /etc/os-release
      DISTRO_ID="''${ID:-}"
      CODENAME="''${VERSION_CODENAME:-''${UBUNTU_CODENAME:-}}"
      TEMP_SOURCE="$(${sys.cmds.mktemp})"

      if [ -z "$CODENAME" ]; then
        log_warn "Cannot configure the APT mirror: the distribution codename is unknown."
        ${sys.cmds.rm} -f "$TEMP_SOURCE"
        remove_envy_apt_mirror
      else
        case "$DISTRO_ID" in
          ubuntu)
            APT_ARCH="$(${sys.cmds.dpkg} --print-architecture)"
            case "$APT_ARCH" in
              amd64|i386) UBUNTU_URI="${profile.apt.ubuntu}" ;;
              *) UBUNTU_URI="${profile.apt.ubuntuPorts}" ;;
            esac
            ${sys.cmds.cat} > "$TEMP_SOURCE" <<EOF
Types: deb
URIs: $UBUNTU_URI
Suites: $CODENAME $CODENAME-updates $CODENAME-backports $CODENAME-security
Components: main restricted universe multiverse
Signed-By: /usr/share/keyrings/ubuntu-archive-keyring.gpg
EOF
            ;;
          debian)
            ${sys.cmds.cat} > "$TEMP_SOURCE" <<EOF
Types: deb
URIs: ${profile.apt.debian}
Suites: $CODENAME $CODENAME-updates
Components: main contrib non-free non-free-firmware
Signed-By: /usr/share/keyrings/debian-archive-keyring.gpg

Types: deb
URIs: ${profile.apt.debianSecurity}
Suites: $CODENAME-security
Components: main contrib non-free non-free-firmware
Signed-By: /usr/share/keyrings/debian-archive-keyring.gpg
EOF
            ;;
          *)
            log_warn "APT mirror is not managed for distribution '$DISTRO_ID'; keeping its existing sources."
            ${sys.cmds.rm} -f "$TEMP_SOURCE"
            remove_envy_apt_mirror
            TEMP_SOURCE=""
            ;;
        esac

        if [ -n "$TEMP_SOURCE" ]; then
          esudo ${sys.cmds.mkdir} -p /etc/apt/sources.list.d
          esudo ${sys.cmds.install} -m 0644 -o root -g root "$TEMP_SOURCE" "${sourcePath}"
          ${sys.cmds.rm} -f "$TEMP_SOURCE"
          log_info "Configured the envY APT mirror for $DISTRO_ID/$CODENAME."
        fi
      fi
    fi
  '';
  removeManagedMirror = ''
    ${removeManagedMirrorFile}
    if [ -e "${sourcePath}" ]; then
      remove_envy_apt_mirror
      log_info "Removed the envY-managed APT mirror; system sources remain unchanged."
    fi
  '';
in
{
  home.activation.configureNixDaemonTrust = sys.task.root {
    name = "configure-nix-daemon-trust";
    script = ''
      if ${nixTrustCommand} status \
          --mode "${config.envy.mirrors.mode}" \
          --user "${config.envy.user.name}"; then
        :
      else
        TRUST_STATUS=$?
        if [ "$TRUST_STATUS" -ne 1 ]; then
          exit "$TRUST_STATUS"
        fi
        esudo ${nixTrustCommand} repair \
          --mode "${config.envy.mirrors.mode}" \
          --user "${config.envy.user.name}" \
          --elevated
      fi
    '';
  };

  home.activation.configureAptMirror = sys.task.root {
    name = "configure-apt-mirror";
    script = if config.envy.mirrors.mode == "china"
      then configureChinaMirror
      else removeManagedMirror;
  };
}
