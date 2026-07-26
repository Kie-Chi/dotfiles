import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from typer.main import get_command

from envy.main import cli, complete_rollback_target
from envy.workflows import generations


class GenerationTests(unittest.TestCase):
    def test_inventory_marks_current_target_and_orders_newest_first(self):
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root)
            target_one = directory / "store-one"
            target_two = directory / "store-two"
            target_one.mkdir()
            target_two.mkdir()
            (directory / "system-1-link").symlink_to(target_one)
            (directory / "system-2-link").symlink_to(target_two)
            current = directory / "current-system"
            current.symlink_to(target_two)

            with patch.object(
                generations, "_profile_candidates",
                return_value=[(directory, "system", current)],
            ):
                rows = generations.generations()

        self.assertEqual([row.number for row in rows], [2, 1])
        self.assertTrue(rows[0].current)
        self.assertFalse(rows[1].current)

    def test_previous_generation_is_older_than_current(self):
        rows = [
            generations.Generation(3, Path("3"), Path("target-3"), "now", True),
            generations.Generation(2, Path("2"), Path("target-2"), "before", False),
        ]
        with patch.object(generations, "generations", return_value=rows):
            self.assertEqual(generations.previous_generation().number, 2)
            self.assertEqual(generations.require_generation(3).target, Path("target-3"))

    def test_generation_completion_is_prefix_filtered_and_marks_current(self):
        rows = [
            generations.Generation(31, Path("31"), Path("target-31"), "today", True),
            generations.Generation(20, Path("20"), Path("target-20"), "yesterday", False),
        ]
        with patch.object(generations, "generations", return_value=rows):
            candidates = generations.complete_generation_numbers(None, "3")
            rollback = complete_rollback_target(None, "")

        self.assertEqual(candidates, [("31", "today [current]")])
        self.assertEqual(rollback[0], ("list", "List all available generations"))
        self.assertIn(("31", "today [current]"), rollback)

    def test_history_diff_registers_completion_for_both_generations(self):
        command = get_command(cli).commands["history"].commands["diff"]
        before = next(param for param in command.params if param.name == "before")
        after = next(param for param in command.params if param.name == "after")

        self.assertIsNotNone(before._custom_shell_complete)
        self.assertIsNotNone(after._custom_shell_complete)


if __name__ == "__main__":
    unittest.main()
