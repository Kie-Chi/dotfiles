import importlib.util
import os
import unittest
from pathlib import Path
from unittest.mock import patch


def _load_setup_module():
    root = Path(os.environ.get("ENVY_TEST_ROOT", Path(__file__).resolve().parents[3]))
    path = root / "setup.py"
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

    def test_changes_summary_never_prints_secret_values(self):
        setup = _load_setup_module()
        secret = setup.SECRET_FIELDS[0]
        old_secret = "old-secret-value"
        new_secret = "new-secret-value"
        exclusions = setup.normalize_exclusions({})

        with setup.log.console.capture() as capture:
            changed = setup.show_changes(
                {secret.path: old_secret},
                {secret.path: new_secret},
                exclusions,
                exclusions,
            )
        rendered = capture.get()

        self.assertTrue(changed)
        self.assertNotIn(old_secret, rendered)
        self.assertNotIn(new_secret, rendered)
        self.assertIn("<set>", rendered)

    def test_secret_values_are_masked_in_list_and_edit_context(self):
        setup = _load_setup_module()
        secret = setup.SECRET_FIELDS[0]
        value = "visible-only-in-the-edit-buffer"
        state = setup.AppState({secret.path: value})
        state.editing_field = secret

        list_text = "".join(part for _, part in setup._list_text(state))
        edit_text = "".join(part for _, part in setup._edit_context(state))

        self.assertNotIn(value, list_text)
        self.assertNotIn(value, edit_text)
        self.assertIn("<set>", list_text)
        self.assertIn("<set>", edit_text)

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

    def test_darwin_cask_toggle_changes_checkbox_to_checked(self):
        setup = _load_setup_module()
        manifest = {
            "id": "test-mac",
            "platform": "darwin",
            "packages": {"home": [], "system": [], "fonts": []},
            "homebrew": {"brews": ["gh"], "casks": ["iterm2"], "taps": []},
            "inclusions": {
                "packages": {"home": [], "system": [], "fonts": []},
                "homebrew": {
                    "brews": ["gh"],
                    "casks": ["iterm2", "uuremote"],
                    "taps": [],
                },
            },
            "exclusions": {
                "packages": {"home": [], "system": [], "fonts": []},
                "homebrew": {"brews": [], "casks": ["uuremote"], "taps": []},
            },
        }
        state = setup.AppState({}, manifest, {"homebrew.casks": ["uuremote"]})
        state.mode = "policy"
        state.policy_group = next(
            index
            for index, group in enumerate(state.policy_groups)
            if group.key == "homebrew.casks"
        )
        state.policy_cursor = 1

        before = "".join(part for _, part in setup._policy_text(state))
        self.assertIn("[ ] uuremote", before)
        self.assertNotIn("stale exclusion", before)

        setup._toggle_policy_item(state)

        after = "".join(part for _, part in setup._policy_text(state))
        self.assertIn("[x] uuremote", after)
        self.assertIn("pending", after)

    def test_linux_policy_view_has_only_common_group(self):
        setup = _load_setup_module()
        manifest = {
            "id": "test-linux",
            "platform": "linux",
            "packages": {"home": ["git"]},
            "homebrew": {"brews": ["gh"], "casks": ["iterm2"], "taps": []},
            "inclusions": {
                "packages": {"home": ["git"]},
                "homebrew": {"brews": ["gh"], "casks": ["iterm2"]},
            },
            "exclusions": {},
        }
        state = setup.AppState({}, manifest, {})
        state.mode = "policy"

        rendered = "".join(part for _, part in setup._policy_text(state))

        self.assertEqual([group.key for group in state.policy_groups], ["packages.home"])
        self.assertIn("Home packages  (1/1)", rendered)
        self.assertIn("[x] git", rendered)
        self.assertNotIn("Homebrew", rendered)


if __name__ == "__main__":
    unittest.main()
