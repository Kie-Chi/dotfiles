import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from envy import utils


class EnvyRootResolutionTests(unittest.TestCase):
    def test_stale_legacy_environment_falls_back_to_working_checkout(self):
        with tempfile.TemporaryDirectory() as tempdir:
            checkout = Path(tempdir) / "envy"
            checkout.mkdir()
            (checkout / "flake.nix").touch()
            (checkout / "resources" / "scripts" / "envy").mkdir(parents=True)
            stale = Path(tempdir) / "dotfiles"

            with patch.dict(
                os.environ,
                {
                    "ENVY_ROOT": "",
                    "ENVY_DOTFILES": "",
                    "DOTFILES_DIR": str(stale),
                },
            ), patch.object(Path, "cwd", return_value=checkout):
                self.assertEqual(utils._resolve_envy_root(), checkout)

    def test_valid_legacy_environment_remains_supported(self):
        with tempfile.TemporaryDirectory() as tempdir:
            checkout = Path(tempdir) / "envy"
            checkout.mkdir()
            (checkout / "flake.nix").touch()
            (checkout / "resources" / "scripts" / "envy").mkdir(parents=True)

            with patch.dict(
                os.environ,
                {
                    "ENVY_ROOT": "",
                    "ENVY_DOTFILES": str(checkout),
                    "DOTFILES_DIR": "",
                },
            ):
                self.assertEqual(utils._resolve_envy_root(), checkout)


if __name__ == "__main__":
    unittest.main()
