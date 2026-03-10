{ ... }: {
  homebrew = {
    enable = true;
    onActivation = {
      autoUpdate = true;
      upgrade = true;
      cleanup = "zap"; 
    };

    # taps = [
    #    {
    #      name = "kde-mac/kde";
    #      clone_target = "git@github.com:KDE/homebrew-kde.git";
    #    }
    #  ];

    brews = [
      "chsrc"
      "gum"
      "proxychains-ng"
      "uv"
      "java"
      "go"
    ];

    casks = [
      "squirrel-app"
      "trae"
      "linearmouse"
      "tailscale-app"
      "moonlight"
      "raycast"
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
