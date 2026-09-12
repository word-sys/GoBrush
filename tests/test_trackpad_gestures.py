from __future__ import annotations
import unittest
import cairo
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk

from gobrush.ui.canvas import Canvas


class TestTrackpadGestures(unittest.TestCase):
    def setUp(self) -> None:
        self.canvas = Canvas()
        self.surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 800, 600)
        self.canvas.set_image_surface(self.surface, 800, 600)
        self.canvas.set_zoom(1.0)
        self.canvas.set_pan(0.0, 0.0)

    def test_initial_state(self) -> None:
        self.assertFalse(self.canvas.is_pinching)
        self.assertIsNotNone(self.canvas._zoom_gesture)
        self.assertIsInstance(self.canvas._zoom_gesture, Gtk.GestureZoom)

    def test_kinetic_scroll_flags_enabled(self) -> None:
        flags = self.canvas._scroll_controller.get_flags()
        self.assertTrue(bool(flags & Gtk.EventControllerScrollFlags.KINETIC))
        self.assertTrue(bool(flags & Gtk.EventControllerScrollFlags.BOTH_AXES))

    def test_pinch_zoom_lifecycle(self) -> None:
        gesture = self.canvas._zoom_gesture

        # Begin pinch
        self.canvas._on_zoom_gesture_begin(gesture, None)
        self.assertTrue(self.canvas.is_pinching)
        self.assertEqual(self.canvas._last_gesture_scale, 1.0)

        # Scale changed: spread fingers to 1.5x zoom
        self.canvas._on_zoom_gesture_scale_changed(gesture, 1.5)
        self.assertAlmostEqual(self.canvas.zoom, 1.5)
        self.assertEqual(self.canvas._last_gesture_scale, 1.5)

        # Scale changed further: spread to 2.0x
        self.canvas._on_zoom_gesture_scale_changed(gesture, 2.0)
        self.assertAlmostEqual(self.canvas.zoom, 2.0)
        self.assertEqual(self.canvas._last_gesture_scale, 2.0)

        # Scale changed: pinch fingers together back to 1.0x
        self.canvas._on_zoom_gesture_scale_changed(gesture, 1.0)
        self.assertAlmostEqual(self.canvas.zoom, 1.0)

        # End pinch
        self.canvas._on_zoom_gesture_end(gesture, None)
        self.assertFalse(self.canvas.is_pinching)
        self.assertEqual(self.canvas._last_gesture_scale, 1.0)

    def test_pinch_zoom_cancel(self) -> None:
        gesture = self.canvas._zoom_gesture
        self.canvas._on_zoom_gesture_begin(gesture, None)
        self.assertTrue(self.canvas.is_pinching)

        self.canvas._on_zoom_gesture_cancel(gesture, None)
        self.assertFalse(self.canvas.is_pinching)

    def test_kinetic_scroll_decelerate(self) -> None:
        self.canvas.set_pan(100.0, 100.0)

        # High velocity flick (vel_x = 200, vel_y = 100)
        self.canvas._on_scroll_decelerate(self.canvas._scroll_controller, 200.0, 100.0)
        # Verify animation or pan target calculated without error

        # Very low velocity should be ignored
        initial_pan = (self.canvas.pan_x, self.canvas.pan_y)
        self.canvas._on_scroll_decelerate(self.canvas._scroll_controller, 2.0, 3.0)
        self.assertEqual((self.canvas.pan_x, self.canvas.pan_y), initial_pan)


if __name__ == "__main__":
    unittest.main()
