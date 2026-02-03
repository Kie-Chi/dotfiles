{ ... }: {
  homebrew = {
    enable = true;
    onActivation = {
      autoUpdate = true;
      upgrade = true;
      cleanup = "zap"; 
    };

    # taps = [
    #   {
    #     name = "kde-mac/kde";
    #     clone_target = "git@github.com:KDE/homebrew-kde.git";
    #   }
    # ];

    brews = [
      # "okular"
      "chsrc"
    ];

    casks = [
      "moonlight"
      "raycast"
      "skim"
      "wechat"
      "google-chrome"
      "feishu"
      "tencent-meeting"
      "dingtalk"
      "karabiner-elements"
      "orbstack"
      "squirrel-app"
      "iina"
      "iterm2"
      "snipaste"
      "neteasemusic"
    ];
  };
}