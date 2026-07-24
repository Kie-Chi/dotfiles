import unittest
from types import SimpleNamespace
from unittest.mock import patch

from envy.doctor import policy


class DoctorPolicyTests(unittest.TestCase):
    def test_excluded_cask_is_not_expected(self):
        manifest = {
            "schemaVersion": 2,
            "software": {"groups": {
                "homebrew.system.cask": {
                    "selection": {
                        "include": [{"id": "zotero", "name": "zotero"}],
                        "exclude": ["zotero"],
                        "effective": [],
                    },
                },
            }},
        }
        spec = SimpleNamespace(casks=["zotero"], brews=[], packages=[])
        with patch.object(policy, "machine_manifest", return_value=manifest):
            enabled, reason = policy.app_policy(spec)
        self.assertFalse(enabled)
        self.assertIn("cask", reason)

    def test_excluded_nix_package_is_not_expected(self):
        manifest = {
            "schemaVersion": 2,
            "software": {"groups": {
                "nix.user.package": {
                    "selection": {
                        "include": [
                            {"id": "git", "name": "git"},
                            {"id": "okular", "name": "okular"},
                        ],
                        "exclude": ["okular"],
                        "effective": [{"id": "git", "name": "git"}],
                    },
                },
            }},
        }
        spec = SimpleNamespace(casks=[], brews=[], packages=["okular"])
        with patch.object(policy, "machine_manifest", return_value=manifest):
            enabled, reason = policy.app_policy(spec)
        self.assertFalse(enabled)
        self.assertIn("Nix package", reason)



if __name__ == "__main__":
    unittest.main()
