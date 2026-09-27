from __future__ import annotations
import unittest
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk

from gobrush.tools.base import (
    ToolManager,
    DEFAULT_STROKE_WIDTH,
    DEFAULT_FILL_MODE,
    DEFAULT_TOOL_COLOR,
    PenTool,
    RectangleTool,
    CropTool,
)
from gobrush.ui.property_bar import ContextPropertyBar, SIZE_OPTIONS, FILL_OPTIONS
from gobrush.ui.palette import ToolPalette
from gobrush.ui.canvas import Canvas
from gobrush.ui.window import MainWindow


class TestContextPropertyBar(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        Gtk.init()

    def test_options_definitions(self) -> None:
        self.assertEqual(len(SIZE_OPTIONS), 4)
        size_labels = [opt["label"] for opt in SIZE_OPTIONS]
        self.assertEqual(size_labels, ["2px", "4px", "8px", "16px"])

        self.assertEqual(len(FILL_OPTIONS), 3)
        fill_values = [opt["value"] for opt in FILL_OPTIONS]
        self.assertEqual(fill_values, ["outline", "semi", "solid"])

    def test_property_bar_defaults(self) -> None:
        bar = ContextPropertyBar()
        self.assertEqual(bar.stroke_width, DEFAULT_STROKE_WIDTH)
        self.assertEqual(bar.fill_mode, DEFAULT_FILL_MODE)

        btn_4 = bar.get_size_button("4px")
        self.assertIsNotNone(btn_4)
        self.assertTrue(btn_4.get_active())
        self.assertTrue(btn_4.has_css_class("is-active-size"))

        btn_outline = bar.get_fill_button("outline")
        self.assertIsNotNone(btn_outline)
        self.assertTrue(btn_outline.get_active())
        self.assertTrue(btn_outline.has_css_class("is-active-fill"))

    def test_size_button_switching(self) -> None:
        bar = ContextPropertyBar()

        for opt in SIZE_OPTIONS:
            lbl = opt["label"]
            val = opt["value"]
            btn = bar.get_size_button(lbl)
            self.assertIsNotNone(btn)
            btn.emit("clicked")

            self.assertEqual(bar.stroke_width, val)
            self.assertTrue(btn.get_active())
            self.assertTrue(btn.has_css_class("is-active-size"))

            # Other size buttons should not be active
            for other_opt in SIZE_OPTIONS:
                if other_opt["label"] != lbl:
                    other_btn = bar.get_size_button(other_opt["label"])
                    self.assertFalse(other_btn.has_css_class("is-active-size"))

    def test_fill_button_switching(self) -> None:
        bar = ContextPropertyBar()

        for opt in FILL_OPTIONS:
            mode = opt["value"]
            btn = bar.get_fill_button(mode)
            self.assertIsNotNone(btn)
            btn.emit("clicked")

            self.assertEqual(bar.fill_mode, mode)
            self.assertTrue(btn.get_active())
            self.assertTrue(btn.has_css_class("is-active-fill"))

            for other_opt in FILL_OPTIONS:
                if other_opt["value"] != mode:
                    other_btn = bar.get_fill_button(other_opt["value"])
                    self.assertFalse(other_btn.has_css_class("is-active-fill"))

    def test_style_callbacks(self) -> None:
        bar = ContextPropertyBar()
        events: list[tuple[float, str]] = []

        def on_style(w: float, f: str) -> None:
            events.append((w, f))

        bar.add_style_changed_callback(on_style)

        bar.set_stroke_width(8.0)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0], (8.0, "outline"))

        bar.set_fill_mode("semi")
        self.assertEqual(len(events), 2)
        self.assertEqual(events[1], (8.0, "semi"))

        bar.remove_style_changed_callback(on_style)
        bar.set_stroke_width(16.0)
        self.assertEqual(len(events), 2)

    def test_tool_manager_bidirectional_sync(self) -> None:
        canvas = Canvas()
        mgr = ToolManager(canvas)
        bar = ContextPropertyBar(mgr)

        self.assertEqual(mgr.stroke_width, 4.0)
        self.assertEqual(mgr.fill_mode, "outline")

        # Manager -> Bar
        mgr.set_stroke_width(2.0)
        self.assertEqual(bar.stroke_width, 2.0)
        self.assertTrue(bar.get_size_button("2px").has_css_class("is-active-size"))

        mgr.set_fill_mode("solid")
        self.assertEqual(bar.fill_mode, "solid")
        self.assertTrue(bar.get_fill_button("solid").has_css_class("is-active-fill"))

        # Bar -> Manager
        bar.get_size_button("16px").emit("clicked")
        self.assertEqual(mgr.stroke_width, 16.0)

        bar.get_fill_button("semi").emit("clicked")
        self.assertEqual(mgr.fill_mode, "semi")

    def test_effective_fill_color_calculation(self) -> None:
        mgr = ToolManager()
        # Red: (0.88, 0.11, 0.14, 1.0)
        mgr.set_current_color((0.88, 0.11, 0.14, 1.0))

        # Outline -> None
        mgr.set_fill_mode("outline")
        self.assertIsNone(mgr.get_effective_fill_color())

        # Semi-Fill -> alpha 0.25
        mgr.set_fill_mode("semi")
        semi_color = mgr.get_effective_fill_color()
        self.assertIsNotNone(semi_color)
        self.assertAlmostEqual(semi_color[0], 0.88, places=2)
        self.assertAlmostEqual(semi_color[3], 0.25, places=2)

        # Solid -> alpha 1.0
        mgr.set_fill_mode("solid")
        solid_color = mgr.get_effective_fill_color()
        self.assertIsNotNone(solid_color)
        self.assertAlmostEqual(solid_color[0], 0.88, places=2)
        self.assertAlmostEqual(solid_color[3], 1.0, places=2)

    def test_context_sensitivity(self) -> None:
        canvas = Canvas()
        mgr = ToolManager(canvas)
        bar = ContextPropertyBar(mgr)

        # Pen: size enabled, fill disabled
        bar.update_for_tool("pen")
        self.assertTrue(bar.box_size.get_sensitive())
        self.assertFalse(bar.box_fill.get_sensitive())

        # Rectangle: both enabled
        bar.update_for_tool("rectangle")
        self.assertTrue(bar.box_size.get_sensitive())
        self.assertTrue(bar.box_fill.get_sensitive())

        # Crop: both disabled
        bar.update_for_tool("crop")
        self.assertFalse(bar.box_size.get_sensitive())
        self.assertFalse(bar.box_fill.get_sensitive())

    def test_palette_and_window_integration(self) -> None:
        win = MainWindow()
        self.assertIsInstance(win.property_bar, ContextPropertyBar)
        self.assertEqual(win.property_bar.stroke_width, 4.0)
        self.assertEqual(win.property_bar.fill_mode, "outline")

        # Via ToolPalette forwards
        self.assertEqual(win.palette.stroke_width, 4.0)
        self.assertEqual(win.palette.fill_mode, "outline")

        win.palette.set_stroke_width(8.0)
        self.assertEqual(win.canvas.tool_manager.stroke_width, 8.0)
        self.assertEqual(win.property_bar.stroke_width, 8.0)

        win.palette.set_fill_mode("semi")
        self.assertEqual(win.canvas.tool_manager.fill_mode, "semi")
        self.assertEqual(win.property_bar.fill_mode, "semi")


if __name__ == "__main__":
    unittest.main()
