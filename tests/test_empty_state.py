from __future__ import annotations
import unittest
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw

from gobrush.ui.empty_state import EmptyStateView
from gobrush.ui.window import MainWindow


class TestEmptyState(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        Gtk.init()

    def test_empty_state_view_creation(self) -> None:
        opened = False
        pasted = False

        def on_o() -> None:
            nonlocal opened
            opened = True

        def on_p() -> None:
            nonlocal pasted
            pasted = True

        view = EmptyStateView(on_open=on_o, on_paste=on_p)
        self.assertIsInstance(view.status_page, Adw.StatusPage)
        self.assertEqual(view.status_page.get_title(), "GoBrush")
        self.assertEqual(view.btn_open.get_label(), "Open File...")
        self.assertEqual(view.btn_paste.get_label(), "Paste from Clipboard")

        view.btn_open.emit("clicked")
        self.assertTrue(opened)

        view.btn_paste.emit("clicked")
        self.assertTrue(pasted)

    def test_window_empty_state_integration(self) -> None:
        win = MainWindow()
        self.assertTrue(win.is_empty())
        self.assertFalse(win.btn_copy.get_sensitive())
        self.assertFalse(win.btn_save.get_sensitive())

        dummy_widget = Gtk.Label(label="Canvas Placeholder")
        win.show_content(dummy_widget)
        self.assertFalse(win.is_empty())
        self.assertTrue(win.btn_copy.get_sensitive())
        self.assertTrue(win.btn_save.get_sensitive())

        win.show_empty_state()
        self.assertTrue(win.is_empty())
        self.assertFalse(win.btn_copy.get_sensitive())
        self.assertFalse(win.btn_save.get_sensitive())


if __name__ == "__main__":
    unittest.main()
