{ pkgs, config, ... }:

{
  home.packages = with pkgs; [
    # utils
    desktoppr

    # apps
    claude-code
    sing-box
  ];
}
