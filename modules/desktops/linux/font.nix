{ config, lib, pkgs, ... }:

let
  isDesktop = config.envy.linux.option == "desktop";
in
{
  config = lib.mkIf isDesktop {
  envy.packages.home.include = with pkgs; [
    maple-mono.NF-CN
    noto-fonts-cjk-sans
    noto-fonts-cjk-serif
    noto-fonts-color-emoji
  ];
  fonts = {
    fontconfig.enable = true;
    fontconfig.defaultFonts = {
      sansSerif = [ "Noto Sans" "Noto Sans CJK SC" ];
      serif = [ "Noto Serif" "Noto Serif CJK SC" ];
      emoji = [ "Noto Color Emoji" ];
      monospace = [ "Maple Mono NF CN" ];
    };
    fontconfig.antialiasing = true;
    fontconfig.subpixelRendering = "rgb";
    fontconfig.hinting = "slight";
  };
  };
}
