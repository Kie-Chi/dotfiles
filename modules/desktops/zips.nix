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
  home.packages = [ 
    # guiForSingbox
  ];

  # home.file."${userConfigDir}/subscribes.yaml" = {
  #   text = ''
  #     - name: MySub
  #       url: "sub url"
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
    rm -rf "$APP_TARGET"
    mkdir -p "$APP_TARGET/Contents/MacOS"
    ln -s "$APP_SOURCE/Contents/Info.plist" "$APP_TARGET/Contents/Info.plist"
    ln -s "$APP_SOURCE/Contents/PkgInfo" "$APP_TARGET/Contents/PkgInfo"
    ln -s "$APP_SOURCE/Contents/Resources" "$APP_TARGET/Contents/Resources"
    cp "$APP_SOURCE/Contents/MacOS/GUI.for.SingBox" "$APP_TARGET/Contents/MacOS/GUI.for.SingBox"
    chmod +w "$APP_TARGET/Contents/MacOS/GUI.for.SingBox"
    ln -sfn "$USER_DATA" "$APP_TARGET/Contents/MacOS/data"
    chmod -R 755 "$APP_TARGET"
  '';
}