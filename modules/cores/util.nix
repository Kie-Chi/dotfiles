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
      home-manager
      nix
      sops
      age
      ssh-to-age
      jq
      gnupg
      curl
    ]);
    text = ''
      export PYTHONPATH="${scriptsSrc}:$${PYTHONPATH:-}"
      exec python3 -m envy "$@"
    '';
  };

  packagedScripts = lib.filter (x: x != null) (packageScriptsFromDir scriptsSrc);

in
{
  home.packages = packagedScripts ++ [ envyPackage ];
  home.file.".config/ccli/prompt".source = ../../files/ccli/prompt;
}