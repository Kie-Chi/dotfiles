import unittest
from types import SimpleNamespace
from unittest.mock import patch

import typer

from envy import main


class GitImpactTests(unittest.TestCase):
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
                    yes=True,
                )


if __name__ == "__main__":
    unittest.main()
