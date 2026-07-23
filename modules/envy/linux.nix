{ config, lib, ... }:

let
  policy = config.envy.linux;
  homePolicy = config.envy.packages.home;
in
{
  imports = [ ./linux/options.nix ];

  config = {
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
        "envy.vscode.mode" = config.envy.vscode.mode;
        "envy.linux.desktop" = policy.desktop;
        "envy.linux.option" = policy.option;
      };
      packages = {
        home = map lib.getName homePolicy.effective;
        system = [ ];
        fonts = [ ];
      };
      homebrew = { brews = [ ]; casks = [ ]; taps = [ ]; };
      inclusions = {
        packages = {
          home = map lib.getName homePolicy.include;
          system = [ ];
          fonts = [ ];
        };
        homebrew = { brews = [ ]; casks = [ ]; taps = [ ]; };
      };
      exclusions = {
        packages = {
          home = homePolicy.exclude;
          system = [ ];
          fonts = [ ];
        };
        homebrew = { brews = [ ]; casks = [ ]; taps = [ ]; };
      };
    };
  };
}
