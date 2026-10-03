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
    DEFAULT_FILL_OPACITY,
    DEFAULT_TOOL_COLOR,
    PenTool,
    RectangleTool,
    CropTool,
)
from gobrush.ui.property_bar import (
    ContextPropertyBar,
    SIZE_OPTIONS,
    FILL_OPTIONS,
    OPACITY_OPTIONS,
    RADIUS_OPTIONS,
)
from gobrush.ui.palette import ToolPalette
from gobrush.ui.canvas import Canvas
from gobrush.ui.window import MainWindow


class TestContextPropertyBar(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        Gtk.init()

    def test_options_definitions(self) -> None:
        self.assertEqual(len(SIZE_OPTIONS), 6)
        size_labels = [opt["label"] for opt in SIZE_OPTIONS]
        self.assertEqual(size_labels, ["2px", "4px", "8px", "16px", "24px", "32px"])

        self.assertEqual(len(FILL_OPTIONS), 3)
        fill_values = [opt["value"] for opt in FILL_OPTIONS]
        self.assertEqual(fill_values, ["outline", "semi", "solid"])

        self.assertEqual(len(OPACITY_OPTIONS), 4)
        opacity_values = [opt["value"] for opt in OPACITY_OPTIONS]
        self.assertEqual(opacity_values, [0.15, 0.25, 0.50, 0.75])

        self.assertEqual(len(RADIUS_OPTIONS), 3)
        radius_labels = [opt["label"] for opt in RADIUS_OPTIONS]
        self.assertEqual(radius_labels, ["Sharp", "Round", "Pill"])
        radius_values = [opt["value"] for opt in RADIUS_OPTIONS]
        self.assertEqual(radius_values, [0.0, 8.0, 16.0])

    def test_property_bar_defaults(self) -> None:
        bar = ContextPropertyBar()
        self.assertEqual(bar.stroke_width, DEFAULT_STROKE_WIDTH)
        self.assertEqual(bar.fill_mode, DEFAULT_FILL_MODE)
        self.assertAlmostEqual(bar.fill_opacity, DEFAULT_FILL_OPACITY, places=2)

        # Size 4px active by default
        btn_4 = bar.get_size_button("4px")
        self.assertIsNotNone(btn_4)
        self.assertTrue(btn_4.get_active())
        self.assertTrue(btn_4.has_css_class("is-active-size"))
        self.assertEqual(bar.scale_size.get_value(), 4.0)
        self.assertEqual(bar.badge_size.get_text(), "4 px")

        # Outline active by default
        btn_outline = bar.get_fill_button("outline")
        self.assertIsNotNone(btn_outline)
        self.assertTrue(btn_outline.get_active())
        self.assertTrue(btn_outline.has_css_class("is-active-fill"))
        self.assertEqual(bar.badge_fill.get_text(), "Outline")

        # Opacity slider default
        self.assertAlmostEqual(bar.scale_opacity.get_value(), 25.0, places=1)
        self.assertEqual(bar.badge_opacity.get_text(), "25%")
        # In outline mode, opacity controls are insensitive
        self.assertFalse(bar.box_opacity.get_sensitive())

    def test_size_slider_continuous_adjustment(self) -> None:
        bar = ContextPropertyBar()

        # Adjust slider to custom value not in presets (e.g. 13)
        bar.scale_size.set_value(13.0)
        self.assertEqual(bar.stroke_width, 13.0)
        self.assertEqual(bar.badge_size.get_text(), "13 px")

        # Preset buttons should not be active for custom value
        for opt in SIZE_OPTIONS:
            btn = bar.get_size_button(opt["label"])
            self.assertFalse(btn.has_css_class("is-active-size"))

        # Adjust slider to preset value (e.g. 24)
        bar.scale_size.set_value(24.0)
        self.assertEqual(bar.stroke_width, 24.0)
        self.assertEqual(bar.badge_size.get_text(), "24 px")
        btn_24 = bar.get_size_button("24px")
        self.assertTrue(btn_24.has_css_class("is-active-size"))

    def test_size_button_switching(self) -> None:
        bar = ContextPropertyBar()

        for opt in SIZE_OPTIONS:
            lbl = opt["label"]
            val = opt["value"]
            btn = bar.get_size_button(lbl)
            self.assertIsNotNone(btn)
            btn.emit("clicked")

            self.assertEqual(bar.stroke_width, val)
            self.assertEqual(bar.scale_size.get_value(), val)
            self.assertTrue(btn.get_active())
            self.assertTrue(btn.has_css_class("is-active-size"))

            # Other size buttons should not be active
            for other_opt in SIZE_OPTIONS:
                if other_opt["label"] != lbl:
                    other_btn = bar.get_size_button(other_opt["label"])
                    self.assertFalse(other_btn.has_css_class("is-active-size"))

    def test_fill_button_switching_and_opacity_state(self) -> None:
        bar = ContextPropertyBar()

        # Switch to Semi-Fill
        btn_semi = bar.get_fill_button("semi")
        self.assertIsNotNone(btn_semi)
        btn_semi.emit("clicked")
        self.assertEqual(bar.fill_mode, "semi")
        self.assertTrue(btn_semi.get_active())
        self.assertTrue(bar.box_opacity.get_sensitive())
        self.assertEqual(bar.badge_fill.get_text(), "25%")

        # Switch to Solid
        btn_solid = bar.get_fill_button("solid")
        self.assertIsNotNone(btn_solid)
        btn_solid.emit("clicked")
        self.assertEqual(bar.fill_mode, "solid")
        self.assertTrue(btn_solid.get_active())
        self.assertFalse(bar.box_opacity.get_sensitive())
        self.assertEqual(bar.badge_fill.get_text(), "Solid")

        # Switch to Outline
        btn_outline = bar.get_fill_button("outline")
        self.assertIsNotNone(btn_outline)
        btn_outline.emit("clicked")
        self.assertEqual(bar.fill_mode, "outline")
        self.assertTrue(btn_outline.get_active())
        self.assertFalse(bar.box_opacity.get_sensitive())
        self.assertEqual(bar.badge_fill.get_text(), "Outline")

    def test_opacity_slider_and_chips(self) -> None:
        bar = ContextPropertyBar()
        bar.set_fill_mode("semi")

        # Continuous scale change
        bar.scale_opacity.set_value(65.0)
        self.assertAlmostEqual(bar.fill_opacity, 0.65, places=2)
        self.assertEqual(bar.badge_opacity.get_text(), "65%")
        self.assertEqual(bar.badge_fill.get_text(), "65%")

        # Opacity chip click (e.g. 50%)
        chip_50 = bar.get_opacity_button("50%")
        self.assertIsNotNone(chip_50)
        chip_50.emit("clicked")
        self.assertAlmostEqual(bar.fill_opacity, 0.50, places=2)
        self.assertAlmostEqual(bar.scale_opacity.get_value(), 50.0, places=1)
        self.assertTrue(chip_50.has_css_class("is-active-opacity"))

        # Adjusting opacity while in outline mode activates semi
        bar.set_fill_mode("outline")
        self.assertEqual(bar.fill_mode, "outline")
        bar.scale_opacity.set_value(40.0)
        self.assertEqual(bar.fill_mode, "semi")
        self.assertAlmostEqual(bar.fill_opacity, 0.40, places=2)

    def test_style_callbacks(self) -> None:
        bar = ContextPropertyBar()
        events_2param: list[tuple[float, str]] = []
        events_3param: list[tuple[float, str, float]] = []

        def on_style_2(w: float, f: str) -> None:
            events_2param.append((w, f))

        def on_style_3(w: float, f: str, op: float) -> None:
            events_3param.append((w, f, op))

        bar.add_style_changed_callback(on_style_2)
        bar.add_style_changed_callback(on_style_3)

        bar.set_stroke_width(8.0)
        self.assertEqual(len(events_2param), 1)
        self.assertEqual(events_2param[0], (8.0, "outline"))
        self.assertEqual(len(events_3param), 1)
        self.assertEqual(events_3param[0], (8.0, "outline", 0.25))

        bar.set_fill_mode("semi")
        self.assertEqual(len(events_2param), 2)
        self.assertEqual(events_2param[1], (8.0, "semi"))
        self.assertEqual(len(events_3param), 2)
        self.assertEqual(events_3param[1], (8.0, "semi", 0.25))

        bar.set_fill_opacity(0.6)
        self.assertEqual(len(events_2param), 3)
        self.assertEqual(events_2param[2], (8.0, "semi"))
        self.assertEqual(len(events_3param), 3)
        self.assertEqual(events_3param[2], (8.0, "semi", 0.6))

        bar.remove_style_changed_callback(on_style_2)
        bar.set_stroke_width(16.0)
        self.assertEqual(len(events_2param), 3)
        self.assertEqual(len(events_3param), 4)

    def test_tool_manager_bidirectional_sync(self) -> None:
        canvas = Canvas()
        mgr = ToolManager(canvas)
        bar = ContextPropertyBar(mgr)

        self.assertEqual(mgr.stroke_width, 4.0)
        self.assertEqual(mgr.fill_mode, "outline")
        self.assertAlmostEqual(mgr.fill_opacity, 0.25, places=2)

        # Manager -> Bar: stroke width
        mgr.set_stroke_width(2.0)
        self.assertEqual(bar.stroke_width, 2.0)
        self.assertEqual(bar.scale_size.get_value(), 2.0)
        self.assertTrue(bar.get_size_button("2px").has_css_class("is-active-size"))

        # Manager -> Bar: fill mode
        mgr.set_fill_mode("solid")
        self.assertEqual(bar.fill_mode, "solid")
        self.assertTrue(bar.get_fill_button("solid").has_css_class("is-active-fill"))

        # Manager -> Bar: fill opacity
        mgr.set_fill_mode("semi")
        mgr.set_fill_opacity(0.75)
        self.assertAlmostEqual(bar.fill_opacity, 0.75, places=2)
        self.assertAlmostEqual(bar.scale_opacity.get_value(), 75.0, places=1)

        # Bar -> Manager: size button click
        bar.get_size_button("16px").emit("clicked")
        self.assertEqual(mgr.stroke_width, 16.0)

        # Bar -> Manager: size slider
        bar.scale_size.set_value(32.0)
        self.assertEqual(mgr.stroke_width, 32.0)

        # Bar -> Manager: fill button click
        bar.get_fill_button("solid").emit("clicked")
        self.assertEqual(mgr.fill_mode, "solid")

        # Bar -> Manager: opacity slider
        bar.get_fill_button("semi").emit("clicked")
        bar.scale_opacity.set_value(50.0)
        self.assertAlmostEqual(mgr.fill_opacity, 0.50, places=2)

    def test_effective_fill_color_calculation(self) -> None:
        mgr = ToolManager()
        # Red: (0.88, 0.11, 0.14, 1.0)
        mgr.set_current_color((0.88, 0.11, 0.14, 1.0))

        # Outline -> None
        mgr.set_fill_mode("outline")
        self.assertIsNone(mgr.get_effective_fill_color())

        # Semi-Fill with default opacity -> alpha 0.25
        mgr.set_fill_mode("semi")
        semi_color = mgr.get_effective_fill_color()
        self.assertIsNotNone(semi_color)
        self.assertAlmostEqual(semi_color[0], 0.88, places=2)
        self.assertAlmostEqual(semi_color[3], 0.25, places=2)

        # Semi-Fill with custom opacity -> alpha 0.65
        mgr.set_fill_opacity(0.65)
        semi_custom = mgr.get_effective_fill_color()
        self.assertIsNotNone(semi_custom)
        self.assertAlmostEqual(semi_custom[3], 0.65, places=2)

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
        self.assertAlmostEqual(win.property_bar.fill_opacity, 0.25, places=2)

        # Via ToolPalette forwards
        self.assertEqual(win.palette.stroke_width, 4.0)
        self.assertEqual(win.palette.fill_mode, "outline")
        self.assertAlmostEqual(win.palette.fill_opacity, 0.25, places=2)

        win.palette.set_stroke_width(8.0)
        self.assertEqual(win.canvas.tool_manager.stroke_width, 8.0)
        self.assertEqual(win.property_bar.stroke_width, 8.0)

        win.palette.set_fill_mode("semi")
        self.assertEqual(win.canvas.tool_manager.fill_mode, "semi")
        self.assertEqual(win.property_bar.fill_mode, "semi")

        win.palette.set_fill_opacity(0.5)
        self.assertAlmostEqual(win.canvas.tool_manager.fill_opacity, 0.5, places=2)
        self.assertAlmostEqual(win.property_bar.fill_opacity, 0.5, places=2)

    def test_corner_radius_integration(self) -> None:
        mgr = ToolManager()
        bar = ContextPropertyBar(mgr)

        # By default not visible when no tool active
        self.assertFalse(bar.box_radius.get_visible())

        # Switch to rectangle tool -> box_radius becomes visible & sensitive
        bar.update_for_tool("rectangle")
        self.assertTrue(bar.box_radius.get_visible())
        self.assertTrue(bar.box_radius.get_sensitive())

        # Default corner radius is 0 (Sharp)
        self.assertEqual(bar.corner_radius, 0.0)
        self.assertEqual(bar.badge_radius.get_text(), "Sharp")
        btn_sharp = bar.get_radius_button("sharp")
        self.assertIsNotNone(btn_sharp)
        self.assertTrue(btn_sharp.has_css_class("is-active-radius"))

        # Click Round (8px)
        btn_round = bar.get_radius_button("round")
        self.assertIsNotNone(btn_round)
        btn_round.emit("clicked")
        self.assertEqual(mgr.corner_radius, 8.0)
        self.assertEqual(bar.corner_radius, 8.0)
        self.assertEqual(bar.badge_radius.get_text(), "Round")

        # Click Pill (16px)
        btn_pill = bar.get_radius_button("pill")
        self.assertIsNotNone(btn_pill)
        btn_pill.emit("clicked")
        self.assertEqual(mgr.corner_radius, 16.0)
        self.assertEqual(bar.corner_radius, 16.0)
        self.assertEqual(bar.badge_radius.get_text(), "Pill")

        # Switch to Pen tool -> box_radius becomes hidden
        bar.update_for_tool("pen")
        self.assertFalse(bar.box_radius.get_visible())


if __name__ == "__main__":
    unittest.main()
