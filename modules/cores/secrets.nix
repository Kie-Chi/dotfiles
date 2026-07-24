{ ... }:

{
  # Required by the core activation tasks that update host-level Nix settings.
  sops.secrets.home-passwd = {
    sopsFile = ../../secrets/secrets.yaml;
    key = "home/passwd";
  };
}
