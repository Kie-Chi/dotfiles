{ lib }:

let
  inherit (lib) mkOption types;
in
{
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
}
