{ config, pkgs, lib, ... }:

let
  # Helper Function to package a macOS App from a .zip archive
  #   - pname:   The package name (e.g., "gui-for-singbox").
  #   - version: The package version (e.g., "1.19.0").
  #   - url:     The full URL to the .zip file. You can use `${version}` inside.
  #   - hash:    The SHA256 hash of the .zip file.
  #   - appName: The name of the .app bundle inside the zip (e.g., "GUI.for.SingBox.app").
  makeMacZipApp = { pname, version, url, hash, appName }:
    pkgs.stdenv.mkDerivation rec {
      inherit pname version;
      src = pkgs.fetchurl {
        inherit url hash;
      };
      nativeBuildInputs = [ pkgs.unzip ];
      dontStrip = true;
      dontFixup = true;
      sourceRoot = ".";
      installPhase = ''
        mkdir -p $out/Applications
        cp -r "${appName}" $out/Applications/
      '';
    };
  
  
  guiForSingbox = makeMacZipApp rec {
    pname = "gui-for-singbox";
    version = "1.19.0";
    url = "https://github.com/GUI-for-Cores/GUI.for.SingBox/releases/download/v${version}/GUI.for.SingBox-darwin-arm64.zip";
    hash = "sha256-pm4Kxg6aUsZ7emAyaNEQ80Dn9c8dttvxoQPJgnPBKqE=";
    appName = "GUI.for.SingBox.app";
  };  
  wireguard-macos-app = makeMacZipApp rec {
    pname = "wireguard-macos-app";
    version = "1.0.16";
    url = "https://github.com/mintc2/wireguard-macos-app/releases/download/v${version}/wireguard_${lib.replaceStrings ["."] ["_"] version}.zip";
    hash = "sha256-34Tqt9W5kRZNUIwaTIWW1Cikz2ogzCAXFq3Azw9r7XU=";
    appName = "WireGuard.app";
  };

in
{
  home.packages = [ 
    # Add WireGuard to your packages to install it
    wireguard-macos-app
    # guiForSingbox 
  ];

  # home.file."${userConfigDir}/subscribes.yaml" = {
  #   text = ''
  #     - name: MySub
  #       url: "sub url"
  #       enabled: true
  #   '';
  # };

  # home.activation.linkGuiForSingbox = lib.hm.dag.entryAfter ["writeBoundary"] ''
  #   APP_TARGET="${config.home.homeDirectory}/Applications/Home Manager Apps/GUI.for.SingBox.app"
  #   USER_DATA="${config.home.homeDirectory}/.config/gui-for-singbox-data"
  #   APP_SOURCE="${guiForSingbox}/Applications/GUI.for.SingBox.app"

  #   echo "Ensuring persistent data directory..."
  #   mkdir -p "$USER_DATA/subscribes"
  #   mkdir -p "$USER_DATA/sing-box"
  #   ln -sf "${pkgs.sing-box}/bin/sing-box" "$USER_DATA/sing-box/sing-box"
  #   rm -rf "$APP_TARGET"
  #   mkdir -p "$APP_TARGET/Contents/MacOS"
  #   ln -s "$APP_SOURCE/Contents/Info.plist" "$APP_TARGET/Contents/Info.plist"
  #   ln -s "$APP_SOURCE/Contents/PkgInfo" "$APP_TARGET/Contents/PkgInfo"
  #   ln -s "$APP_SOURCE/Contents/Resources" "$APP_TARGET/Contents/Resources"
  #   cp "$APP_SOURCE/Contents/MacOS/GUI.for.SingBox" "$APP_TARGET/Contents/MacOS/GUI.for.SingBox"
  #   chmod +w "$APP_TARGET/Contents/MacOS/GUI.for.SingBox"
  #   ln -sfn "$USER_DATA" "$APP_TARGET/Contents/MacOS/data"
  #   chmod -R 755 "$APP_TARGET"
  # '';
  
}