from __future__ import annotations
import unittest
import cairo
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Gdk, GLib

from gobrush.ui.canvas import Canvas
from gobrush.ui.window import MainWindow


class TestGeneralNavigation(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        Gtk.init()

    def setUp(self) -> None:
        self.canvas = Canvas()
        self.surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 800, 600)
        self.canvas.set_image_surface(self.surface, 800, 600)

    def test_scroll_to_zoom_toggle_property(self) -> None:
        self.assertTrue(self.canvas.scroll_to_zoom)
        self.canvas.scroll_to_zoom = False
        self.assertFalse(self.canvas.scroll_to_zoom)
        self.canvas.scroll_to_zoom = True
        self.assertTrue(self.canvas.scroll_to_zoom)

    def test_drag_to_pan_property(self) -> None:
        self.assertTrue(self.canvas.drag_to_pan)
        self.canvas.drag_to_pan = False
        self.assertFalse(self.canvas.drag_to_pan)

    def test_double_click_toggle_fit_and_actual(self) -> None:
        large_surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 1600, 1200)
        self.canvas.set_image_surface(large_surf, 1600, 1200)
        self.canvas.zoom_fit(viewport_width=800, viewport_height=600, animate=False)
        fit_zoom = self.canvas.zoom
        self.assertAlmostEqual(fit_zoom, 0.4666, places=2)

        # Double-click when at fit zoom -> toggles to 1.0 (100% actual size)
        self.canvas.toggle_zoom_fit_actual(pivot=(400.0, 300.0), viewport_width=800, viewport_height=600, animate=False)
        self.assertAlmostEqual(self.canvas.zoom, 1.0, places=4)

        # Double-click again when at 1.0 -> toggles back to fit
        self.canvas.toggle_zoom_fit_actual(pivot=(400.0, 300.0), viewport_width=800, viewport_height=600, animate=False)
        self.assertAlmostEqual(self.canvas.zoom, fit_zoom, places=2)

    def test_single_click_does_not_toggle_zoom(self) -> None:
        self.canvas.zoom_fit(viewport_width=1000, viewport_height=800, animate=False)
        initial_zoom = self.canvas.zoom

        # Single click (n_press = 1) must not change zoom
        self.canvas._on_click_pressed(self.canvas._click_gesture, 1, 500.0, 400.0)
        self.assertEqual(self.canvas.zoom, initial_zoom)

    def test_arrow_keys_navigation(self) -> None:
        ctrl = self.canvas._key_controller
        self.canvas.set_pan(0.0, 0.0)

        # Left arrow (+50 pan_x)
        self.canvas.handle_key_pressed(Gdk.KEY_Left, Gdk.ModifierType(0))
        self.assertEqual(self.canvas.pan_x, 50.0)

        # Right arrow (-50 pan_x)
        self.canvas.handle_key_pressed(Gdk.KEY_Right, Gdk.ModifierType(0))
        self.assertEqual(self.canvas.pan_x, 0.0)

        # Up arrow (+50 pan_y)
        self.canvas.handle_key_pressed(Gdk.KEY_Up, Gdk.ModifierType(0))
        self.assertEqual(self.canvas.pan_y, 50.0)

        # Down arrow (-50 pan_y)
        self.canvas.handle_key_pressed(Gdk.KEY_Down, Gdk.ModifierType(0))
        self.assertEqual(self.canvas.pan_y, 0.0)

        # Shift + Arrow pans 150px
        self.canvas.handle_key_pressed(Gdk.KEY_Right, Gdk.ModifierType.SHIFT_MASK)
        self.assertEqual(self.canvas.pan_x, -150.0)

    def test_single_key_zoom_shortcuts(self) -> None:
        # + zooms in
        self.canvas.set_zoom(1.0)
        handled = self.canvas.handle_key_pressed(Gdk.KEY_plus, Gdk.ModifierType(0))
        self.assertTrue(handled)
        self.assertAlmostEqual(self.canvas.zoom, 1.25, places=4)

        # = zooms in
        handled = self.canvas.handle_key_pressed(Gdk.KEY_equal, Gdk.ModifierType(0))
        self.assertTrue(handled)
        self.assertAlmostEqual(self.canvas.zoom, 1.25 * 1.25, places=4)

        # - zooms out
        handled = self.canvas.handle_key_pressed(Gdk.KEY_minus, Gdk.ModifierType(0))
        self.assertTrue(handled)
        self.assertAlmostEqual(self.canvas.zoom, 1.25, places=4)

        # 1 sets 100%
        handled = self.canvas.handle_key_pressed(Gdk.KEY_1, Gdk.ModifierType(0))
        self.assertTrue(handled)
        self.assertAlmostEqual(self.canvas.zoom, 1.0, places=4)

        # f fits to window
        handled = self.canvas.handle_key_pressed(Gdk.KEY_f, Gdk.ModifierType(0))
        self.assertTrue(handled)

        # F fits to window
        handled = self.canvas.handle_key_pressed(Gdk.KEY_F, Gdk.ModifierType(0))
        self.assertTrue(handled)

    def test_window_scroll_to_zoom_action(self) -> None:
        win = MainWindow()
        self.assertTrue(win.canvas.scroll_to_zoom)

        action = win.action_scroll_to_zoom
        self.assertTrue(action.get_state().get_boolean())

        # Toggle via action
        action.change_state(GLib.Variant.new_boolean(False))
        self.assertFalse(win.canvas.scroll_to_zoom)
        self.assertFalse(action.get_state().get_boolean())

        # Toggle back
        action.change_state(GLib.Variant.new_boolean(True))
        self.assertTrue(win.canvas.scroll_to_zoom)
        self.assertTrue(action.get_state().get_boolean())


if __name__ == "__main__":
    unittest.main()
