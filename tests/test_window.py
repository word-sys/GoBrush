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
        self.assertEqual(win.btn_open.get_label(), "Open")
        self.assertEqual(win.btn_save.get_label(), "Save")
        self.assertEqual(win.btn_undo.get_icon_name(), "edit-undo-symbolic")
        self.assertEqual(win.btn_redo.get_icon_name(), "edit-redo-symbolic")
        self.assertEqual(win.btn_copy.get_icon_name(), "edit-copy-symbolic")

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

    def test_toast_overlay(self) -> None:
        win = MainWindow()
        self.assertIsInstance(win.toast_overlay, Adw.ToastOverlay)
        self.assertIsInstance(win.content_bin, Adw.Bin)

        t1 = win.show_toast("Copied to clipboard", timeout=2)
        self.assertIsInstance(t1, Adw.Toast)
        self.assertEqual(t1.get_title(), "Copied to clipboard")
        self.assertEqual(t1.get_timeout(), 2)

        t2 = win.show_toast_with_action("Saved", "Open", "app.open-saved", timeout=4)
        self.assertIsInstance(t2, Adw.Toast)
        self.assertEqual(t2.get_title(), "Saved")
        self.assertEqual(t2.get_button_label(), "Open")
        self.assertEqual(t2.get_action_name(), "app.open-saved")


if __name__ == "__main__":
    unittest.main()
