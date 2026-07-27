import io
import json
import unittest
from unittest.mock import patch

import typer
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


    def test_json_output_includes_field_choices_metadata(self):
        settings = {field.path: field.default_fn() for field in config.MACHINE_FIELDS}
        manifest = {"schemaVersion": 2, "settings": settings}
        output = io.StringIO()
        console = Console(file=output, force_terminal=False, width=220)
        with patch.object(config, "machine_manifest", return_value=manifest), patch.object(
            config, "read_device_metadata", return_value={"machine_id": "test-mac"}
        ), patch.object(config, "read_secrets_yaml", return_value=({}, True)), patch.object(
            config.log, "console", console
        ):
            config.cmd_show(refresh=False, json_output=True)

        payload = json.loads(output.getvalue())
        fields = {entry["path"]: entry for entry in payload["fields"]}
        # Enumerated fields expose their choices so the frontend can render a dropdown.
        self.assertEqual(fields["envy.mirrors.mode"]["choices"], ["upstream", "china"])
        self.assertEqual(fields["envy.vscode.mode"]["choices"], ["remote", "local"])
        # Freeform fields report an empty choices list, signalling a text input.
        self.assertEqual(fields["envy.user.name"]["choices"], [])


class ConfigSetTests(unittest.TestCase):
    def test_set_json_emits_result_and_suppresses_command_logs(self):
        output = io.StringIO()
        console = Console(file=output, force_terminal=False, width=220)
        with patch.object(config, "set_config_value") as setter, patch.object(
            config, "offer_mutation_commit"
        ) as commit, patch.object(
            config, "current_machine_id", return_value="test-mac"
        ), patch.object(config.log, "console", console):
            config.cmd_set("envy.mirrors.mode", "china", json_output=True, yes=True)

        payload = json.loads(output.getvalue())
        self.assertEqual(payload["command"], "config.set")
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["data"]["path"], "envy.mirrors.mode")
        self.assertEqual(payload["data"]["value"], "china")
        setter.assert_called_once_with("envy.mirrors.mode", "china", quiet=True)
        commit.assert_called_once()

    def test_set_json_invalid_value_errors_without_committing(self):
        output = io.StringIO()
        console = Console(file=output, force_terminal=False, width=220)
        with patch.object(
            config, "set_config_value", side_effect=typer.BadParameter("invalid value")
        ), patch.object(config, "offer_mutation_commit") as commit, patch.object(
            config.log, "console", console
        ):
            with self.assertRaises(typer.Exit):
                config.cmd_set("envy.mirrors.mode", "bogus", json_output=True)

        payload = json.loads(output.getvalue())
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["error"]["code"], "invalid-value")
        commit.assert_not_called()


if __name__ == "__main__":
    unittest.main()
