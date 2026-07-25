import importlib.util
import os
import tempfile
import unittest
from pathlib import Path


ROOT = Path(os.environ.get("ENVY_TEST_ROOT", Path(__file__).resolve().parents[3]))
MODULE_PATH = ROOT / "resources/helpers/codegraph-codex.py"
SPEC = importlib.util.spec_from_file_location("codegraph_codex", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
codegraph_codex = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(codegraph_codex)


class CodegraphCodexConfigTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.config = Path(self.tempdir.name) / "config.toml"

    def tearDown(self):
        self.tempdir.cleanup()

    def test_indented_table_moves_after_siblings_without_rewriting_them(self):
        sibling = (
            "  [mcp_servers.computer-use]\n"
            '    command = "computer-use"\n'
            "  [mcp_servers.node_repl]\n"
            '    command = "node"\n'
            "    [mcp_servers.node_repl.env]\n"
            '      MODE = "safe"\n'
        )
        self.config.write_text(
            "model = \"gpt-5\"\n\n"
            "[mcp_servers]\n"
            "  [mcp_servers.codegraph]\n"
            '    args = ["serve", "--mcp"]\n'
            '    command = "codegraph"\n'
            + sibling
        )

        self.assertTrue(codegraph_codex.normalize_codegraph_table(self.config))

        result = self.config.read_text()
        self.assertIn(sibling, result)
        self.assertEqual(result.count("[mcp_servers.codegraph]"), 1)
        self.assertTrue(
            result.endswith(
                "[mcp_servers.codegraph]\n"
                'command = "codegraph"\n'
                'args = ["serve", "--mcp"]\n'
            )
        )

    def test_duplicate_tables_and_descendants_collapse_to_one(self):
        self.config.write_text(
            "[mcp_servers]\n"
            "  [mcp_servers.codegraph]\n"
            '    command = "old"\n'
            "    [mcp_servers.codegraph.env]\n"
            '      OLD = "1"\n'
            "  [mcp_servers.other]\n"
            '    command = "keep"\n\n'
            "[mcp_servers.codegraph]\n"
            'command = "duplicate"\n'
        )

        self.assertTrue(codegraph_codex.normalize_codegraph_table(self.config))

        result = self.config.read_text()
        self.assertEqual(result.count("[mcp_servers.codegraph]"), 1)
        self.assertNotIn("[mcp_servers.codegraph.env]", result)
        self.assertNotIn('command = "old"', result)
        self.assertNotIn('command = "duplicate"', result)
        self.assertIn("[mcp_servers.other]", result)
        self.assertIn('command = "keep"', result)

    def test_canonical_result_is_idempotent(self):
        self.config.write_text(
            "model = \"gpt-5\"\n\n"
            "[mcp_servers.codegraph]\n"
            'command = "codegraph"\n'
            'args = ["serve", "--mcp"]\n'
        )

        before = self.config.read_bytes()
        self.assertFalse(codegraph_codex.normalize_codegraph_table(self.config))
        self.assertEqual(self.config.read_bytes(), before)

    def test_missing_table_is_added_but_missing_file_is_untouched(self):
        self.config.write_text("model = \"gpt-5\"\n")

        self.assertTrue(codegraph_codex.normalize_codegraph_table(self.config))
        self.assertEqual(
            self.config.read_text(),
            "model = \"gpt-5\"\n\n"
            "[mcp_servers.codegraph]\n"
            'command = "codegraph"\n'
            'args = ["serve", "--mcp"]\n',
        )
        self.assertFalse(
            codegraph_codex.normalize_codegraph_table(self.config.with_name("missing.toml"))
        )


if __name__ == "__main__":
    unittest.main()
