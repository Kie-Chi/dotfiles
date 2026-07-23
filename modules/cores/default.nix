{ ... }:

{
  imports = [
    ./secrets.nix
    ./base.nix
    ./shell.nix
    ./git.nix
    ./ssh.nix
    ./util.nix
  ];
}
