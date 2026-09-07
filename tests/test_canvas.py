from __future__ import annotations
import unittest
from unittest.mock import Mock
import cairo
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw

from gobrush.ui.canvas import Canvas
from gobrush.ui.window import MainWindow


class TestCanvas(unittest.TestCase):
    def setUp(self) -> None:
        self.app = Adw.Application(application_id="io.github.word_sys.GoBrush.TestCanvas")

    def test_canvas_init(self) -> None:
        canvas = Canvas()
        self.assertIsInstance(canvas, Gtk.DrawingArea)
        self.assertTrue(canvas.get_hexpand())
        self.assertTrue(canvas.get_vexpand())
        self.assertTrue(canvas.get_focusable())
        self.assertFalse(canvas.has_image)
        self.assertIsNone(canvas.image_surface)
        self.assertEqual(canvas.image_width, 0)
        self.assertEqual(canvas.image_height, 0)
        self.assertEqual(canvas.background_color, (0.12, 0.12, 0.14, 1.0))

    def test_canvas_set_and_clear_surface(self) -> None:
        canvas = Canvas()
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 320, 240)
        canvas.set_image_surface(surface)

        self.assertTrue(canvas.has_image)
        self.assertIs(canvas.image_surface, surface)
        self.assertEqual(canvas.image_width, 320)
        self.assertEqual(canvas.image_height, 240)

        canvas.clear()
        self.assertFalse(canvas.has_image)
        self.assertIsNone(canvas.image_surface)
        self.assertEqual(canvas.image_width, 0)
        self.assertEqual(canvas.image_height, 0)

    def test_canvas_background_color_property(self) -> None:
        canvas = Canvas()
        new_color = (0.2, 0.3, 0.4, 1.0)
        canvas.background_color = new_color
        self.assertEqual(canvas.background_color, new_color)

    def test_canvas_draw_rendering(self) -> None:
        canvas = Canvas()
        target_surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 100, 100)
        cr = cairo.Context(target_surface)

        # Draw without image surface
        canvas._on_draw(canvas, cr, 100, 100)

        # Draw with image surface
        img = cairo.ImageSurface(cairo.FORMAT_ARGB32, 50, 50)
        canvas.set_image_surface(img)
        canvas._on_draw(canvas, cr, 100, 100)

    def test_canvas_draw_hooks(self) -> None:
        canvas = Canvas()
        target_surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 100, 100)
        cr = cairo.Context(target_surface)

        mock_hook = Mock()
        canvas.add_draw_hook(mock_hook)

        canvas._on_draw(canvas, cr, 100, 100)
        mock_hook.assert_called_once_with(cr, 100, 100)

        # Remove hook
        mock_hook.reset_mock()
        canvas.remove_draw_hook(mock_hook)
        canvas._on_draw(canvas, cr, 100, 100)
        mock_hook.assert_not_called()

    def test_window_canvas_integration(self) -> None:
        win = MainWindow(application=self.app)
        self.assertIsInstance(win.canvas, Canvas)
        self.assertTrue(win.is_empty())

        win.show_canvas()
        self.assertFalse(win.is_empty())
        self.assertIs(win.content_bin.get_child(), win.canvas)
        self.assertTrue(win.btn_copy.get_sensitive())
        self.assertTrue(win.btn_save.get_sensitive())

        win.show_empty_state()
        self.assertTrue(win.is_empty())
        self.assertFalse(win.btn_copy.get_sensitive())
        self.assertFalse(win.btn_save.get_sensitive())


if __name__ == "__main__":
    unittest.main()
