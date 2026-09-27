from __future__ import annotations
import unittest
import cairo
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk
from gobrush.ui.canvas import Canvas


class TestCanvasSharpening(unittest.TestCase):
    def setUp(self) -> None:
        self.canvas = Canvas()
        self.surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 200, 200)
        self.canvas.set_image_surface(self.surface, 200, 200)

    def test_default_crisp_zoom_enabled(self) -> None:
        self.assertTrue(self.canvas.crisp_zoom)

    def test_filter_at_100_percent_zoom(self) -> None:
        self.canvas.set_zoom(1.0)
        self.assertEqual(self.canvas.get_active_filter(), cairo.FILTER_NEAREST)

    def test_filter_at_magnified_zoom(self) -> None:
        self.canvas.set_zoom(3.5)
        self.assertEqual(self.canvas.get_active_filter(), cairo.FILTER_NEAREST)

    def test_filter_at_minified_zoom(self) -> None:
        self.canvas.set_zoom(0.75)
        self.assertEqual(self.canvas.get_active_filter(), cairo.FILTER_GOOD)

        self.canvas.set_zoom(0.25)
        self.assertEqual(self.canvas.get_active_filter(), cairo.FILTER_GOOD)

    def test_disabled_crisp_zoom_always_good(self) -> None:
        self.canvas.crisp_zoom = False
        self.assertFalse(self.canvas.crisp_zoom)

        self.canvas.set_zoom(1.0)
        self.assertEqual(self.canvas.get_active_filter(), cairo.FILTER_GOOD)

        self.canvas.set_zoom(4.0)
        self.assertEqual(self.canvas.get_active_filter(), cairo.FILTER_GOOD)

        self.canvas.set_zoom(0.5)
        self.assertEqual(self.canvas.get_active_filter(), cairo.FILTER_GOOD)

    def test_draw_with_crisp_zoom_magnified(self) -> None:
        target = cairo.ImageSurface(cairo.FORMAT_ARGB32, 400, 400)
        cr = cairo.Context(target)
        self.canvas.set_zoom(2.0)
        self.canvas._on_draw(self.canvas, cr, 400, 400)

    def test_draw_with_crisp_zoom_minified(self) -> None:
        target = cairo.ImageSurface(cairo.FORMAT_ARGB32, 400, 400)
        cr = cairo.Context(target)
        self.canvas.set_zoom(0.5)
        self.canvas._on_draw(self.canvas, cr, 400, 400)


if __name__ == "__main__":
    unittest.main()
