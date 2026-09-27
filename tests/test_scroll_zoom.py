from __future__ import annotations
import unittest
from unittest.mock import Mock
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk

from gobrush.ui.canvas import Canvas


class TestScrollZoom(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        Gtk.init()

    def test_cursor_tracking(self) -> None:
        canvas = Canvas()
        self.assertIsNone(canvas.cursor_pos)

        canvas._on_motion_internal(canvas._motion_controller, 150.0, 250.0)
        self.assertEqual(canvas.cursor_pos, (150.0, 250.0))

        canvas._on_leave_internal(canvas._motion_controller)
        self.assertIsNone(canvas.cursor_pos)

    def test_ctrl_scroll_zoom_in_and_out(self) -> None:
        canvas = Canvas()
        self.assertEqual(canvas.zoom, 1.0)

        mock_ctrl = Mock()
        mock_ctrl.get_current_event_state.return_value = Gdk.ModifierType.CONTROL_MASK

        # Scroll up (dy = -1.0) -> zoom in
        handled = canvas._on_scroll(mock_ctrl, 0.0, -1.0)
        self.assertTrue(handled)
        self.assertAlmostEqual(canvas.zoom, 1.15, places=5)

        # Scroll down (dy = 1.0) -> zoom back out to 1.0
        handled = canvas._on_scroll(mock_ctrl, 0.0, 1.0)
        self.assertTrue(handled)
        self.assertAlmostEqual(canvas.zoom, 1.0, places=5)

    def test_ctrl_scroll_zoom_clamping(self) -> None:
        canvas = Canvas()
        mock_ctrl = Mock()
        mock_ctrl.get_current_event_state.return_value = Gdk.ModifierType.CONTROL_MASK

        # Zoom in past max_zoom (32.0)
        for _ in range(50):
            canvas._on_scroll(mock_ctrl, 0.0, -1.0)
        self.assertEqual(canvas.zoom, 32.0)

        # Zoom out past min_zoom (0.1)
        for _ in range(100):
            canvas._on_scroll(mock_ctrl, 0.0, 1.0)
        self.assertEqual(canvas.zoom, 0.1)

    def test_ctrl_scroll_zoom_stationary_pivot(self) -> None:
        canvas = Canvas()
        canvas._on_motion_internal(canvas._motion_controller, 200.0, 150.0)

        mock_ctrl = Mock()
        mock_ctrl.get_current_event_state.return_value = Gdk.ModifierType.CONTROL_MASK

        # Image point before scroll zoom
        ix_before, iy_before = canvas.screen_to_image(200.0, 150.0)

        # Scroll zoom
        canvas._on_scroll(mock_ctrl, 0.0, -1.0)

        # Image point after zoom must match
        ix_after, iy_after = canvas.screen_to_image(200.0, 150.0)
        self.assertAlmostEqual(ix_before, ix_after, places=5)
        self.assertAlmostEqual(iy_before, iy_after, places=5)

    def test_default_scroll_to_zoom_without_ctrl(self) -> None:
        canvas = Canvas()
        self.assertTrue(canvas.scroll_to_zoom)
        self.assertEqual(canvas.zoom, 1.0)

        mock_ctrl = Mock()
        mock_ctrl.get_current_event_state.return_value = Gdk.ModifierType(0)

        # Normal scroll up zooms in directly (general navigation standard)
        handled = canvas._on_scroll(mock_ctrl, 0.0, -1.0)
        self.assertTrue(handled)
        self.assertAlmostEqual(canvas.zoom, 1.15, places=5)

        # Normal scroll down zooms back out
        handled = canvas._on_scroll(mock_ctrl, 0.0, 1.0)
        self.assertTrue(handled)
        self.assertAlmostEqual(canvas.zoom, 1.0, places=5)

    def test_shift_scroll_pans_canvas(self) -> None:
        canvas = Canvas()
        self.assertEqual((canvas.pan_x, canvas.pan_y), (0.0, 0.0))

        mock_ctrl = Mock()
        mock_ctrl.get_current_event_state.return_value = Gdk.ModifierType.SHIFT_MASK

        handled = canvas._on_scroll(mock_ctrl, 2.0, 3.0)
        self.assertTrue(handled)
        self.assertEqual(canvas.pan_x, -40.0)
        self.assertEqual(canvas.pan_y, -60.0)

    def test_horizontal_scroll_pans_canvas(self) -> None:
        canvas = Canvas()
        self.assertEqual((canvas.pan_x, canvas.pan_y), (0.0, 0.0))

        mock_ctrl = Mock()
        mock_ctrl.get_current_event_state.return_value = Gdk.ModifierType(0)

        handled = canvas._on_scroll(mock_ctrl, 2.0, 0.0)
        self.assertTrue(handled)
        self.assertEqual(canvas.pan_x, -40.0)
        self.assertEqual(canvas.pan_y, 0.0)

    def test_scroll_to_zoom_disabled_pans_canvas(self) -> None:
        canvas = Canvas()
        canvas.scroll_to_zoom = False
        self.assertFalse(canvas.scroll_to_zoom)
        self.assertEqual((canvas.pan_x, canvas.pan_y), (0.0, 0.0))

        mock_ctrl = Mock()
        mock_ctrl.get_current_event_state.return_value = Gdk.ModifierType(0)

        handled = canvas._on_scroll(mock_ctrl, 2.0, 3.0)
        self.assertTrue(handled)
        self.assertEqual(canvas.pan_x, -40.0)
        self.assertEqual(canvas.pan_y, -60.0)


if __name__ == "__main__":
    unittest.main()
