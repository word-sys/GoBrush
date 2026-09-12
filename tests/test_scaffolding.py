from __future__ import annotations
import unittest
import gobrush


class TestScaffolding(unittest.TestCase):
    def test_version(self) -> None:
        self.assertEqual(gobrush.__version__, "0.1.0")

    def test_app_id(self) -> None:
        self.assertEqual(gobrush.__app_id__, "io.github.word_sys.GoBrush")

    def test_readme(self) -> None:
        import pathlib
        readme = pathlib.Path(__file__).resolve().parent.parent / "README.md"
        self.assertTrue(readme.exists())
        content = readme.read_text(encoding="utf-8")
        self.assertIn("# GoBrush", content)
        self.assertIn("Requirements", content)
        self.assertIn("Shortcuts", content)


if __name__ == "__main__":
    unittest.main()
