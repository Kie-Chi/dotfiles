import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from envy import key


class SetupGitTests(unittest.TestCase):
    def test_key_confirmation_has_no_implicit_no_default(self):
        with patch.object(key.Confirm, "ask", return_value=True) as ask:
            self.assertTrue(key.confirm("Commit managed files?"))
        ask.assert_called_once_with("Commit managed files?", console=key.log.console)

    def test_staging_explicit_setup_files_leaves_other_changes_unstaged(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            selected = root / "hosts" / "darwin" / "work-mac.nix"
            unrelated = root / "modules" / "desktops" / "darwin" / "apps.nix"
            selected.parent.mkdir(parents=True)
            unrelated.parent.mkdir(parents=True)
            selected.write_text("{ }\n")
            unrelated.write_text("{ }\n")
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)

            with patch.object(key, "DOTFILES_DIR", root):
                changed = key._stage_repo_files([selected])

            staged = subprocess.run(
                ["git", "diff", "--cached", "--name-only"],
                cwd=root, capture_output=True, text=True, check=True,
            ).stdout.splitlines()

        self.assertEqual(changed, ["hosts/darwin/work-mac.nix"])
        self.assertEqual(staged, ["hosts/darwin/work-mac.nix"])

    def test_setup_commit_scopes_candidates_to_machine_and_sops_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            machine = root / "hosts" / "darwin" / "work-mac.nix"
            candidates = [
                machine,
                root / ".sops.yaml",
                root / "secrets" / "secrets.yaml",
                root / "secrets" / "recovery-key.age",
            ]
            with patch.object(key, "DOTFILES_DIR", root), patch.object(
                key, "SOPS_YAML", candidates[1]
            ), patch.object(key, "SECRETS_FILE", candidates[2]), patch.object(
                key, "RECOVERY_KEY_FILE", candidates[3]
            ), patch.object(
                key, "_stage_repo_files", return_value=["hosts/darwin/work-mac.nix"]
            ) as stage, patch.object(key, "_commit_staged_files") as commit:
                (root / ".git").mkdir()

                key.git_commit_setup_files(machine)

        stage.assert_called_once_with(candidates)
        commit.assert_called_once_with(
            ["hosts/darwin/work-mac.nix"],
            "chore(setup): update work-mac configuration (work-mac.nix)",
        )

    def test_setup_commit_skips_prompt_when_candidates_are_unchanged(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            machine = root / "hosts" / "darwin" / "work-mac.nix"
            with patch.object(key, "DOTFILES_DIR", root), patch.object(
                key, "_stage_repo_files", return_value=[]
            ), patch.object(key, "_commit_staged_files") as commit:
                (root / ".git").mkdir()

                key.git_commit_setup_files(machine)

        commit.assert_not_called()


if __name__ == "__main__":
    unittest.main()
