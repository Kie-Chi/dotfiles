import unittest

from envy.evaluation import manifest_selection_rows, manifest_settings


class EvaluationTests(unittest.TestCase):
    def test_settings_are_read_from_the_evaluated_manifest(self):
        values = manifest_settings({
            "settings": {
                "envy.proxy.mode": "none",
                "envy.proxy.tun": False,
            }
        })

        self.assertEqual(values["envy.proxy.mode"], "none")
        self.assertEqual(values["envy.proxy.tun"], "false")

    def test_selection_rows_include_all_three_views(self):
        manifest = {
            "packages": {"home": ["git"]},
            "homebrew": {},
            "inclusions": {"packages": {"home": ["git", "okular"]}},
            "exclusions": {"packages": {"home": ["okular"]}},
        }

        rows = {path: (include, exclude, effective) for path, include, exclude, effective
                in manifest_selection_rows(manifest)}

        self.assertEqual(
            rows["envy.packages.home"],
            (["git", "okular"], ["okular"], ["git"]),
        )


if __name__ == "__main__":
    unittest.main()
