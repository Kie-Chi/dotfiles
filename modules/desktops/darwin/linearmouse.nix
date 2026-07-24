{ config, lib, ... }:

{
  xdg.configFile."linearmouse/linearmouse.json" =
    lib.mkIf (!(builtins.elem "linearmouse" config.envy.darwin.software.homebrew.casks.exclude)) {
      source = ../../../files/apps/linearmouse/linearmouse.json;
    };
}
