import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from envy import evaluation
from envy.evaluation import manifest_selection_rows, manifest_settings


class EvaluationTests(unittest.TestCase):
    def tearDown(self):
        evaluation.invalidate_machine_manifest()

    def test_settings_are_read_from_the_evaluated_manifest(self):
        values = manifest_settings({
            "settings": {
                "envy.darwin.proxy.mode": "none",
                "envy.darwin.proxy.tun": False,
            }
        })

        self.assertEqual(values["envy.darwin.proxy.mode"], "none")
        self.assertEqual(values["envy.darwin.proxy.tun"], "false")

    def test_selection_rows_include_all_three_views(self):
        manifest = {
            "platform": "darwin",
            "packages": {"home": ["git"]},
            "homebrew": {"brews": ["gh"], "casks": ["iterm2"], "taps": []},
            "inclusions": {
                "packages": {"home": ["git", "okular"]},
                "homebrew": {
                    "brews": ["gh"],
                    "casks": ["iterm2", "uuremote"],
                    "taps": [],
                },
            },
            "exclusions": {
                "packages": {"home": ["okular"]},
                "homebrew": {"brews": [], "casks": ["uuremote"], "taps": []},
            },
        }

        rows = {path: (include, exclude, effective) for path, include, exclude, effective
                in manifest_selection_rows(manifest)}

        self.assertEqual(
            rows["envy.packages.home"],
            (["git", "okular"], ["okular"], ["git"]),
        )
        self.assertEqual(
            rows["envy.darwin.homebrew.brews"],
            (["gh"], [], ["gh"]),
        )
        self.assertEqual(
            rows["envy.darwin.homebrew.casks"],
            (["iterm2", "uuremote"], ["uuremote"], ["iterm2"]),
        )

    def test_platform_specific_selection_paths_are_not_exposed_on_linux(self):
        linux_rows = list(manifest_selection_rows({
            "platform": "linux",
            "packages": {"home": ["git"], "system": [], "fonts": []},
            "homebrew": {"brews": [], "casks": [], "taps": []},
            "inclusions": {},
            "exclusions": {},
        }))
        self.assertEqual([row[0] for row in linux_rows], ["envy.packages.home"])

        darwin_rows = list(manifest_selection_rows({
            "platform": "darwin",
            "packages": {},
            "homebrew": {},
            "inclusions": {},
            "exclusions": {},
        }))
        self.assertIn("envy.darwin.packages.system", [row[0] for row in darwin_rows])
        self.assertIn("envy.darwin.homebrew.casks", [row[0] for row in darwin_rows])

    def test_persistent_cache_survives_process_memoization_clear(self):
        manifest = {"id": "test-machine", "settings": {}}
        with tempfile.TemporaryDirectory() as cache_root, patch.dict(
            os.environ, {"XDG_CACHE_HOME": cache_root}, clear=False
        ), patch.object(
            evaluation, "current_machine_id", return_value="test-machine"
        ), patch.object(
            evaluation, "_repository_fingerprint", return_value="fingerprint"
        ), patch.object(
            evaluation, "_evaluate_machine_manifest", return_value=manifest
        ) as evaluate:
            os.environ.pop("ENVY_NO_CACHE", None)
            first = evaluation.machine_manifest()
            evaluation.invalidate_machine_manifest()
            second = evaluation.machine_manifest()

            self.assertEqual(first, manifest)
            self.assertEqual(second, manifest)
            evaluate.assert_called_once_with("test-machine")
            self.assertTrue(evaluation._cache_path("test-machine").exists())

    def test_refresh_bypasses_persistent_cache_and_replaces_it(self):
        first_manifest = {"id": "first"}
        refreshed_manifest = {"id": "refreshed"}
        with tempfile.TemporaryDirectory() as cache_root, patch.dict(
            os.environ, {"XDG_CACHE_HOME": cache_root}, clear=False
        ), patch.object(
            evaluation, "current_machine_id", return_value="test-machine"
        ), patch.object(
            evaluation, "_repository_fingerprint", return_value="fingerprint"
        ), patch.object(
            evaluation,
            "_evaluate_machine_manifest",
            side_effect=[first_manifest, refreshed_manifest],
        ) as evaluate:
            os.environ.pop("ENVY_NO_CACHE", None)
            self.assertEqual(evaluation.machine_manifest(), first_manifest)
            self.assertEqual(evaluation.machine_manifest(refresh=True), refreshed_manifest)
            self.assertEqual(evaluation.machine_manifest(), refreshed_manifest)
            self.assertEqual(evaluate.call_count, 2)

    def test_no_cache_environment_bypasses_memory_and_disk(self):
        manifest = {"id": "uncached"}
        with tempfile.TemporaryDirectory() as cache_root, patch.dict(
            os.environ,
            {"XDG_CACHE_HOME": cache_root, "ENVY_NO_CACHE": "1"},
            clear=False,
        ), patch.object(
            evaluation, "current_machine_id", return_value="test-machine"
        ), patch.object(
            evaluation, "_evaluate_machine_manifest", return_value=manifest
        ) as evaluate:
            self.assertEqual(evaluation.machine_manifest(), manifest)
            self.assertEqual(evaluation.machine_manifest(), manifest)
            self.assertEqual(evaluate.call_count, 2)
            self.assertFalse(evaluation._cache_path("test-machine").exists())

    def test_repository_fingerprint_covers_head_index_worktree_and_untracked(self):
        with tempfile.TemporaryDirectory() as checkout:
            root = Path(checkout)
            source = root / "flake.nix"
            source.write_text("base\n")
            self._git(root, "init", "-q")
            self._git(root, "add", "flake.nix")
            self._git(
                root,
                "-c", "user.name=Envy Test",
                "-c", "user.email=envy@example.invalid",
                "commit", "-qm", "base",
            )

            real_command = evaluation._command_bytes

            def command_with_test_nix(command):
                if command == ["nix", "--version"]:
                    return b"nix (test) 1.0\n"
                return real_command(command)

            with patch.object(evaluation, "DOTFILES_DIR", root), patch.object(
                evaluation, "_command_bytes", side_effect=command_with_test_nix
            ):
                clean = evaluation._repository_fingerprint("test-machine")

                source.write_text("worktree\n")
                worktree = evaluation._repository_fingerprint("test-machine")
                self.assertNotEqual(clean, worktree)

                self._git(root, "add", "flake.nix")
                staged = evaluation._repository_fingerprint("test-machine")
                self.assertNotEqual(worktree, staged)

                self._git(
                    root,
                    "-c", "user.name=Envy Test",
                    "-c", "user.email=envy@example.invalid",
                    "commit", "-qm", "staged",
                )
                committed = evaluation._repository_fingerprint("test-machine")
                self.assertNotEqual(staged, committed)

                extra = root / "new-module.nix"
                extra.write_text("first\n")
                untracked = evaluation._repository_fingerprint("test-machine")
                self.assertNotEqual(committed, untracked)

                extra.write_text("second\n")
                changed_untracked = evaluation._repository_fingerprint("test-machine")
                self.assertNotEqual(untracked, changed_untracked)
                self.assertNotEqual(
                    changed_untracked,
                    evaluation._repository_fingerprint("other-machine"),
                )

    @staticmethod
    def _git(root: Path, *args: str) -> None:
        subprocess.run(
            ["git", *args],
            cwd=root,
            capture_output=True,
            check=True,
        )


if __name__ == "__main__":
    unittest.main()
