{ pkgs, config, ... }:

{
  home.packages = with pkgs; [
    # utils
    desktoppr

    # apps
    sing-box
  ];
}