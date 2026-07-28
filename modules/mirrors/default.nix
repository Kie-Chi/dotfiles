{ config, lib, machinePlatform, ... }:

let
  catalog = import ./catalog.nix;
  profile = (import ./resolve.nix { inherit lib; })
    catalog.${config.envy.mirrors.mode}
    config.envy.mirrors.overrides;
  extraSubstituters = lib.concatStringsSep " " profile.nix.extraSubstituters;
  condaConfig = {
    envs_dirs = [ "~/.mamba/envs" ];
    pkgs_dirs = [ "~/.mamba/pkgs" ];
    channels = [ profile.conda.condaForge "defaults" ];
    show_channel_urls = true;
    default_channels = profile.conda.defaultChannels;
  };
  nixMirrorConfig = lib.optionalString (profile.nix.extraSubstituters != [ ]) ''
    extra-substituters = ${extraSubstituters}
  '';
in
{
  imports = lib.optionals (machinePlatform == "linux") [ ./linux.nix ];

  home.sessionVariables = {
    npm_config_registry = profile.npm.registry;
    PIP_INDEX_URL = profile.python.index;
    UV_DEFAULT_INDEX = profile.python.index;
    GOPROXY = profile.go.proxy;
    RUSTUP_DIST_SERVER = profile.rust.distServer;
    RUSTUP_UPDATE_ROOT = profile.rust.updateRoot;
    CARGO_REGISTRIES_CRATES_IO_INDEX = profile.rust.cargoIndex;
    CARGO_REGISTRIES_CRATES_IO_PROTOCOL = "sparse";
  };

  home.file = {
    ".config/nix/nix.conf".text = ''
      ${nixMirrorConfig}fallback = true
      connect-timeout = 5
      download-attempts = 3
    '';
  } // lib.optionalAttrs (machinePlatform == "linux") {
    ".condarc".text = lib.generators.toYAML { } condaConfig;
  } // lib.optionalAttrs (
    machinePlatform == "linux" && config.envy.mirrors.mode == "china"
  ) {
    ".m2/settings.xml".text = ''
      <?xml version="1.0" encoding="UTF-8"?>
      <settings xmlns="http://maven.apache.org/SETTINGS/1.0.0"
                xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
                xsi:schemaLocation="http://maven.apache.org/SETTINGS/1.0.0 https://maven.apache.org/xsd/settings-1.0.0.xsd">
        <mirrors>
          <mirror>
            <id>envy-china</id>
            <name>envY China Maven mirror</name>
            <url>${profile.maven.repository}</url>
            <mirrorOf>central</mirrorOf>
          </mirror>
        </mirrors>
      </settings>
    '';
  };
}
