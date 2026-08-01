from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(os.environ.get("ENVY_TEST_ROOT", Path(__file__).resolve().parents[3]))
SCRIPT = ROOT / "resources" / "scripts" / "nix-trust.sh"
BEGIN = "# BEGIN ENVY MANAGED NIX MIRROR"
END = "# END ENVY MANAGED NIX MIRROR"
THALHEIM = "https://cache.thalheim.io"
THALHEIM_KEY = "cache.thalheim.io-1:R7msbosLEZKrxk/lKxf9BTjOOH7Ax3H0Qj0/6wiHOgc="
USTC = "https://mirrors.ustc.edu.cn/nix-channels/store"


class NixTrustScriptTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.system_config = self.root / "nix.conf"
        self.custom_config = self.root / "nix.custom.conf"
        self.system_config.write_text("!include nix.custom.conf\n")

    def tearDown(self):
        self.root.chmod(0o700)
        self.temporary.cleanup()

    def run_helper(
        self,
        action: str,
        *,
        mode: str = "china",
        systemctl: Path | str = "missing-systemctl",
        environment: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        env = dict(os.environ)
        if environment:
            env.update(environment)
        return subprocess.run(
            [
                "bash",
                str(SCRIPT),
                action,
                "--mode",
                mode,
                "--user",
                "policy-user",
                "--system-config",
                str(self.system_config),
                "--custom-config",
                str(self.custom_config),
                "--systemctl",
                str(systemctl),
            ],
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )

    def test_upstream_policy_always_trusts_sops_nix_cache(self):
        result = self.run_helper("repair", mode="upstream")

        self.assertEqual(result.returncode, 0, result.stderr)
        text = self.custom_config.read_text()
        self.assertIn(f"extra-substituters = {THALHEIM}", text)
        self.assertIn(f"extra-trusted-public-keys = {THALHEIM_KEY}", text)
        self.assertNotIn(USTC, text)
        self.assertIn("extra-trusted-users = policy-user", text)
        self.assertIn("download-attempts = 3", text)

    def test_old_marker_block_is_upgraded_without_touching_admin_content(self):
        self.custom_config.write_text(
            "admin-setting = keep\n"
            f"{BEGIN}\n"
            "extra-trusted-substituters = https://old.invalid\n"
            f"{END}\n"
            "admin-tail = keep\n"
        )

        result = self.run_helper("repair")

        self.assertEqual(result.returncode, 0, result.stderr)
        text = self.custom_config.read_text()
        self.assertTrue(text.startswith("admin-setting = keep\n"))
        self.assertTrue(text.endswith("admin-tail = keep\n"))
        self.assertIn(f"extra-substituters = {THALHEIM} {USTC}", text)
        self.assertNotIn("old.invalid", text)
        self.assertEqual(text.count(BEGIN), 1)
        self.assertEqual(text.count(END), 1)

    def test_repair_is_idempotent_and_restarts_only_after_change(self):
        calls = self.root / "systemctl.calls"
        systemctl = self.root / "systemctl"
        bash = shutil.which("bash")
        self.assertIsNotNone(bash)
        systemctl.write_text(
            f"#!{bash}\n"
            "set -eu\n"
            "if [ \"$1\" = is-active ]; then\n"
            "  [ \"${3:-}\" = nix-daemon.service ]\n"
            "  exit\n"
            "fi\n"
            f"printf '%s\\n' \"$*\" >> {str(calls)!r}\n"
        )
        systemctl.chmod(0o755)

        first = self.run_helper("repair", systemctl=systemctl)
        inode = self.custom_config.stat().st_ino
        second = self.run_helper("repair", systemctl=systemctl)

        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(self.custom_config.stat().st_ino, inode)
        self.assertTrue(
            calls.is_file(),
            f"first={first.stdout!r}/{first.stderr!r}; "
            f"second={second.stdout!r}/{second.stderr!r}",
        )
        self.assertEqual(calls.read_text().splitlines(), ["restart nix-daemon.service"])

    def test_malformed_markers_fail_without_modifying_file(self):
        original = f"admin-setting = keep\n{BEGIN}\nunfinished = true\n"
        self.custom_config.write_text(original)

        result = self.run_helper("repair")

        self.assertEqual(result.returncode, 2)
        self.assertIn("malformed", result.stderr)
        self.assertEqual(self.custom_config.read_text(), original)

    def test_status_reports_repair_without_writing(self):
        original = "admin-setting = keep\n"
        self.custom_config.write_text(original)

        result = self.run_helper("status")

        self.assertEqual(result.returncode, 1)
        self.assertIn("requires repair", result.stdout)
        self.assertEqual(self.custom_config.read_text(), original)

    def test_ready_configuration_needs_no_sudo_or_write(self):
        self.assertEqual(self.run_helper("repair").returncode, 0)
        inode = self.custom_config.stat().st_ino
        self.root.chmod(0o500)
        try:
            result = self.run_helper(
                "repair", environment={"ENVY_NIX_TRUST_SUDO": "missing-sudo"}
            )
        finally:
            self.root.chmod(0o700)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.custom_config.stat().st_ino, inode)

    @unittest.skipIf(os.geteuid() == 0, "root does not need sudo for the test directory")
    def test_missing_sudo_fails_explicitly_when_repair_needs_root(self):
        self.root.chmod(0o500)
        try:
            result = self.run_helper(
                "repair", environment={"ENVY_NIX_TRUST_SUDO": "missing-sudo"}
            )
        finally:
            self.root.chmod(0o700)

        self.assertEqual(result.returncode, 2)
        self.assertIn("sudo is unavailable", result.stderr)
        self.assertFalse(self.custom_config.exists())

    def test_missing_parent_include_fails_without_writing(self):
        self.system_config.write_text("experimental-features = nix-command flakes\n")

        result = self.run_helper("repair")

        self.assertEqual(result.returncode, 2)
        self.assertIn("does not include nix.custom.conf", result.stderr)
        self.assertFalse(self.custom_config.exists())


if __name__ == "__main__":
    unittest.main()
