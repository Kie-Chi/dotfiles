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
  };

  outputs = { self, nixpkgs, home-manager, nixgl, niri-scratchpad-flake, ... }:
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
      repoSecretsPath = ./secrets.nix;
      homeSecretsPath = (builtins.getEnv "HOME") + "/.config/dotfiles/secrets.nix";
      secrets =
        if builtins.pathExists repoSecretsPath
        then import repoSecretsPath
        else if builtins.pathExists homeSecretsPath
        then import homeSecretsPath
        else {};
    in
    {
      homeConfigurations."default" = home-manager.lib.homeManagerConfiguration {
        inherit pkgs;
        extraSpecialArgs = {
          inherit secrets niri-scratchpad-flake nixGLDefault;
        };
        modules = [ ./home.nix ];
      };
    };
}
