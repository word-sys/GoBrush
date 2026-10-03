from __future__ import annotations
import math
import unittest
import cairo
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gtk, Gdk

from gobrush.items.pen import PenItem, build_smooth_path
from gobrush.tools.pen import PenTool
from gobrush.tools.select import SelectTool
from gobrush.core.document import AnnotationDocument
from gobrush.core.history import UndoManager
from gobrush.ui.canvas import Canvas


class TestPenItem(unittest.TestCase):
    def test_pen_item_defaults(self):
        item = PenItem()
        self.assertEqual(item.type_name, "pen")
        self.assertEqual(item.points, [])
        self.assertEqual(item.stroke_width, 4.0)
        self.assertEqual(item.stroke_color, (0.88, 0.11, 0.14, 1.0))
        self.assertIsNone(item.fill_color)
        self.assertTrue(item.is_visible)
        self.assertFalse(item.is_selected)
        self.assertTrue(len(item.item_id) > 0)

    def test_add_point_and_filtering(self):
        item = PenItem()
        self.assertTrue(item.add_point(10.0, 10.0))
        self.assertEqual(len(item.points), 1)

        # Micro movement less than min_distance (1.0) should be skipped
        self.assertFalse(item.add_point(10.2, 10.2, min_distance=1.0))
        self.assertEqual(len(item.points), 1)

        # Movement greater than or equal to min_distance should be appended
        self.assertTrue(item.add_point(12.0, 10.0, min_distance=1.0))
        self.assertEqual(len(item.points), 2)
        self.assertEqual(item.points[-1], (12.0, 10.0))

    def test_get_bounds_empty_and_points(self):
        empty_item = PenItem()
        self.assertEqual(empty_item.get_bounds(), (0.0, 0.0, 0.0, 0.0))

        # Single dot
        dot_item = PenItem(points=[(50.0, 50.0)], stroke_width=4.0)
        bx, by, bw, bh = dot_item.get_bounds()
        pad = 4.0 / 2.0 + 1.0
        self.assertAlmostEqual(bx, 50.0 - pad)
        self.assertAlmostEqual(by, 50.0 - pad)
        self.assertAlmostEqual(bw, 2.0 * pad)
        self.assertAlmostEqual(bh, 2.0 * pad)

        # Multi-point stroke
        multi_item = PenItem(points=[(10.0, 20.0), (50.0, 80.0), (30.0, 100.0)], stroke_width=4.0)
        bx, by, bw, bh = multi_item.get_bounds()
        self.assertAlmostEqual(bx, 10.0 - pad)
        self.assertAlmostEqual(by, 20.0 - pad)
        self.assertAlmostEqual(bw, 40.0 + 2.0 * pad)
        self.assertAlmostEqual(bh, 80.0 + 2.0 * pad)

    def test_hit_test(self):
        item = PenItem(points=[(10.0, 10.0), (50.0, 10.0)], stroke_width=4.0)
        # Directly on segment
        self.assertTrue(item.hit_test(30.0, 10.0))
        # Near segment within tolerance (6.0 + 2.0 = 8.0)
        self.assertTrue(item.hit_test(30.0, 16.0, tolerance=6.0))
        # Outside tolerance
        self.assertFalse(item.hit_test(30.0, 25.0, tolerance=6.0))

        # Single dot hit testing
        dot = PenItem(points=[(100.0, 100.0)], stroke_width=6.0)
        self.assertTrue(dot.hit_test(100.0, 100.0))
        self.assertTrue(dot.hit_test(105.0, 100.0))
        self.assertFalse(dot.hit_test(120.0, 100.0))

    def test_draw_surface(self):
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 100, 100)
        cr = cairo.Context(surf)

        # Empty item
        PenItem().draw(cr)

        # Single dot
        dot = PenItem(points=[(20.0, 20.0)], stroke_width=4.0)
        dot.draw(cr)

        # 2-point line
        line = PenItem(points=[(10.0, 10.0), (90.0, 90.0)], stroke_width=2.0)
        line.draw(cr)

        # Multi-point smoothed curve with fill
        curve = PenItem(
            points=[(10.0, 10.0), (40.0, 80.0), (80.0, 20.0)],
            stroke_width=3.0,
            fill_color=(0.2, 0.4, 0.8, 0.5),
        )
        curve.draw(cr)

    def test_move_by(self):
        item = PenItem(points=[(10.0, 15.0), (20.0, 25.0)], stroke_width=4.0)
        item.move_by(5.0, -3.0)
        self.assertEqual(item.points, [(15.0, 12.0), (25.0, 22.0)])

    def test_get_and_set_geometry_scaling(self):
        item = PenItem(points=[(10.0, 10.0), (50.0, 50.0)], stroke_width=4.0)
        b0 = item.get_geometry()
        self.assertEqual(len(b0), 4)

        # Resize to double width and height
        new_geom = (b0[0], b0[1], b0[2] * 2.0, b0[3] * 2.0)
        self.assertTrue(item.set_geometry(new_geom))
        self.assertGreater(item.points[-1][0], 50.0)

        # Scale back to original geometry
        self.assertTrue(item.set_geometry(b0))
        self.assertAlmostEqual(item.points[0][0], 10.0, places=3)
        self.assertAlmostEqual(item.points[0][1], 10.0, places=3)
        self.assertAlmostEqual(item.points[1][0], 50.0, places=3)
        self.assertAlmostEqual(item.points[1][1], 50.0, places=3)

    def test_clone_and_serialization(self):
        item = PenItem(
            points=[(5.0, 5.0), (15.0, 25.0)],
            stroke_color=(0.1, 0.2, 0.3, 1.0),
            stroke_width=8.0,
            fill_color=(0.5, 0.5, 0.5, 0.2),
        )
        cloned = item.clone()
        self.assertNotEqual(item.item_id, cloned.item_id)
        self.assertEqual(cloned.points, item.points)
        self.assertEqual(cloned.stroke_color, item.stroke_color)
        self.assertEqual(cloned.stroke_width, item.stroke_width)
        self.assertEqual(cloned.fill_color, item.fill_color)

        data = item.to_dict()
        self.assertEqual(data["type"], "pen")
        self.assertEqual(len(data["points"]), 2)

        restored = PenItem.from_dict(data)
        self.assertEqual(restored.points, item.points)
        self.assertEqual(restored.stroke_color, item.stroke_color)
        self.assertEqual(restored.stroke_width, item.stroke_width)
        self.assertEqual(restored.fill_color, item.fill_color)


class TestPenTool(unittest.TestCase):
    def setUp(self):
        self.canvas = Canvas()
        # Create a mock 400x300 image on canvas
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 400, 300)
        self.canvas.set_image_surface(surf, width=400, height=300)
        self.tool = PenTool(self.canvas)
        self.canvas.tool_manager.register_tool(self.tool)
        self.canvas.tool_manager.set_active_tool("pen")

    def test_tool_metadata(self):
        self.assertEqual(self.tool.tool_id, "pen")
        self.assertEqual(self.tool.name, "Pen")
        self.assertEqual(self.tool.shortcut, "P")
        self.assertEqual(self.tool.cursor_name, "crosshair")

    def test_draw_stroke_workflow(self):
        doc = self.canvas.document
        self.assertEqual(len(doc.items), 0)

        # Press
        handled = self.tool.on_press(50.0, 50.0, 50.0, 50.0, Gdk.ModifierType(0))
        self.assertTrue(handled)
        self.assertTrue(self.tool.is_drawing)
        self.assertEqual(len(self.tool.current_points), 1)

        # Drag points
        self.tool.on_drag(60.0, 55.0, 10.0, 5.0, 60.0, 55.0, Gdk.ModifierType(0))
        self.tool.on_drag(80.0, 70.0, 20.0, 15.0, 80.0, 70.0, Gdk.ModifierType(0))
        self.assertEqual(len(self.tool.current_points), 3)

        # Release creates PenItem in document
        handled = self.tool.on_release(90.0, 80.0, 90.0, 80.0, Gdk.ModifierType(0))
        self.assertTrue(handled)
        self.assertFalse(self.tool.is_drawing)
        self.assertEqual(len(doc.items), 1)

        item = doc.items[0]
        self.assertIsInstance(item, PenItem)
        self.assertGreaterEqual(len(item.points), 3)

    def test_undo_and_redo_pen_stroke(self):
        doc = self.canvas.document
        self.tool.on_press(20.0, 20.0, 20.0, 20.0, Gdk.ModifierType(0))
        self.tool.on_drag(40.0, 40.0, 20.0, 20.0, 40.0, 40.0, Gdk.ModifierType(0))
        self.tool.on_release(40.0, 40.0, 40.0, 40.0, Gdk.ModifierType(0))

        self.assertEqual(len(doc.items), 1)

        # Undo
        self.canvas.undo()
        self.assertEqual(len(doc.items), 0)

        # Redo
        self.canvas.redo()
        self.assertEqual(len(doc.items), 1)
        self.assertIsInstance(doc.items[0], PenItem)

    def test_cancel_via_escape(self):
        doc = self.canvas.document
        self.tool.on_press(30.0, 30.0, 30.0, 30.0, Gdk.ModifierType(0))
        self.tool.on_drag(50.0, 50.0, 20.0, 20.0, 50.0, 50.0, Gdk.ModifierType(0))
        self.assertTrue(self.tool.is_drawing)

        # Press Escape
        handled = self.tool.on_key_pressed(Gdk.KEY_Escape, Gdk.ModifierType(0))
        self.assertTrue(handled)
        self.assertFalse(self.tool.is_drawing)
        self.assertEqual(len(self.tool.current_points), 0)
        self.assertEqual(len(doc.items), 0)

    def test_draw_overlay(self):
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 100, 100)
        cr = cairo.Context(surf)

        # No drawing: does nothing
        self.tool.draw_overlay(cr)

        # In-progress drawing
        self.tool.on_press(10.0, 10.0, 10.0, 10.0, Gdk.ModifierType(0))
        self.tool.on_drag(20.0, 30.0, 10.0, 20.0, 20.0, 30.0, Gdk.ModifierType(0))
        self.tool.draw_overlay(cr)
        self.tool.on_cancel()

    def test_select_and_manipulate_drawn_pen(self):
        # Draw a stroke with pen
        self.tool.on_press(100.0, 100.0, 100.0, 100.0, Gdk.ModifierType(0))
        self.tool.on_drag(150.0, 100.0, 50.0, 0.0, 150.0, 100.0, Gdk.ModifierType(0))
        self.tool.on_release(150.0, 100.0, 150.0, 100.0, Gdk.ModifierType(0))

        # Switch to Select tool
        self.canvas.tool_manager.set_active_tool("select")
        select_tool = self.canvas.tool_manager.get_tool("select")

        # Click on the pen stroke to select it
        select_tool.on_press(125.0, 100.0, 125.0, 100.0, Gdk.ModifierType(0))
        select_tool.on_release(125.0, 100.0, 125.0, 100.0, Gdk.ModifierType(0))

        self.assertEqual(len(self.canvas.document.selected_items), 1)
        selected_item = self.canvas.document.selected_items[0]
        self.assertIsInstance(selected_item, PenItem)

        # Duplicate via Ctrl+D
        self.assertTrue(select_tool.duplicate_selected())
        self.assertEqual(len(self.canvas.document.items), 2)

        # Delete selected
        self.assertTrue(select_tool.delete_selected())
        self.assertEqual(len(self.canvas.document.items), 1)


if __name__ == "__main__":
    unittest.main()
