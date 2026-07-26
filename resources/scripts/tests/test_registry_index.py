import tempfile
import unittest
from pathlib import Path

from envy.search.index import RegistryIndex
from envy.search.model import ProviderReport, SearchResult


class RegistryIndexTests(unittest.TestCase):
    @staticmethod
    def _result(name="ruff"):
        return SearchResult(
            source="pypi", ecosystem="pypi", name=name, kind="tool",
            version="1.2.3", ref=f"pypi:{name}",
        )

    def test_exact_identity_round_trip_uses_name_or_canonical_ref(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "registry" / "index.sqlite3"
            index = RegistryIndex(path)

            self.assertEqual(index.put_results([self._result()]), 1)

            by_name = index.lookup("pypi", "tool", "RUFF")
            by_ref = index.lookup("pypi", "tool", "pypi:ruff")
            self.assertEqual(by_name.result.ref, "pypi:ruff")
            self.assertEqual(by_ref.result.version, "1.2.3")
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            self.assertEqual(path.parent.stat().st_mode & 0o777, 0o700)

    def test_stale_entries_require_explicit_offline_acceptance(self):
        with tempfile.TemporaryDirectory() as root:
            index = RegistryIndex(Path(root) / "index.sqlite3")
            index.put_results([self._result()], ttl_seconds=1, now=1)

            self.assertIsNone(index.lookup("pypi", "tool", "ruff"))
            stale = index.lookup("pypi", "tool", "ruff", allow_stale=True)
            self.assertTrue(stale.stale)

    def test_successful_report_clears_negative_cache(self):
        with tempfile.TemporaryDirectory() as root:
            index = RegistryIndex(Path(root) / "index.sqlite3")
            index.put_miss("pypi", "tool", "ruff")
            self.assertTrue(index.recently_missing("pypi", "tool", "ruff"))

            count = index.put_reports([ProviderReport("pypi", [self._result()])])

            self.assertEqual(count, 1)
            self.assertFalse(index.recently_missing("pypi", "tool", "ruff"))

    def test_stats_and_clear_do_not_require_an_existing_index(self):
        with tempfile.TemporaryDirectory() as root:
            index = RegistryIndex(Path(root) / "index.sqlite3")
            self.assertEqual(index.stats()["entries"], 0)
            self.assertFalse(index.clear())
            index.put_results([self._result()])
            self.assertEqual(index.stats()["providers"], {"pypi": 1})
            self.assertTrue(index.clear())

    def test_suggest_is_prefix_filtered_and_does_not_create_an_empty_index(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "registry" / "index.sqlite3"
            index = RegistryIndex(path)

            self.assertEqual(index.suggest("pypi", "tool", "r"), [])
            self.assertIsNone(index.lookup("pypi", "tool", "ruff"))
            self.assertFalse(index.recently_missing("pypi", "tool", "ruff"))
            self.assertFalse(path.exists())

            index.put_results([self._result("ruff"), self._result("uv")])
            matches = index.suggest("pypi", "tool", "ru")

            self.assertEqual([match.result.name for match in matches], ["ruff"])
            self.assertEqual(index.suggest("pypi", "package", "ru"), [])


if __name__ == "__main__":
    unittest.main()
