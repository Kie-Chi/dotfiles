import subprocess
import unittest
from unittest.mock import patch

from envy.mirror import mirror_entries, probe_endpoint, probe_specs


class MirrorTests(unittest.TestCase):
    def test_entries_flatten_effective_values_and_hide_probe_metadata(self):
        mirrors = {
            "mode": "china",
            "nix": {"substituters": ["https://mirror.invalid", "https://cache.invalid"]},
            "dockerInstallerMirror": None,
            "probes": [{"name": "Nix", "url": "https://mirror.invalid/info"}],
        }

        self.assertEqual(
            list(mirror_entries(mirrors)),
            [
                ("mode", "china"),
                ("dockerInstallerMirror", "disabled"),
                ("nix.substituters[0]", "https://mirror.invalid"),
                ("nix.substituters[1]", "https://cache.invalid"),
            ],
        )

    def test_probe_specs_ignore_malformed_manifest_values(self):
        mirrors = {
            "probes": [
                {"name": "Nix", "url": "https://mirror.invalid/info"},
                {"name": "missing-url"},
                "invalid",
            ]
        }

        self.assertEqual(
            probe_specs(mirrors),
            [("Nix", "https://mirror.invalid/info")],
        )

    @patch("envy.mirror.subprocess.run")
    def test_successful_probe_reports_http_status_and_latency(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, "200\t0.1234", "")

        result = probe_endpoint("Nix", "https://mirror.invalid/info", timeout=7)

        self.assertTrue(result.ok)
        self.assertEqual(result.status, "200")
        self.assertEqual(result.elapsed_ms, 123)
        self.assertIn("--head", run.call_args.args[0])
        self.assertIn("7", run.call_args.args[0])

    @patch("envy.mirror.subprocess.run")
    def test_failed_probe_preserves_non_secret_error_detail(self, run):
        run.return_value = subprocess.CompletedProcess([], 28, "000\t5.0", "timeout")

        result = probe_endpoint("Nix", "https://mirror.invalid/info")

        self.assertFalse(result.ok)
        self.assertEqual(result.status, "000")
        self.assertEqual(result.detail, "timeout")


if __name__ == "__main__":
    unittest.main()
