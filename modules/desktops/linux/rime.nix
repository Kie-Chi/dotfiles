{ config
, pkgs
, lib
, sys
, ...
}:

let
  isDesktop = config.envy.linux.option == "desktop";
  rime-ice-for-deploy = pkgs.runCommand "rime-ice-with-entrypoint" { } ''
    DEST="$out/share/rime-data"
    mkdir -p "$DEST"
    cp -r ${pkgs.rime-data}/share/rime-data/* "$DEST/"
    chmod -R u+w "$DEST/"
    cp -rT ${pkgs.rime-ice}/share/rime-data "$DEST/"
    cat > "$DEST/default.yaml" << EOF
    schema_list:
      - schema: rime_ice
    EOF
  '';

  deployScript = builtins.readFile ../../../files/fcitx/deploy.sh;
  customConfig = builtins.readFile ../../../files/fcitx/rime.yaml;
in
{
  config = lib.mkIf isDesktop {
  xdg.dataFile."fcitx5/rime/default.custom.yaml".text = customConfig;

  home.activation.rimeDeploy = sys.task.activation {
    name = "rimeDeploy";
    script = ''
      export RIME_ICE_PATH="${rime-ice-for-deploy}/share/rime-data"
      export CONFIG_SOURCE="${config.xdg.dataFile."fcitx5/rime/default.custom.yaml".source}"
      export CACHE_HOME="${config.xdg.cacheHome}"
      export DATA_HOME="${config.xdg.dataHome}"

      export LIBRIME_BIN="${pkgs.librime}/bin/rime_deployer"
      export PGREP_BIN="${pkgs.procps}/bin/pgrep"
      export FCITX_REMOTE_BIN="${pkgs.fcitx5}/bin/fcitx5-remote"

      ${deployScript}
    '';
  };
  };
}
