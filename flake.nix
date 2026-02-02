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
  };


  outputs = { self, nixpkgs, home-manager, darwin, ... }@inputs:
    let
      system = "aarch64-darwin";
      envHome = builtins.getEnv "HOME";
      userSecretsPath = envHome + "/.config/dotfiles/secrets.nix";
      systemSecretsPath = "/etc/dotfiles/secrets.nix";

      secrets = 
        if builtins.pathExists userSecretsPath then 
          builtins.trace "DEBUG: Found secrets at USER path: ${userSecretsPath}" (import userSecretsPath)
        else if builtins.pathExists systemSecretsPath then 
          builtins.trace "DEBUG: Found secrets at SYSTEM path: ${systemSecretsPath}" (import systemSecretsPath)
        else 
          builtins.trace "DEBUG: No secrets.nix found! Using empty set." {};
      debugSecrets = builtins.trace "DEBUG: Secrets Content: ${builtins.toJSON secrets}" secrets;
      user = secrets.home.user;
    in
    {
      darwinConfigurations."MacBook-Air" = darwin.lib.darwinSystem {
        inherit system;
        modules = [ 
          # ./modules/darwin/default.nix
          home-manager.darwinModules.home-manager
          {
	    system.stateVersion = 6;          
	    nixpkgs.config.allowUnfree = true;
	    nix.enable = false;
            home-manager.useGlobalPkgs = true;
            home-manager.useUserPackages = true;
            home-manager.users."${user}" = import ./home.nix;
            home-manager.extraSpecialArgs = {
                secrets = debugSecrets;
            };
	    _module.args.secrets = debugSecrets;
          }
        ];
      };
    };
}
