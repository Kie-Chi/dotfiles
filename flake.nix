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
    academic-research-skills = {
      url = "github:Imbad0202/academic-research-skills";
      flake = false;
    };
    academic-research-skills-codex = {
      url = "github:Imbad0202/academic-research-skills-codex";
      flake = false;
    };
  };


  outputs = { self, nixpkgs, home-manager, darwin, sops-nix, ... }@inputs:
    let
      system = "aarch64-darwin";
      lib = nixpkgs.lib;

      machineDir = ./hosts/machines;
      machineFiles = lib.filterAttrs
        (name: type: type == "regular" && lib.hasSuffix ".nix" name)
        (builtins.readDir machineDir);

      mkDarwinConfiguration = machineId: machineModule: darwin.lib.darwinSystem {
        inherit system;
        specialArgs = { inherit machineId; };
        modules = [
          sops-nix.darwinModules.sops
          ./modules/darwin/default.nix
          machineModule
          home-manager.darwinModules.home-manager
          ({ config, ... }: {
            home-manager.useGlobalPkgs = true;
            home-manager.useUserPackages = true;
            home-manager.users."${config.envy.user.name}" = import ./home.nix;
            home-manager.backupFileExtension = "backup";
            home-manager.extraSpecialArgs = {
              inherit machineId;
              academicResearchSkills = inputs.academic-research-skills;
              academicResearchSkillsCodex = inputs.academic-research-skills-codex;
            };
            home-manager.sharedModules = [
              sops-nix.homeManagerModules.sops
              machineModule
              {
                sops.age.keyFile = "${config.envy.user.home}/Library/Application Support/sops/age/keys.txt";
                sops.age.generateKey = false;
              }
            ];
          })
        ];
      };

      machineConfigurations = lib.mapAttrs'
        (fileName: _:
          let machineId = lib.removeSuffix ".nix" fileName;
          in lib.nameValuePair machineId
            (mkDarwinConfiguration machineId (machineDir + "/${fileName}")))
        machineFiles;

    in
    {
      darwinConfigurations = machineConfigurations;

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
