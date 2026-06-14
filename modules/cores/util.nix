{ pkgs, lib, ... }:

let
  scriptsSrc = lib.cleanSource ../../resources/scripts;

  # Package single-file scripts, skipping the "dtf" entry (it's now a Python package directory)
  packageScriptsFromDir = dirPath:
    let dirContents = builtins.readDir dirPath;
    in
    lib.mapAttrsToList
      (scriptName: fileType:
        if scriptName == "dtf" then
          null  # handled separately as dtfPackage
        else if fileType == "regular" then
          pkgs.writeShellScriptBin scriptName (builtins.readFile (dirPath + "/${scriptName}"))
        else
          null
      )
      dirContents;

  # Python environment with all dtf dependencies
  dtfPythonEnv = pkgs.python3.withPackages (ps: [
    ps.typer
    ps.rich
    ps.prompt-toolkit
    ps.pyyaml
  ]);

  # Special package for dtf Python CLI — writeShellApplication wraps it with all runtime deps
  dtfPackage = pkgs.writeShellApplication {
    name = "dtf";
    runtimeInputs = [ dtfPythonEnv ] ++ (with pkgs; [
      # External tools used by dtf commands
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
      export PYTHONPATH="${scriptsSrc}:$${PYTHONPATH:-}"
      exec python3 -m dtf "$@"
    '';
  };

  packagedScripts = lib.filter (x: x != null) (packageScriptsFromDir scriptsSrc);

in
{
  home.packages = packagedScripts ++ [ dtfPackage ];
  home.file.".config/ccli/prompt".source = ../../files/ccli/prompt;
}