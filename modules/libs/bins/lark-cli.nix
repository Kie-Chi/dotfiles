{ pkgs, lib, machinePlatform, ... }:

let
  lark-cli = pkgs.stdenv.mkDerivation rec {
    pname = "lark-cli";
    version = "1.0.64";

    src = pkgs.fetchurl {
      url = "https://github.com/larksuite/cli/releases/download/v${version}/lark-cli-${version}-darwin-arm64.tar.gz";
      hash = "sha256-zcOFWr9VmX8YP88z7GSUlsoZdBjeyYpF/RH6oQLon5U=";
    };

    sourceRoot = ".";
    dontConfigure = true;
    dontBuild = true;
    dontFixup = true;

    installPhase = ''
      runHook preInstall

      mkdir -p "$out/bin" "$out/share/doc/lark-cli"
      cp lark-cli "$out/bin/lark-cli"
      chmod 0755 "$out/bin/lark-cli"
      cp README.md CHANGELOG.md LICENSE "$out/share/doc/lark-cli/"

      runHook postInstall
    '';

    meta = with lib; {
      description = "Feishu/Lark CLI tool";
      homepage = "https://github.com/larksuite/cli";
      license = licenses.mit;
      platforms = [ "aarch64-darwin" ];
      mainProgram = "lark-cli";
    };
  };
in
{
  envy.software.nix.packages.include = lib.optionals (machinePlatform == "darwin") [ lark-cli ];
  envy.software.nix.packages.references = lib.optionalAttrs (machinePlatform == "darwin") {
    "lark-cli" = "local:modules/libs/bins/lark-cli.nix#lark-cli";
  };
}
