{
  description = "Chi's Config";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
    home-manager = {
      url = "github:nix-community/home-manager";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    nixgl.url = "github:nix-community/nixGL";
    niri-scratchpad-flake = {
      url = "github:gvolpe/niri-scratchpad";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    sops-nix.url = "github:Mic92/sops-nix";
  };

  outputs = { self, nixpkgs, home-manager, nixgl, niri-scratchpad-flake, sops-nix, ... }@inputs:
    let
      system = "x86_64-linux";
      pkgs = import nixpkgs {
        inherit system;
        config.allowUnfree = true;
      };
      nixGLDefault = (import nixgl {
        inherit pkgs;
        enable32bits = pkgs.stdenv.hostPlatform.isx86;
        enableIntelX86Extensions = pkgs.stdenv.hostPlatform.system == "x86_64-linux";
      }).auto.nixGLDefault;

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
      ageKeyPath = "/home/${user}/.config/sops/age/keys.txt";
    in
    {
      homeConfigurations."default" = home-manager.lib.homeManagerConfiguration {
        inherit pkgs;
        extraSpecialArgs = {
          cfg = debugCfg;
          niri-scratchpad-flake = niri-scratchpad-flake;
          nixGLDefault = nixGLDefault;
        };
        modules = [
          ./home.nix
          sops-nix.homeManagerModules.sops
          {
            sops.age.keyFile = ageKeyPath;
            sops.age.generateKey = false;
            _module.args.cfg = debugCfg;
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
          python3
          python3Packages.rich
          python3Packages.prompt-toolkit
          python3Packages.pyyaml
          git
          curl
          gnupg
        ];
        shellHook = ''
          echo "[DEBUG] devShell: setup environment ready"
          echo "[DEBUG] Available tools: jq, sops, age, ssh-to-age, python3, rich, prompt_toolkit"
        '';
      };
    };
}