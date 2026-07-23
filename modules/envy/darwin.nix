{ config, lib, ... }:

let
  unique = values: lib.unique values;
  selectPackages = selection: lib.filter
    (package: !(builtins.elem (lib.getName package) selection.exclude))
    (unique selection.include);
  selectStrings = selection: lib.subtractLists selection.exclude (unique selection.include);
  policy = config.envy.darwin;
  systemPackages = selectPackages policy.packages.system;
  fontPackages = selectPackages policy.packages.fonts;
  brews = selectStrings policy.homebrew.brews;
  casks = selectStrings policy.homebrew.casks;
  taps = selectStrings policy.homebrew.taps;
  homePolicy = config.home-manager.users.${config.envy.user.name}.envy.packages.home;
in
{
  imports = [
    ./options.nix
    ./darwin/options.nix
  ];

  config = {
    envy.darwin.packages.system.effective = systemPackages;
    envy.darwin.packages.fonts.effective = fontPackages;
    envy.darwin.homebrew.brews.effective = brews;
    envy.darwin.homebrew.casks.effective = casks;
    envy.darwin.homebrew.taps.effective = taps;

    envy.machine.manifest = {
      id = config.envy.machine.id;
      platform = config.envy.machine.platform;
      system = config.envy.machine.system;
      settings = {
        "envy.user.name" = config.envy.user.name;
        "envy.user.home" = config.envy.user.home;
        "envy.repository.path" = config.envy.repository.path;
        "envy.git.name" = config.envy.git.name;
        "envy.git.email" = config.envy.git.email;
        "envy.llm.steps.url" = config.envy.llm.steps.url;
        "envy.llm.steps.model" = config.envy.llm.steps.model;
        "envy.llm.deepseek.url" = config.envy.llm.deepseek.url;
        "envy.llm.deepseek.model" = config.envy.llm.deepseek.model;
        "envy.darwin.proxy.mode" = policy.proxy.mode;
        "envy.darwin.proxy.tun" = policy.proxy.tun;
        "envy.vscode.mode" = config.envy.vscode.mode;
      };
      packages = {
        home = map lib.getName homePolicy.effective;
        system = map lib.getName systemPackages;
        fonts = map lib.getName fontPackages;
      };
      homebrew = { inherit brews casks taps; };
      inclusions = {
        packages = {
          home = map lib.getName homePolicy.include;
          system = map lib.getName policy.packages.system.include;
          fonts = map lib.getName policy.packages.fonts.include;
        };
        homebrew = {
          brews = policy.homebrew.brews.include;
          casks = policy.homebrew.casks.include;
          taps = policy.homebrew.taps.include;
        };
      };
      exclusions = {
        packages = {
          home = homePolicy.exclude;
          system = policy.packages.system.exclude;
          fonts = policy.packages.fonts.exclude;
        };
        homebrew = {
          brews = policy.homebrew.brews.exclude;
          casks = policy.homebrew.casks.exclude;
          taps = policy.homebrew.taps.exclude;
        };
      };
    };

    environment.systemPackages = systemPackages;
    fonts.packages = fontPackages;
    homebrew = {
      enable = true;
      inherit brews casks taps;
      onActivation = {
        autoUpdate = false;
        upgrade = false;
      };
    };
  };
}
