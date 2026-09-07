from __future__ import annotations
import unittest
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from gobrush.compat.dialogs import open_file_dialog, save_file_dialog, _build_image_filters


class TestCompatDialogs(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        Gtk.init()

    def test_build_image_filters(self) -> None:
        filters = _build_image_filters()
        self.assertGreaterEqual(len(filters), 5)
        names = [f.get_name() for f in filters]
        self.assertTrue(any("All Supported Images" in n for n in names))
        self.assertTrue(any("PNG" in n for n in names))

    def test_open_file_dialog_creation(self) -> None:
        result: list[str | None] = []
        dialog = open_file_dialog(None, lambda path: result.append(path), show=False)
        self.assertIsInstance(dialog, Gtk.FileChooserDialog)
        self.assertEqual(dialog.get_action(), Gtk.FileChooserAction.OPEN)
        dialog.destroy()

    def test_save_file_dialog_creation(self) -> None:
        result: list[str | None] = []
        dialog = save_file_dialog(None, lambda path: result.append(path), default_name="test.png", show=False)
        self.assertIsInstance(dialog, Gtk.FileChooserDialog)
        self.assertEqual(dialog.get_action(), Gtk.FileChooserAction.SAVE)
        dialog.destroy()

    def test_open_file_dialog_response(self) -> None:
        result: list[str | None] = []
        win = Gtk.Window()
        dialog = open_file_dialog(win, lambda path: result.append(path), show=False)
        self.assertIs(getattr(win, "_active_file_dialog", None), dialog)
        dialog.response(Gtk.ResponseType.CANCEL)
        self.assertEqual(result, [None])
        self.assertIsNone(getattr(win, "_active_file_dialog", None))


if __name__ == "__main__":
    unittest.main()
