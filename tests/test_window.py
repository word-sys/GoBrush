from __future__ import annotations
import unittest
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw

from gobrush.ui.window import MainWindow


class TestWindow(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        Gtk.init()

    def test_window_initialization(self) -> None:
        win = MainWindow()
        self.assertEqual(win.get_title(), "GoBrush")
        self.assertIsNotNone(win.header_bar)
        self.assertIsNotNone(win.btn_open)
        self.assertIsNotNone(win.btn_undo)
        self.assertIsNotNone(win.btn_redo)
        self.assertIsNotNone(win.btn_copy)
        self.assertIsNotNone(win.btn_save)

    def test_button_sensitivities(self) -> None:
        win = MainWindow()
        self.assertFalse(win.btn_undo.get_sensitive())
        self.assertFalse(win.btn_redo.get_sensitive())
        self.assertFalse(win.btn_copy.get_sensitive())

        win.set_undo_sensitive(True)
        self.assertTrue(win.btn_undo.get_sensitive())

        win.set_redo_sensitive(True)
        self.assertTrue(win.btn_redo.get_sensitive())

        win.set_has_image(True)
        self.assertTrue(win.btn_copy.get_sensitive())
        self.assertTrue(win.btn_save.get_sensitive())


if __name__ == "__main__":
    unittest.main()
