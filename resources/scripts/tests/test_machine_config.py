import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from envy import config


class MachineConfigTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.machines = self.root / "hosts" / "darwin"
        self.machines.mkdir(parents=True)
        self.machine = self.machines / "test-mac.nix"
        self.machine.write_text(
            """{ ... }:

{
  imports = [ ../default.nix ];
  envy.packages.home.exclude = [ "okular" ];
}
"""
        )

    def tearDown(self):
        self.tempdir.cleanup()

    def values(self):
        values = {field.path: field.default_fn() for field in config.MACHINE_FIELDS}
        values["envy.user.name"] = "chi"
        values["envy.user.home"] = "/Users/chi"
        values["envy.repository.path"] = "/Users/chi/.dotfiles"
        values["envy.git.name"] = "Chi"
        values["envy.git.email"] = "chi@example.com"
        values["envy.llm.steps.url"] = "https://example.com"
        values["envy.darwin.proxy.tun"] = "false"
        return values

    def machine_file_patch(self):
        return patch.object(
            config,
            "versioned_machine_file",
            side_effect=lambda machine_id=None: self.machines / f"{machine_id or 'test-mac'}.nix",
        )

    def test_writer_preserves_hand_maintained_machine_policy(self):
        with self.machine_file_patch(), patch.object(
            config, "current_machine_id", return_value="test-mac"
        ), patch.object(config, "set_device_machine_id"):
            config.write_machine_nix(self.values())

        text = self.machine.read_text()
        self.assertIn('envy.packages.home.exclude = [ "okular" ];', text)
        self.assertIn(config.MANAGED_START, text)
        self.assertIn("envy.darwin.proxy.tun = false;", text)

    def test_second_write_replaces_only_managed_block(self):
        values = self.values()
        with self.machine_file_patch(), patch.object(
            config, "current_machine_id", return_value="test-mac"
        ), patch.object(config, "set_device_machine_id"):
            config.write_machine_nix(values)
            values["envy.vscode.mode"] = "local"
            config.write_machine_nix(values)

        text = self.machine.read_text()
        self.assertEqual(text.count(config.MANAGED_START), 1)
        self.assertIn('envy.vscode.mode = "local";', text)
        self.assertIn('envy.packages.home.exclude = [ "okular" ];', text)

    def test_reader_understands_strings_and_booleans(self):
        with self.machine_file_patch(), patch.object(
            config, "current_machine_id", return_value="test-mac"
        ), patch.object(config, "set_device_machine_id"):
            config.write_machine_nix(self.values())
            values = config.read_machine_nix()

        self.assertEqual(values["envy.user.name"], "chi")
        self.assertEqual(values["envy.darwin.proxy.tun"], "false")

    def test_writer_uses_schema_default_for_hidden_conditional_field(self):
        values = self.values()
        values.pop("envy.darwin.proxy.tun")
        with self.machine_file_patch(), patch.object(
            config, "current_machine_id", return_value="test-mac"
        ), patch.object(config, "set_device_machine_id"):
            config.write_machine_nix(values)
        self.assertIn("envy.darwin.proxy.tun = false;", self.machine.read_text())

    def test_refine_migrates_legacy_config_into_machine_block(self):
        legacy = self.root / "legacy-config.nix"
        legacy.write_text(
            """{
  home.user = "chi";
  home.dir = "/Users/chi";
  dotfiles.path = "/Users/chi/.dotfiles";
  git.name = "Chi";
  git.email = "chi@example.com";
  proxy.status = "none";
  proxy.tun = "false";
  vscode.mode = "remote";
  llm.steps.url = "https://example.com";
  llm.steps.model = "step-model";
  llm.deepseek.url = "https://api.deepseek.com";
  llm.deepseek.model = "deepseek-model";
}
"""
        )
        with self.machine_file_patch(), patch.object(
            config, "current_machine_id", return_value="test-mac"
        ), patch.object(config, "LEGACY_USER_CONFIG", legacy), patch.object(
            config, "LEGACY_SYSTEM_CONFIG", self.root / "missing-system-config"
        ), patch.object(config, "DOTFILES_DIR", self.root), patch.object(
            config, "set_device_machine_id"
        ):
            report = config.refine_config(write=True)
            values = config.read_machine_nix()

        self.assertTrue(report.ok)
        self.assertEqual(values["envy.user.name"], "chi")
        self.assertEqual(values["envy.llm.steps.model"], "step-model")
        self.assertIn(config.MANAGED_START, self.machine.read_text())


if __name__ == "__main__":
    unittest.main()
