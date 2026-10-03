from __future__ import annotations
import math
import unittest
import cairo
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gtk, Gdk

from gobrush.items.base import HANDLE_START, HANDLE_END
from gobrush.items.arrow import ArrowItem, compute_arrowhead, point_in_triangle
from gobrush.items.line import snap_angle
from gobrush.tools.arrow import ArrowTool
from gobrush.tools.select import SelectTool
from gobrush.ui.canvas import Canvas


class TestArrowItem(unittest.TestCase):
    def test_creation_and_defaults(self) -> None:
        item = ArrowItem(10.0, 20.0, 100.0, 200.0)
        self.assertEqual(item.x1, 10.0)
        self.assertEqual(item.y1, 20.0)
        self.assertEqual(item.x2, 100.0)
        self.assertEqual(item.y2, 200.0)
        self.assertEqual(item.type_name, "arrow")
        self.assertEqual(item.stroke_width, 4.0)
        self.assertEqual(item.stroke_color, (0.88, 0.11, 0.14, 1.0))
        self.assertTrue(item.is_visible)
        self.assertFalse(item.is_selected)

    def test_arrowhead_geometry_horizontal(self) -> None:
        # Arrow pointing directly to the right (+X)
        tip, wing1, wing2, base = compute_arrowhead(0.0, 50.0, 100.0, 50.0, 4.0)
        self.assertEqual(tip, (100.0, 50.0))
        # Base should be behind the tip on X
        self.assertLess(base[0], tip[0])
        self.assertAlmostEqual(base[1], 50.0, places=3)
        # Wings should be symmetric across the shaft line (Y=50)
        self.assertLess(wing1[0], tip[0])
        self.assertLess(wing2[0], tip[0])
        self.assertAlmostEqual(abs(wing1[1] - 50.0), abs(wing2[1] - 50.0), places=3)

    def test_arrowhead_geometry_vertical(self) -> None:
        # Arrow pointing down (+Y)
        tip, wing1, wing2, base = compute_arrowhead(50.0, 0.0, 50.0, 100.0, 4.0)
        self.assertEqual(tip, (50.0, 100.0))
        self.assertLess(base[1], tip[1])
        self.assertAlmostEqual(base[0], 50.0, places=3)
        self.assertAlmostEqual(abs(wing1[0] - 50.0), abs(wing2[0] - 50.0), places=3)

    def test_short_arrow_geometry_clamping(self) -> None:
        # Very short arrow (5px total length)
        tip, wing1, wing2, base = compute_arrowhead(0.0, 0.0, 5.0, 0.0, 10.0)
        dist = math.hypot(tip[0] - base[0], tip[1] - base[1])
        # Head length should not exceed total distance
        self.assertLess(dist, 5.0)

    def test_bounds(self) -> None:
        item = ArrowItem(20.0, 30.0, 120.0, 30.0, stroke_width=4.0)
        x, y, w, h = item.get_bounds()
        self.assertLessEqual(x, 20.0)
        self.assertGreaterEqual(x + w, 120.0)
        # Bounds must also encompass arrowhead wings vertically
        tip, wing1, wing2, _ = item._compute_arrowhead()
        self.assertLessEqual(y, min(wing1[1], wing2[1]))
        self.assertGreaterEqual(y + h, max(wing1[1], wing2[1]))

    def test_hit_test(self) -> None:
        # Horizontal arrow from (10, 50) to (110, 50)
        item = ArrowItem(10.0, 50.0, 110.0, 50.0, stroke_width=4.0)

        # Hit on shaft center
        self.assertTrue(item.hit_test(50.0, 50.0, tolerance=4.0))
        self.assertTrue(item.hit_test(50.0, 52.0, tolerance=4.0))
        self.assertFalse(item.hit_test(50.0, 70.0, tolerance=4.0))

        # Hit on arrowhead tip
        self.assertTrue(item.hit_test(110.0, 50.0, tolerance=4.0))

        # Hit inside arrowhead triangle
        tip, wing1, wing2, base = item._compute_arrowhead()
        center_head_x = (tip[0] + wing1[0] + wing2[0]) / 3.0
        center_head_y = (tip[1] + wing1[1] + wing2[1]) / 3.0
        self.assertTrue(item.hit_test(center_head_x, center_head_y, tolerance=4.0))

        # Far away
        self.assertFalse(item.hit_test(200.0, 200.0, tolerance=4.0))

    def test_geometry_and_handles(self) -> None:
        item = ArrowItem(10.0, 20.0, 30.0, 40.0)
        self.assertEqual(item.get_geometry(), (10.0, 20.0, 30.0, 40.0))

        handles = item.get_handles()
        self.assertEqual(len(handles), 2)
        self.assertEqual(handles[HANDLE_START], (10.0, 20.0))
        self.assertEqual(handles[HANDLE_END], (30.0, 40.0))

        # set_geometry tuple
        self.assertTrue(item.set_geometry((50.0, 60.0, 70.0, 80.0)))
        self.assertEqual(item.get_geometry(), (50.0, 60.0, 70.0, 80.0))

        # set_geometry dict
        self.assertTrue(item.set_geometry({"x1": 5.0, "y1": 6.0, "x2": 7.0, "y2": 8.0}))
        self.assertEqual(item.get_geometry(), (5.0, 6.0, 7.0, 8.0))

        # move_by
        item.move_by(10.0, -5.0)
        self.assertEqual(item.get_geometry(), (15.0, 1.0, 17.0, 3.0))

    def test_clone_and_serialization(self) -> None:
        item = ArrowItem(
            15.0, 25.0, 75.0, 85.0, stroke_color=(0.1, 0.5, 0.9, 1.0), stroke_width=6.0
        )
        cloned = item.clone()
        self.assertIsInstance(cloned, ArrowItem)
        self.assertIsNot(cloned, item)
        self.assertEqual(cloned.get_geometry(), item.get_geometry())
        self.assertEqual(cloned.stroke_color, item.stroke_color)
        self.assertEqual(cloned.stroke_width, item.stroke_width)

        data = item.to_dict()
        self.assertEqual(data["type"], "arrow")
        self.assertEqual(data["x1"], 15.0)
        self.assertEqual(data["x2"], 75.0)

        restored = ArrowItem.from_dict(data)
        self.assertIsInstance(restored, ArrowItem)
        self.assertEqual(restored.get_geometry(), item.get_geometry())
        self.assertEqual(restored.stroke_color, item.stroke_color)
        self.assertEqual(restored.stroke_width, item.stroke_width)

    def test_cairo_draw_and_selection(self) -> None:
        item = ArrowItem(20.0, 40.0, 150.0, 120.0, stroke_width=5.0)
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 200, 200)
        cr = cairo.Context(surface)

        # Drawing without exception
        item.draw(cr)

        # Selection rendering
        item.is_selected = True
        item.draw_selection(cr, scale=1.0)


class TestArrowTool(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        Gtk.init()

    def setUp(self) -> None:
        self.canvas = Canvas()
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 400, 300)
        self.canvas.set_image_surface(surf, width=400, height=300)
        self.tool = ArrowTool(self.canvas)
        self.canvas.tool_manager.register_tool(self.tool)
        self.canvas.tool_manager.set_active_tool("arrow")

    def test_tool_metadata(self) -> None:
        self.assertEqual(self.tool.tool_id, "arrow")
        self.assertEqual(self.tool.name, "Arrow")
        self.assertEqual(self.tool.shortcut, "A")
        self.assertEqual(self.tool.cursor_name, "crosshair")

    def test_drawing_lifecycle(self) -> None:
        self.canvas.tool_manager.set_current_color((0.2, 0.4, 0.8, 1.0))
        self.canvas.tool_manager.set_stroke_width(8.0)

        # Press
        self.assertTrue(self.tool.on_press(50.0, 50.0, 50.0, 50.0, Gdk.ModifierType(0)))
        self.assertEqual(self.tool.start_pos, (50.0, 50.0))
        self.assertEqual(self.tool.current_end, (50.0, 50.0))
        self.assertEqual(self.tool._stroke_width, 8.0)
        self.assertEqual(self.tool._stroke_color, (0.2, 0.4, 0.8, 1.0))

        # Drag
        self.assertTrue(self.tool.on_drag(120.0, 90.0, 70.0, 40.0, 120.0, 90.0, Gdk.ModifierType(0)))
        self.assertEqual(self.tool.current_end, (120.0, 90.0))

        # Release
        doc = self.canvas.document
        initial_count = len(doc.items)
        self.assertTrue(self.tool.on_release(120.0, 90.0, 120.0, 90.0, Gdk.ModifierType(0)))

        self.assertEqual(len(doc.items), initial_count + 1)
        item = doc.items[-1]
        self.assertIsInstance(item, ArrowItem)
        self.assertEqual(item.get_geometry(), (50.0, 50.0, 120.0, 90.0))
        self.assertEqual(item.stroke_width, 8.0)
        self.assertEqual(item.stroke_color, (0.2, 0.4, 0.8, 1.0))

    def test_shift_angle_snapping(self) -> None:
        # Dragging roughly horizontal-diagonal with Shift snaps to 45 degrees
        self.tool.on_press(100.0, 100.0, 100.0, 100.0, Gdk.ModifierType(0))
        # Drag to (180, 110) with Shift -> angle is ~7 degrees -> snaps to 0 degrees (horizontal)
        self.tool.on_drag(
            180.0, 110.0, 80.0, 10.0, 180.0, 110.0, Gdk.ModifierType.SHIFT_MASK
        )
        self.assertAlmostEqual(self.tool.current_end[1], 100.0, places=3)

        # Release with Shift
        self.tool.on_release(180.0, 110.0, 180.0, 110.0, Gdk.ModifierType.SHIFT_MASK)
        item = self.canvas.document.items[-1]
        self.assertIsInstance(item, ArrowItem)
        self.assertAlmostEqual(item.y1, 100.0, places=3)
        self.assertAlmostEqual(item.y2, 100.0, places=3)

    def test_minimum_drag_threshold(self) -> None:
        # Clicks with less than 4px distance should not create zero-length items
        doc = self.canvas.document
        count_before = len(doc.items)

        self.tool.on_press(50.0, 50.0, 50.0, 50.0, Gdk.ModifierType(0))
        self.tool.on_release(52.0, 51.0, 52.0, 51.0, Gdk.ModifierType(0))

        self.assertEqual(len(doc.items), count_before)

    def test_escape_cancellation(self) -> None:
        doc = self.canvas.document
        count_before = len(doc.items)

        self.tool.on_press(50.0, 50.0, 50.0, 50.0, Gdk.ModifierType(0))
        self.tool.on_drag(150.0, 150.0, 100.0, 100.0, 150.0, 150.0, Gdk.ModifierType(0))

        # Press Escape
        self.assertTrue(self.tool.on_key_pressed(Gdk.KEY_Escape, Gdk.ModifierType(0)))
        self.assertIsNone(self.tool.start_pos)
        self.assertIsNone(self.tool.current_end)

        # Release after cancel does not add item
        self.assertFalse(self.tool.on_release(150.0, 150.0, 150.0, 150.0, Gdk.ModifierType(0)))
        self.assertEqual(len(doc.items), count_before)

    def test_undo_redo_integration(self) -> None:
        doc = self.canvas.document
        self.tool.on_press(40.0, 40.0, 40.0, 40.0, Gdk.ModifierType(0))
        self.tool.on_release(140.0, 140.0, 140.0, 140.0, Gdk.ModifierType(0))
        self.assertEqual(len(doc.items), 1)

        # Undo removes arrow
        self.canvas.undo()
        self.assertEqual(len(doc.items), 0)

        # Redo restores arrow
        self.canvas.redo()
        self.assertEqual(len(doc.items), 1)
        self.assertIsInstance(doc.items[0], ArrowItem)

    def test_live_overlay_drawing(self) -> None:
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 200, 200)
        cr = cairo.Context(surface)

        # Before press: does nothing
        self.tool.draw_overlay(cr)

        # During drag: renders preview
        self.tool.on_press(20.0, 20.0, 20.0, 20.0, Gdk.ModifierType(0))
        self.tool.on_drag(80.0, 80.0, 60.0, 60.0, 80.0, 80.0, Gdk.ModifierType(0))
        self.tool.draw_overlay(cr)

    def test_select_tool_handle_dragging_on_arrow(self) -> None:
        arrow = ArrowItem(50.0, 50.0, 150.0, 50.0, stroke_width=4.0)
        self.canvas.document.add_item(arrow)

        select_tool = SelectTool(self.canvas)
        self.canvas.tool_manager.register_tool(select_tool)
        self.canvas.tool_manager.set_active_tool("select")

        # Select arrow
        arrow.is_selected = True

        # Drag HANDLE_START (tail) from (50, 50) to (30, 70)
        select_tool._apply_handle_resize(
            arrow,
            HANDLE_START,
            initial_geom=arrow.get_geometry(),
            dx=-20.0,
            dy=20.0,
            lock_aspect=False,
        )
        self.assertEqual(arrow.get_geometry(), (30.0, 70.0, 150.0, 50.0))

        # Drag HANDLE_END (tip) from (150, 50) to (180, 80)
        select_tool._apply_handle_resize(
            arrow,
            HANDLE_END,
            initial_geom=arrow.get_geometry(),
            dx=30.0,
            dy=30.0,
            lock_aspect=False,
        )
        self.assertEqual(arrow.get_geometry(), (30.0, 70.0, 180.0, 80.0))


if __name__ == "__main__":
    unittest.main()
