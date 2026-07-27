{ config, lib, pkgs, ... }:

let
  isDesktop = config.envy.linux.option == "desktop";
in
{
  config = lib.mkIf isDesktop {
  envy.software.nix.packages.include = with pkgs; [
    maple-mono.NF-CN
    noto-fonts-cjk-sans
    noto-fonts-cjk-serif
    noto-fonts-color-emoji
  ];
  envy.software.nix.packages.references = {
    "MapleMono-NF-CN" = "nix:maple-mono.NF-CN";
    "noto-fonts-cjk-sans" = "nix:noto-fonts-cjk-sans";
    "noto-fonts-cjk-serif" = "nix:noto-fonts-cjk-serif";
    "noto-fonts-color-emoji" = "nix:noto-fonts-color-emoji";
  };
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
