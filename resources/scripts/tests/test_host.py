import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from envy import host
from envy import utils


class HostInitTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.default = self.root / "hosts" / "default.nix"
        self.machines = self.root / "hosts" / "darwin"
        self.default.parent.mkdir(parents=True)
        self.default.write_text('{ ... }: { envy.software.nix.packages.exclude = [ "okular" ]; }\n')

    def tearDown(self):
        self.tempdir.cleanup()

    def test_import_mode_creates_small_override_module(self):
        with patch.object(host, "DEFAULT_MACHINE", self.default), patch.object(
            host, "MACHINES_DIR", self.machines
        ), patch.object(host, "set_device_machine_id") as select:
            target = host.initialize_machine("work-macbook", "import")
        self.assertIn("imports = [ ../default.nix ];", target.read_text())
        self.assertIn("envy.*", target.read_text())
        select.assert_called_once_with("work-macbook")

    def test_copy_mode_snapshots_default_policy(self):
        with patch.object(host, "DEFAULT_MACHINE", self.default), patch.object(
            host, "MACHINES_DIR", self.machines
        ), patch.object(host, "set_device_machine_id") as select:
            target = host.initialize_machine("offline-macbook", "copy")
        text = target.read_text()
        self.assertIn("does not inherit later default policy changes", text)
        self.assertIn('envy.software.nix.packages.exclude = [ "okular" ];', text)
        select.assert_called_once_with("offline-macbook")

    def test_machine_id_validation_rejects_git_ref_punctuation(self):
        with self.assertRaises(Exception):
            host.validate_machine_id("darwin:work")

    def test_machine_completion_lists_current_platform_hosts(self):
        self.machines.mkdir(parents=True)
        (self.machines / "work-macbook.nix").write_text("{ ... }: { }\n")
        (self.machines / "home-macbook.nix").write_text("{ ... }: { }\n")
        with patch.object(host, "MACHINES_DIR", self.machines), patch.object(
            host, "current_machine_id", return_value="work-macbook"
        ), patch.object(host, "platform_name", return_value="darwin"):
            items = host.complete_machine_ids(None, "work")

        self.assertEqual(items, [("work-macbook", "currently selected")])

    def test_init_mode_completion_is_prefix_filtered(self):
        self.assertEqual(
            host.complete_init_modes(None, "i"),
            [("import", "inherit future changes from hosts/default.nix")],
        )

    def test_darwin_flake_target_uses_path_source_for_untracked_machine(self):
        with patch.object(utils, "PLATFORM", "darwin"), patch.object(
            utils, "current_machine_id", return_value="work-macbook"
        ):
            self.assertEqual(utils.flake_target(), "path:.#work-macbook")

    def test_platform_machine_paths_and_linux_attributes(self):
        with patch.object(utils, "HOSTS_DIR", self.root / "hosts"), patch.object(
            utils, "PLATFORM", "linux"
        ), patch.object(utils, "current_machine_id", return_value="workstation"):
            self.assertEqual(
                utils.machine_config_file(),
                self.root / "hosts" / "linux" / "workstation.nix",
            )
            self.assertEqual(
                utils.machine_manifest_attr(),
                "path:.#homeConfigurations.workstation.config.envy.machine.manifest",
            )
            self.assertEqual(
                utils.machine_build_attr(),
                "path:.#homeConfigurations.workstation.activationPackage",
            )


if __name__ == "__main__":
    unittest.main()
