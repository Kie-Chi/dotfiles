{ lib }:

let
  packageItem = package:
    let version = lib.getVersion package;
    in {
      id = lib.getName package;
      name = lib.getName package;
      version = if version == "" then null else version;
      ref = null;
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
  packageSelection = normalize packageItem;
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
