from __future__ import annotations
import unittest
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk

from gobrush.ui.canvas import Canvas
from gobrush.ui.window import MainWindow


class TestCanvasPanning(unittest.TestCase):
    def setUp(self) -> None:
        self.canvas = Canvas()
        self.canvas.set_pan(100.0, 200.0)

    def test_middle_drag_panning(self) -> None:
        gesture = self.canvas._middle_drag

        # Begin drag at (50, 50)
        self.canvas._on_middle_drag_begin(gesture, 50.0, 50.0)
        self.assertTrue(self.canvas.is_panning)
        self.assertEqual(self.canvas.current_cursor_name, "grabbing")

        # Update drag offset by (+30, -40)
        self.canvas._on_middle_drag_update(gesture, 30.0, -40.0)
        self.assertAlmostEqual(self.canvas.pan_x, 130.0)
        self.assertAlmostEqual(self.canvas.pan_y, 160.0)

        # End drag with final offset (+50, -60)
        self.canvas._on_middle_drag_end(gesture, 50.0, -60.0)
        self.assertFalse(self.canvas.is_panning)
        self.assertAlmostEqual(self.canvas.pan_x, 150.0)
        self.assertAlmostEqual(self.canvas.pan_y, 140.0)
        self.assertIsNone(self.canvas.current_cursor_name)

    def test_middle_drag_cancel(self) -> None:
        gesture = self.canvas._middle_drag
        self.canvas._on_middle_drag_begin(gesture, 10.0, 10.0)
        self.assertTrue(self.canvas.is_panning)

        self.canvas._on_middle_drag_cancel(gesture, None)
        self.assertFalse(self.canvas.is_panning)
        self.assertIsNone(self.canvas.current_cursor_name)

    def test_spacebar_cursor_state(self) -> None:
        # Press Space
        handled = self.canvas.handle_key_pressed(Gdk.KEY_space, Gdk.ModifierType(0))
        self.assertTrue(handled)
        self.assertTrue(self.canvas.is_space_pressed)
        self.assertEqual(self.canvas.current_cursor_name, "grab")

        # Release Space
        handled_release = self.canvas.handle_key_released(Gdk.KEY_space, Gdk.ModifierType(0))
        self.assertTrue(handled_release)
        self.assertFalse(self.canvas.is_space_pressed)
        self.assertIsNone(self.canvas.current_cursor_name)

    def test_space_left_click_drag_panning(self) -> None:
        gesture = self.canvas._primary_drag

        # Press space first
        self.canvas.handle_key_pressed(Gdk.KEY_space, Gdk.ModifierType(0))
        self.assertEqual(self.canvas.current_cursor_name, "grab")

        # Begin left click drag
        self.canvas._on_primary_drag_begin(gesture, 10.0, 10.0)
        self.assertTrue(self.canvas.is_panning)
        self.assertEqual(self.canvas.current_cursor_name, "grabbing")

        # Drag motion
        self.canvas._on_primary_drag_update(gesture, -25.0, 45.0)
        self.assertAlmostEqual(self.canvas.pan_x, 75.0)
        self.assertAlmostEqual(self.canvas.pan_y, 245.0)

        # End drag while space is still held
        self.canvas._on_primary_drag_end(gesture, -25.0, 45.0)
        self.assertFalse(self.canvas.is_panning)
        self.assertEqual(self.canvas.current_cursor_name, "grab")

        # Release space
        self.canvas.handle_key_released(Gdk.KEY_space, Gdk.ModifierType(0))
        self.assertIsNone(self.canvas.current_cursor_name)

    def test_space_released_during_drag(self) -> None:
        gesture = self.canvas._primary_drag

        self.canvas.handle_key_pressed(Gdk.KEY_space, Gdk.ModifierType(0))
        self.canvas._on_primary_drag_begin(gesture, 0.0, 0.0)
        self.assertEqual(self.canvas.current_cursor_name, "grabbing")

        # Release space while still dragging
        self.canvas.handle_key_released(Gdk.KEY_space, Gdk.ModifierType(0))
        self.assertFalse(self.canvas.is_space_pressed)
        self.assertTrue(self.canvas.is_panning)
        self.assertEqual(self.canvas.current_cursor_name, "grabbing")

        # Update continues panning
        self.canvas._on_primary_drag_update(gesture, 15.0, 15.0)
        self.assertAlmostEqual(self.canvas.pan_x, 115.0)
        self.assertAlmostEqual(self.canvas.pan_y, 215.0)

        # Releasing mouse resets cursor to default since space is already released
        self.canvas._on_primary_drag_end(gesture, 15.0, 15.0)
        self.assertFalse(self.canvas.is_panning)
        self.assertIsNone(self.canvas.current_cursor_name)

    def test_left_click_drag_pans_in_navigate_mode(self) -> None:
        gesture = self.canvas._primary_drag
        self.canvas.tool_cursor_name = None
        self.assertTrue(self.canvas.drag_to_pan)

        self.canvas._on_primary_drag_begin(gesture, 5.0, 5.0)
        self.assertTrue(self.canvas.is_panning)
        self.assertEqual(self.canvas.current_cursor_name, "grabbing")

        self.canvas._on_primary_drag_update(gesture, 40.0, 60.0)
        self.assertAlmostEqual(self.canvas.pan_x, 140.0)
        self.assertAlmostEqual(self.canvas.pan_y, 260.0)

        self.canvas._on_primary_drag_end(gesture, 40.0, 60.0)
        self.assertFalse(self.canvas.is_panning)
        self.assertAlmostEqual(self.canvas.pan_x, 140.0)
        self.assertAlmostEqual(self.canvas.pan_y, 260.0)
        self.assertIsNone(self.canvas.current_cursor_name)

    def test_left_click_with_active_tool_does_not_pan(self) -> None:
        gesture = self.canvas._primary_drag
        self.canvas.tool_cursor_name = "crosshair"

        self.canvas._on_primary_drag_begin(gesture, 5.0, 5.0)
        self.assertFalse(self.canvas.is_panning)
        self.assertEqual(self.canvas.current_cursor_name, "crosshair")

        self.canvas._on_primary_drag_update(gesture, 100.0, 100.0)
        self.assertAlmostEqual(self.canvas.pan_x, 100.0)
        self.assertAlmostEqual(self.canvas.pan_y, 200.0)

        self.canvas._on_primary_drag_end(gesture, 100.0, 100.0)
        self.assertFalse(self.canvas.is_panning)
        self.assertEqual(self.canvas.current_cursor_name, "crosshair")

    def test_left_click_with_drag_to_pan_disabled_does_not_pan(self) -> None:
        gesture = self.canvas._primary_drag
        self.canvas.drag_to_pan = False

        self.canvas._on_primary_drag_begin(gesture, 5.0, 5.0)
        self.assertFalse(self.canvas.is_panning)

        self.canvas._on_primary_drag_update(gesture, 100.0, 100.0)
        self.assertAlmostEqual(self.canvas.pan_x, 100.0)
        self.assertAlmostEqual(self.canvas.pan_y, 200.0)

        self.canvas._on_primary_drag_end(gesture, 100.0, 100.0)
        self.assertFalse(self.canvas.is_panning)

    def test_tool_cursor_restoration(self) -> None:
        self.canvas.tool_cursor_name = "crosshair"
        self.assertEqual(self.canvas.current_cursor_name, "crosshair")

        self.canvas.handle_key_pressed(Gdk.KEY_space, Gdk.ModifierType(0))
        self.assertEqual(self.canvas.current_cursor_name, "grab")

        self.canvas._on_primary_drag_begin(self.canvas._primary_drag, 0.0, 0.0)
        self.assertEqual(self.canvas.current_cursor_name, "grabbing")

        self.canvas._on_primary_drag_end(self.canvas._primary_drag, 0.0, 0.0)
        self.assertEqual(self.canvas.current_cursor_name, "grab")

        self.canvas.handle_key_released(Gdk.KEY_space, Gdk.ModifierType(0))
        self.assertEqual(self.canvas.current_cursor_name, "crosshair")

    def test_focus_leave_resets_space(self) -> None:
        self.canvas.handle_key_pressed(Gdk.KEY_space, Gdk.ModifierType(0))
        self.assertTrue(self.canvas.is_space_pressed)
        self.assertEqual(self.canvas.current_cursor_name, "grab")

        self.canvas._on_focus_leave(self.canvas._focus_controller)
        self.assertFalse(self.canvas.is_space_pressed)
        self.assertIsNone(self.canvas.current_cursor_name)

    def test_window_routes_space_key(self) -> None:
        win = MainWindow()
        # Empty state active
        handled = win._on_key_pressed(win._key_controller, Gdk.KEY_space, 65, Gdk.ModifierType(0))
        self.assertFalse(handled)
        self.assertFalse(win.canvas.is_space_pressed)

        # Show canvas
        win.show_canvas()
        handled = win._on_key_pressed(win._key_controller, Gdk.KEY_space, 65, Gdk.ModifierType(0))
        self.assertTrue(handled)
        self.assertTrue(win.canvas.is_space_pressed)
        self.assertEqual(win.canvas.current_cursor_name, "grab")

        # Release space via window
        win._on_key_released(win._key_controller, Gdk.KEY_space, 65, Gdk.ModifierType(0))
        self.assertFalse(win.canvas.is_space_pressed)
        self.assertIsNone(win.canvas.current_cursor_name)


if __name__ == "__main__":
    unittest.main()
