{ ... }: {
  homebrew = {
    enable = true;
    onActivation = {
      autoUpdate = true;
      upgrade = true;
      cleanup = "uninstall"; 
    };

    casks = [
      "wechat"
      "google-chrome"
      "feishu"
      "tencent-meeting"
      "dingtalk"
      "karabiner-elements"
      "orbstack"
      "squirrel-app"
      "iina"
      "iterm2" # 确保安装了 iTerm2
      "snipaste"
    ];
  };
}