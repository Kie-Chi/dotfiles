{ ... }: {
  homebrew = {
    enable = true;
    onActivation = {
      autoUpdate = false;
      upgrade = false;
    };

    # taps = [
    #    {
    #      name = "kde-mac/kde";
    #      clone_target = "git@github.com:KDE/homebrew-kde.git";
    #    }
    #  ];

    brews = [
      "gh"
      "chsrc"
      "gum"
      "proxychains-ng"
      "uv"
      "java"
      "go"
    ];

    casks = [
      # "uuremote" # Game for Windows
      "telegram-desktop"
      "clash-verge-rev"
      "cyberduck"
      "betterdisplay"
      # "skim"
      # "microsoft-remote-desktop"
      "wpsoffice-cn"
      "karabiner-elements"
      # "ticktick"
      "squirrel-app"
      # "trae"
      "linearmouse"
      "tailscale-app"
      # "moonlight"
      "raycast"
      "wechat"
      "google-chrome"
      "feishu"
      "tencent-meeting"
      # "dingtalk"
      "orbstack"
      "iina"
      "iterm2"
      "snipaste"
      # "neteasemusic"
    ];
  };
}
