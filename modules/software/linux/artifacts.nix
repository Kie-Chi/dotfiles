{ config, lib, pkgs, sys, ... }:

let
  artifacts = config.envy.linux.software.url.artifacts.effective;
  installArtifact = artifact:
    let
      url = artifact.parameters.url or (throw "URL artifact '${artifact.id}' requires parameters.url");
      format = artifact.parameters.format or "";
      packageName = artifact.parameters.packageName or artifact.name;
    in
    if format != "deb" then throw "Unsupported URL artifact format '${format}' for '${artifact.id}'"
    else ''
      PKG=${lib.escapeShellArg packageName}
      if ! pkg_installed "$PKG"; then
        URL=${lib.escapeShellArg url}
        TARGET="$TEMP_DIR/$(basename "$URL")"
        ${pkgs.curl}/bin/curl --fail --location "$URL" --output "$TARGET"
        pkg_install_files "$TARGET"
      else
        log_info "'$PKG' already installed, skip."
      fi
    '';
in
{
  home.activation.installSystemArtifacts = sys.task.root {
    name = "system-artifacts";
    after = [ "configureAptMirror" ];
    script = ''
      if [ "$(detect_pkg_manager)" != "apt" ]; then
        log_warn "URL artifacts currently require an APT-compatible host."
      else
        TEMP_DIR=$(mktemp -d)
        trap 'rm -rf "$TEMP_DIR"' EXIT
        ${lib.concatMapStringsSep "\n" installArtifact artifacts}
      fi
    '';
  };
}
