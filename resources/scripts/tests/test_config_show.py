import io
import unittest
from unittest.mock import patch

from rich.console import Console

from envy import config


class ConfigShowTests(unittest.TestCase):
    def test_show_uses_evaluated_defaults_and_software_policy(self):
        settings = {field.path: field.default_fn() for field in config.MACHINE_FIELDS}
        settings["envy.user.name"] = "evaluated-user"
        settings["envy.proxy.tun"] = False
        manifest = {
            "settings": settings,
            "packages": {"home": ["git"]},
            "homebrew": {},
            "inclusions": {"packages": {"home": ["git", "okular"]}},
            "exclusions": {"packages": {"home": ["okular"]}},
        }
        output = io.StringIO()
        console = Console(file=output, force_terminal=False, width=220)

        with patch.object(config, "machine_manifest", return_value=manifest), patch.object(
            config, "read_machine_nix", return_value={"envy.user.name": "source-user"}
        ), patch.object(config, "read_device_metadata", return_value={
            "machine_id": "test-mac", "sops_label": "test_mac"
        }), patch.object(config, "read_secrets_yaml", return_value=({}, True)), patch.object(
            config.log, "console", console
        ):
            config.cmd_show()

        rendered = output.getvalue()
        self.assertIn("evaluated-user", rendered)
        self.assertNotIn("source-user", rendered)
        self.assertIn("envy.packages.home.include", rendered)
        self.assertIn("[git, okular]", rendered)
        self.assertIn("envy.packages.home.exclude", rendered)
        self.assertIn("envy.packages.home.effective", rendered)


if __name__ == "__main__":
    unittest.main()
