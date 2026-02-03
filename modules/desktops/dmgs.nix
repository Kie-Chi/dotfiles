{ config, pkgs, lib, ... }:

let
  v2rayNApp = pkgs.stdenv.mkDerivation {
    pname = "v2rayN";
    version = "7.17.3";
    src = pkgs.fetchurl {
      url = "https://github.com/2dust/v2rayN/releases/download/7.17.3/v2rayN-macos-arm64.dmg";
      sha256 = "sha256-EGWDManMYMdtzCb5Es70GoqSB5O4fkLtEZufZe/TYFc=";
    };
    nativeBuildInputs = with pkgs; [ undmg ];
    sourceRoot = ".";
    installPhase = ''
      mkdir -p $out/Applications
      cp -r *.app $out/Applications
    '';
    dontStrip = true;
    dontFixup = true;
    dontPatchELF = true;
    meta = with lib; {
      description = "A GUI client for V2Ray/Xray/sing-box";
      homepage = "https://github.com/2dust/v2rayN";
      license = licenses.gpl3;
      platforms = platforms.darwin;
    };
  };
in
{
  home.packages = with pkgs; [
    # v2rayNApp
  ];
}