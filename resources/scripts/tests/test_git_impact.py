from io import StringIO
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import typer
from rich.console import Console
from typer.testing import CliRunner

from envy import main


class GitImpactTests(unittest.TestCase):
    def test_refine_creates_missing_machine_after_explicit_mode_selection(self):
        missing = Path("/tmp/missing-machine.nix")
        report = SimpleNamespace(ok=True)
        with patch.object(main, "current_machine_file", return_value=missing), patch.object(
            main.sys.stdin, "isatty", return_value=True
        ), patch.object(main.typer, "confirm", return_value=True), patch.object(
            main.typer, "prompt", return_value="copy"
        ), patch.object(main, "initialize_machine") as initialize, patch.object(
            main, "refine_all", return_value=report
        ):
            main._refine_before_apply()

        initialize.assert_called_once_with("missing-machine", "copy")

    def test_refine_noninteractive_missing_machine_stops_before_migration(self):
        missing = Path("/tmp/missing-machine.nix")
        with patch.object(main, "current_machine_file", return_value=missing), patch.object(
            main.sys.stdin, "isatty", return_value=False
        ), patch.object(main, "initialize_machine") as initialize, patch.object(
            main, "refine_all"
        ) as refine:
            with self.assertRaises(typer.Exit):
                main._refine_before_apply()

        initialize.assert_not_called()
        refine.assert_not_called()

    def test_changed_paths_preserve_first_character_spaces_and_rename_destination(self):
        completed = SimpleNamespace(
            stdout=(
                " M resources/scripts/envy/main.py\0"
                "?? docs/file with spaces.md\0"
                "R  hosts/darwin/new-name.nix\0"
                "hosts/darwin/old-name.nix\0"
            ),
            returncode=0,
        )
        with patch.object(main.subprocess, "run", return_value=completed):
            paths = main._git_changed_paths()
        self.assertEqual(paths, [
            "resources/scripts/envy/main.py",
            "docs/file with spaces.md",
            "hosts/darwin/new-name.nix",
        ])

    def test_push_impact_logging_uses_non_conflicting_scope_field(self):
        output = StringIO()
        with patch.object(
            main.log, "console", Console(file=output, color_system=None, width=160)
        ):
            main._show_push_impact(
                paths=["modules/cores/base.nix"],
                worktree_paths=[],
                outgoing_commits={"c1"},
                counts={"origin": 1},
                affected=["one", "two"],
                shared=True,
                branch="master",
            )
        self.assertIn("change_scope=shared", output.getvalue())

    def test_push_help_exposes_scope_guards(self):
        result = CliRunner().invoke(main.cli, ["push", "--help"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("--self", result.output)
        self.assertIn("--machine-only", result.output)

    def test_branch_completion_lists_matching_local_branches(self):
        completed = SimpleNamespace(stdout="master\nfeature/test\n", returncode=0)
        with patch.object(main.subprocess, "run", return_value=completed):
            items = main.complete_git_branches(None, "mas")
        self.assertEqual(items, ["master"])

    def test_machine_files_affect_only_their_targets(self):
        affected, shared = main._affected_machines([
            "hosts/linux/two.nix",
        ])
        self.assertFalse(shared)
        self.assertEqual(affected, ["linux/two"])

    def test_module_changes_are_conservatively_shared(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for relative in ("hosts/darwin/one.nix", "hosts/linux/two.nix"):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("{ ... }: {}\n")
            with patch.object(main, "DOTFILES_DIR", root):
                affected, shared = main._affected_machines([
                    "modules/cores/base.nix",
                ])
        self.assertTrue(shared)
        self.assertEqual(affected, ["darwin/one", "linux/two"])

    def test_outgoing_impact_unions_paths_and_commits_across_remotes(self):
        outputs = {
            ("rev-list", "origin/master..HEAD"): "c2\nc1",
            ("log", "--format=", "--name-only", "origin/master..HEAD"): (
                "modules/cores/base.nix\nhosts/darwin/one.nix"
            ),
            ("rev-list", "backup/master..HEAD"): "c1",
            ("log", "--format=", "--name-only", "backup/master..HEAD"): (
                "hosts/darwin/one.nix"
            ),
        }
        with patch.object(main, "_git_output", side_effect=lambda *args: outputs[args]):
            paths, commits, counts = main._outgoing_impact(
                ["origin", "backup"], "master", set(),
            )
        self.assertEqual(paths, ["modules/cores/base.nix", "hosts/darwin/one.nix"])
        self.assertEqual(commits, {"c1", "c2"})
        self.assertEqual(counts, {"origin": 2, "backup": 1})

    def test_self_scope_allows_only_the_selected_machine(self):
        with patch.object(main, "current_machine_id", return_value="one"), patch.object(
            main, "platform_name", return_value="darwin"
        ):
            affected, shared = main._enforce_push_scope(
                ["hosts/darwin/one.nix"], machine_only=False, self_only=True,
            )
        self.assertEqual(affected, ["darwin/one"])
        self.assertFalse(shared)

    def test_self_scope_rejects_other_machine_and_shared_paths(self):
        with patch.object(main, "current_machine_id", return_value="one"), patch.object(
            main, "platform_name", return_value="darwin"
        ):
            with self.assertRaises(typer.Exit):
                main._enforce_push_scope(
                    ["hosts/linux/two.nix", "modules/cores/base.nix"],
                    machine_only=False, self_only=True,
                )

    def test_machine_only_allows_multiple_machine_files(self):
        affected, shared = main._enforce_push_scope(
            ["hosts/darwin/one.nix", "hosts/linux/two.nix"],
            machine_only=True,
            self_only=False,
        )
        self.assertEqual(affected, ["darwin/one", "linux/two"])
        self.assertFalse(shared)

    def test_machine_only_rejects_shared_paths(self):
        with self.assertRaises(typer.Exit):
            main._enforce_push_scope(
                ["hosts/darwin/one.nix", "modules/cores/base.nix"],
                machine_only=True,
                self_only=False,
            )

    def test_outgoing_shared_commits_require_confirmation_with_clean_worktree(self):
        with patch.object(main, "_git_output", return_value="master"), patch.object(
            main, "_selected_git_remotes", return_value=["origin"]
        ), patch.object(
            main, "_preflight_push_remotes", return_value=set()
        ), patch.object(
            main, "_git_changed_paths", return_value=[]
        ), patch.object(
            main, "_outgoing_impact",
            return_value=(["modules/cores/base.nix"], {"c1"}, {"origin": 1}),
        ), patch.object(main, "_show_push_impact"), patch.object(
            main, "_confirm_push_scope", return_value=False
        ) as confirm:
            with self.assertRaises(typer.Abort):
                main.cmd_push(
                    msg="test", remote=None, branch="master", machine_only=False,
                    self_only=False, yes=False,
                )
        confirm.assert_called_once()

    def test_sync_selects_the_newest_compatible_remote(self):
        ancestry = {
            ("origin/master", "HEAD"): False,
            ("HEAD", "origin/master"): True,
            ("backup/master", "origin/master"): False,
            ("origin/master", "backup/master"): True,
        }
        with patch.object(main, "_git_is_ancestor", side_effect=lambda older, newer: ancestry[(older, newer)]):
            target = main._select_sync_target(["origin/master", "backup/master"])
        self.assertEqual(target, "backup/master")

    def test_sync_rejects_divergent_remote_branches(self):
        ancestry = {
            ("origin/master", "HEAD"): False,
            ("HEAD", "origin/master"): True,
            ("backup/master", "origin/master"): False,
            ("origin/master", "backup/master"): False,
        }
        with patch.object(main, "_git_is_ancestor", side_effect=lambda older, newer: ancestry[(older, newer)]):
            with self.assertRaises(typer.Exit):
                main._select_sync_target(["origin/master", "backup/master"])

    def test_push_preflight_rejects_remote_ahead_before_commit(self):
        results = [
            SimpleNamespace(returncode=0),  # fetch
            SimpleNamespace(returncode=0),  # rev-parse --verify
        ]
        with patch.object(main.subprocess, "run", side_effect=results), patch.object(
            main, "_git_output", return_value="2"
        ):
            with self.assertRaises(typer.Exit):
                main._preflight_push_remotes(["origin"], "master")

    def test_push_preflight_allows_a_new_remote_branch(self):
        results = [
            SimpleNamespace(returncode=0),  # fetch
            SimpleNamespace(returncode=1),  # rev-parse --verify
        ]
        with patch.object(main.subprocess, "run", side_effect=results):
            new_branches = main._preflight_push_remotes(["backup"], "master")
        self.assertEqual(new_branches, {"backup"})

    def test_push_rejects_an_unintentional_machine_branch(self):
        with patch.object(main, "_git_output", return_value="darwin-work-macbook"):
            with self.assertRaises(typer.Exit):
                main.cmd_push(
                    msg="test",
                    remote=None,
                    branch="master",
                    machine_only=False,
                    self_only=False,
                    yes=True,
                )


if __name__ == "__main__":
    unittest.main()
