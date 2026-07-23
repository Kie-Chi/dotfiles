from io import StringIO
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import typer
from rich.console import Console
from typer.testing import CliRunner

from envy import main


class GitImpactTests(unittest.TestCase):
    def test_changed_paths_preserve_first_character_spaces_and_rename_destination(self):
        completed = SimpleNamespace(
            stdout=(
                " M resources/scripts/envy/main.py\0"
                "?? docs/file with spaces.md\0"
                "R  hosts/machines/new-name.nix\0"
                "hosts/machines/old-name.nix\0"
            ),
            returncode=0,
        )
        with patch.object(main.subprocess, "run", return_value=completed):
            paths = main._git_changed_paths()
        self.assertEqual(paths, [
            "resources/scripts/envy/main.py",
            "docs/file with spaces.md",
            "hosts/machines/new-name.nix",
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
                branch="darwin",
            )
        self.assertIn("change_scope=shared", output.getvalue())

    def test_push_help_exposes_scope_guards(self):
        result = CliRunner().invoke(main.cli, ["push", "--help"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("--self", result.output)
        self.assertIn("--machine-only", result.output)

    def test_branch_completion_lists_matching_local_branches(self):
        completed = SimpleNamespace(stdout="darwin\nfeature/test\n", returncode=0)
        with patch.object(main.subprocess, "run", return_value=completed):
            items = main.complete_git_branches(None, "dar")
        self.assertEqual(items, ["darwin"])

    def test_machine_files_affect_only_their_targets(self):
        with patch.object(main, "machine_ids", return_value=["one", "two"]):
            affected, shared = main._affected_machines([
                "hosts/machines/two.nix",
            ])
        self.assertFalse(shared)
        self.assertEqual(affected, ["two"])

    def test_module_changes_are_conservatively_shared(self):
        with patch.object(main, "machine_ids", return_value=["one", "two"]):
            affected, shared = main._affected_machines([
                "modules/cores/base.nix",
            ])
        self.assertTrue(shared)
        self.assertEqual(affected, ["one", "two"])

    def test_outgoing_impact_unions_paths_and_commits_across_remotes(self):
        outputs = {
            ("rev-list", "origin/darwin..HEAD"): "c2\nc1",
            ("log", "--format=", "--name-only", "origin/darwin..HEAD"): (
                "modules/cores/base.nix\nhosts/machines/one.nix"
            ),
            ("rev-list", "backup/darwin..HEAD"): "c1",
            ("log", "--format=", "--name-only", "backup/darwin..HEAD"): (
                "hosts/machines/one.nix"
            ),
        }
        with patch.object(main, "_git_output", side_effect=lambda *args: outputs[args]):
            paths, commits, counts = main._outgoing_impact(
                ["origin", "backup"], "darwin", set(),
            )
        self.assertEqual(paths, ["modules/cores/base.nix", "hosts/machines/one.nix"])
        self.assertEqual(commits, {"c1", "c2"})
        self.assertEqual(counts, {"origin": 2, "backup": 1})

    def test_self_scope_allows_only_the_selected_machine(self):
        with patch.object(main, "machine_ids", return_value=["one", "two"]), patch.object(
            main, "current_machine_id", return_value="one"
        ):
            affected, shared = main._enforce_push_scope(
                ["hosts/machines/one.nix"], machine_only=False, self_only=True,
            )
        self.assertEqual(affected, ["one"])
        self.assertFalse(shared)

    def test_self_scope_rejects_other_machine_and_shared_paths(self):
        with patch.object(main, "machine_ids", return_value=["one", "two"]), patch.object(
            main, "current_machine_id", return_value="one"
        ):
            with self.assertRaises(typer.Exit):
                main._enforce_push_scope(
                    ["hosts/machines/two.nix", "modules/cores/base.nix"],
                    machine_only=False, self_only=True,
                )

    def test_machine_only_allows_multiple_machine_files(self):
        with patch.object(main, "machine_ids", return_value=["one", "two"]):
            affected, shared = main._enforce_push_scope(
                ["hosts/machines/one.nix", "hosts/machines/two.nix"],
                machine_only=True,
                self_only=False,
            )
        self.assertEqual(affected, ["one", "two"])
        self.assertFalse(shared)

    def test_machine_only_rejects_shared_paths(self):
        with patch.object(main, "machine_ids", return_value=["one", "two"]):
            with self.assertRaises(typer.Exit):
                main._enforce_push_scope(
                    ["hosts/machines/one.nix", "modules/cores/base.nix"],
                    machine_only=True,
                    self_only=False,
                )

    def test_outgoing_shared_commits_require_confirmation_with_clean_worktree(self):
        with patch.object(main, "_git_output", return_value="darwin"), patch.object(
            main, "_selected_git_remotes", return_value=["origin"]
        ), patch.object(
            main, "_preflight_push_remotes", return_value=set()
        ), patch.object(
            main, "_git_changed_paths", return_value=[]
        ), patch.object(
            main, "_outgoing_impact",
            return_value=(["modules/cores/base.nix"], {"c1"}, {"origin": 1}),
        ), patch.object(
            main, "machine_ids", return_value=["one", "two"]
        ), patch.object(main, "_show_push_impact"), patch.object(
            main, "_confirm_push_scope", return_value=False
        ) as confirm:
            with self.assertRaises(typer.Abort):
                main.cmd_push(
                    msg="test", remote=None, branch="darwin", machine_only=False,
                    self_only=False, yes=False,
                )
        confirm.assert_called_once()

    def test_sync_selects_the_newest_compatible_remote(self):
        ancestry = {
            ("origin/darwin", "HEAD"): False,
            ("HEAD", "origin/darwin"): True,
            ("backup/darwin", "origin/darwin"): False,
            ("origin/darwin", "backup/darwin"): True,
        }
        with patch.object(main, "_git_is_ancestor", side_effect=lambda older, newer: ancestry[(older, newer)]):
            target = main._select_sync_target(["origin/darwin", "backup/darwin"])
        self.assertEqual(target, "backup/darwin")

    def test_sync_rejects_divergent_remote_branches(self):
        ancestry = {
            ("origin/darwin", "HEAD"): False,
            ("HEAD", "origin/darwin"): True,
            ("backup/darwin", "origin/darwin"): False,
            ("origin/darwin", "backup/darwin"): False,
        }
        with patch.object(main, "_git_is_ancestor", side_effect=lambda older, newer: ancestry[(older, newer)]):
            with self.assertRaises(typer.Exit):
                main._select_sync_target(["origin/darwin", "backup/darwin"])

    def test_push_preflight_rejects_remote_ahead_before_commit(self):
        results = [
            SimpleNamespace(returncode=0),  # fetch
            SimpleNamespace(returncode=0),  # rev-parse --verify
        ]
        with patch.object(main.subprocess, "run", side_effect=results), patch.object(
            main, "_git_output", return_value="2"
        ):
            with self.assertRaises(typer.Exit):
                main._preflight_push_remotes(["origin"], "darwin")

    def test_push_preflight_allows_a_new_remote_branch(self):
        results = [
            SimpleNamespace(returncode=0),  # fetch
            SimpleNamespace(returncode=1),  # rev-parse --verify
        ]
        with patch.object(main.subprocess, "run", side_effect=results):
            new_branches = main._preflight_push_remotes(["backup"], "darwin")
        self.assertEqual(new_branches, {"backup"})

    def test_push_rejects_an_unintentional_machine_branch(self):
        with patch.object(main, "_git_output", return_value="darwin-work-macbook"):
            with self.assertRaises(typer.Exit):
                main.cmd_push(
                    msg="test",
                    remote=None,
                    branch="darwin",
                    machine_only=False,
                    self_only=False,
                    yes=True,
                )


if __name__ == "__main__":
    unittest.main()
