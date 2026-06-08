{ pkgs, cfg, ... }:
{
  system.stateVersion = 6;
  system.primaryUser = cfg.home.user;
  nixpkgs.config.allowUnfree = true;
  nix.enable = false;
  system.defaults = {
    dock = {
      autohide = true;
      show-recents = false;
    };
    finder.AppleShowAllExtensions = true;
    NSGlobalDomain = {
      "com.apple.mouse.tapBehavior" = 1;
      KeyRepeat = 2;
    };
  };
  system.defaults.NSGlobalDomain."com.apple.keyboard.fnState" = true;

  programs.zsh.enable = true;
}