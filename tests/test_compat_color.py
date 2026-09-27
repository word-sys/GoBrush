from __future__ import annotations
import unittest
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk

from gobrush.compat.color import (
    rgba_from_floats,
    rgba_from_hex,
    rgba_to_hex,
    rgba_to_cairo,
    pick_color_dialog,
)


class TestCompatColor(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        Gtk.init()

    def test_rgba_from_floats(self) -> None:
        c = rgba_from_floats(1.0, 0.5, 0.0, 0.8)
        self.assertAlmostEqual(c.red, 1.0)
        self.assertAlmostEqual(c.green, 0.5)
        self.assertAlmostEqual(c.blue, 0.0)
        self.assertAlmostEqual(c.alpha, 0.8)

    def test_hex_conversion(self) -> None:
        c = rgba_from_hex("#FF8800")
        hex_val = rgba_to_hex(c)
        self.assertEqual(hex_val, "#FF8800")

    def test_hex_with_alpha(self) -> None:
        c = rgba_from_floats(1.0, 0.0, 0.0, 0.5)
        hex_val = rgba_to_hex(c, include_alpha=True)
        self.assertEqual(hex_val[:3], "#FF")
        self.assertEqual(hex_val[3:5], "00")
        self.assertEqual(hex_val[5:7], "00")

    def test_cairo_tuple(self) -> None:
        c = rgba_from_floats(0.2, 0.4, 0.6, 1.0)
        t = rgba_to_cairo(c)
        self.assertEqual(len(t), 4)
        self.assertAlmostEqual(t[0], 0.2)
        self.assertAlmostEqual(t[1], 0.4)
        self.assertAlmostEqual(t[2], 0.6)
        self.assertAlmostEqual(t[3], 1.0)

    def test_pick_color_dialog_creation(self) -> None:
        c = rgba_from_floats(1.0, 0.0, 0.0)
        res: list[Gdk.RGBA | None] = []
        dlg = pick_color_dialog(None, c, lambda val: res.append(val), show=False)
        self.assertIsInstance(dlg, Gtk.ColorChooserDialog)
        dlg.destroy()


if __name__ == "__main__":
    unittest.main()
