from __future__ import annotations
import unittest
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk

from gobrush.tools.base import ToolManager, DEFAULT_TOOL_COLOR
from gobrush.ui.palette import ToolPalette, CURATED_PALETTE_COLORS, colors_match
from gobrush.ui.canvas import Canvas
from gobrush.ui.window import MainWindow


class TestPaletteColor(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        Gtk.init()

    def test_curated_palette_colors_structure(self) -> None:
        self.assertEqual(len(CURATED_PALETTE_COLORS), 9)
        expected_names = [
            "Red", "Orange", "Yellow", "Green", "Cyan",
            "Blue", "Violet", "Black", "White"
        ]
        actual_names = [c["name"] for c in CURATED_PALETTE_COLORS]
        self.assertEqual(actual_names, expected_names)

        for c in CURATED_PALETTE_COLORS:
            self.assertTrue(c["hex"].startswith("#"))
            self.assertEqual(len(c["hex"]), 7)
            rgba = c["rgba"]
            self.assertEqual(len(rgba), 4)
            for v in rgba:
                self.assertGreaterEqual(v, 0.0)
                self.assertLessEqual(v, 1.0)

    def test_colors_match_helper(self) -> None:
        c1 = (0.88, 0.11, 0.14, 1.0)
        c2 = (224 / 255, 27 / 255, 36 / 255, 1.0)
        self.assertTrue(colors_match(c1, c2))
        self.assertTrue(colors_match(c1, c1))

        c_different = (0.1, 0.5, 0.9, 1.0)
        self.assertFalse(colors_match(c1, c_different))

    def test_palette_default_color(self) -> None:
        palette = ToolPalette()
        self.assertEqual(palette.current_color, DEFAULT_TOOL_COLOR)

        red_dot = palette.get_color_dot("red")
        self.assertIsNotNone(red_dot)
        self.assertTrue(red_dot.has_css_class("is-active-color"))

        blue_dot = palette.get_color_dot("blue")
        self.assertIsNotNone(blue_dot)
        self.assertFalse(blue_dot.has_css_class("is-active-color"))

        self.assertFalse(palette.btn_color.has_css_class("is-active-color"))

    def test_select_curated_color_dots(self) -> None:
        palette = ToolPalette()

        for c in CURATED_PALETTE_COLORS:
            name = c["name"].lower()
            dot = palette.get_color_dot(name)
            self.assertIsNotNone(dot, f"Dot for {name} should exist")
            dot.emit("clicked")

            self.assertEqual(palette.current_color, c["rgba"])
            self.assertTrue(dot.has_css_class("is-active-color"))
            self.assertFalse(palette.btn_color.has_css_class("is-active-color"))

            # All other dots should not be active
            for other_c in CURATED_PALETTE_COLORS:
                if other_c["name"].lower() != name:
                    other_dot = palette.get_color_dot(other_c["name"].lower())
                    self.assertFalse(other_dot.has_css_class("is-active-color"))

    def test_custom_color_selection(self) -> None:
        palette = ToolPalette()

        custom_color = (0.42, 0.15, 0.77, 1.0)
        palette.set_current_color(custom_color)
        self.assertEqual(palette.current_color, custom_color)

        # None of the curated dots should be active
        for c in CURATED_PALETTE_COLORS:
            dot = palette.get_color_dot(c["name"].lower())
            self.assertFalse(dot.has_css_class("is-active-color"))

        # The color button itself should have active styling
        self.assertTrue(palette.btn_color.has_css_class("is-active-color"))

    def test_palette_color_callback(self) -> None:
        palette = ToolPalette()
        received_colors: list[tuple[float, float, float, float]] = []

        def on_color(c: tuple[float, float, float, float]) -> None:
            received_colors.append(c)

        palette.add_color_changed_callback(on_color)

        green_dot = palette.get_color_dot("green")
        self.assertIsNotNone(green_dot)
        green_dot.emit("clicked")

        self.assertEqual(len(received_colors), 1)
        self.assertEqual(received_colors[0], palette.current_color)

        # Removing callback
        palette.remove_color_changed_callback(on_color)
        palette.get_color_dot("blue").emit("clicked")
        self.assertEqual(len(received_colors), 1)

    def test_tool_manager_color_sync(self) -> None:
        canvas = Canvas()
        mgr = ToolManager(canvas)
        palette = ToolPalette(mgr)

        self.assertEqual(mgr.current_color, DEFAULT_TOOL_COLOR)
        self.assertEqual(palette.current_color, DEFAULT_TOOL_COLOR)

        # Changing via ToolManager updates palette
        cyan_rgba = CURATED_PALETTE_COLORS[4]["rgba"]
        mgr.set_current_color(cyan_rgba)
        self.assertEqual(palette.current_color, cyan_rgba)
        cyan_dot = palette.get_color_dot("cyan")
        self.assertTrue(cyan_dot.has_css_class("is-active-color"))

        # Changing via Palette updates ToolManager
        orange_dot = palette.get_color_dot("orange")
        orange_dot.emit("clicked")
        self.assertEqual(mgr.current_color, palette.current_color)

    def test_main_window_palette_color_integration(self) -> None:
        win = MainWindow()
        self.assertIsInstance(win.palette, ToolPalette)
        self.assertEqual(win.palette.current_color, DEFAULT_TOOL_COLOR)
        self.assertEqual(win.canvas.tool_manager.current_color, DEFAULT_TOOL_COLOR)

        yellow_dot = win.palette.get_color_dot("yellow")
        self.assertIsNotNone(yellow_dot)
        yellow_dot.emit("clicked")

        self.assertEqual(
            win.canvas.tool_manager.current_color,
            win.palette.current_color
        )


if __name__ == "__main__":
    unittest.main()
