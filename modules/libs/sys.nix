{ pkgs, lib, config, ... }:

let
  sopsHomePasswdPath = config.sops.secrets.home-passwd.path;
  hasSopsSecrets = config.sops.secrets != {};

  sys = rec {
    cmds = {
      # Linux system tools (outside Nix sandbox)
      sudo = "/usr/bin/sudo";
      sh = "/bin/sh";
      apt = "/usr/bin/apt";
      grep = "${pkgs.gnugrep}/bin/grep";
      systemctl = "/usr/bin/systemctl";
      usermod = "/usr/sbin/usermod";
      touch = "/usr/bin/touch";
      dpkg = "/usr/bin/dpkg";
      dpkgQuery = "/usr/bin/dpkg-query";
      udevadm = "/usr/bin/udevadm";
      modprobe = "/usr/sbin/modprobe";
      setcap = "/usr/sbin/setcap";
      install = "/usr/bin/install";
      cmp = "/usr/bin/cmp";
      mktemp = "/usr/bin/mktemp";
      rm = "/usr/bin/rm";
      mkdir = "/usr/bin/mkdir";
      curl = "${pkgs.curl}/bin/curl";
      ufw = "/usr/sbin/ufw";
    };

    initSudoPwd = ''
      SUDO_PWD=""
    '';

    esudoFn = ''
      esudo() {
        if [ -z "''${SUDO_PWD:-}" ] && [ -f "${sopsHomePasswdPath}" ]; then
          SUDO_PWD=$(cat "${sopsHomePasswdPath}")
        fi
        if [ -n "''${SUDO_PWD:-}" ]; then
          printf '%s\n' "$SUDO_PWD" | ${cmds.sudo} -S "$@"
        else
          ${cmds.sudo} "$@"
        fi
      }
    '';

    logFn = ''
      _log() {
        LEVEL="$1"
        shift
        MSG="$*"
        RESET="\033[0m"
        case "$LEVEL" in
          debug) COLOR="\033[0;36m"  ;; # cyan
          info)  COLOR="\033[0;32m"  ;; # green
          warn)  COLOR="\033[0;33m"  ;; # yellow
          error) COLOR="\033[0;31m"  ;; # red
          *)     COLOR="$RESET"      ;;
        esac
        printf "''${COLOR}[%s][%s]''${RESET} %s\n" "$LEVEL" "''${_LOG_CTX:-activation}" "$MSG" >&2
      }
      log_debug() { _log debug "$@"; }
      log_info()  { _log info  "$@"; }
      log_warn()  { _log warn  "$@"; }
      log_error() { _log error "$@"; }
    '';

    sopsDecrypt = lib.hm.dag.entryAfter [ "writeBoundary" ] ''
      _LOG_CTX="sopsDecrypt"
      # sops-nix on Linux uses systemd services for decryption;
      # the secrets are automatically decrypted by sops-nix during activation.
      # Read sudo password from decrypted secret
      if [ -f "${sopsHomePasswdPath}" ]; then
        SUDO_PWD=$(cat "${sopsHomePasswdPath}")
      fi
    '';

    userBoundary = lib.hm.dag.entryAfter [ "writeBoundary" "sopsDecrypt" ] ''
      _LOG_CTX="userBoundary"
      ${lib.optionalString hasSopsSecrets ''
        if [ -f "${sopsHomePasswdPath}" ]; then
          log_info "sops secrets available"
        else
          log_warn "sops secrets unavailable — esudo will require manual password"
        fi
      ''}
      log_info "user script boundary ready"
    '';

    pkg = rec {
      detectManagerFn = ''
        detect_pkg_manager() {
          if [ -x "${cmds.apt}" ] || command -v apt >/dev/null 2>&1; then
            echo "apt"
          elif [ -x "/usr/bin/dnf" ] || command -v dnf >/dev/null 2>&1; then
            echo "dnf"
          elif [ -x "/usr/bin/pacman" ] || command -v pacman >/dev/null 2>&1; then
            echo "pacman"
          elif [ -x "/usr/bin/zypper" ] || command -v zypper >/dev/null 2>&1; then
            echo "zypper"
          else
            log_error "[pkg] no supported package manager found; PATH=$PATH"
            echo "unknown"
          fi
        }
      '';

      isInstalledFn = ''
        pkg_installed() {
          PKG_MANAGER="$(detect_pkg_manager)"
          case "$PKG_MANAGER" in
            apt)
              if [ ! -x "${cmds.dpkgQuery}" ]; then
                return 1
              fi
              ${cmds.dpkgQuery} -W -f='$'"{Status}" "$1" 2>/dev/null | ${cmds.grep} -q "ok installed"
              ;;
            dnf|zypper)
              if [ ! -x "/usr/bin/rpm" ] && ! command -v rpm >/dev/null 2>&1; then
                return 1
              fi
              /usr/bin/rpm -q "$1" >/dev/null 2>&1
              ;;
            pacman)
              if [ ! -x "/usr/bin/pacman" ] && ! command -v pacman >/dev/null 2>&1; then
                return 1
              fi
              /usr/bin/pacman -Q "$1" >/dev/null 2>&1
              ;;
            *)
              return 1
              ;;
          esac
        }
      '';

      updateFn = ''
        pkg_update() {
          PKG_MANAGER="$(detect_pkg_manager)"
          case "$PKG_MANAGER" in
            apt)
              esudo ${cmds.apt} update
              ;;
            dnf)
              esudo /usr/bin/dnf makecache -y
              ;;
            pacman)
              esudo /usr/bin/pacman -Sy --noconfirm
              ;;
            zypper)
              esudo /usr/bin/zypper --gpg-auto-import-keys refresh
              ;;
            *)
              echo "No supported package manager found. Skipping package index update."
              return 1
              ;;
          esac
        }
      '';

      installFn = ''
        pkg_install() {
          if [ $# -eq 0 ]; then
            return 0
          fi

          PKG_MANAGER="$(detect_pkg_manager)"
          case "$PKG_MANAGER" in
            apt)
              esudo ${cmds.apt} install -y "$@"
              ;;
            dnf)
              esudo /usr/bin/dnf install -y "$@"
              ;;
            pacman)
              esudo /usr/bin/pacman -S --noconfirm --needed "$@"
              ;;
            zypper)
              esudo /usr/bin/zypper --non-interactive install "$@"
              ;;
            *)
              echo "No supported package manager found. Cannot install: $*"
              return 1
              ;;
          esac
        }
      '';

      installFilesFn = ''
        pkg_install_files() {
          if [ $# -eq 0 ]; then
            return 0
          fi

          PKG_MANAGER="$(detect_pkg_manager)"
          case "$PKG_MANAGER" in
            apt)
              esudo ${cmds.apt} install -y "$@"
              ;;
            dnf)
              esudo /usr/bin/dnf install -y "$@"
              ;;
            zypper)
              esudo /usr/bin/zypper --non-interactive install "$@"
              ;;
            pacman)
              echo "Local package file installation is not implemented for pacman in this module."
              return 1
              ;;
            *)
              echo "No supported package manager found. Cannot install local package files: $*"
              return 1
              ;;
          esac
        }
      '';
    };

    config = rec {
      renderers = {
        ini = attrs: lib.generators.toINI {} attrs;
        yaml = attrs: lib.generators.toYAML {} attrs;
        json = attrs: builtins.toJSON attrs;
        toml = attrs: lib.generators.toTOML {} attrs;
        plain = text: text;
        lines = values: lib.concatStringsSep "\n" values + "\n";
        kv = attrs: renderers.lines (lib.mapAttrsToList (k: v: "${k} ${toString v}") attrs);
        kvEq = attrs: renderers.lines (lib.mapAttrsToList (k: v: "${k} = ${toString v}") attrs);
      };

      renderedText = { format, data }:
        if format == "concat" then
          lib.concatMapStrings (
            item:
              if builtins.isAttrs item && item ? format && item ? data
              then renderedText item
              else throw "Invalid concat item: expected { format, data; }"
          ) data
        else if format == "ini" then renderers.ini data
        else if format == "yaml" then renderers.yaml data
        else if format == "json" then renderers.json data
        else if format == "toml" then renderers.toml data
        else if format == "plain" then data
        else if format == "lines" then renderers.lines data
        else if format == "kv" then renderers.kv data
        else if format == "kvEq" then renderers.kvEq data
        else throw "Unsupported render format: ${format}";

      renderedFile = { name, format, data }:
        pkgs.writeText name (renderedText { inherit format data; });

      deployScript = {
        source,
        target,
        owner ? "root",
        group ? "root",
        mode ? "0644",
        postDeploy ? ""
      }: ''
        TMP_FILE="$(${cmds.mktemp})"
        cp "${source}" "$TMP_FILE"
        if [ ! -f "${target}" ] || ! ${cmds.cmp} -s "$TMP_FILE" "${target}"; then
          esudo ${cmds.mkdir} -p "$(dirname "${target}")"
          esudo ${cmds.install} -m ${mode} -o ${owner} -g ${group} "$TMP_FILE" "${target}"
          ${postDeploy}
        fi
        ${cmds.rm} -f "$TMP_FILE"
      '';

      deploy = {
        name,
        format,
        data,
        target,
        owner ? "root",
        group ? "root",
        mode ? "0644",
        post ? ""
      }:
        let src = renderedFile { inherit name format data; };
        in deployScript {
          source = src;
          postDeploy = post;
          inherit target owner group mode;
        };

      activation = {
        after ? [ "userBoundary" ],
        pre ? "",
        name,
        format,
        data,
        target,
        owner ? "root",
        group ? "root",
        mode ? "0644",
        post ? "",
        message ? null
      }:
        sys.task.root {
          inherit after name;
          script = ''
            ${lib.optionalString (message != null) "log_info \"${message}\""}
            ${pre}
            ${deploy {
              inherit name format data target owner group mode post;
            }}
          '';
        };
    };

    # Global init activation - runs before writeBoundary
    # Defines log functions, esudo (which dynamically reads sops secret when available),
    # and pkg management functions.
    # Secret decryption happens in sopsDecrypt (after writeBoundary), before userBoundary.
    initActivation = lib.hm.dag.entryBefore [ "writeBoundary" ] ''
      # === Global function definitions ===
      # Logging functions
      ${logFn}

      # Sudo with password support (dynamic: reads from sops-decrypted file)
      ${initSudoPwd}
      ${esudoFn}

      # Package management functions
      ${pkg.detectManagerFn}
      ${pkg.isInstalledFn}
      ${pkg.updateFn}
      ${pkg.installFn}
      ${pkg.installFilesFn}
    '';

    task = rec {
      activation = {
        after ? [ "userBoundary" ],
        asRoot ? false,
        guardDryRun ? true,
        name ? "activation",
        pre ? "",
        script ? "",
        post ? "",
        message ? null
      }:
        lib.hm.dag.entryAfter after ''
          _LOG_CTX="${name}"
          ${lib.optionalString (message != null) "log_info \"${message}\""}
          ${pre}
          ${lib.optionalString guardDryRun ''
            if [ -z "$DRY_RUN_CMD" ]; then
          ''}
          ${script}
          ${lib.optionalString guardDryRun ''
            fi
          ''}
          ${post}
        '';

      root = args: activation (args // { asRoot = true; });

      mkAttr     = args: { home.activation.${args.name} = activation args; };
      mkRootAttr = args: mkAttr (args // { asRoot = true; });
    };

    mkActivation = {
      after ? [ "userBoundary" ],
      asRoot ? false,
      guardDryRun ? true,
      name ? "activation",
      script
    }:
      lib.hm.dag.entryAfter after ''
        _LOG_CTX="${name}"
        ${lib.optionalString guardDryRun ''
          if [ -z "$DRY_RUN_CMD" ]; then
        ''}
        ${script}
        ${lib.optionalString guardDryRun ''
          fi
        ''}
      '';

    render = config.renderers;
    mkRenderedText = config.renderedText;
    mkRenderedFile = config.renderedFile;
    mkDeployScript = config.deployScript;
    deploy = config.deploy;
  };
in
{
  _module.args.sys = sys;
  home.activation = {
    sysInit = sys.initActivation;
    sopsDecrypt = sys.sopsDecrypt;
    userBoundary = sys.userBoundary;
  };
}