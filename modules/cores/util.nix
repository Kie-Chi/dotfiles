{ pkgs, lib, ... }:

let
  dotfilesSrc = lib.cleanSource ../../.;
  scriptsPath = dotfilesSrc + "/resources/scripts";
  # helpersPath = dotfilesSrc + "/resources/helpers";


  packageScriptsFromDir = dirPath:
    let dirContents = builtins.readDir dirPath;
    in
    lib.mapAttrsToList
      (scriptName: fileType:
        if fileType == "regular" then
          pkgs.writeShellScriptBin scriptName (builtins.readFile (dirPath + "/${scriptName}"))
        else
          null
      )
      dirContents;
  packagedScripts = packageScriptsFromDir scriptsPath;
  # packagedHelpers = packageScriptsFromDir helpersPath;

in
{
  home.packages = packagedScripts;
  home.file.".config/ccli/prompt".source = ../../files/ccli/prompt;
}
