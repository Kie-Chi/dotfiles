{ academicResearchSkills, academicResearchSkillsCodex, lib, machinePlatform, ... }:

{
  imports = [
    ./claude.nix
    ./skills.nix
    ./tools.nix
  ] ++ lib.optionals (machinePlatform == "linux") [ ./linux.nix ];

  # Shared agent defaults. Provider modules define reusable options; this file
  # decides which providers and skills are part of the shared environment.
  agents = {
    claude = {
      # Keep this security-sensitive policy visible in the Nix machine
      # configuration instead of exposing machine-specific agent toggles.
      extraArgs = [ "--dangerously-skip-permissions" ];
      ccliAlias = true;
    };

    skills = {
      catalog = import ./skills/catalog.nix {
        inherit academicResearchSkills academicResearchSkillsCodex;
      };
      active = [
        "academic-research-suite"
        "academic-paper"
        "academic-paper-reviewer"
        "academic-pipeline"
        "deep-research"
      ];
    };
  };
}
