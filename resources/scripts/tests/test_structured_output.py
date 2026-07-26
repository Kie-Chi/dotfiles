import io
import json
import unittest

from rich.console import Console
from unittest.mock import patch

from envy.doctor import runner
from envy.doctor.model import info, ok, warn, SECTION_DOCTOR, SECTION_SYSTEM
from envy.jsonio import emit, emit_error


class StructuredOutputTests(unittest.TestCase):
    def test_frontend_envelope_has_stable_success_and_error_shapes(self):
        output = io.StringIO()
        console = Console(file=output, force_terminal=False, width=220)
        with patch("envy.jsonio.log.console", console):
            emit("software.add", data={"result": "dry-run"})
            success = json.loads(output.getvalue())
            output.seek(0)
            output.truncate(0)
            emit_error("software.add", "confirmation required", code="confirmation-required")
            failure = json.loads(output.getvalue())

        self.assertEqual(success["schemaVersion"], 1)
        self.assertEqual(success["command"], "software.add")
        self.assertTrue(success["ok"])
        self.assertFalse(failure["ok"])
        self.assertEqual(failure["error"]["code"], "confirmation-required")

    def test_doctor_json_has_stable_summary_and_serializable_details(self):
        results = [
            ok(SECTION_SYSTEM, "git", "available"),
            warn(SECTION_SYSTEM, "branch", "unexpected", hint="switch branch"),
            info(SECTION_DOCTOR, "source", "repo", path="/tmp/repo"),
        ]
        output = io.StringIO()
        console = Console(file=output, force_terminal=False, width=220)
        with patch.object(runner.log, "console", console):
            runner.render_json(results, strict=True)

        payload = json.loads(output.getvalue())
        self.assertEqual(payload["schemaVersion"], 1)
        self.assertEqual(payload["summary"]["warn"], 1)
        self.assertEqual(payload["summary"]["exitCode"], 1)
        self.assertEqual(payload["results"][1]["hint"], "switch branch")


if __name__ == "__main__":
    unittest.main()
