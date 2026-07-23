"""Use the evaluated machine manifest for policy-aware diagnostics."""

from envy.evaluation import machine_manifest


def app_policy(spec) -> tuple[bool, str]:
    """Return whether an AppSpec is expected and why it is disabled."""
    manifest = machine_manifest()
    if not manifest:
        return True, ""

    homebrew = manifest.get("homebrew", {})
    exclusions = manifest.get("exclusions", {})
    homebrew_exclusions = exclusions.get("homebrew", {})
    package_exclusions = exclusions.get("packages", {})

    if _selection_disabled(
        spec.casks,
        homebrew.get("casks", []),
        homebrew_exclusions.get("casks", []),
    ):
        return False, "cask is excluded from the selected machine"
    if _selection_disabled(
        spec.brews,
        homebrew.get("brews", []),
        homebrew_exclusions.get("brews", []),
    ):
        return False, "formula is excluded from the selected machine"

    packages = manifest.get("packages", {}).get("home", [])
    if _selection_disabled(
        spec.packages,
        packages,
        package_exclusions.get("home", []),
    ):
        return False, "Nix package is excluded from the selected machine"
    return True, ""


def _selection_disabled(names: list[str], effective: list[str], excluded: list[str]) -> bool:
    """Treat an app as disabled only when policy explicitly excludes all selectors."""
    requested = set(names)
    return bool(requested) and not requested.intersection(effective) and requested.issubset(excluded)
