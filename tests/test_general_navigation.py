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

    def test_set_zoom_level_presets_and_centering(self) -> None:
        large_surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 400, 300)
        self.canvas.set_image_surface(large_surf, 400, 300)

        # 50% zoom in 800x600 viewport
        self.canvas.set_zoom_level(0.50, viewport_width=800, viewport_height=600)
        self.assertAlmostEqual(self.canvas.zoom, 0.50)
        # 400 * 0.5 = 200; (800 - 200) / 2 = 300
        # 300 * 0.5 = 150; (600 - 150) / 2 = 225
        self.assertAlmostEqual(self.canvas.pan_x, 300.0)
        self.assertAlmostEqual(self.canvas.pan_y, 225.0)

        # 100% zoom in 800x600 viewport
        self.canvas.set_zoom_level(1.00, viewport_width=800, viewport_height=600)
        self.assertAlmostEqual(self.canvas.zoom, 1.00)
        self.assertAlmostEqual(self.canvas.pan_x, 200.0)
        self.assertAlmostEqual(self.canvas.pan_y, 150.0)

        # 25% zoom in 800x600 viewport
        self.canvas.set_zoom_level(0.25, viewport_width=800, viewport_height=600)
        self.assertAlmostEqual(self.canvas.zoom, 0.25)
        self.assertAlmostEqual(self.canvas.pan_x, 350.0)
        self.assertAlmostEqual(self.canvas.pan_y, 262.5)

    def test_image_opened_centered_in_middle_on_first_draw(self) -> None:
        canvas = Canvas()
        # Initial state before widget is allocated
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 256, 256)
        canvas.set_image_surface(surf, 256, 256)
        self.assertTrue(canvas._pending_fit)

        # Simulate first draw with allocated size 800x600
        target_surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 800, 600)
        cr = cairo.Context(target_surface)
        canvas._on_draw(canvas, cr, 800, 600)

        self.assertFalse(canvas._pending_fit)
        self.assertAlmostEqual(canvas.zoom, 1.0)
        # Centered: (800 - 256) / 2 = 272, (600 - 256) / 2 = 172
        self.assertAlmostEqual(canvas.pan_x, 272.0)
        self.assertAlmostEqual(canvas.pan_y, 172.0)

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

    def test_main_menu_zoom_buttons_and_presets(self) -> None:
        win = MainWindow()
        self.assertIsNotNone(win.menu_popover)
        self.assertIsNotNone(win.btn_zoom_out)
        self.assertIsNotNone(win.btn_zoom_fit)
        self.assertIsNotNone(win.btn_zoom_100)
        self.assertIsNotNone(win.btn_zoom_in)

        # In empty state, buttons are insensitive
        self.assertFalse(win.btn_zoom_100.get_sensitive())
        for pct in (25, 50, 75, 100, 150, 200):
            self.assertIn(pct, win.preset_buttons)
            self.assertFalse(win.preset_buttons[pct].get_sensitive())

        # Load image -> buttons become sensitive
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 400, 400)
        win.load_surface(surf, has_alpha=False)
        self.assertTrue(win.btn_zoom_100.get_sensitive())
        self.assertTrue(win.preset_buttons[50].get_sensitive())

        # Click preset 50%
        win.preset_buttons[50].emit("clicked")
        self.assertAlmostEqual(win.canvas.zoom, 0.50)

        # Click preset 200%
        win.preset_buttons[200].emit("clicked")
        self.assertAlmostEqual(win.canvas.zoom, 2.00)

        # Click 100%
        win.btn_zoom_100.emit("clicked")
        self.assertAlmostEqual(win.canvas.zoom, 1.00)

        # Click Fit
        win.btn_zoom_fit.emit("clicked")
        self.assertIsNotNone(win.canvas.zoom)


if __name__ == "__main__":
    unittest.main()
