{
  description = "Chi's cross-platform configuration";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
    darwin.url = "github:LnL7/nix-darwin";
    darwin.inputs.nixpkgs.follows = "nixpkgs";
    home-manager = {
      url = "github:nix-community/home-manager";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    nixgl.url = "github:nix-community/nixGL";
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

  outputs = { nixpkgs, home-manager, darwin, nixgl, sops-nix, ... }@inputs:
    let
      lib = nixpkgs.lib;
      darwinSystem = "aarch64-darwin";
      linuxSystem = "x86_64-linux";
      darwinMachineDir = ./hosts/darwin;
      linuxMachineDir = ./hosts/linux;
      legacyHome = builtins.getEnv "HOME";
      legacyUserConfigPath = legacyHome + "/.config/dotfiles/config.nix";
      legacySystemConfigPath = "/etc/dotfiles/config.nix";
      legacyConfigPath =
        if legacyHome != "" && builtins.pathExists legacyUserConfigPath then legacyUserConfigPath
        else if builtins.pathExists legacySystemConfigPath then legacySystemConfigPath
        else null;
      legacyConfig = if legacyConfigPath == null then null else import legacyConfigPath;
      machineFiles = directory: lib.filterAttrs
        (name: type: type == "regular" && lib.hasSuffix ".nix" name)
        (builtins.readDir directory);
      darwinMachines = machineFiles darwinMachineDir;
      linuxMachines = machineFiles linuxMachineDir;

      sharedSpecialArgs = machineId: platform: system: {
        inherit machineId;
        machinePlatform = platform;
        machineSystem = system;
        academicResearchSkills = inputs.academic-research-skills;
        academicResearchSkillsCodex = inputs.academic-research-skills-codex;
      };

      mkDarwinConfiguration = fileName: _:
        let
          machineId = lib.removeSuffix ".nix" fileName;
          machineModule = darwinMachineDir + "/${fileName}";
          specialArgs = sharedSpecialArgs machineId "darwin" darwinSystem;
        in darwin.lib.darwinSystem {
          system = darwinSystem;
          inherit specialArgs;
          modules = [
            sops-nix.darwinModules.sops
            ./darwin.nix
            machineModule
            home-manager.darwinModules.home-manager
            ({ config, ... }: {
              home-manager.useGlobalPkgs = true;
              home-manager.useUserPackages = true;
              home-manager.users."${config.envy.user.name}" = import ./home.nix;
              home-manager.backupFileExtension = "backup";
              home-manager.extraSpecialArgs = specialArgs;
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

      mkLinuxConfigurationFor = machineId: machineModule:
        let
          pkgs = import nixpkgs {
            system = linuxSystem;
            config.allowUnfree = true;
          };
          nixGLPackages = import nixgl {
            inherit pkgs;
            enable32bits = pkgs.stdenv.hostPlatform.isx86;
            enableIntelX86Extensions = pkgs.stdenv.hostPlatform.system == "x86_64-linux";
          };
          # Keep hardware auto-detection on the real Linux host.  When another
          # platform (notably Darwin CI/evaluation) inspects this output, use
          # the pure Mesa wrapper so evaluation never tries to build a Linux
          # /proc-based Nvidia detector on the evaluator.
          evaluatorSystem =
            if builtins ? currentSystem then builtins.currentSystem else null;
          nixGLDefault =
            if evaluatorSystem == linuxSystem
            then nixGLPackages.auto.nixGLDefault
            else nixGLPackages.nixGLIntel;
        in home-manager.lib.homeManagerConfiguration {
          inherit pkgs;
          extraSpecialArgs = (sharedSpecialArgs machineId "linux" linuxSystem) // { inherit nixGLDefault; };
          modules = [
            ./home.nix
            machineModule
            sops-nix.homeManagerModules.sops
            ({ config, ... }: {
              sops.age.keyFile = "${config.envy.user.home}/.config/sops/age/keys.txt";
              sops.age.generateKey = false;
            })
          ];
        };

      mkLinuxConfiguration = fileName: _:
        mkLinuxConfigurationFor
          (lib.removeSuffix ".nix" fileName)
          (linuxMachineDir + "/${fileName}");

      legacyLinuxConfiguration =
        if legacyConfig == null then null
        else
          let
            get = path: fallback: lib.attrByPath path fallback legacyConfig;
            user = get [ "home" "user" ] "chi";
            userHome = get [ "home" "dir" ] "/home/${user}";
          in mkLinuxConfigurationFor "default" ({ ... }: {
            imports = [ ./hosts/default.nix ];
            envy.user.name = user;
            envy.user.home = userHome;
            envy.repository.path = get [ "dotfiles" "path" ] "${userHome}/.dotfiles";
            envy.git.name = get [ "git" "name" ] user;
            envy.git.email = get [ "git" "email" ] "${user}@localhost";
            envy.llm.steps.url = get [ "llm" "steps" "url" ] "https://models-proxy.stepfun-inc.com";
            envy.llm.steps.model = get [ "llm" "steps" "model" ] "step-3.7-flash";
            envy.llm.deepseek.url = get [ "llm" "deepseek" "url" ] "https://api.deepseek.com";
            envy.llm.deepseek.model = get [ "llm" "deepseek" "model" ] "deepseek-v4-pro";
            envy.vscode.mode = get [ "vscode" "mode" ] "remote";
            envy.linux.option = get [ "home" "option" ] "desktop";
            envy.linux.desktop = get [ "home" "desktop" ] "all";
          });

      mkDevShell = system: nixpkgs.legacyPackages.${system}.mkShell {
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
          export ENVY_DEV_SHELL=1
          export PYTHONPATH="${./resources/scripts}:$PYTHONPATH"
          echo "[DEBUG] devShell: setup environment ready"
          echo "[DEBUG] Available tools: jq, sops, age, ssh-to-age, python3, typer, rich, prompt_toolkit, home-manager"
        '';
      };

      darwinConfigurations = lib.mapAttrs' (fileName: value:
        lib.nameValuePair (lib.removeSuffix ".nix" fileName)
          (mkDarwinConfiguration fileName value)) darwinMachines;
      namedHomeConfigurations = lib.mapAttrs' (fileName: value:
        lib.nameValuePair (lib.removeSuffix ".nix" fileName)
          (mkLinuxConfiguration fileName value)) linuxMachines;
      # The historical Linux CLI invoked .#default after pulling. Expose that
      # target only when its ignored legacy config exists, and derive identity
      # from that file instead of guessing one of the versioned hosts.
      homeConfigurations = namedHomeConfigurations // lib.optionalAttrs
        (legacyLinuxConfiguration != null)
        { default = legacyLinuxConfiguration; };

      platformOptionBoundaries =
        lib.all
          (configuration:
            configuration.options.envy ? darwin
            && !(configuration.options.envy ? linux))
          (builtins.attrValues darwinConfigurations)
        && lib.all
          (configuration:
            configuration.options.envy ? linux
            && !(configuration.options.envy ? darwin))
          (builtins.attrValues homeConfigurations);
      mkPlatformOptionCheck = system:
        assert platformOptionBoundaries;
        nixpkgs.legacyPackages.${system}.runCommand "envy-platform-option-boundaries" { } ''
          touch $out
        '';
      linuxPolicyCheck = import ./checks/linux-policy.nix { inherit inputs; };
    in
    {
      inherit darwinConfigurations homeConfigurations;

      devShells.aarch64-darwin.default = mkDevShell "aarch64-darwin";
      devShells.x86_64-linux.default = mkDevShell "x86_64-linux";
      checks.aarch64-darwin.platform-option-boundaries = mkPlatformOptionCheck "aarch64-darwin";
      checks.x86_64-linux.platform-option-boundaries = mkPlatformOptionCheck "x86_64-linux";
      checks.x86_64-linux.linux-policy-boundaries = linuxPolicyCheck;
    };
}
