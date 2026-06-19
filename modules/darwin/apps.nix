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
      "clash-verge-rev"
      "codex"
      "codex-app"
      "cyberduck"
      "betterdisplay"
      "skim"
      "microsoft-remote-desktop"
      "wpsoffice-cn"
      "karabiner-elements"
      "ticktick"
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
