"""Darwin-only machine and secret fields."""

from envy.schemas.common.config import FieldDef
from envy.schemas.validators import is_url


MACHINE_FIELDS = [
    FieldDef(group="DARWIN_PROXY", dest="machine", path="envy.darwin.proxy.mode",
             prompt="Darwin proxy status", default_fn=lambda: "none",
             choices=["none", "manual", "keep"], required=True),
    FieldDef(group="DARWIN_PROXY", dest="machine", path="envy.darwin.proxy.tun",
             prompt="Darwin proxy TUN status", default_fn=lambda: "false",
             choices=["true", "false"],
             condition=lambda values: values.get("envy.darwin.proxy.mode") != "none",
             nix_type="bool"),
]

SECRET_FIELDS = [
    FieldDef(group="DARWIN_SECRET", dest="secret", yaml_path="proxy/url", path="proxy_url",
             prompt="Proxy URL", default_fn=lambda: "",
             condition=lambda values: values.get("envy.darwin.proxy.mode") != "none",
             validators=[is_url]),
]

LEGACY_CONFIG_PATHS = {
    "envy.darwin.proxy.mode": ("envy.proxy.mode", "proxy.status"),
    "envy.darwin.proxy.tun": ("envy.proxy.tun", "proxy.tun"),
}
OBSOLETE_MACHINE_KEYS: list[str] = []
OBSOLETE_SECRET_PATHS: list[str] = []
