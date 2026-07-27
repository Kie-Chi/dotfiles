{ config, pkgs, lib, ... }:

let
  # The flake source is already filtered and materialized. Creating another
  # cleanSource here races under Nix 2.34 when flake outputs evaluate in parallel.
  scriptsSrc = ../../resources/scripts;

  # Package single-file scripts, skipping the "envy" entry (it's now a Python package directory)
  packageScriptsFromDir = dirPath:
    let dirContents = builtins.readDir dirPath;
    in
    lib.mapAttrsToList
      (scriptName: fileType:
        if builtins.elem scriptName [ "envy" "ccli" ] then
          null  # handled by a dedicated package/module
        else if fileType == "regular" then
          pkgs.writeShellScriptBin scriptName (builtins.readFile (dirPath + "/${scriptName}"))
        else
          null
      )
      dirContents;

  # Python environment with all envy dependencies
  envyPythonEnv = pkgs.python3.withPackages (ps: [
    ps.typer
    ps.rich
    ps.prompt-toolkit
    ps.pyyaml
  ]);

  # Special package for envy Python CLI — writeShellApplication wraps it with all runtime deps
  envyPackage = pkgs.writeShellApplication {
    name = "envy";
    runtimeInputs = [ envyPythonEnv envyTuiPackage ] ++ (with pkgs; [
      # External tools used by envy commands
      git
      nix
      sops
      age
      ssh-to-age
      jq
      gnupg
      curl
    ]);
    text = ''
      bundled="${scriptsSrc}"
      repo="''${ENVY_DOTFILES:-}"
      if [ -z "$repo" ]; then
        repo=${lib.escapeShellArg config.envy.repository.path}
      fi

      # Prefer repo source unless explicitly using bundled
      if [ -d "$repo/resources/scripts/envy" ] && [ "''${ENVY_USE_BUNDLED:-0}" != "1" ]; then
        export PYTHONPATH="$repo/resources/scripts:$bundled:''${PYTHONPATH:-}"
      else
        export PYTHONPATH="$bundled:''${PYTHONPATH:-}"
      fi

      if [ "''${1:-}" = "tui" ] && [ "$#" -eq 1 ] \
        && [ -z "''${_ENVY_COMPLETE:-}" ] \
        && command -v envy-tui >/dev/null 2>&1; then
        shift
        exec envy-tui "$@"
      fi

      exec python3 -m envy "$@"
    '';
  };

  envyTuiPackage = pkgs.rustPlatform.buildRustPackage {
    pname = "envy-tui";
    version = "0.1.0";
    src = ../../tools/envy-tui;
    cargoLock.lockFile = ../../tools/envy-tui/Cargo.lock;
    meta = {
      description = "Ratatui frontend for the Envy dotfiles manager";
      mainProgram = "envy-tui";
    };
  };

  packagedScripts = lib.filter (x: x != null) (packageScriptsFromDir scriptsSrc);

in
{
  envy.software.nix.packages.include = packagedScripts ++ [ envyPackage envyTuiPackage ];

  envy.software.nix.packages.references = {
    "mirror-env.sh" = "local:resources/scripts/mirror-env.sh";
    ppack = "local:resources/scripts/ppack";
    scrctl = "local:resources/scripts/scrctl";
    spk = "local:resources/scripts/spk";
    envy = "local:modules/cores/util.nix#envyPackage";
    "envy-tui" = "local:modules/cores/util.nix#envyTuiPackage";
  };
}
