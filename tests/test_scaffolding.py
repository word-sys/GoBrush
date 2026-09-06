from __future__ import annotations
import unittest
import gobrush


class TestScaffolding(unittest.TestCase):
    def test_version(self) -> None:
        self.assertEqual(gobrush.__version__, "0.1.0")

    def test_app_id(self) -> None:
        self.assertEqual(gobrush.__app_id__, "io.github.gobrush.GoBrush")


if __name__ == "__main__":
    unittest.main()
