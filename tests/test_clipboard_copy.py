from __future__ import annotations
import tempfile
from pathlib import Path
import unittest
from unittest.mock import Mock, patch
import uuid
import cairo
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Gdk, Gio

from gobrush.app import GoBrushApp
from gobrush.ui.canvas import Canvas
from gobrush.ui.window import MainWindow


def _create_test_app() -> GoBrushApp:
    return GoBrushApp(application_id=f"io.github.word_sys.GoBrush.t{uuid.uuid4().hex[:8]}")


class TestClipboardCopy(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        Gtk.init()

    def test_get_flattened_surface_without_image(self) -> None:
        canvas = Canvas()
        self.assertIsNone(canvas.get_flattened_surface())

    def test_get_flattened_surface_with_image(self) -> None:
        canvas = Canvas()
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 100, 80)
        cr = cairo.Context(surf)
        cr.set_source_rgb(0.5, 0.2, 0.8)
        cr.paint()

        canvas.set_image_surface(surf, 100, 80)
        flat = canvas.get_flattened_surface()
        self.assertIsNotNone(flat)
        self.assertEqual(flat.get_width(), 100)
        self.assertEqual(flat.get_height(), 80)

    def test_get_flattened_surface_includes_image_draw_hooks(self) -> None:
        canvas = Canvas()
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 60, 40)
        canvas.set_image_surface(surf, 60, 40)

        hook_called = False

        def sample_hook(cr: cairo.Context) -> None:
            nonlocal hook_called
            hook_called = True
            cr.set_source_rgba(1.0, 0.0, 0.0, 1.0)
            cr.rectangle(5, 5, 20, 20)
            cr.fill()

        canvas.add_image_draw_hook(sample_hook)
        flat = canvas.get_flattened_surface()
        self.assertIsNotNone(flat)
        self.assertTrue(hook_called)

    def test_copy_to_clipboard_empty_state(self) -> None:
        win = MainWindow()
        mock_cb = Mock()
        res = win.copy_to_clipboard(clipboard=mock_cb)
        self.assertFalse(res)
        mock_cb.set_content.assert_not_called()
        mock_cb.set.assert_not_called()

    def test_copy_to_clipboard_with_image_success(self) -> None:
        win = MainWindow()
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 50, 50)
        win.load_surface(surf, has_alpha=False)

        mock_cb = Mock()
        callback_called = False

        def cb_result(ok: bool) -> None:
            nonlocal callback_called
            callback_called = ok

        res = win.copy_to_clipboard(clipboard=mock_cb, callback=cb_result)
        self.assertTrue(res)
        self.assertTrue(callback_called)
        mock_cb.set_content.assert_called_once()
        args, _ = mock_cb.set_content.call_args
        cp = args[0]
        self.assertIsInstance(cp, Gdk.ContentProvider)
        formats = cp.ref_formats()
        self.assertTrue(formats.contain_mime_type("image/png"))
        self.assertTrue(
            formats.contain_gtype(Gdk.MemoryTexture.__gtype__)
            or formats.contain_gtype(Gdk.Texture.__gtype__)
        )

    def test_copy_preserves_jpeg_format(self) -> None:
        win = MainWindow()
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 50, 50)
        win.load_surface(surf, has_alpha=False, image_format="jpeg")

        mock_cb = Mock()
        res = win.copy_to_clipboard(clipboard=mock_cb)
        self.assertTrue(res)
        mock_cb.set_content.assert_called_once()
        cp = mock_cb.set_content.call_args[0][0]
        formats = cp.ref_formats()
        self.assertTrue(formats.contain_mime_type("image/jpeg"))
        self.assertTrue(formats.contain_mime_type("image/jpg"))
        self.assertEqual(formats.get_mime_types()[0], "image/jpeg")
        self.assertTrue(formats.contain_mime_type("image/png"))

    def test_copy_preserves_ico_format(self) -> None:
        win = MainWindow()
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 50, 50)
        win.load_surface(surf, has_alpha=True, image_format="ico")

        mock_cb = Mock()
        res = win.copy_to_clipboard(clipboard=mock_cb)
        self.assertTrue(res)
        mock_cb.set_content.assert_called_once()
        cp = mock_cb.set_content.call_args[0][0]
        formats = cp.ref_formats()
        self.assertTrue(formats.contain_mime_type("image/x-icon"))
        self.assertEqual(formats.get_mime_types()[0], "image/x-icon")
        self.assertTrue(formats.contain_mime_type("image/png"))

    def test_copy_preserves_svg_format(self) -> None:
        win = MainWindow()
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 50, 50)
        win.load_surface(surf, has_alpha=True, image_format="svg")

        mock_cb = Mock()
        res = win.copy_to_clipboard(clipboard=mock_cb)
        self.assertTrue(res)
        mock_cb.set_content.assert_called_once()
        cp = mock_cb.set_content.call_args[0][0]
        formats = cp.ref_formats()
        self.assertTrue(formats.contain_mime_type("image/svg+xml"))
        self.assertEqual(formats.get_mime_types()[0], "image/svg+xml")
        self.assertTrue(formats.contain_mime_type("image/png"))

    def test_copy_unmodified_svg_file_preserves_exact_bytes(self) -> None:
        svg_content = b'<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10"><rect width="10" height="10" fill="red"/></svg>'
        with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as f:
            f.write(svg_content)
            svg_path = f.name

        try:
            win = MainWindow()
            surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 10, 10)
            win.load_surface(surf, has_alpha=True, file_path=svg_path)

            mock_cb = Mock()
            res = win.copy_to_clipboard(clipboard=mock_cb)
            self.assertTrue(res)
            mock_cb.set_content.assert_called_once()
            cp = mock_cb.set_content.call_args[0][0]
            formats = cp.ref_formats()
            self.assertTrue(formats.contain_mime_type("image/svg+xml"))
            self.assertEqual(formats.get_mime_types()[0], "image/svg+xml")
            self.assertTrue(formats.contain_mime_type("text/uri-list"))
        finally:
            Path(svg_path).unlink(missing_ok=True)

    def test_copy_unmodified_jpeg_file_preserves_exact_bytes(self) -> None:
        jpeg_header = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 30
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(jpeg_header)
            jpg_path = f.name

        try:
            win = MainWindow()
            surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 10, 10)
            win.load_surface(surf, has_alpha=False, file_path=jpg_path)

            mock_cb = Mock()
            res = win.copy_to_clipboard(clipboard=mock_cb)
            self.assertTrue(res)
            mock_cb.set_content.assert_called_once()
            cp = mock_cb.set_content.call_args[0][0]
            formats = cp.ref_formats()
            self.assertTrue(formats.contain_mime_type("image/jpeg"))
            self.assertEqual(formats.get_mime_types()[0], "image/jpeg")
            self.assertTrue(formats.contain_mime_type("text/uri-list"))
        finally:
            Path(jpg_path).unlink(missing_ok=True)

    def test_copy_to_clipboard_no_clipboard_available(self) -> None:
        win = MainWindow()
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 50, 50)
        win.load_surface(surf, has_alpha=False)

        with patch.object(win, "get_clipboard", return_value=None):
            res = win.copy_to_clipboard(clipboard=None)
            self.assertFalse(res)

    def test_btn_copy_sensitivity(self) -> None:
        win = MainWindow()
        # In empty state, btn_copy is disabled
        self.assertFalse(win.btn_copy.get_sensitive())

        # Load image -> btn_copy becomes enabled
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 50, 50)
        win.load_surface(surf, has_alpha=False)
        self.assertTrue(win.btn_copy.get_sensitive())

        # Close file -> btn_copy is disabled again
        win.close_file()
        self.assertFalse(win.btn_copy.get_sensitive())

    def test_btn_copy_triggers_copy(self) -> None:
        win = MainWindow()
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 50, 50)
        win.load_surface(surf, has_alpha=False)

        with patch.object(win, "copy_to_clipboard") as mock_copy:
            win.btn_copy.emit("clicked")
            mock_copy.assert_called_once()

    def test_ctrl_c_triggers_copy(self) -> None:
        win = MainWindow()
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 50, 50)
        win.load_surface(surf, has_alpha=False)

        with patch.object(win, "copy_to_clipboard") as mock_copy:
            handled = win._on_key_pressed(
                win._key_controller,
                Gdk.KEY_c,
                0,
                Gdk.ModifierType.CONTROL_MASK,
            )
            self.assertTrue(handled)
            mock_copy.assert_called_once()

    def test_win_copy_action(self) -> None:
        win = MainWindow()
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 50, 50)
        win.load_surface(surf, has_alpha=False)

        with patch.object(win, "copy_to_clipboard") as mock_copy:
            win.action_copy.activate(None)
            mock_copy.assert_called_once()

    def test_app_copy_action(self) -> None:
        app = _create_test_app()
        app.register(None)

        win = MainWindow(application=app)
        win.present()
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 50, 50)
        win.load_surface(surf, has_alpha=False)

        with patch.object(win, "copy_to_clipboard") as mock_copy:
            action = app.lookup_action("copy-clipboard")
            self.assertIsNotNone(action)
            action.activate(None)
            mock_copy.assert_called_once()


if __name__ == "__main__":
    unittest.main()
