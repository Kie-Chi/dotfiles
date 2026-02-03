{ config, pkgs, lib, ... }:

let
  guiForSingbox = pkgs.stdenv.mkDerivation rec {
    pname = "gui-for-singbox";
    version = "1.19.0";
    src = pkgs.fetchurl {
      url = "https://github.com/GUI-for-Cores/GUI.for.SingBox/releases/download/v${version}/GUI.for.SingBox-darwin-arm64.zip";
      hash = "sha256-pm4Kxg6aUsZ7emAyaNEQ80Dn9c8dttvxoQPJgnPBKqE="; 
    };
    nativeBuildInputs = [ pkgs.unzip ];
    dontStrip = true;
    dontFixup = true;
    sourceRoot = ".";
    installPhase = ''
      mkdir -p $out/Applications
      cp -r "GUI.for.SingBox.app" $out/Applications/
    '';
  };
  appInstallPath = "${config.home.homeDirectory}/Applications/Home Manager Apps/GUI.for.SingBox.app";

in
{
  home.packages = [ guiForSingbox ];

  # 2. 如果你想用 Nix 直接管理订阅列表，可以取消注释下面部分
  # home.file."${userConfigDir}/subscribes.yaml" = {
  #   text = ''
  #     - name: MySub
  #       url: "你的订阅链接"
  #       enabled: true
  #   '';
  # };

  home.activation.linkGuiForSingbox = lib.hm.dag.entryAfter ["writeBoundary"] ''
    APP_TARGET="${config.home.homeDirectory}/Applications/Home Manager Apps/GUI.for.SingBox.app"
    USER_DATA="${config.home.homeDirectory}/.config/gui-for-singbox-data"
    APP_SOURCE="${guiForSingbox}/Applications/GUI.for.SingBox.app"

    echo "Ensuring persistent data directory..."
    mkdir -p "$USER_DATA/subscribes"
    mkdir -p "$USER_DATA/sing-box"
    ln -sf "${pkgs.sing-box}/bin/sing-box" "$USER_DATA/sing-box/sing-box"

    # 1. 每次构建先清理旧的包装目录（确保结构是最新的）
    rm -rf "$APP_TARGET"
    mkdir -p "$APP_TARGET/Contents/MacOS"

    # 2. 链接不常变动的只读资源 (Plist, 图标等)
    ln -s "$APP_SOURCE/Contents/Info.plist" "$APP_TARGET/Contents/Info.plist"
    ln -s "$APP_SOURCE/Contents/PkgInfo" "$APP_TARGET/Contents/PkgInfo"
    ln -s "$APP_SOURCE/Contents/Resources" "$APP_TARGET/Contents/Resources"

    # 3. 【关键改动】拷贝二进制文件，而不是链接它
    # 这样程序运行阶段获取的可执行文件路径就会在你的家目录下，而不是 Nix Store
    cp "$APP_SOURCE/Contents/MacOS/GUI.for.SingBox" "$APP_TARGET/Contents/MacOS/GUI.for.SingBox"
    chmod +w "$APP_TARGET/Contents/MacOS/GUI.for.SingBox"

    # 4. 链接数据文件夹
    ln -sfn "$USER_DATA" "$APP_TARGET/Contents/MacOS/data"
    
    # 修复权限
    chmod -R 755 "$APP_TARGET"
  '';
}