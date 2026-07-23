import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from envy import config, utils


class DeviceMetadataTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.metadata = self.root / ".device-label"
        self.legacy_selector = self.root / ".config" / "envy" / "machine"
        self.legacy_selector.parent.mkdir(parents=True)
        self.machines = self.root / "hosts" / "machines"
        self.machines.mkdir(parents=True)
        (self.machines / "test-mac.nix").write_text("{ ... }: {}\n")

    def tearDown(self):
        self.tempdir.cleanup()

    def patches(self):
        return (
            patch.object(utils, "DEVICE_LABEL_FILE", self.metadata),
            patch.object(utils, "LEGACY_MACHINE_SELECTOR", self.legacy_selector),
            patch.object(config, "DEVICE_LABEL_FILE", self.metadata),
            patch.object(config, "LEGACY_MACHINE_SELECTOR", self.legacy_selector),
            patch.object(config, "MACHINES_DIR", self.machines),
        )

    def test_machine_selector_is_stored_in_device_toml(self):
        self.metadata.write_text("old_label\n")
        self.legacy_selector.write_text("test-mac\n")
        patches = self.patches()
        with patches[0], patches[1], patches[2], patches[3], patches[4]:
            utils.set_device_machine_id("test-mac")
            values = utils.read_device_metadata()

        self.assertEqual(values["machine_id"], "test-mac")
        self.assertEqual(values["sops_label"], "old_label")
        self.assertIn("[device]", self.metadata.read_text())
        self.assertFalse(self.legacy_selector.exists())

    def test_config_refine_migrates_and_validates_device_metadata(self):
        self.metadata.write_text("test-mac\n")
        self.legacy_selector.write_text("test-mac\n")
        patches = self.patches()
        with patches[0], patches[1], patches[2], patches[3], patches[4]:
            report = config.refine_device_metadata(write=True)
            check = config.refine_device_metadata(write=False)
            values = utils.read_device_metadata()

        self.assertTrue(report.ok)
        self.assertTrue(check.ok)
        self.assertEqual(values["machine_id"], "test-mac")
        self.assertEqual(values["sops_label"], "test_mac")
        self.assertTrue(self.metadata.read_text().startswith("version = 1"))

    def test_config_check_rejects_invalid_toml_without_rewriting_it(self):
        invalid = "version = [\n"
        self.metadata.write_text(invalid)
        patches = self.patches()
        with patches[0], patches[1], patches[2], patches[3], patches[4]:
            report = config.refine_device_metadata(write=False)

        self.assertFalse(report.ok)
        self.assertEqual(self.metadata.read_text(), invalid)


if __name__ == "__main__":
    unittest.main()
