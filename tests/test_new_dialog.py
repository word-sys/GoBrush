from __future__ import annotations
import unittest
import cairo
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Gdk

from gobrush.ui.new_dialog import (
    NewCanvasDialog,
    px_to_unit,
    unit_to_px,
    UNIT_PIXELS,
    UNIT_MILLIMETERS,
    UNIT_INCHES,
    BG_TRANSPARENT,
    BG_WHITE,
    BG_BLACK,
    BG_CUSTOM,
    PRESET_TEMPLATES,
)
from gobrush.ui.window import MainWindow


class TestNewCanvasDialog(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        Gtk.init()

    def test_unit_conversions(self) -> None:
        # Pixels
        self.assertEqual(px_to_unit(100.0, UNIT_PIXELS), 100.0)
        self.assertEqual(unit_to_px(100.0, UNIT_PIXELS), 100)

        # Inches (96 DPI)
        self.assertAlmostEqual(px_to_unit(96.0, UNIT_INCHES), 1.0)
        self.assertEqual(unit_to_px(1.0, UNIT_INCHES), 96)
        self.assertEqual(unit_to_px(2.5, UNIT_INCHES), 240)

        # Millimeters (96 DPI / 25.4)
        mm_val = px_to_unit(96.0, UNIT_MILLIMETERS)
        self.assertAlmostEqual(mm_val, 25.4, places=2)
        self.assertEqual(unit_to_px(25.4, UNIT_MILLIMETERS), 96)

        # Clamp min 1px
        self.assertEqual(unit_to_px(0.0, UNIT_PIXELS), 1)
        self.assertEqual(unit_to_px(-50.0, UNIT_PIXELS), 1)

    def test_dialog_initialization(self) -> None:
        dlg = NewCanvasDialog()
        self.assertIsNotNone(dlg.btn_create)
        self.assertIsNotNone(dlg.btn_cancel)
        self.assertIsNotNone(dlg.combo_template)
        self.assertIsNotNone(dlg.combo_unit)
        self.assertIsNotNone(dlg.combo_bg)
        self.assertIsNotNone(dlg.spin_width)
        self.assertIsNotNone(dlg.spin_height)
        self.assertIsNotNone(dlg.btn_portrait)
        self.assertIsNotNone(dlg.btn_landscape)

        # Default 1920x1080 Landscape
        self.assertEqual(dlg._width_px, 1920)
        self.assertEqual(dlg._height_px, 1080)
        self.assertTrue(dlg._is_landscape)
        self.assertEqual(dlg.spin_width.get_value(), 1920.0)
        self.assertEqual(dlg.spin_height.get_value(), 1080.0)
        dlg.destroy()

    def test_template_selection(self) -> None:
        dlg = NewCanvasDialog()
        # Select 1080 x 1080 Square (index 4)
        dlg.combo_template.set_selected(4)
        self.assertEqual(dlg._width_px, 1080)
        self.assertEqual(dlg._height_px, 1080)
        self.assertEqual(dlg.spin_width.get_value(), 1080.0)
        self.assertEqual(dlg.spin_height.get_value(), 1080.0)

        # Select 1280 x 720 HD (index 1)
        dlg.combo_template.set_selected(1)
        self.assertEqual(dlg._width_px, 1280)
        self.assertEqual(dlg._height_px, 720)
        self.assertEqual(dlg.spin_width.get_value(), 1280.0)
        self.assertEqual(dlg.spin_height.get_value(), 720.0)
        dlg.destroy()

    def test_orientation_toggle(self) -> None:
        dlg = NewCanvasDialog()
        self.assertEqual(dlg._width_px, 1920)
        self.assertEqual(dlg._height_px, 1080)
        self.assertTrue(dlg.btn_landscape.get_active())

        # Switch to Portrait
        dlg.btn_portrait.set_active(True)
        self.assertFalse(dlg._is_landscape)
        self.assertEqual(dlg._width_px, 1080)
        self.assertEqual(dlg._height_px, 1920)
        self.assertEqual(dlg.spin_width.get_value(), 1080.0)
        self.assertEqual(dlg.spin_height.get_value(), 1920.0)

        # Switch back to Landscape
        dlg.btn_landscape.set_active(True)
        self.assertTrue(dlg._is_landscape)
        self.assertEqual(dlg._width_px, 1920)
        self.assertEqual(dlg._height_px, 1080)
        dlg.destroy()

    def test_unit_change(self) -> None:
        dlg = NewCanvasDialog()
        # Switch unit to Inches (index 2)
        dlg.combo_unit.set_selected(2)
        self.assertEqual(dlg._current_unit, UNIT_INCHES)
        # 1920 px / 96 = 20.0 in; 1080 px / 96 = 11.25 in
        self.assertAlmostEqual(dlg.spin_width.get_value(), 20.0, places=2)
        self.assertAlmostEqual(dlg.spin_height.get_value(), 11.25, places=2)

        # Change spin width to 10.0 inches
        dlg.spin_width.set_value(10.0)
        self.assertEqual(dlg._width_px, 960)

        # Switch back to Pixels (index 0)
        dlg.combo_unit.set_selected(0)
        self.assertEqual(dlg._current_unit, UNIT_PIXELS)
        self.assertEqual(dlg.spin_width.get_value(), 960.0)
        dlg.destroy()

    def test_create_transparent_surface(self) -> None:
        created_surface: cairo.ImageSurface | None = None
        created_alpha: bool | None = None
        created_w = 0
        created_h = 0

        def on_create(surf: cairo.ImageSurface, has_alpha: bool, w: int, h: int) -> None:
            nonlocal created_surface, created_alpha, created_w, created_h
            created_surface = surf
            created_alpha = has_alpha
            created_w = w
            created_h = h

        dlg = NewCanvasDialog(on_create=on_create)
        dlg.spin_width.set_value(320)
        dlg.spin_height.set_value(240)
        dlg.combo_bg.set_selected(0)  # Transparent

        dlg.btn_create.emit("clicked")
        self.assertIsNotNone(created_surface)
        self.assertTrue(created_alpha)
        self.assertEqual(created_w, 320)
        self.assertEqual(created_h, 240)
        self.assertEqual(created_surface.get_width(), 320)
        self.assertEqual(created_surface.get_height(), 240)

        # Verify transparent pixels
        data = created_surface.get_data()
        self.assertEqual(sum(data[:64]), 0)

    def test_create_solid_white_surface(self) -> None:
        created_surface: cairo.ImageSurface | None = None
        created_alpha: bool | None = None

        def on_create(surf: cairo.ImageSurface, has_alpha: bool, w: int, h: int) -> None:
            nonlocal created_surface, created_alpha
            created_surface = surf
            created_alpha = has_alpha

        dlg = NewCanvasDialog(on_create=on_create)
        dlg.spin_width.set_value(100)
        dlg.spin_height.set_value(100)
        dlg.combo_bg.set_selected(1)  # Solid White

        dlg.btn_create.emit("clicked")
        self.assertIsNotNone(created_surface)
        self.assertFalse(created_alpha)
        self.assertEqual(created_surface.get_width(), 100)
        self.assertEqual(created_surface.get_height(), 100)

        # Verify white pixels (all 255 bytes)
        data = created_surface.get_data()
        self.assertEqual(data[0], 255)
        self.assertEqual(data[1], 255)
        self.assertEqual(data[2], 255)
        self.assertEqual(data[3], 255)

    def test_create_solid_black_surface(self) -> None:
        created_surface: cairo.ImageSurface | None = None
        created_alpha: bool | None = None

        def on_create(surf: cairo.ImageSurface, has_alpha: bool, w: int, h: int) -> None:
            nonlocal created_surface, created_alpha
            created_surface = surf
            created_alpha = has_alpha

        dlg = NewCanvasDialog(on_create=on_create)
        dlg.spin_width.set_value(100)
        dlg.spin_height.set_value(100)
        dlg.combo_bg.set_selected(2)  # Solid Black

        dlg.btn_create.emit("clicked")
        self.assertIsNotNone(created_surface)
        self.assertFalse(created_alpha)

        # In ARGB32 (native endian / B, G, R, A on x86 little endian), Black with 1.0 alpha has RGB=0, A=255
        data = created_surface.get_data()
        self.assertEqual(data[0], 0)
        self.assertEqual(data[1], 0)
        self.assertEqual(data[2], 0)
        self.assertEqual(data[3], 255)

    def test_main_window_new_canvas_integration(self) -> None:
        win = MainWindow()
        self.assertTrue(win.is_empty())
        self.assertIsNotNone(win.btn_new)
        self.assertEqual(win.btn_new.get_label(), "New")

        # Open new canvas dialog
        dlg = win.show_new_canvas_dialog()
        self.assertIsInstance(dlg, NewCanvasDialog)

        # Trigger create on dialog
        dlg.spin_width.set_value(800)
        dlg.spin_height.set_value(600)
        dlg.btn_create.emit("clicked")

        # MainWindow should now have a canvas active with Untitled - GoBrush
        self.assertFalse(win.is_empty())
        self.assertEqual(win.get_title(), "Untitled - GoBrush")
        self.assertEqual(win.canvas.image_width, 800)
        self.assertEqual(win.canvas.image_height, 600)
        self.assertIsNone(win.current_file_path)
        self.assertTrue(win.btn_copy.get_sensitive())
        self.assertTrue(win.btn_save.get_sensitive())

    def test_main_window_new_shortcut(self) -> None:
        win = MainWindow()
        handled = win._on_key_pressed(None, Gdk.KEY_n, 0, Gdk.ModifierType.CONTROL_MASK)
        self.assertTrue(handled)


if __name__ == "__main__":
    unittest.main()
