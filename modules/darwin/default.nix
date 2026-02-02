{ pkgs, ... }:

{
  # --- 1. Nix 基础设置 ---
  services.nix-daemon.enable = true;
  nix.settings.experimental-features = [ "nix-command" "flakes" ];

  # --- 2. Homebrew 管理 GUI 软件 ---
  homebrew = {
    enable = true;
    onActivation = {
      autoUpdate = true;
      upgrade = true;
      cleanup = "zap";
    };
    taps = [ "homebrew/services" ];
    casks = [
      "wechat"
      "google-chrome"
      "visual-studio-code"
      "sunshine"
      "karabiner-elements" # Fn/Control 映射
      "orbstack"           # Docker 替代品
      "squirrel"           # Rime 输入法
      "iina"
      "iterm2"
      "snipaste"
    ];
  };

  # --- 3. 系统偏好设置 ---
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

  # --- 4. 键盘映射 ---
  system.keyboard.enableKeyMapping = true;
  system.keyboard.remapCapsLockToControl = true;

  # 必须
  system.stateVersion = 4; 
}
