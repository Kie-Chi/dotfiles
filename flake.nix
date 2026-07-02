{
  description = "Chi's Config";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
    darwin.url = "github:LnL7/nix-darwin";
    darwin.inputs.nixpkgs.follows = "nixpkgs";
    home-manager = {
      url = "github:nix-community/home-manager";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    sops-nix.url = "github:Mic92/sops-nix";
  };


  outputs = { self, nixpkgs, home-manager, darwin, sops-nix, ... }@inputs:
    let
      system = "aarch64-darwin";
      envHome = builtins.getEnv "HOME";
      userConfigPath = envHome + "/.config/dotfiles/config.nix";
      systemConfigPath = "/etc/dotfiles/config.nix";

      cfg =
        if builtins.pathExists userConfigPath then
          builtins.trace "DEBUG: Found config at USER path: ${userConfigPath}" (import userConfigPath)
        else if builtins.pathExists systemConfigPath then
          builtins.trace "DEBUG: Found config at SYSTEM path: ${systemConfigPath}" (import systemConfigPath)
        else
          builtins.trace "DEBUG: No config.nix found! Using empty set." {};
      debugCfg = builtins.trace "DEBUG: Config Content: ${builtins.toJSON cfg}" cfg;
      user = cfg.home.user;
      ageKeyPath = "/Users/${user}/Library/Application Support/sops/age/keys.txt";
      debugAgeKey = builtins.trace "DEBUG: sops age key path: ${ageKeyPath}" ageKeyPath;
    in
    {
      darwinConfigurations."MacBook-Air" = darwin.lib.darwinSystem {
        inherit system;
        modules = [
          sops-nix.darwinModules.sops
          ./modules/darwin/default.nix
          home-manager.darwinModules.home-manager
          {
            home-manager.useGlobalPkgs = true;
            home-manager.useUserPackages = true;
            home-manager.users."${user}" = import ./home.nix;
            home-manager.backupFileExtension = "backup";
            home-manager.extraSpecialArgs = {
              cfg = debugCfg;
            };
            _module.args.cfg = debugCfg;
            home-manager.sharedModules = [
              sops-nix.homeManagerModules.sops
              {
                sops.age.keyFile = debugAgeKey;
                sops.age.generateKey = false;
              }
            ];
          }
        ];
      };

      # --- devShell for setup environment ---
      devShells.${system}.default = nixpkgs.legacyPackages.${system}.mkShell {
        packages = with nixpkgs.legacyPackages.${system}; [
          jq
          sops
          age
          ssh-to-age
          (python3.withPackages (ps: [
            ps.typer
            ps.rich
            ps.prompt-toolkit
            ps.pyyaml
          ]))
          git
          curl
          gnupg
        ] ++ [ inputs.home-manager.packages.${system}.default ];
        shellHook = ''
          export PYTHONPATH="${toString ./.}/resources/scripts:$PYTHONPATH"
          echo "[DEBUG] devShell: setup environment ready"
          echo "[DEBUG] Available tools: jq, sops, age, ssh-to-age, python3, typer, rich, prompt_toolkit, home-manager"
        '';
      };
    };
}
