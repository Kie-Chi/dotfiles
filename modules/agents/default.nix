{ ... }:

{
  imports = [
    ./claude.nix
    ./skills.nix
  ];

  # This is the machine's agent profile. Provider modules define reusable
  # options; this file decides which providers and skills are active here.
  agents = {
    claude = {
      enable = true;
      # Keep this security-sensitive policy visible in the Nix machine
      # profile instead of exposing it through envy/config.nix.
      extraArgs = [ "--dangerously-skip-permissions" ];
      ccliAlias = true;
    };

    skills = {
      enable = true;
      catalog = import ./skills/catalog.nix;
      active = [ ];
    };
  };
}
