from __future__ import annotations
import unittest
import io
import cairo
from unittest.mock import Mock, patch
from PIL import Image
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Gdk, GLib, Gio

from gobrush.core.loader import load_image_with_info, load_image_from_texture, ImageLoadError
from gobrush.ui.window import MainWindow


class TestClipboardPaste(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        Gtk.init()

    def _create_test_texture(self, width: int = 120, height: int = 80, alpha: bool = True) -> Gdk.Texture:
        mode = "RGBA" if alpha else "RGB"
        color = (255, 100, 50, 180) if alpha else (255, 100, 50)
        im = Image.new(mode, (width, height), color)
        buf = io.BytesIO()
        im.save(buf, format="PNG")
        return Gdk.Texture.new_from_bytes(GLib.Bytes.new(buf.getvalue()))

    def test_load_image_from_texture(self) -> None:
        texture = self._create_test_texture(width=160, height=90, alpha=True)
        surface, has_alpha = load_image_from_texture(texture)
        self.assertIsInstance(surface, cairo.ImageSurface)
        self.assertEqual(surface.get_width(), 160)
        self.assertEqual(surface.get_height(), 90)
        self.assertTrue(has_alpha)

    def test_load_image_with_info_accepts_texture(self) -> None:
        texture = self._create_test_texture(width=64, height=64, alpha=False)
        surface, has_alpha = load_image_with_info(texture)
        self.assertIsInstance(surface, cairo.ImageSurface)
        self.assertEqual(surface.get_width(), 64)
        self.assertEqual(surface.get_height(), 64)

    def test_load_image_from_texture_invalid_object(self) -> None:
        with self.assertRaises(ImageLoadError):
            load_image_from_texture("not-a-texture")

    def test_load_pasted_image_success(self) -> None:
        win = MainWindow()
        self.assertTrue(win.is_empty())

        texture = self._create_test_texture(200, 100)
        ok = win.load_pasted_image(texture)
        self.assertTrue(ok)
        self.assertFalse(win.is_empty())
        self.assertEqual(win.canvas.image_width, 200)
        self.assertEqual(win.canvas.image_height, 100)
        self.assertIsNone(win.current_file_path)
        self.assertEqual(win.get_title(), "Pasted Image - GoBrush")

    def test_load_pasted_image_failure(self) -> None:
        win = MainWindow()
        self.assertTrue(win.is_empty())

        ok = win.load_pasted_image(b"invalid corrupt data")
        self.assertFalse(ok)
        self.assertTrue(win.is_empty())

    def test_paste_from_clipboard_with_texture(self) -> None:
        win = MainWindow()
        texture = self._create_test_texture(100, 50)

        mock_cb = Mock(spec=Gdk.Clipboard)

        def mock_read_texture_async(cancellable, callback, user_data=None):
            mock_res = Mock(spec=Gio.AsyncResult)
            mock_cb.read_texture_finish.return_value = texture
            callback(mock_cb, mock_res)

        mock_cb.read_texture_async.side_effect = mock_read_texture_async

        done = False
        def on_done(ok: bool):
            nonlocal done
            done = ok

        win.paste_from_clipboard(clipboard=mock_cb, callback=on_done)
        self.assertTrue(done)
        self.assertFalse(win.is_empty())
        self.assertEqual(win.canvas.image_width, 100)
        self.assertEqual(win.canvas.image_height, 50)

    def test_paste_from_clipboard_without_image(self) -> None:
        win = MainWindow()
        mock_cb = Mock(spec=Gdk.Clipboard)

        def mock_read_texture_async(cancellable, callback, user_data=None):
            mock_res = Mock(spec=Gio.AsyncResult)
            mock_cb.read_texture_finish.return_value = None
            callback(mock_cb, mock_res)

        def mock_read_text_async(cancellable, callback, user_data=None):
            mock_res = Mock(spec=Gio.AsyncResult)
            mock_cb.read_text_finish.return_value = "just some random text without images"
            callback(mock_cb, mock_res)

        mock_cb.read_texture_async.side_effect = mock_read_texture_async
        mock_cb.read_text_async.side_effect = mock_read_text_async

        done_ok = None
        def on_done(ok: bool):
            nonlocal done_ok
            done_ok = ok

        win.paste_from_clipboard(clipboard=mock_cb, callback=on_done)
        self.assertFalse(done_ok)
        self.assertTrue(win.is_empty())

    def test_ctrl_v_triggers_paste(self) -> None:
        win = MainWindow()
        texture = self._create_test_texture(80, 40)

        mock_cb = Mock(spec=Gdk.Clipboard)
        def mock_read_texture_async(cancellable, callback, user_data=None):
            mock_res = Mock(spec=Gio.AsyncResult)
            mock_cb.read_texture_finish.return_value = texture
            callback(mock_cb, mock_res)
        mock_cb.read_texture_async.side_effect = mock_read_texture_async

        with patch.object(win, "get_clipboard", return_value=mock_cb):
            handled = win._on_key_pressed(
                win._key_controller,
                Gdk.KEY_v,
                0,
                Gdk.ModifierType.CONTROL_MASK,
            )
            self.assertTrue(handled)
            self.assertFalse(win.is_empty())
            self.assertEqual(win.canvas.image_width, 80)
            self.assertEqual(win.canvas.image_height, 40)

    def test_win_paste_action(self) -> None:
        win = MainWindow()
        texture = self._create_test_texture(70, 35)

        mock_cb = Mock(spec=Gdk.Clipboard)
        def mock_read_texture_async(cancellable, callback, user_data=None):
            mock_res = Mock(spec=Gio.AsyncResult)
            mock_cb.read_texture_finish.return_value = texture
            callback(mock_cb, mock_res)
        mock_cb.read_texture_async.side_effect = mock_read_texture_async

        with patch.object(win, "get_clipboard", return_value=mock_cb):
            win.action_paste.activate(None)
            self.assertFalse(win.is_empty())
            self.assertEqual(win.canvas.image_width, 70)

    def test_empty_state_paste_button_triggers_paste(self) -> None:
        win = MainWindow()
        texture = self._create_test_texture(50, 50)

        mock_cb = Mock(spec=Gdk.Clipboard)
        def mock_read_texture_async(cancellable, callback, user_data=None):
            mock_res = Mock(spec=Gio.AsyncResult)
            mock_cb.read_texture_finish.return_value = texture
            callback(mock_cb, mock_res)
        mock_cb.read_texture_async.side_effect = mock_read_texture_async

        with patch.object(win, "get_clipboard", return_value=mock_cb):
            win.empty_state.btn_paste.emit("clicked")
            self.assertFalse(win.is_empty())
            self.assertEqual(win.canvas.image_width, 50)


if __name__ == "__main__":
    unittest.main()
