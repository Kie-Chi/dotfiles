"""Declarative schema definitions for envy — the single source of truth.

This module contains all declarative data (field definitions, app specs,
permission specs, validators) used by the envy engine and doctor checks.
Separating schema from engine allows version detection and prevents the
chicken-and-egg problem where installed envy cannot see new schema fields.
"""

__version__ = "0.2.0"

# Bump when CONFIG_FIELDS/SECRET_FIELDS change (add/remove/rename fields)
CONFIG_SCHEMA_VERSION = 1

# Bump when FieldDef protocol changes (new parameters, validator calling convention)
CONFIG_SCHEMA_API_VERSION = 1

# Engine checks this on startup
SUPPORTED_SCHEMA_API_VERSIONS = {1}
