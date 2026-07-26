import io
import json
import unittest
from unittest.mock import patch

from rich.console import Console

from envy import config


class ConfigShowTests(unittest.TestCase):
    def test_show_uses_evaluated_values_without_software_policy(self):
        settings = {field.path: field.default_fn() for field in config.MACHINE_FIELDS}
        settings["envy.user.name"] = "evaluated-user"
        manifest = {
            "schemaVersion": 2,
            "settings": settings,
            "software": {"groups": {
                "nix.user.package": {
                    "optionPath": "envy.software.nix.packages",
                    "selection": {
                        "include": [{"id": "git", "name": "git"}],
                        "exclude": [],
                        "effective": [{"id": "git", "name": "git"}],
                    },
                },
            }},
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
            config.cmd_show(refresh=False)

        rendered = output.getvalue()
        self.assertIn("evaluated-user", rendered)
        self.assertNotIn("source-user", rendered)
        self.assertNotIn("envy.software", rendered)
        self.assertNotIn("include", rendered)
        evaluate.assert_called_once_with(refresh=False)

    def test_json_output_reports_secret_presence_without_values(self):
        settings = {field.path: field.default_fn() for field in config.MACHINE_FIELDS}
        manifest = {"schemaVersion": 2, "settings": settings}
        output = io.StringIO()
        console = Console(file=output, force_terminal=False, width=220)
        with patch.object(config, "machine_manifest", return_value=manifest), patch.object(
            config, "read_device_metadata", return_value={"machine_id": "test-mac"}
        ), patch.object(
            config, "read_secrets_yaml", return_value=({"llm_steps_apikey": "top-secret"}, True)
        ), patch.object(config.log, "console", console):
            config.cmd_show(refresh=False, json_output=True)

        rendered = output.getvalue()
        payload = json.loads(rendered)
        self.assertNotIn("top-secret", rendered)
        self.assertTrue(payload["secrets"]["llm/steps/apikey"])
        self.assertEqual(payload["schemaVersion"], 1)
        self.assertEqual(payload["platform"], config.platform_name())


if __name__ == "__main__":
    unittest.main()
