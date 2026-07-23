{ inputs }:

let
  system = "x86_64-linux";
  pkgs = import inputs.nixpkgs {
    inherit system;
    config.allowUnfree = true;
  };

  mkConfiguration = machineId: option: desktop: exclude:
    inputs.home-manager.lib.homeManagerConfiguration {
      inherit pkgs;
      extraSpecialArgs = {
        inherit machineId;
        machinePlatform = "linux";
        machineSystem = system;
        academicResearchSkills = inputs.academic-research-skills;
        academicResearchSkillsCodex = inputs.academic-research-skills-codex;
        nixGLDefault = null;
      };
      modules = [
        ../home.nix
        ({ ... }: {
          imports = [ ../hosts/default.nix ];
          envy.user.name = "policy-check";
          envy.user.home = "/home/policy-check";
          envy.repository.path = "/home/policy-check/.dotfiles";
          envy.git.name = "Policy Check";
          envy.git.email = "policy-check@example.com";
          envy.llm.steps.url = "https://example.com";
          envy.llm.steps.model = "model";
          envy.llm.deepseek.url = "https://api.deepseek.com";
          envy.llm.deepseek.model = "model";
          envy.vscode.mode = "remote";
          envy.linux = { inherit option desktop; };
          envy.packages.home = { inherit exclude; };
        })
        inputs.sops-nix.homeManagerModules.sops
        {
          sops.age.keyFile = "/home/policy-check/.config/sops/age/keys.txt";
          sops.age.generateKey = false;
        }
      ];
    };

  server = mkConfiguration "policy-server" "server" "all" [ ];
  none = mkConfiguration "policy-none" "desktop" "none" [ ];
  gnome = mkConfiguration "policy-gnome" "desktop" "gnome" [ ];
  niri = mkConfiguration "policy-niri" "desktop" "niri" [ ];
  all = mkConfiguration "policy-all" "desktop" "all" [ ];
  niriExcluded = mkConfiguration "policy-niri-excluded" "desktop" "niri" [ "niri" ];
  sunshineExcluded = mkConfiguration "policy-sunshine-excluded" "desktop" "gnome" [ "sunshine" ];
  vscodeExcluded = mkConfiguration "policy-vscode-excluded" "desktop" "gnome" [ "vscode" ];
  waydroidExcluded = mkConfiguration "policy-waydroid-excluded" "desktop" "gnome" [ "waydroid" ];

  packageNames = configuration: map inputs.nixpkgs.lib.getName configuration.config.home.packages;
  hasPackage = name: configuration: builtins.elem name (packageNames configuration);
  niriScratchpad = builtins.head (builtins.filter
    (package: inputs.nixpkgs.lib.getName package == "niri-scratchpad")
    niri.config.home.packages);
  hasGnome = configuration:
    builtins.hasAttr "org/gnome/desktop/background" configuration.config.dconf.settings;
  hasNiri = configuration:
    builtins.hasAttr "niri/config.kdl" configuration.config.xdg.configFile;
  hasService = name: configuration:
    builtins.hasAttr name configuration.config.systemd.user.services;
  hasActivation = name: configuration:
    builtins.hasAttr name configuration.config.home.activation;

  serverForbiddenPackages = inputs.nixpkgs.lib.intersectLists
    [ "sunshine" "waydroid" "google-chrome" "fcitx5-with-addons" "vscode" "cursor" "niri" "tilix" ]
    (packageNames server);
  serverForbiddenActivations = inputs.nixpkgs.lib.intersectLists
    [ "installWayDroid" "rimeDeploy" "setupSunshineInput" "swayosdSystemSetup" "niriStartUp" ]
    (builtins.attrNames server.config.home.activation);
in
assert serverForbiddenPackages == [ ];
assert serverForbiddenActivations == [ ];
assert builtins.attrNames server.config.systemd.user.services == [ "sops-nix" ];
assert !hasGnome server && !hasNiri server;
assert !hasGnome none && !hasNiri none;
assert !none.config.programs.gnome-shell.enable;
assert !hasPackage "gnome-shell-extension-sunshinestatus" none;
assert hasGnome gnome && !hasNiri gnome;
assert gnome.config.programs.gnome-shell.enable;
assert hasPackage "quake" gnome;
assert hasPackage "vscode" gnome && gnome.config.programs.vscode.enable;
assert hasPackage "tilix" gnome && !hasPackage "niri" gnome;
assert !hasGnome niri && hasNiri niri;
assert !niri.config.programs.gnome-shell.enable;
assert !hasPackage "gnome-shell-extension-sunshinestatus" niri;
assert hasPackage "niri" niri && hasPackage "niri-scratchpad" niri;
assert hasPackage "screenshot" niri && hasPackage "fix-pipewire" niri;
assert niriScratchpad.meta.mainProgram == "nscratch";
assert !hasPackage "tilix" niri;
assert hasGnome all && hasNiri all;
assert all.config.programs.gnome-shell.enable;
assert !hasPackage "niri" niriExcluded && !hasNiri niriExcluded;
assert !hasPackage "niri-scratchpad" niriExcluded;
assert !hasPackage "screenshot" niriExcluded && !hasPackage "fix-pipewire" niriExcluded;
assert !hasService "swayosd" niriExcluded;
assert !hasActivation "niriStartUp" niriExcluded;
assert !hasActivation "swayosdSystemSetup" niriExcluded;
assert !hasPackage "sunshine" sunshineExcluded;
assert !hasService "sunshine" sunshineExcluded;
assert !hasActivation "setupSunshineInput" sunshineExcluded;
assert !hasPackage "vscode" vscodeExcluded;
assert !vscodeExcluded.config.programs.vscode.enable;
assert !hasActivation "vscodeProfiles" vscodeExcluded;
assert !hasActivation "vscodeRemoteSyncNotice" vscodeExcluded;
assert !hasPackage "waydroid" waydroidExcluded;
assert !hasPackage "waydroid-helper" waydroidExcluded;
assert !hasActivation "installWayDroid" waydroidExcluded;
assert !(builtins.hasAttr "id.waydro.waydroid_helper" waydroidExcluded.config.xdg.desktopEntries);
pkgs.runCommand "envy-linux-policy-boundaries" { } ''
  touch $out
''
