{ lib, machinePlatform, ... }:

{
  imports = [
    ./npm.nix
    ./pypi.nix
  ] ++ lib.optionals (machinePlatform == "linux") [
    ./linux/native.nix
    ./linux/artifacts.nix
  ];
}
