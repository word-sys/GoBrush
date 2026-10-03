from __future__ import annotations
import math
import unittest
import cairo
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gtk, Gdk

from gobrush.items.line import LineItem, snap_angle
from gobrush.items.base import HANDLE_START, HANDLE_END
from gobrush.tools.line import LineTool
from gobrush.tools.select import SelectTool
from gobrush.core.document import AnnotationDocument
from gobrush.ui.canvas import Canvas


class TestLineItem(unittest.TestCase):
    def test_line_item_defaults(self):
        item = LineItem(10.0, 20.0, 100.0, 200.0)
        self.assertEqual(item.type_name, "line")
        self.assertEqual((item.x1, item.y1, item.x2, item.y2), (10.0, 20.0, 100.0, 200.0))
        self.assertEqual(item.stroke_width, 4.0)
        self.assertEqual(item.stroke_color, (0.88, 0.11, 0.14, 1.0))
        self.assertTrue(item.is_visible)
        self.assertFalse(item.is_selected)

    def test_bounds(self):
        item = LineItem(20.0, 30.0, 120.0, 30.0, stroke_width=4.0)
        bx, by, bw, bh = item.get_bounds()
        pad = 4.0 / 2.0 + 1.0
        self.assertAlmostEqual(bx, 20.0 - pad)
        self.assertAlmostEqual(by, 30.0 - pad)
        self.assertAlmostEqual(bw, 100.0 + 2.0 * pad)
        self.assertAlmostEqual(bh, 2.0 * pad)

    def test_hit_test(self):
        item = LineItem(50.0, 50.0, 150.0, 50.0, stroke_width=4.0)
        # Directly on segment
        self.assertTrue(item.hit_test(100.0, 50.0))
        # Within tolerance (6.0 + 2.0 = 8.0)
        self.assertTrue(item.hit_test(100.0, 56.0, tolerance=6.0))
        # Outside perpendicular tolerance
        self.assertFalse(item.hit_test(100.0, 65.0, tolerance=6.0))
        # Outside longitudinal bounds
        self.assertFalse(item.hit_test(200.0, 50.0, tolerance=6.0))

    def test_draw(self):
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 100, 100)
        cr = cairo.Context(surf)
        item = LineItem(10.0, 10.0, 90.0, 90.0, stroke_width=3.0)
        item.draw(cr)

    def test_move_by(self):
        item = LineItem(10.0, 10.0, 50.0, 50.0)
        item.move_by(15.0, -5.0)
        self.assertEqual((item.x1, item.y1, item.x2, item.y2), (25.0, 5.0, 65.0, 45.0))

    def test_get_and_set_geometry(self):
        item = LineItem(10.0, 20.0, 30.0, 40.0)
        geom = item.get_geometry()
        self.assertEqual(geom, (10.0, 20.0, 30.0, 40.0))

        self.assertTrue(item.set_geometry((100.0, 200.0, 300.0, 400.0)))
        self.assertEqual((item.x1, item.y1, item.x2, item.y2), (100.0, 200.0, 300.0, 400.0))

    def test_handles_and_draw_selection(self):
        item = LineItem(20.0, 40.0, 80.0, 100.0)
        handles = item.get_handles()
        self.assertIn(HANDLE_START, handles)
        self.assertIn(HANDLE_END, handles)
        self.assertEqual(handles[HANDLE_START], (20.0, 40.0))
        self.assertEqual(handles[HANDLE_END], (80.0, 100.0))

        item.is_selected = True
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 120, 120)
        cr = cairo.Context(surf)
        item.draw_selection(cr)

    def test_clone_and_serialization(self):
        item = LineItem(15.0, 25.0, 75.0, 85.0, stroke_color=(0.1, 0.5, 0.9, 1.0), stroke_width=6.0)
        cloned = item.clone()
        self.assertIsInstance(cloned, LineItem)
        self.assertNotEqual(item.item_id, cloned.item_id)
        self.assertEqual((cloned.x1, cloned.y1, cloned.x2, cloned.y2), (item.x1, item.y1, item.x2, item.y2))
        self.assertEqual(cloned.stroke_color, item.stroke_color)
        self.assertEqual(cloned.stroke_width, item.stroke_width)

        data = item.to_dict()
        self.assertEqual(data["type"], "line")
        self.assertEqual(data["x1"], 15.0)

        restored = LineItem.from_dict(data)
        self.assertIsInstance(restored, LineItem)
        self.assertEqual((restored.x1, restored.y1, restored.x2, restored.y2), (15.0, 25.0, 75.0, 85.0))


class TestAngleSnapping(unittest.TestCase):
    def test_snap_horizontal(self):
        sx, sy = snap_angle(100.0, 100.0, 200.0, 108.0)
        self.assertAlmostEqual(sy, 100.0, places=4)
        self.assertGreater(sx, 195.0)

    def test_snap_vertical(self):
        sx, sy = snap_angle(100.0, 100.0, 105.0, 250.0)
        self.assertAlmostEqual(sx, 100.0, places=4)
        self.assertGreater(sy, 245.0)

    def test_snap_45_degrees(self):
        sx, sy = snap_angle(100.0, 100.0, 200.0, 205.0)
        dx = sx - 100.0
        dy = sy - 100.0
        self.assertAlmostEqual(dx, dy, places=4)


class TestLineTool(unittest.TestCase):
    def setUp(self):
        self.canvas = Canvas()
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 400, 300)
        self.canvas.set_image_surface(surf, width=400, height=300)
        self.tool = LineTool(self.canvas)
        self.canvas.tool_manager.register_tool(self.tool)
        self.canvas.tool_manager.set_active_tool("line")

    def test_tool_metadata(self):
        self.assertEqual(self.tool.tool_id, "line")
        self.assertEqual(self.tool.name, "Line")
        self.assertEqual(self.tool.shortcut, "L")
        self.assertEqual(self.tool.cursor_name, "crosshair")

    def test_draw_line_workflow(self):
        doc = self.canvas.document
        self.assertEqual(len(doc.items), 0)

        # Press
        self.assertTrue(self.tool.on_press(25.0, 30.0, 25.0, 30.0, Gdk.ModifierType(0)))
        self.assertTrue(self.tool.is_drawing)
        self.assertEqual(self.tool.start_pos, (25.0, 30.0))

        # Drag
        self.tool.on_drag(120.0, 150.0, 95.0, 120.0, 120.0, 150.0, Gdk.ModifierType(0))
        self.assertEqual(self.tool.current_end, (120.0, 150.0))

        # Release
        self.assertTrue(self.tool.on_release(120.0, 150.0, 120.0, 150.0, Gdk.ModifierType(0)))
        self.assertFalse(self.tool.is_drawing)
        self.assertEqual(len(doc.items), 1)

        item = doc.items[0]
        self.assertIsInstance(item, LineItem)
        self.assertEqual((item.x1, item.y1, item.x2, item.y2), (25.0, 30.0, 120.0, 150.0))

    def test_draw_line_with_shift_snapping(self):
        doc = self.canvas.document

        # Drag slightly off horizontal with Shift held
        self.tool.on_press(50.0, 100.0, 50.0, 100.0, Gdk.ModifierType(0))
        shift_mask = Gdk.ModifierType.SHIFT_MASK
        self.tool.on_drag(200.0, 110.0, 150.0, 10.0, 200.0, 110.0, shift_mask)
        self.tool.on_release(200.0, 110.0, 200.0, 110.0, shift_mask)

        self.assertEqual(len(doc.items), 1)
        item = doc.items[0]
        self.assertIsInstance(item, LineItem)
        self.assertAlmostEqual(item.y1, item.y2, places=4)

    def test_line_size_selection(self):
        doc = self.canvas.document
        doc.clear()

        for expected_size in (2.0, 4.0, 8.0, 16.0):
            self.canvas.tool_manager.set_stroke_width(expected_size)
            self.tool.on_press(10.0, 10.0, 10.0, 10.0, Gdk.ModifierType(0))
            self.tool.on_drag(100.0, 10.0, 90.0, 0.0, 100.0, 10.0, Gdk.ModifierType(0))
            self.tool.on_release(100.0, 10.0, 100.0, 10.0, Gdk.ModifierType(0))

            last_item = doc.items[-1]
            self.assertIsInstance(last_item, LineItem)
            self.assertEqual(last_item.stroke_width, expected_size)

    def test_undo_redo(self):
        doc = self.canvas.document
        self.tool.on_press(10.0, 10.0, 10.0, 10.0, Gdk.ModifierType(0))
        self.tool.on_drag(50.0, 50.0, 40.0, 40.0, 50.0, 50.0, Gdk.ModifierType(0))
        self.tool.on_release(50.0, 50.0, 50.0, 50.0, Gdk.ModifierType(0))

        self.assertEqual(len(doc.items), 1)
        self.canvas.undo()
        self.assertEqual(len(doc.items), 0)
        self.canvas.redo()
        self.assertEqual(len(doc.items), 1)
        self.assertIsInstance(doc.items[0], LineItem)

    def test_cancel_via_escape(self):
        doc = self.canvas.document
        self.tool.on_press(20.0, 20.0, 20.0, 20.0, Gdk.ModifierType(0))
        self.tool.on_drag(60.0, 60.0, 40.0, 40.0, 60.0, 60.0, Gdk.ModifierType(0))

        self.assertTrue(self.tool.on_key_pressed(Gdk.KEY_Escape, Gdk.ModifierType(0)))
        self.assertFalse(self.tool.is_drawing)
        self.assertEqual(len(doc.items), 0)

    def test_select_and_drag_handles(self):
        # Draw a line
        self.tool.on_press(100.0, 100.0, 100.0, 100.0, Gdk.ModifierType(0))
        self.tool.on_drag(200.0, 100.0, 100.0, 0.0, 200.0, 100.0, Gdk.ModifierType(0))
        self.tool.on_release(200.0, 100.0, 200.0, 100.0, Gdk.ModifierType(0))

        # Switch to Select tool
        self.canvas.tool_manager.set_active_tool("select")
        select_tool = self.canvas.tool_manager.get_tool("select")

        # Click on line to select it
        select_tool.on_press(150.0, 100.0, 150.0, 100.0, Gdk.ModifierType(0))
        select_tool.on_release(150.0, 100.0, 150.0, 100.0, Gdk.ModifierType(0))
        self.assertEqual(len(self.canvas.document.selected_items), 1)
        line = self.canvas.document.selected_items[0]
        self.assertIsInstance(line, LineItem)

        # Grab HANDLE_END at (200, 100) and drag to (220, 150)
        select_tool.on_press(200.0, 100.0, 200.0, 100.0, Gdk.ModifierType(0))
        select_tool.on_drag(220.0, 150.0, 20.0, 50.0, 220.0, 150.0, Gdk.ModifierType(0))
        select_tool.on_release(220.0, 150.0, 220.0, 150.0, Gdk.ModifierType(0))

        self.assertEqual((line.x1, line.y1), (100.0, 100.0))
        self.assertAlmostEqual(line.x2, 220.0, places=3)
        self.assertAlmostEqual(line.y2, 150.0, places=3)

        # Duplicate via Ctrl+D
        self.assertTrue(select_tool.duplicate_selected())
        self.assertEqual(len(self.canvas.document.items), 2)


if __name__ == "__main__":
    unittest.main()
