{ config, lib, ... }:

let
  profile = (import ./resolve.nix { inherit lib; })
    (import ./catalog.nix).${config.envy.mirrors.mode}
    config.envy.mirrors.overrides;
  homebrewEnv = lib.optionalAttrs (
    config.envy.mirrors.mode == "china" || config.envy.mirrors.overrides ? homebrew
  ) {
    HOMEBREW_API_DOMAIN = profile.homebrew.apiDomain;
    HOMEBREW_BOTTLE_DOMAIN = profile.homebrew.bottleDomain;
    HOMEBREW_BREW_GIT_REMOTE = profile.homebrew.brewGitRemote;
    HOMEBREW_CORE_GIT_REMOTE = profile.homebrew.coreGitRemote;
    HOMEBREW_PIP_INDEX_URL = profile.python.index;
  };
in
{
  nix.settings = {
    substituters = profile.nix.substituters ++ profile.nix.extraSubstituters;
    trusted-substituters = profile.nix.substituters ++ profile.nix.extraSubstituters;
    extra-trusted-public-keys = profile.nix.extraTrustedPublicKeys;
    download-attempts = 3;
  };

  environment.variables = homebrewEnv;
  homebrew.onActivation.extraEnv = homebrewEnv;
}
