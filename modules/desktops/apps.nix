{ pkgs, ... }:

{
  home.packages = with pkgs; [
    # utils
    desktoppr

    # apps
    sing-box
  ];
}
