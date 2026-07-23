"""Compose common and local-platform application schemas."""

from envy.schemas.common.apps import (
    APP_ALIASES as COMMON_APP_ALIASES,
    APP_SPECS as COMMON_APP_SPECS,
    AppSpec,
    EXPECTED_EXTENSIONS,
    PermissionReq,
)
from envy.utils import platform_name


if platform_name() == "darwin":
    from envy.schemas.darwin.apps import (
        APP_ALIASES as PLATFORM_APP_ALIASES,
        APP_SPECS as PLATFORM_APP_SPECS,
    )
else:
    from envy.schemas.linux.apps import (
        APP_ALIASES as PLATFORM_APP_ALIASES,
        APP_SPECS as PLATFORM_APP_SPECS,
    )


ALL_APP_SPECS = COMMON_APP_SPECS | PLATFORM_APP_SPECS
APP_ALIASES = COMMON_APP_ALIASES | PLATFORM_APP_ALIASES


__all__ = [
    "ALL_APP_SPECS",
    "APP_ALIASES",
    "AppSpec",
    "EXPECTED_EXTENSIONS",
    "PermissionReq",
]
