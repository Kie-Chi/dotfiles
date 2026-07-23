{ config, lib, ... }:

let
  unique = values: lib.unique values;
  selectPackages = selection: lib.filter
    (package: !(builtins.elem (lib.getName package) selection.exclude))
    (unique selection.include);
  selectStrings = selection: lib.subtractLists selection.exclude (unique selection.include);

  systemPackages = selectPackages config.envy.packages.system;
  fontPackages = selectPackages config.envy.packages.fonts;
  brews = selectStrings config.envy.homebrew.brews;
  casks = selectStrings config.envy.homebrew.casks;
  taps = selectStrings config.envy.homebrew.taps;
in
{
  imports = [ ./options.nix ];

  config = {
    envy.packages.system.effective = systemPackages;
    envy.packages.fonts.effective = fontPackages;
    envy.homebrew.brews.effective = brews;
    envy.homebrew.casks.effective = casks;
    envy.homebrew.taps.effective = taps;

    envy.machine.manifest = {
      id = config.envy.machine.id;
      settings = {
        "envy.user.name" = config.envy.user.name;
        "envy.user.home" = config.envy.user.home;
        "envy.repository.path" = config.envy.repository.path;
        "envy.git.name" = config.envy.git.name;
        "envy.git.email" = config.envy.git.email;
        "envy.proxy.mode" = config.envy.proxy.mode;
        "envy.proxy.tun" = config.envy.proxy.tun;
        "envy.vscode.mode" = config.envy.vscode.mode;
        "envy.llm.steps.url" = config.envy.llm.steps.url;
        "envy.llm.steps.model" = config.envy.llm.steps.model;
        "envy.llm.deepseek.url" = config.envy.llm.deepseek.url;
        "envy.llm.deepseek.model" = config.envy.llm.deepseek.model;
      };
      packages = {
        home = map lib.getName
          config.home-manager.users.${config.envy.user.name}.envy.packages.home.effective;
        system = map lib.getName systemPackages;
        fonts = map lib.getName fontPackages;
      };
      homebrew = {
        inherit brews casks taps;
      };
      inclusions = {
        packages = {
          home = map lib.getName
            config.home-manager.users.${config.envy.user.name}.envy.packages.home.include;
          system = map lib.getName config.envy.packages.system.include;
          fonts = map lib.getName config.envy.packages.fonts.include;
        };
        homebrew = {
          brews = config.envy.homebrew.brews.include;
          casks = config.envy.homebrew.casks.include;
          taps = config.envy.homebrew.taps.include;
        };
      };
      exclusions = {
        packages = {
          home = config.home-manager.users.${config.envy.user.name}.envy.packages.home.exclude;
          system = config.envy.packages.system.exclude;
          fonts = config.envy.packages.fonts.exclude;
        };
        homebrew = {
          brews = config.envy.homebrew.brews.exclude;
          casks = config.envy.homebrew.casks.exclude;
          taps = config.envy.homebrew.taps.exclude;
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
