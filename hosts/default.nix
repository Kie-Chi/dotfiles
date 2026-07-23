{ lib, ... }:

{
  # Only defaults that are meaningful for every new machine belong here.
  # Identity, paths, endpoints, and machine software policy are written in the
  # concrete hosts/machines/<id>.nix file by `envy config` or by the user.
  envy.proxy.mode = lib.mkDefault "none";
  envy.proxy.tun = lib.mkDefault false;
  envy.vscode.mode = lib.mkDefault "remote";
  envy.llm.steps.model = lib.mkDefault "step-3.7-flash";
  envy.llm.deepseek.url = lib.mkDefault "https://api.deepseek.com";
  envy.llm.deepseek.model = lib.mkDefault "deepseek-v4-pro";
}
