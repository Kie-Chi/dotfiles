import io
import unittest
from unittest.mock import patch

from rich.console import Console

from envy import config


class ConfigShowTests(unittest.TestCase):
    def test_show_uses_evaluated_defaults_and_software_policy(self):
        settings = {field.path: field.default_fn() for field in config.MACHINE_FIELDS}
        settings["envy.user.name"] = "evaluated-user"
        settings["envy.darwin.proxy.tun"] = False
        manifest = {
            "platform": "darwin",
            "settings": settings,
            "packages": {"home": ["git"]},
            "homebrew": {},
            "inclusions": {"packages": {"home": ["git", "okular"]}},
            "exclusions": {"packages": {"home": ["okular"]}},
        }
        output = io.StringIO()
        console = Console(file=output, force_terminal=False, width=220)

        with patch.object(config, "machine_manifest", return_value=manifest) as evaluate, patch.object(
            config, "read_machine_nix", return_value={"envy.user.name": "source-user"}
        ), patch.object(config, "read_device_metadata", return_value={
            "machine_id": "test-mac", "sops_label": "test_mac"
        }), patch.object(config, "read_secrets_yaml", return_value=({}, True)), patch.object(
            config.log, "console", console
        ):
            config.cmd_show(refresh=False, details=True)

        rendered = output.getvalue()
        self.assertIn("evaluated-user", rendered)
        self.assertNotIn("source-user", rendered)
        self.assertIn("envy.packages.home.include", rendered)
        self.assertIn("[git, okular]", rendered)
        self.assertIn("envy.packages.home.exclude", rendered)
        self.assertIn("envy.packages.home.effective", rendered)
        evaluate.assert_called_once_with(refresh=False)

    def test_show_defaults_to_nonempty_software_exclusions_only(self):
        settings = {field.path: field.default_fn() for field in config.MACHINE_FIELDS}
        manifest = {
            "platform": "darwin",
            "settings": settings,
            "packages": {"home": ["git"]},
            "homebrew": {},
            "inclusions": {"packages": {"home": ["git", "okular"]}},
            "exclusions": {"packages": {"home": ["okular"]}},
        }
        output = io.StringIO()
        console = Console(file=output, force_terminal=False, width=220)

        with patch.object(config, "machine_manifest", return_value=manifest), patch.object(
            config, "read_machine_nix", return_value={}
        ), patch.object(config, "read_device_metadata", return_value={}), patch.object(
            config, "read_secrets_yaml", return_value=({}, True)
        ), patch.object(config.log, "console", console):
            config.cmd_show(refresh=False, details=False)

        rendered = output.getvalue()
        self.assertIn("envy.packages.home.exclude", rendered)
        self.assertIn("[okular]", rendered)
        self.assertNotIn("envy.packages.home.include", rendered)
        self.assertNotIn("envy.packages.home.effective", rendered)
        self.assertNotIn("envy.darwin.packages.system.exclude", rendered)


if __name__ == "__main__":
    unittest.main()
