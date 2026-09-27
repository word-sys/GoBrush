from __future__ import annotations
import tempfile
import unittest
from pathlib import Path
from PIL import Image
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Gdk, Gio, GObject

from gobrush.ui.window import MainWindow


class TestDragDrop(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        Gtk.init()

    def setUp(self) -> None:
        self.win = MainWindow()

    def test_drop_target_configuration(self) -> None:
        target = self.win.drop_target
        self.assertIsInstance(target, Gtk.DropTarget)
        self.assertTrue(bool(target.get_actions() & Gdk.DragAction.COPY))

        gtypes = target.get_gtypes()
        type_names = [GObject.type_name(t) for t in gtypes]
        self.assertTrue(any("GdkFileList" in name for name in type_names))
        self.assertTrue(any("GFile" in name for name in type_names))
        self.assertTrue(any("gchararray" in name for name in type_names))

    def test_extract_paths_from_various_sources(self) -> None:
        # Single URI with URL encoding
        uri1 = "file:///home/user/my%20test%20image.png"
        paths1 = MainWindow._extract_paths_from_drop_value(uri1)
        self.assertEqual(paths1, ["/home/user/my test image.png"])

        # Multiple URIs (RFC 2483 text/uri-list with comments)
        uri_list = "# Header comment\r\nfile:///tmp/img1.png\r\nfile:///tmp/img2.jpg\r\n\r\n"
        paths2 = MainWindow._extract_paths_from_drop_value(uri_list)
        self.assertEqual(paths2, ["/tmp/img1.png", "/tmp/img2.jpg"])

        # Direct absolute path string
        paths3 = MainWindow._extract_paths_from_drop_value("/tmp/photo.webp")
        self.assertEqual(paths3, ["/tmp/photo.webp"])

        # Single Gio.File
        gfile = Gio.File.new_for_path("/tmp/sample.png")
        paths4 = MainWindow._extract_paths_from_drop_value(gfile)
        self.assertEqual(paths4, ["/tmp/sample.png"])

        # Empty or None
        self.assertEqual(MainWindow._extract_paths_from_drop_value(None), [])
        self.assertEqual(MainWindow._extract_paths_from_drop_value("   \n\n"), [])

    def test_drop_valid_png_file_path(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            im = Image.new("RGBA", (100, 60), (255, 0, 0, 255))
            im.save(tmp.name, format="PNG")
            path = tmp.name

        try:
            self.assertTrue(self.win.is_empty())
            res = self.win._on_drop(self.win.drop_target, path, 50.0, 50.0)
            self.assertTrue(res)
            self.assertFalse(self.win.is_empty())
            self.assertEqual(self.win.current_file_path, str(Path(path).resolve()))
            self.assertTrue(self.win.canvas.has_image)
            self.assertEqual(self.win.canvas.image_width, 100)
            self.assertEqual(self.win.canvas.image_height, 60)
            self.assertIn(Path(path).name, self.win.get_title())
        finally:
            Path(path).unlink(missing_ok=True)

    def test_drop_valid_gio_file(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
            im = Image.new("RGB", (80, 50), (0, 255, 0))
            im.save(tmp.name, format="JPEG")
            path = tmp.name

        try:
            gfile = Gio.File.new_for_path(path)
            res = self.win._on_drop(self.win.drop_target, gfile, 10.0, 10.0)
            self.assertTrue(res)
            self.assertFalse(self.win.is_empty())
            self.assertEqual(self.win.canvas.image_width, 80)
            self.assertEqual(self.win.canvas.image_height, 50)
        finally:
            Path(path).unlink(missing_ok=True)

    def test_drop_unsupported_file_format(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as tmp:
            tmp.write(b"Hello text file")
            path = tmp.name

        try:
            res = self.win._on_drop(self.win.drop_target, path, 0.0, 0.0)
            self.assertFalse(res)
            self.assertTrue(self.win.is_empty())
        finally:
            Path(path).unlink(missing_ok=True)

    def test_drop_nonexistent_file(self) -> None:
        res = self.win._on_drop(self.win.drop_target, "/missing/photo_12345.png", 0.0, 0.0)
        self.assertFalse(res)
        self.assertTrue(self.win.is_empty())

    def test_close_file_resets_view(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            im = Image.new("RGB", (30, 30), (0, 0, 255))
            im.save(tmp.name, format="PNG")
            path = tmp.name

        try:
            self.win.open_file(path)
            self.assertFalse(self.win.is_empty())

            self.win.close_file()
            self.assertTrue(self.win.is_empty())
            self.assertIsNone(self.win.current_file_path)
            self.assertEqual(self.win.get_title(), "GoBrush")
            self.assertFalse(self.win.canvas.has_image)
        finally:
            Path(path).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
