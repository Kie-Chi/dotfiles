"""envy — dotfiles manager."""

import sys
from pathlib import Path


def _source_info() -> dict:
    """Return info about where envy source is being loaded from."""
    envy_dir = Path(__file__).resolve().parent
    scripts_dir = envy_dir.parent  # resources/scripts/
    in_nix_store = str(scripts_dir).startswith("/nix/store/")
    return {
        "source_dir": str(scripts_dir),
        "in_nix_store": in_nix_store,
    }


def _check_schema_api() -> None:
    """Verify schema API is compatible with this engine."""
    from envy.schemas import CONFIG_SCHEMA_API_VERSION, SUPPORTED_SCHEMA_API_VERSIONS

    if CONFIG_SCHEMA_API_VERSION not in SUPPORTED_SCHEMA_API_VERSIONS:
        from envy import log

        log.error("envy", "schema API version mismatch")
        log.hint(
            f"Schema API: {CONFIG_SCHEMA_API_VERSION}, "
            f"supported: {SUPPORTED_SCHEMA_API_VERSIONS}"
        )
        log.hint("Use ./envy from the dotfiles repo, or run: envy apply")
        sys.exit(1)
