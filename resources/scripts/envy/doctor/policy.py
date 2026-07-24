"""Use the evaluated machine manifest for policy-aware diagnostics."""

from envy.evaluation import machine_manifest, manifest_software_groups


def app_policy(spec) -> tuple[bool, str]:
    """Return whether an AppSpec is expected and why it is disabled."""
    manifest = machine_manifest()
    if not manifest:
        return True, ""

    cask_effective, cask_excluded = _selection(manifest, "homebrew.system.cask")
    if _selection_disabled(spec.casks, cask_effective, cask_excluded):
        return False, "cask is excluded from the selected machine"

    formula_effective, formula_excluded = _selection(
        manifest, "homebrew.system.formula"
    )
    if _selection_disabled(spec.brews, formula_effective, formula_excluded):
        return False, "formula is excluded from the selected machine"

    package_effective, package_excluded = _selection(manifest, "nix.user.package")
    if _selection_disabled(spec.packages, package_effective, package_excluded):
        return False, "Nix package is excluded from the selected machine"
    return True, ""


def _selection(manifest, group_id: str) -> tuple[list[str], list[str]]:
    group = manifest_software_groups(manifest).get(group_id, {})
    selection = group.get("selection") if isinstance(group, dict) else None
    if not isinstance(selection, dict):
        return [], []
    effective = []
    for item in selection.get("effective", []):
        if isinstance(item, dict) and isinstance(item.get("id"), str):
            effective.append(item["id"])
    excluded = [item for item in selection.get("exclude", []) if isinstance(item, str)]
    return effective, excluded


def _selection_disabled(names: list[str], effective: list[str], excluded: list[str]) -> bool:
    """Treat an app as disabled only when policy explicitly excludes all selectors."""
    requested = set(names)
    return bool(requested) and not requested.intersection(effective) and requested.issubset(excluded)
