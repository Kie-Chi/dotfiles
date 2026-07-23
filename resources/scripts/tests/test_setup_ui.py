import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch


def _load_setup_module():
    path = Path(__file__).resolve().parents[3] / "setup.py"
    spec = importlib.util.spec_from_file_location("envy_setup_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SetupUiTests(unittest.TestCase):
    def test_yes_no_prompt_retries_blank_and_invalid_answers(self):
        setup = _load_setup_module()
        with patch.object(setup, "pt_prompt", side_effect=["", "later", "YES"]) as prompt:
            self.assertTrue(setup.prompt_yes_no("Continue?"))
        self.assertEqual(prompt.call_count, 3)

    def test_yes_no_prompt_accepts_explicit_no(self):
        setup = _load_setup_module()
        with patch.object(setup, "pt_prompt", side_effect=["unknown", "no"]) as prompt:
            self.assertFalse(setup.prompt_yes_no("Continue?"))
        self.assertEqual(prompt.call_count, 2)

    def test_policy_view_shows_machine_exclusion_checkboxes(self):
        setup = _load_setup_module()
        manifest = {
            "packages": {"home": ["git"]},
            "homebrew": {},
            "inclusions": {"packages": {"home": ["git", "okular"]}},
            "exclusions": {"packages": {"home": ["okular"]}},
        }

        exclusions = {"packages.home": ["okular"]}
        state = setup.AppState({}, manifest, exclusions)
        rendered = "".join(part for _, part in setup._policy_text(state))

        self.assertIn("[x] git", rendered)
        self.assertIn("[ ] okular", rendered)
        self.assertIn("machine exclusion", rendered)
        setup.build_application(state)


if __name__ == "__main__":
    unittest.main()
