import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import typer
from rich.console import Console
from typer.main import get_command

from envy import host
from envy.main import cli
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

    def test_all_machine_completion_includes_both_platforms(self):
        hosts = self.root / "hosts"
        (hosts / "darwin").mkdir(parents=True)
        (hosts / "linux").mkdir(parents=True)
        (hosts / "darwin" / "work.nix").write_text("{ ... }: { }\n")
        (hosts / "linux" / "workstation.nix").write_text("{ ... }: { }\n")
        with patch.object(host, "HOSTS_DIR", hosts), patch.object(
            host, "current_machine_id", return_value="work"
        ), patch.object(host, "platform_name", return_value="darwin"):
            items = host.complete_all_machine_ids(None, "work")

        self.assertEqual(items, [
            ("work", "currently selected"),
            ("workstation", "linux machine"),
        ])

    def test_platform_and_matrix_group_completion_are_static_and_filtered(self):
        self.assertEqual(
            host.complete_platforms(None, "l"),
            [("linux", "linux machine")],
        )
        with patch.object(host, "evaluate_machine_manifest") as evaluate:
            groups = host.complete_matrix_groups(None, "homebrew.system.c")

        evaluate.assert_not_called()
        self.assertEqual(groups, [
            ("homebrew.system.cask", "Homebrew casks (darwin)"),
        ])

    def test_diff_and_matrix_register_custom_completion(self):
        root_commands = get_command(cli).commands
        commands = root_commands["host"].commands
        diff = commands["diff"]
        for name in ("left", "right", "left_platform", "right_platform"):
            parameter = next(param for param in diff.params if param.name == name)
            self.assertIsNotNone(parameter._custom_shell_complete)
        matrix_group = next(
            param for param in commands["matrix"].params if param.name == "group"
        )
        self.assertIsNotNone(matrix_group._custom_shell_complete)
        check_platform = next(
            param for param in root_commands["check"].params
            if param.name == "selected_platform"
        )
        self.assertIsNotNone(check_platform._custom_shell_complete)

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

    def test_manifest_diff_compares_settings_and_effective_software(self):
        def manifest(user, items):
            return {
                "settings": {"envy.user.name": user},
                "software": {"groups": {"nix.user.package": {
                    "selection": {"effective": [
                        {"id": item, "name": item} for item in items
                    ]},
                }}},
            }

        diff = host.manifest_diff(
            manifest("chi", ["git", "ripgrep"]),
            manifest("work", ["git", "bat"]),
        )

        self.assertEqual(diff["settings"][0]["path"], "envy.user.name")
        self.assertEqual(
            diff["software"]["leftOnly"],
            [{"group": "nix.user.package", "item": "ripgrep"}],
        )
        self.assertEqual(
            diff["software"]["rightOnly"],
            [{"group": "nix.user.package", "item": "bat"}],
        )


    def test_select_json_emits_structured_result(self):
        self.machines.mkdir(parents=True)
        machine = self.machines / "work-macbook.nix"
        machine.write_text("{ ... }: { }\n")
        output = io.StringIO()
        console = Console(file=output, force_terminal=False, width=220)
        with patch.object(host, "machine_file", return_value=machine), patch.object(
            host, "set_device_machine_id"
        ) as select, patch.object(
            host, "flake_target", return_value="path:.#work-macbook"
        ), patch.object(host, "platform_name", return_value="darwin"), patch.object(
            host.log, "console", console
        ):
            host.cmd_select("work-macbook", json_output=True, yes=True)

        payload = json.loads(output.getvalue())
        self.assertEqual(payload["command"], "host.select")
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["data"]["machine"], "work-macbook")
        select.assert_called_once_with("work-macbook")

    def test_select_json_missing_machine_errors_without_writing(self):
        missing = self.machines / "ghost.nix"
        output = io.StringIO()
        console = Console(file=output, force_terminal=False, width=220)
        with patch.object(host, "machine_file", return_value=missing), patch.object(
            host, "set_device_machine_id"
        ) as select, patch.object(host.log, "console", console):
            with self.assertRaises(typer.Exit):
                host.cmd_select("ghost", json_output=True)

        payload = json.loads(output.getvalue())
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "invalid-machine")
        select.assert_not_called()


if __name__ == "__main__":
    unittest.main()
