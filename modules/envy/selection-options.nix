{ lib }:

let
  inherit (lib) mkOption types;
  softwareItem = types.submodule {
    options = {
      id = mkOption {
        type = types.nonEmptyStr;
        description = "Stable identifier used by machine exclusions.";
      };
      name = mkOption {
        type = types.nonEmptyStr;
        description = "Package name in the source ecosystem.";
      };
      version = mkOption {
        type = types.nullOr types.nonEmptyStr;
        default = null;
        description = "Pinned package version, when one is declared.";
      };
      ref = mkOption {
        type = types.nullOr types.nonEmptyStr;
        default = null;
        description = "Canonical Envy software reference, when available.";
      };
      parameters = mkOption {
        type = types.attrsOf types.anything;
        default = { };
        description = "Structured installer-specific parameters.";
      };
    };
  };
in
{
  inherit softwareItem;

  packageSelection = description: {
    include = mkOption {
      type = types.listOf types.package;
      default = [ ];
      inherit description;
    };
    exclude = mkOption {
      type = types.listOf types.str;
      default = [ ];
      description = "Package names removed from ${description}; exclusions win over inclusions.";
    };
    effective = mkOption {
      type = types.listOf types.package;
      readOnly = true;
      description = "Final ${description} after de-duplication and exclusions.";
    };
  };

  stringSelection = description: {
    include = mkOption {
      type = types.listOf types.str;
      default = [ ];
      inherit description;
    };
    exclude = mkOption {
      type = types.listOf types.str;
      default = [ ];
      description = "Entries removed from ${description}; exclusions win over inclusions.";
    };
    effective = mkOption {
      type = types.listOf types.str;
      readOnly = true;
      description = "Final ${description} after de-duplication and exclusions.";
    };
  };

  itemSelection = description: {
    include = mkOption {
      type = types.listOf softwareItem;
      default = [ ];
      inherit description;
    };
    exclude = mkOption {
      type = types.listOf types.str;
      default = [ ];
      description = "Stable item IDs removed from ${description}; exclusions win over inclusions.";
    };
    effective = mkOption {
      type = types.listOf softwareItem;
      readOnly = true;
      description = "Final ${description} after de-duplication and exclusions.";
    };
  };
}
