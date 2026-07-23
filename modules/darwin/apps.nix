{ ... }:

{
  # Software stays grouped by its owning module. Individual machines remove
  # entries with envy.homebrew.<kind>.exclude instead of per-app enable flags.
  envy.homebrew = {
    brews.include = [
      "gh"
      "chsrc"
      "gum"
      "proxychains-ng"
      "uv"
      "java"
      "go"
    ];

    casks.include = [
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
      "snipaste"
      "zotero"
      # "neteasemusic"
    ];
  };
}
