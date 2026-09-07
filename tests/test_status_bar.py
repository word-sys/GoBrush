from __future__ import annotations
import unittest
import cairo
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw

from gobrush.ui.status_bar import CanvasStatusBar
from gobrush.ui.canvas_view import CanvasView
from gobrush.ui.canvas import Canvas
from gobrush.ui.window import MainWindow


class TestStatusBar(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        Gtk.init()


    def test_status_bar_initial_state(self) -> None:
        bar = CanvasStatusBar()
        self.assertEqual(bar.lbl_zoom.get_text(), "100%")
        self.assertFalse(bar.lbl_dimensions.get_visible())
        self.assertEqual(bar.lbl_coords.get_text(), "—, —")
        self.assertTrue(bar.has_css_class("osd"))

    def test_status_bar_set_zoom(self) -> None:
        bar = CanvasStatusBar()
        bar.set_zoom(2.5)
        self.assertEqual(bar.lbl_zoom.get_text(), "250%")

        bar.set_zoom(0.333)
        self.assertEqual(bar.lbl_zoom.get_text(), "33%")

    def test_status_bar_set_dimensions(self) -> None:
        bar = CanvasStatusBar()
        bar.set_dimensions(1920, 1080)
        self.assertTrue(bar.lbl_dimensions.get_visible())
        self.assertEqual(bar.lbl_dimensions.get_text(), "1920 × 1080 px")

        bar.set_dimensions(0, 0)
        self.assertFalse(bar.lbl_dimensions.get_visible())

    def test_status_bar_set_cursor_position(self) -> None:
        bar = CanvasStatusBar()
        bar.set_cursor_position(345, 678)
        self.assertEqual(bar.lbl_coords.get_text(), "345, 678 px")

        bar.set_cursor_position(None, None)
        self.assertEqual(bar.lbl_coords.get_text(), "—, —")

    def test_canvas_view_sync(self) -> None:
        canvas = Canvas()
        view = CanvasView(canvas)

        self.assertIs(view.canvas, canvas)
        self.assertIsInstance(view.status_bar, CanvasStatusBar)

        # Set image surface on canvas and check dimensions sync
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 800, 600)
        canvas.set_image_surface(surface)
        self.assertEqual(view.status_bar.lbl_dimensions.get_text(), "800 × 600 px")

        # Change zoom and check zoom label sync
        canvas.set_zoom(1.75)
        self.assertEqual(view.status_bar.lbl_zoom.get_text(), "175%")

        # Test pointer motion within image bounds
        view._on_pointer_motion(view._motion_ctrl, 80.0, 60.0)
        self.assertNotEqual(view.status_bar.lbl_coords.get_text(), "—, —")

        # Test pointer leave
        view._on_pointer_leave(view._motion_ctrl)
        self.assertEqual(view.status_bar.lbl_coords.get_text(), "—, —")

    def test_main_window_has_status_bar(self) -> None:
        win = MainWindow()
        self.assertIsInstance(win.canvas_view, CanvasView)
        self.assertIsInstance(win.status_bar, CanvasStatusBar)
        self.assertIs(win.canvas, win.canvas_view.canvas)


if __name__ == "__main__":
    unittest.main()
