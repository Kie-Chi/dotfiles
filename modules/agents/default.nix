{ ... }:

{
  imports = [
    ./claude.nix
    ./skills.nix
  ];

  # This is the machine's agent profile. Provider modules define reusable
  # options; this file decides which providers and skills are active here.
  agents = {
    claude.enable = true;

    skills = {
      enable = true;
      catalog = import ./skills/catalog.nix;
      active = [ ];
    };
  };
}
