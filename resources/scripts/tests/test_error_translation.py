import io
import unittest
import subprocess
from unittest.mock import patch

from rich.console import Console

from envy import process
from envy.process import CommandError, translate_failure


class TranslateFailureTests(unittest.TestCase):
    def test_attribute_missing(self):
        hint = translate_failure(["nix"], "error: attribute 'foo' missing")
        self.assertIn("envy host check", hint)

    def test_infinite_recursion(self):
        hint = translate_failure(["nix"], "error: infinite recursion encountered")
        self.assertIn("envy config check", hint)

    def test_hash_mismatch(self):
        hint = translate_failure(["nix"], "hash mismatch in fixed-output derivation")
        self.assertIn("envy update inputs", hint)

    def test_builder_failed(self):
        hint = translate_failure(["nix"], "error: builder for '/nix/store/x.drv' failed")
        self.assertIn("envy doctor", hint)

    def test_syntax_error(self):
        hint = translate_failure(["nix"], "error: syntax error, unexpected }")
        self.assertIn("envy config check", hint)

    def test_sops_no_matching_keys(self):
        hint = translate_failure(["sops"], "sops: no matching creation rules found")
        self.assertIn("age key", hint)

    def test_permission_denied_publickey(self):
        hint = translate_failure(["git"], "git@github.com: Permission denied (publickey).")
        self.assertIn("envy git remote", hint)

    def test_non_fast_forward(self):
        hint = translate_failure(["git"], "! [rejected] master (non-fast-forward)")
        self.assertIn("envy sync", hint)

    def test_no_match_returns_none(self):
        self.assertIsNone(translate_failure(["ls"], "some unrelated failure text"))

    def test_empty_stderr_returns_none(self):
        self.assertIsNone(translate_failure(["nix"], ""))


class RenderCommandErrorTests(unittest.TestCase):
    def test_appends_translation_after_raw_stderr(self):
        error = CommandError(
            subprocess.CompletedProcess(
                ["nix", "build"], 1, "", "error: attribute 'x' missing"
            )
        )
        output = io.StringIO()
        console = Console(file=output, force_terminal=False, width=200)
        with patch.object(process.log, "console", console):
            process.render_command_error(error)
        text = output.getvalue()
        self.assertIn("attribute 'x' missing", text)  # raw stderr preserved
        self.assertIn("envy host check", text)  # translated hint appended


if __name__ == "__main__":
    unittest.main()
