{ config, lib, ... }:

{
  xdg.configFile."karabiner/karabiner.json" =
    lib.mkIf (!(builtins.elem "karabiner-elements" config.envy.darwin.homebrew.casks.exclude)) {
      source = ../../../files/apps/karabiner/karabiner.json;
    };
}
