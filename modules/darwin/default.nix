{ ... }: {
  imports = [
    ../envy/darwin.nix
    ../agents/darwin.nix
    ./base.nix
    ./apps.nix
    ./terminal.nix
    ./proxies.nix

    # Inject sys.cmds (macOS tool paths) into all darwin modules
    ({ pkgs, lib, ... }: {
      _module.args.sys = {
        cmds = import ../libs/cmds.nix;
      };
    })
  ];
}
