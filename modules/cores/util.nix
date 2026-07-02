{ pkgs, lib, ... }:

let
  scriptsSrc = lib.cleanSource ../../resources/scripts;

  # Package single-file scripts, skipping the "envy" entry (it's now a Python package directory)
  packageScriptsFromDir = dirPath:
    let dirContents = builtins.readDir dirPath;
    in
    lib.mapAttrsToList
      (scriptName: fileType:
        if scriptName == "envy" then
          null  # handled separately as envyPackage
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
    runtimeInputs = [ envyPythonEnv ] ++ (with pkgs; [
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

      # Resolve repo path: env var > config file > default
      if [ -z "$repo" ]; then
        if [ -f "$HOME/.config/dotfiles/config.nix" ]; then
          repo=$(sed -n 's/.*dotfiles\.path[[:space:]]*=[[:space:]]*"\([^"]*\)".*/\1/p' "$HOME/.config/dotfiles/config.nix" 2>/dev/null || true)
        fi
      fi
      if [ -z "$repo" ]; then
        repo="$HOME/.dotfiles"
      fi

      # Prefer repo source unless explicitly using bundled
      if [ -d "$repo/resources/scripts/envy" ] && [ "''${ENVY_USE_BUNDLED:-0}" != "1" ]; then
        export PYTHONPATH="$repo/resources/scripts:$bundled:''${PYTHONPATH:-}"
      else
        export PYTHONPATH="$bundled:''${PYTHONPATH:-}"
      fi

      exec python3 -m envy "$@"
    '';
  };

  packagedScripts = lib.filter (x: x != null) (packageScriptsFromDir scriptsSrc);

in
{
  home.packages = packagedScripts ++ [ envyPackage ];
  home.file.".config/ccli/prompt".source = ../../files/ccli/prompt;
}