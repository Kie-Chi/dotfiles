{ pkgs, lib, ... }:

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


  wireguard-macos-app = makeMacZipApp rec {
    pname = "wireguard-macos-app";
    version = "1.0.16";
    url = "https://github.com/mintc2/wireguard-macos-app/releases/download/v${version}/wireguard_${lib.replaceStrings ["."] ["_"] version}.zip";
    hash = "sha256-34Tqt9W5kRZNUIwaTIWW1Cikz2ogzCAXFq3Azw9r7XU=";
    appName = "WireGuard.app";
  };

in
{
  envy.software.nix.packages.include = [ wireguard-macos-app ];
  envy.software.nix.packages.references."wireguard-macos-app" = "local:modules/desktops/darwin/zips.nix#wireguard-macos-app";
}
