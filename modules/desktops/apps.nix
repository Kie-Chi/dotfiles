{ pkgs, config, ... }:

{
  home.packages = with pkgs; [
    # utils

    # apps
    sing-box
  ];
}