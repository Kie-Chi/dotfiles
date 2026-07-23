import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from envy import config, software


class SoftwarePolicyTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tempdir.name)
        self.machine = self.root / "test-mac.nix"
        self.original = """{ ... }:

{
  imports = [ ../default.nix ];

  # BEGIN ENVY MANAGED CONFIG
  envy.user.name = "chi";
  # END ENVY MANAGED CONFIG

  # Hand-written policy remains here.
}
"""
        self.machine.write_text(self.original)

    def tearDown(self):
        self.tempdir.cleanup()

    def test_round_trip_writes_only_non_empty_groups(self):
        values = software.empty_exclusions()
        values["packages.home"] = ["okular", "sing-box"]
        if "homebrew.casks" in values:
            values["homebrew.casks"] = ["uuremote"]

        software.write_managed_exclusions(values, self.machine)
        parsed = software.read_managed_exclusions(self.machine)
        text = self.machine.read_text()

        self.assertEqual(parsed, values)
        self.assertIn(software.MANAGED_START, text)
        self.assertIn('"okular"', text)
        if "homebrew.casks" in values:
            self.assertIn('"uuremote"', text)
        self.assertNotIn("envy.darwin.packages.system.exclude", text)
        self.assertIn("# Hand-written policy remains here.", text)

    def test_removing_last_exclusion_removes_the_whole_block(self):
        values = software.empty_exclusions()
        values["packages.home"] = ["okular"]
        software.write_managed_exclusions(values, self.machine)
        software.write_managed_exclusions(software.empty_exclusions(), self.machine)

        self.assertNotIn(software.MANAGED_START, self.machine.read_text())
        self.assertIn("# Hand-written policy remains here.", self.machine.read_text())

    def test_concurrent_source_change_is_rejected(self):
        digest = software.source_digest(self.machine.read_text())
        self.machine.write_text(self.machine.read_text().replace("chi", "other"))

        with self.assertRaises(software.ConcurrentMachineEdit):
            software.write_managed_exclusions(
                {"packages.home": ["okular"]},
                self.machine,
                expected_digest=digest,
            )

    def test_failed_nix_evaluation_restores_original_source(self):
        evaluator = MagicMock(return_value=None)
        evaluator.cache_clear = MagicMock()

        with patch.object(software, "machine_manifest", evaluator), self.assertRaises(
            software.SoftwarePolicyError
        ):
            software.write_and_validate_exclusions(
                {"packages.home": ["okular"]}, self.machine
            )

        self.assertEqual(self.machine.read_text(), self.original)

    def test_successful_evaluation_keeps_the_new_policy(self):
        evaluator = MagicMock(return_value={"id": "test-mac"})
        evaluator.cache_clear = MagicMock()

        with patch.object(software, "machine_manifest", evaluator):
            software.write_and_validate_exclusions(
                {"packages.home": ["okular"]}, self.machine
            )

        self.assertEqual(
            software.read_managed_exclusions(self.machine)["packages.home"],
            ["okular"],
        )

    def test_checkbox_state_predicts_pending_exclusions(self):
        manifest = {
            "packages": {"home": ["git"]},
            "homebrew": {},
            "inclusions": {"packages": {"home": ["git", "okular"]}},
            "exclusions": {"packages": {"home": ["okular"]}},
        }
        original = software.empty_exclusions()
        original["packages.home"] = ["okular"]
        current = software.normalize_exclusions(original)
        software.set_excluded(current, "packages.home", "git", True)
        software.set_excluded(current, "packages.home", "okular", False)

        items = {
            item.name: item
            for item in software.build_software_items(manifest, current, original)["packages.home"]
        }

        self.assertFalse(items["git"].checked)
        self.assertTrue(items["git"].changed)
        self.assertTrue(items["okular"].checked)
        self.assertTrue(items["okular"].changed)

    def test_darwin_homebrew_paths_and_pending_toggle_are_mapped(self):
        groups = software.groups_for_platform("darwin")
        manifest = {
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
        original = software.empty_exclusions(groups)
        original["homebrew.casks"] = ["uuremote"]
        current = software.normalize_exclusions(original, groups)

        before = software.build_software_items(
            manifest,
            current,
            original,
            groups=groups,
        )
        brews = {item.name: item for item in before["homebrew.brews"]}
        casks = {item.name: item for item in before["homebrew.casks"]}

        self.assertTrue(brews["gh"].checked)
        self.assertTrue(casks["uuremote"].included)
        self.assertFalse(casks["uuremote"].checked)
        self.assertFalse(casks["uuremote"].stale)

        software.set_excluded(
            current,
            "homebrew.casks",
            "uuremote",
            False,
            groups=groups,
        )
        after = {
            item.name: item
            for item in software.build_software_items(
                manifest,
                current,
                original,
                groups=groups,
            )["homebrew.casks"]
        }
        self.assertTrue(after["uuremote"].checked)
        self.assertTrue(after["uuremote"].changed)

    def test_linux_manifest_exposes_only_cross_platform_groups(self):
        manifest = {
            "platform": "linux",
            "packages": {"home": ["git"], "system": [], "fonts": []},
            "homebrew": {"brews": ["gh"], "casks": ["iterm2"], "taps": []},
            "inclusions": {
                "packages": {"home": ["git", "okular"]},
                "homebrew": {"brews": ["gh"], "casks": ["iterm2"]},
            },
            "exclusions": {"packages": {"home": ["okular"]}},
        }
        groups = software.groups_for_platform("linux")
        original = software.empty_exclusions(groups)
        original["packages.home"] = ["okular"]

        items = software.build_software_items(manifest, original, original)

        self.assertEqual(list(items), ["packages.home"])
        self.assertEqual([group.key for group in groups], ["packages.home"])
        self.assertFalse({"homebrew.brews", "homebrew.casks"} & set(items))
        by_name = {item.name: item for item in items["packages.home"]}
        self.assertTrue(by_name["git"].checked)
        self.assertFalse(by_name["okular"].checked)
        self.assertFalse(by_name["okular"].stale)

    def test_invalid_managed_content_is_rejected(self):
        self.machine.write_text(
            self.original.replace(
                "  # Hand-written policy remains here.",
                f"{software.MANAGED_START}\n  builtins.abort \"bad\";\n{software.MANAGED_END}",
            )
        )
        with self.assertRaises(software.SoftwarePolicyError):
            software.read_managed_exclusions(self.machine)

        with patch.object(config, "machine_config_file", return_value=self.machine):
            report = config.refine_software_policy()
        self.assertFalse(report.ok)


if __name__ == "__main__":
    unittest.main()
