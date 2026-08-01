import unittest

from envy.schemas.common.config import COMMON_MACHINE_FIELDS
from envy.schemas.darwin.apps import APP_SPECS as DARWIN_APP_SPECS
from envy.schemas.darwin.config import MACHINE_FIELDS as DARWIN_MACHINE_FIELDS
from envy.schemas.linux.apps import APP_SPECS as LINUX_APP_SPECS
from envy.schemas.linux.config import MACHINE_FIELDS as LINUX_MACHINE_FIELDS


class PlatformSchemaTests(unittest.TestCase):
    def test_common_fields_have_no_platform_prefix(self):
        paths = {field.path for field in COMMON_MACHINE_FIELDS}
        self.assertIn("envy.vscode.mode", paths)
        self.assertIn("envy.mirrors.mode", paths)
        self.assertIn("envy.habits.terminalScratchpad.gesture", paths)
        self.assertIn("envy.habits.globalLauncher.gesture", paths)
        self.assertTrue(all(not path.startswith("envy.darwin.") for path in paths))
        self.assertTrue(all(not path.startswith("envy.linux.") for path in paths))

    def test_darwin_services_exist_only_in_darwin_config_schema(self):
        darwin_paths = {field.path for field in DARWIN_MACHINE_FIELDS}
        linux_paths = {field.path for field in LINUX_MACHINE_FIELDS}
        self.assertEqual(
            {path for path in darwin_paths if ".services." in path},
            {
                "envy.darwin.services.mihomo.mode",
                "envy.darwin.services.mihomo.tun",
                "envy.darwin.services.openssh.mode",
            },
        )
        self.assertFalse(any(".services.mihomo." in path for path in linux_paths))
        self.assertFalse(any(".services.openssh." in path for path in linux_paths))

    def test_darwin_service_modes_share_the_same_semantics(self):
        fields = {field.path: field for field in DARWIN_MACHINE_FIELDS}
        self.assertEqual(
            fields["envy.darwin.services.mihomo.mode"].choices,
            ["none", "manual", "keep"],
        )
        self.assertEqual(
            fields["envy.darwin.services.openssh.mode"].choices,
            ["none", "manual", "keep"],
        )

    def test_linux_app_schema_has_no_darwin_bundle_or_tcc_signals(self):
        self.assertIn("chrome", LINUX_APP_SPECS)
        for spec in LINUX_APP_SPECS.values():
            self.assertEqual(spec.bundles, [])
            self.assertIsNone(spec.bundle_id)
            self.assertEqual(spec.permissions, [])
            self.assertTrue(all("Library/" not in str(path) for path in spec.state_paths))

    def test_darwin_app_schema_keeps_platform_only_signals(self):
        self.assertTrue(DARWIN_APP_SPECS["karabiner"].permissions)
        self.assertTrue(DARWIN_APP_SPECS["zotero"].bundles)
        self.assertEqual(
            DARWIN_APP_SPECS["claude-code"].bundles,
            ["Claude Code URL Handler.app"],
        )
        self.assertEqual(DARWIN_APP_SPECS["wireshark"].bundle_id, "org.wireshark.Wireshark")
        self.assertEqual(DARWIN_APP_SPECS["vscode"].bundles, ["Visual Studio Code.app"])


if __name__ == "__main__":
    unittest.main()
