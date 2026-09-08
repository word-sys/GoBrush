from __future__ import annotations
import unittest
import cairo
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk

from gobrush.ui.canvas import Canvas
from gobrush.ui.canvas_view import CanvasView
from gobrush.ui.window import MainWindow


class TestKeyboardZoom(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        Gtk.init()

    def test_zoom_in_and_out_methods(self) -> None:
        canvas = Canvas()
        self.assertEqual(canvas.zoom, 1.0)

        canvas.zoom_in()
        self.assertAlmostEqual(canvas.zoom, 1.25, places=5)

        canvas.zoom_out()
        self.assertAlmostEqual(canvas.zoom, 1.0, places=5)

    def test_zoom_clamping(self) -> None:
        canvas = Canvas()
        for _ in range(30):
            canvas.zoom_in(factor=2.0)
        self.assertEqual(canvas.zoom, 32.0)

        for _ in range(30):
            canvas.zoom_out(factor=2.0)
        self.assertEqual(canvas.zoom, 0.1)

    def test_zoom_actual_size(self) -> None:
        canvas = Canvas()
        canvas.zoom = 4.0
        canvas.zoom_actual_size(animate=False)
        self.assertEqual(canvas.zoom, 1.0)

    def test_zoom_fit_and_centering(self) -> None:
        canvas = Canvas()
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 1000, 800)
        canvas.set_image_surface(surf, 1000, 800)

        target_zoom, pan_x, pan_y = canvas.get_fit_target(
            viewport_width=800,
            viewport_height=600,
            padding=20.0,
            upscale=False,
        )
        # Expected scale: min((800-40)/1000, (600-40)/800) = min(0.76, 0.70) = 0.70
        self.assertAlmostEqual(target_zoom, 0.70, places=5)
        # Expected pan: (800 - 1000*0.7) / 2 = 50.0, (600 - 800*0.7) / 2 = 20.0
        self.assertAlmostEqual(pan_x, 50.0, places=5)
        self.assertAlmostEqual(pan_y, 20.0, places=5)

        canvas.zoom_fit(
            viewport_width=800,
            viewport_height=600,
            padding=20.0,
            upscale=False,
            animate=False,
        )
        self.assertAlmostEqual(canvas.zoom, 0.70, places=5)
        self.assertAlmostEqual(canvas.pan_x, 50.0, places=5)
        self.assertAlmostEqual(canvas.pan_y, 20.0, places=5)

    def test_canvas_keyboard_shortcuts(self) -> None:
        canvas = Canvas()
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 400, 300)
        canvas.set_image_surface(surf, 400, 300)

        ctrl = canvas._key_controller

        # Ctrl++ and Ctrl+=
        handled = canvas._on_key_pressed(ctrl, Gdk.KEY_plus, 0, Gdk.ModifierType.CONTROL_MASK)
        self.assertTrue(handled)
        self.assertAlmostEqual(canvas.zoom, 1.25, places=5)

        handled = canvas._on_key_pressed(ctrl, Gdk.KEY_equal, 0, Gdk.ModifierType.CONTROL_MASK)
        self.assertTrue(handled)
        self.assertAlmostEqual(canvas.zoom, 1.25 * 1.25, places=5)

        # Ctrl+-
        handled = canvas._on_key_pressed(ctrl, Gdk.KEY_minus, 0, Gdk.ModifierType.CONTROL_MASK)
        self.assertTrue(handled)
        self.assertAlmostEqual(canvas.zoom, 1.25, places=5)

        # Ctrl+0 (1:1 100%)
        handled = canvas._on_key_pressed(ctrl, Gdk.KEY_0, 0, Gdk.ModifierType.CONTROL_MASK)
        self.assertTrue(handled)
        self.assertAlmostEqual(canvas.zoom, 1.0, places=5)

        # Ctrl+9 (Fit to window)
        handled = canvas._on_key_pressed(ctrl, Gdk.KEY_9, 0, Gdk.ModifierType.CONTROL_MASK)
        self.assertTrue(handled)

        # Keypad keys: Ctrl+KP_Add, Ctrl+KP_Subtract, Ctrl+KP_0, Ctrl+KP_9
        handled = canvas._on_key_pressed(ctrl, Gdk.KEY_KP_Add, 0, Gdk.ModifierType.CONTROL_MASK)
        self.assertTrue(handled)

        handled = canvas._on_key_pressed(ctrl, Gdk.KEY_KP_Subtract, 0, Gdk.ModifierType.CONTROL_MASK)
        self.assertTrue(handled)

        handled = canvas._on_key_pressed(ctrl, Gdk.KEY_KP_0, 0, Gdk.ModifierType.CONTROL_MASK)
        self.assertTrue(handled)
        self.assertEqual(canvas.zoom, 1.0)

        handled = canvas._on_key_pressed(ctrl, Gdk.KEY_KP_9, 0, Gdk.ModifierType.CONTROL_MASK)
        self.assertTrue(handled)

    def test_keyboard_shortcuts_rejected_without_ctrl(self) -> None:
        canvas = Canvas()
        ctrl = canvas._key_controller

        handled = canvas._on_key_pressed(ctrl, Gdk.KEY_plus, 0, Gdk.ModifierType(0))
        self.assertFalse(handled)

        handled = canvas._on_key_pressed(ctrl, Gdk.KEY_0, 0, Gdk.ModifierType(0))
        self.assertFalse(handled)

        # Ctrl + Alt should be rejected (reserved for window manager)
        state = Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.ALT_MASK
        handled = canvas._on_key_pressed(ctrl, Gdk.KEY_plus, 0, state)
        self.assertFalse(handled)

        # Non-zoom key
        handled = canvas._on_key_pressed(ctrl, Gdk.KEY_a, 0, Gdk.ModifierType.CONTROL_MASK)
        self.assertFalse(handled)

    def test_canvas_view_delegation(self) -> None:
        view = CanvasView()
        self.assertEqual(view.canvas.zoom, 1.0)

        view.zoom_in()
        self.assertAlmostEqual(view.canvas.zoom, 1.25, places=5)

        view.zoom_out()
        self.assertAlmostEqual(view.canvas.zoom, 1.0, places=5)

        view.zoom_fit(animate=False)
        view.zoom_actual_size(animate=False)
        self.assertEqual(view.canvas.zoom, 1.0)

    def test_window_key_handling(self) -> None:
        window = MainWindow()

        # In empty state, zoom keys should return False
        handled = window._on_key_pressed(
            window._key_controller, Gdk.KEY_plus, 0, Gdk.ModifierType.CONTROL_MASK
        )
        self.assertFalse(handled)

        # Once canvas is showing, zoom keys are handled
        window.show_canvas()
        handled = window._on_key_pressed(
            window._key_controller, Gdk.KEY_plus, 0, Gdk.ModifierType.CONTROL_MASK
        )
        self.assertTrue(handled)
        self.assertAlmostEqual(window.canvas.zoom, 1.25, places=5)


if __name__ == "__main__":
    unittest.main()
