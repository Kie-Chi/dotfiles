{ config, pkgs, secrets, lib, ... }:

{
  imports = [
    ./modules/cores
    ./modules/devps
    ./modules/desktops
  ];
  config = {
    home.username = secrets.home.user;
    home.homeDirectory = lib.mkForce "${secrets.home.dir}";
    home.stateVersion = "25.11";
    home.sessionVariables = {
      API_KEY = secrets.agent.apikey;
      DASHSCOPE_API_KEY = secrets.agent.apikey;
      # ANTHROPIC
      ANTHROPIC_BASE_URL = "https://dashscope.aliyuncs.com/apps/anthropic";
      ANTHROPIC_API_KEY = secrets.agent.apikey;
      ANTHROPIC_MODEL = "qwen3.5-plus";
    };
    programs.home-manager.enable = true;
  };
}