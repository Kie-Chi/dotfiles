{ ... }:

{
  imports = [
    ./base.nix
    ./apps.nix
    ./terminal.nix
    ./mihomo.nix
    ./openssh.nix

    # Inject macOS command paths into the nix-darwin desktop modules.
    ({ pkgs, ... }: {
      _module.args.sys = {
        cmds = import ../../libs/cmds.nix { inherit pkgs; };
      };
    })
  ];
}
