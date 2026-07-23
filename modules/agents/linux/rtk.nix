{ fetchurl, lib, stdenv }:

stdenv.mkDerivation {
  pname = "rtk";
  version = "0.42.2";

  src = fetchurl {
    url = "https://github.com/rtk-ai/rtk/releases/download/v0.42.2/rtk-x86_64-unknown-linux-musl.tar.gz";
    hash = "sha256-F64lkv5tz8YtC8T66onOUg2BiAFYH/CoOUM19yyRFU0=";
  };

  dontUnpack = true;

  installPhase = ''
    runHook preInstall
    mkdir -p $out/bin
    tar xf $src -C $out/bin
    chmod 555 $out/bin/rtk
    runHook postInstall
  '';

  meta = {
    description = "Token-optimized CLI proxy for filtering and summarizing LLM context";
    homepage = "https://github.com/rtk-ai/rtk";
    mainProgram = "rtk";
    platforms = [ "x86_64-linux" ];
    license = lib.licenses.mit;
  };
}
