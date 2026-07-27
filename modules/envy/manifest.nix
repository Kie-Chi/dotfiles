{ lib }:

let
  packageItem = references: package:
    let
      name = lib.getName package;
      version = lib.getVersion package;
    in {
      id = name;
      inherit name;
      version = if version == "" then null else version;
      ref = references.${name} or null;
      parameters = { };
    };

  stringItem = refPrefix: name: {
    id = name;
    inherit name;
    version = null;
    ref = "${refPrefix}/${name}";
    parameters = { };
  };

  normalize = convert: selection: {
    include = map convert selection.include;
    exclude = selection.exclude;
    effective = map convert selection.effective;
  };
in
{
  packageSelection = selection: {
    include = map (packageItem selection.references) selection.include;
    inherit (selection) exclude;
    effective = map (packageItem selection.references) selection.effective;
  };
  itemSelection = selection: {
    inherit (selection) include exclude effective;
  };
  stringSelection = refPrefix: normalize (stringItem refPrefix);

  group = {
    label,
    optionPath,
    ecosystem,
    platforms,
    scope,
    kind,
    installer,
    selection,
    editableInclude ? false,
    editableExclude ? true,
    reconcileInstall ? true,
    reconcileUpgrade ? false,
    reconcileRemove ? false,
  }: {
    inherit label optionPath ecosystem platforms scope kind installer selection;
    editable = {
      include = editableInclude;
      exclude = editableExclude;
    };
    reconcile = {
      install = reconcileInstall;
      upgrade = reconcileUpgrade;
      remove = reconcileRemove;
    };
  };
}
