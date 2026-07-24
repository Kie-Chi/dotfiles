{ config, lib, ... }:

{
  envy.linux.software.url.artifacts.include = lib.optionals
    (config.envy.linux.option == "desktop")
    [
      {
        id = "wechat";
        name = "WeChat";
        parameters = {
          format = "deb";
          packageName = "wechat";
          url = "https://dldir1v6.qq.com/weixin/Universal/Linux/WeChatLinux_x86_64.deb";
        };
      }
    ];
}
