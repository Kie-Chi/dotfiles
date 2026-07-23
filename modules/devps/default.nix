{ lib, machinePlatform, ... }:

{
  # Development tools are exposed as one feature. Only host-system mutation
  # lives in the Linux implementation subtree.
  imports = [
    ./editor.nix
    ./vscode.nix
  ] ++ lib.optionals (machinePlatform == "linux") [ ./linux ];
}
