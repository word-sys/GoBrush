from __future__ import annotations
import math
import unittest
import cairo
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gtk, Gdk

from gobrush.items.highlighter import HighlighterItem
from gobrush.tools.highlighter import HighlighterTool
from gobrush.tools.select import SelectTool
from gobrush.core.document import AnnotationDocument
from gobrush.ui.canvas import Canvas


class TestHighlighterItem(unittest.TestCase):
    def test_highlighter_item_defaults(self):
        item = HighlighterItem()
        self.assertEqual(item.type_name, "highlighter")
        self.assertEqual(item.points, [])
        self.assertEqual(item.stroke_width, 16.0)
        self.assertEqual(item.stroke_color, (0.95, 0.77, 0.06, 0.5))
        self.assertTrue(item.is_visible)
        self.assertFalse(item.is_selected)

    def test_draw_with_multiply_preserves_black_text(self):
        # Create a 200x100 white surface with a solid black rectangle (simulating black text)
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 200, 100)
        cr = cairo.Context(surf)
        cr.set_source_rgb(1.0, 1.0, 1.0)
        cr.paint()

        # Pure black box (e.g. text glyph) at (50, 40, 40, 20)
        cr.set_source_rgb(0.0, 0.0, 0.0)
        cr.rectangle(50, 40, 40, 20)
        cr.fill()

        # Draw yellow highlighter across (20, 50) -> (180, 50)
        hl = HighlighterItem(
            points=[(20.0, 50.0), (180.0, 50.0)],
            stroke_color=(1.0, 0.95, 0.0, 0.5),
            stroke_width=24.0,
        )
        hl.draw(cr)

        surf.flush()
        data = surf.get_data()
        stride = surf.get_stride()

        # Check black text pixel at (60, 50): MUST remain pure black (R=0, G=0, B=0)
        offset_text = 50 * stride + 60 * 4
        b_txt, g_txt, r_txt = data[offset_text], data[offset_text + 1], data[offset_text + 2]
        self.assertEqual((r_txt, g_txt, b_txt), (0, 0, 0))

        # Check white background with yellow highlight at (30, 50): must be yellow tinted
        offset_bg = 50 * stride + 30 * 4
        b_bg, g_bg, r_bg = data[offset_bg], data[offset_bg + 1], data[offset_bg + 2]
        self.assertEqual(r_bg, 255)
        self.assertGreater(g_bg, 200)
        self.assertLess(b_bg, 200)

    def test_bounds_and_hit_testing(self):
        hl = HighlighterItem(points=[(50.0, 50.0), (150.0, 50.0)], stroke_width=20.0)
        bx, by, bw, bh = hl.get_bounds()
        pad = 20.0 / 2.0 + 1.0
        self.assertAlmostEqual(bx, 50.0 - pad)
        self.assertAlmostEqual(by, 50.0 - pad)
        self.assertAlmostEqual(bw, 100.0 + 2.0 * pad)
        self.assertAlmostEqual(bh, 2.0 * pad)

        # Hit testing within 20px stroke width / 2.0 + tolerance
        self.assertTrue(hl.hit_test(100.0, 50.0))
        self.assertTrue(hl.hit_test(100.0, 59.0)) # within 10px half width
        self.assertFalse(hl.hit_test(100.0, 75.0)) # outside

    def test_clone_and_serialization(self):
        hl = HighlighterItem(
            points=[(10.0, 10.0), (80.0, 20.0)],
            stroke_color=(0.2, 0.8, 0.4, 0.5),
            stroke_width=24.0,
        )
        cloned = hl.clone()
        self.assertIsInstance(cloned, HighlighterItem)
        self.assertNotEqual(hl.item_id, cloned.item_id)
        self.assertEqual(cloned.points, hl.points)
        self.assertEqual(cloned.stroke_color, hl.stroke_color)
        self.assertEqual(cloned.stroke_width, 24.0)

        data = hl.to_dict()
        self.assertEqual(data["type"], "highlighter")
        restored = HighlighterItem.from_dict(data)
        self.assertIsInstance(restored, HighlighterItem)
        self.assertEqual(restored.points, hl.points)
        self.assertEqual(restored.stroke_width, 24.0)


class TestHighlighterTool(unittest.TestCase):
    def setUp(self):
        self.canvas = Canvas()
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 400, 300)
        self.canvas.set_image_surface(surf, width=400, height=300)
        self.tool = HighlighterTool(self.canvas)
        self.canvas.tool_manager.register_tool(self.tool)
        self.canvas.tool_manager.set_active_tool("highlighter")

    def test_tool_metadata(self):
        self.assertEqual(self.tool.tool_id, "highlighter")
        self.assertEqual(self.tool.name, "Highlighter")
        self.assertEqual(self.tool.shortcut, "H")
        self.assertEqual(self.tool.cursor_name, "crosshair")

    def test_highlight_drawing_workflow(self):
        doc = self.canvas.document
        self.assertEqual(len(doc.items), 0)

        # Press
        self.assertTrue(self.tool.on_press(30.0, 60.0, 30.0, 60.0, Gdk.ModifierType(0)))
        self.assertTrue(self.tool.is_drawing)

        # Drag freehand
        self.tool.on_drag(50.0, 62.0, 20.0, 2.0, 50.0, 62.0, Gdk.ModifierType(0))
        self.tool.on_drag(80.0, 58.0, 30.0, -4.0, 80.0, 58.0, Gdk.ModifierType(0))

        # Release
        self.assertTrue(self.tool.on_release(100.0, 60.0, 100.0, 60.0, Gdk.ModifierType(0)))
        self.assertFalse(self.tool.is_drawing)
        self.assertEqual(len(doc.items), 1)

        item = doc.items[0]
        self.assertIsInstance(item, HighlighterItem)
        self.assertGreaterEqual(len(item.points), 3)

    def test_shift_straight_line_snapping(self):
        doc = self.canvas.document

        # Press at (50.0, 100.0)
        self.tool.on_press(50.0, 100.0, 50.0, 100.0, Gdk.ModifierType(0))

        # Drag with SHIFT modifier horizontally with some Y jitter
        shift_mask = Gdk.ModifierType.SHIFT_MASK
        self.tool.on_drag(100.0, 107.0, 50.0, 7.0, 100.0, 107.0, shift_mask)
        self.tool.on_drag(200.0, 95.0, 100.0, -12.0, 200.0, 95.0, shift_mask)
        self.tool.on_release(250.0, 104.0, 250.0, 104.0, shift_mask)

        self.assertEqual(len(doc.items), 1)
        item = doc.items[0]
        self.assertIsInstance(item, HighlighterItem)
        # All Y points should be snapped to the start Y (100.0)
        for pt in item.points:
            self.assertAlmostEqual(pt[1], 100.0, places=3)

    def test_undo_and_redo(self):
        doc = self.canvas.document
        self.tool.on_press(10.0, 10.0, 10.0, 10.0, Gdk.ModifierType(0))
        self.tool.on_drag(50.0, 10.0, 40.0, 0.0, 50.0, 10.0, Gdk.ModifierType(0))
        self.tool.on_release(50.0, 10.0, 50.0, 10.0, Gdk.ModifierType(0))

        self.assertEqual(len(doc.items), 1)
        self.canvas.undo()
        self.assertEqual(len(doc.items), 0)
        self.canvas.redo()
        self.assertEqual(len(doc.items), 1)
        self.assertIsInstance(doc.items[0], HighlighterItem)

    def test_cancel_via_escape(self):
        doc = self.canvas.document
        self.tool.on_press(20.0, 20.0, 20.0, 20.0, Gdk.ModifierType(0))
        self.tool.on_drag(40.0, 20.0, 20.0, 0.0, 40.0, 20.0, Gdk.ModifierType(0))

        self.assertTrue(self.tool.on_key_pressed(Gdk.KEY_Escape, Gdk.ModifierType(0)))
        self.assertFalse(self.tool.is_drawing)
        self.assertEqual(len(doc.items), 0)

    def test_select_and_duplicate_highlighter(self):
        # Draw a highlight
        self.tool.on_press(100.0, 150.0, 100.0, 150.0, Gdk.ModifierType(0))
        self.tool.on_drag(200.0, 150.0, 100.0, 0.0, 200.0, 150.0, Gdk.ModifierType(0))
        self.tool.on_release(200.0, 150.0, 200.0, 150.0, Gdk.ModifierType(0))

        # Select tool
        self.canvas.tool_manager.set_active_tool("select")
        select_tool = self.canvas.tool_manager.get_tool("select")

        # Click to select
        select_tool.on_press(150.0, 150.0, 150.0, 150.0, Gdk.ModifierType(0))
        select_tool.on_release(150.0, 150.0, 150.0, 150.0, Gdk.ModifierType(0))

        self.assertEqual(len(self.canvas.document.selected_items), 1)
        self.assertIsInstance(self.canvas.document.selected_items[0], HighlighterItem)

        # Duplicate via Ctrl+D
        self.assertTrue(select_tool.duplicate_selected())
        self.assertEqual(len(self.canvas.document.items), 2)
        self.assertIsInstance(self.canvas.document.items[1], HighlighterItem)

    def test_highlighter_size_selection(self):
        doc = self.canvas.document
        doc.clear()

        # Test each supported size (2px, 4px, 8px, 16px)
        for expected_size in (2.0, 4.0, 8.0, 16.0):
            self.canvas.tool_manager.set_stroke_width(expected_size)
            self.tool.on_press(10.0, 10.0 * expected_size, 10.0, 10.0 * expected_size, Gdk.ModifierType(0))
            self.tool.on_drag(50.0, 10.0 * expected_size, 40.0, 0.0, 50.0, 10.0 * expected_size, Gdk.ModifierType(0))
            self.tool.on_release(50.0, 10.0 * expected_size, 50.0, 10.0 * expected_size, Gdk.ModifierType(0))

            last_item = doc.items[-1]
            self.assertIsInstance(last_item, HighlighterItem)
            self.assertEqual(last_item.stroke_width, expected_size)


if __name__ == "__main__":
    unittest.main()
