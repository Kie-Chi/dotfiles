{ lib, ... }:

{
  # Only defaults that are meaningful for every new machine belong here.
  # Identity, paths, endpoints, and machine software policy are written in the
  # concrete hosts/<platform>/<id>.nix file by `envy config` or by the user.
  envy.llm.steps.model = lib.mkDefault "step-3.7-flash";
  envy.llm.deepseek.url = lib.mkDefault "https://api.deepseek.com";
  envy.llm.deepseek.model = lib.mkDefault "deepseek-v4-pro";
}
