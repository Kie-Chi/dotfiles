import importlib.util
import unittest
from pathlib import Path


def _load_setup_module():
    path = Path(__file__).resolve().parents[3] / "setup.py"
    spec = importlib.util.spec_from_file_location("envy_setup_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SetupUiTests(unittest.TestCase):
    def test_policy_view_shows_include_exclude_and_effective(self):
        setup = _load_setup_module()
        manifest = {
            "packages": {"home": ["git"]},
            "homebrew": {},
            "inclusions": {"packages": {"home": ["git", "okular"]}},
            "exclusions": {"packages": {"home": ["okular"]}},
        }

        state = setup.AppState({}, manifest)
        rendered = "".join(part for _, part in setup._policy_text(state))

        self.assertIn("include:", rendered)
        self.assertIn("exclude:", rendered)
        self.assertIn("effective:", rendered)


if __name__ == "__main__":
    unittest.main()
