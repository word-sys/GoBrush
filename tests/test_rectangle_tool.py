from __future__ import annotations
import math
import unittest
import cairo
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gtk, Gdk

from gobrush.items.base import (
    HANDLE_TOP_LEFT,
    HANDLE_TOP_CENTER,
    HANDLE_TOP_RIGHT,
    HANDLE_MIDDLE_RIGHT,
    HANDLE_BOTTOM_RIGHT,
    HANDLE_BOTTOM_CENTER,
    HANDLE_BOTTOM_LEFT,
    HANDLE_MIDDLE_LEFT,
)
from gobrush.items.rectangle import (
    RectangleItem,
    draw_rounded_rectangle,
    point_in_rounded_rectangle,
)
from gobrush.tools.rectangle import RectangleTool
from gobrush.tools.select import SelectTool
from gobrush.ui.canvas import Canvas


class TestRectangleItem(unittest.TestCase):
    def test_creation_and_defaults(self) -> None:
        item = RectangleItem(10.0, 20.0, 100.0, 80.0)
        self.assertEqual(item.x, 10.0)
        self.assertEqual(item.y, 20.0)
        self.assertEqual(item.w, 100.0)
        self.assertEqual(item.h, 80.0)
        self.assertEqual(item.radius, 0.0)
        self.assertEqual(item.type_name, "rectangle")
        self.assertEqual(item.stroke_width, 4.0)
        self.assertEqual(item.stroke_color, (0.88, 0.11, 0.14, 1.0))
        self.assertIsNone(item.fill_color)
        self.assertTrue(item.is_visible)
        self.assertFalse(item.is_selected)

    def test_coordinate_normalization(self) -> None:
        # Dragging backwards (negative width and height)
        item = RectangleItem(150.0, 120.0, -100.0, -80.0)
        self.assertEqual(item.x, 50.0)
        self.assertEqual(item.y, 40.0)
        self.assertEqual(item.w, 100.0)
        self.assertEqual(item.h, 80.0)

    def test_bounds(self) -> None:
        item = RectangleItem(20.0, 30.0, 100.0, 60.0, stroke_width=4.0)
        x, y, w, h = item.get_bounds()
        self.assertEqual(x, 18.0)
        self.assertEqual(y, 28.0)
        self.assertEqual(w, 104.0)
        self.assertEqual(h, 64.0)

    def test_hit_test_outline_only(self) -> None:
        # 100x100 rectangle with 4px stroke and NO fill (outline mode)
        item = RectangleItem(50.0, 50.0, 100.0, 100.0, stroke_width=4.0, fill_color=None)

        # On the top edge border -> Hit
        self.assertTrue(item.hit_test(100.0, 50.0, tolerance=4.0))
        # On the left edge border -> Hit
        self.assertTrue(item.hit_test(50.0, 100.0, tolerance=4.0))
        # On the bottom edge border -> Hit
        self.assertTrue(item.hit_test(100.0, 150.0, tolerance=4.0))
        # On the right edge border -> Hit
        self.assertTrue(item.hit_test(150.0, 100.0, tolerance=4.0))

        # Far outside -> Miss
        self.assertFalse(item.hit_test(10.0, 10.0, tolerance=4.0))
        self.assertFalse(item.hit_test(200.0, 200.0, tolerance=4.0))

        # Inside hollow interior -> Miss for outline only!
        self.assertFalse(item.hit_test(100.0, 100.0, tolerance=4.0))

    def test_hit_test_filled(self) -> None:
        # 100x100 rectangle with semi-fill
        item = RectangleItem(
            50.0,
            50.0,
            100.0,
            100.0,
            stroke_width=4.0,
            fill_color=(0.2, 0.5, 0.8, 0.3),
        )

        # On the border -> Hit
        self.assertTrue(item.hit_test(50.0, 50.0, tolerance=4.0))
        # Inside the interior -> Hit for filled item!
        self.assertTrue(item.hit_test(100.0, 100.0, tolerance=4.0))
        # Far outside -> Miss
        self.assertFalse(item.hit_test(10.0, 10.0, tolerance=4.0))

    def test_hit_test_rounded_corners(self) -> None:
        # 100x100 rectangle with radius 20
        item = RectangleItem(
            50.0,
            50.0,
            100.0,
            100.0,
            stroke_width=4.0,
            fill_color=(0.1, 0.8, 0.2, 1.0),
            radius=20.0,
        )

        # Center inside -> Hit
        self.assertTrue(item.hit_test(100.0, 100.0, tolerance=4.0))

        # The sharp corner at (51, 51) is clipped away by the 20px radius!
        # Distance from (51, 51) to corner center (70, 70) is hypot(19, 19) = 26.87 > 20 + pad
        self.assertFalse(item.hit_test(51.0, 51.0, tolerance=2.0))

    def test_handles(self) -> None:
        item = RectangleItem(10.0, 20.0, 100.0, 80.0, stroke_width=4.0)
        handles = item.get_handles()
        self.assertEqual(len(handles), 8)
        bx, by, bw, bh = item.get_bounds()
        self.assertEqual(handles[HANDLE_TOP_LEFT], (bx, by))
        self.assertEqual(handles[HANDLE_TOP_CENTER], (bx + bw / 2.0, by))
        self.assertEqual(handles[HANDLE_TOP_RIGHT], (bx + bw, by))
        self.assertEqual(handles[HANDLE_MIDDLE_RIGHT], (bx + bw, by + bh / 2.0))
        self.assertEqual(handles[HANDLE_BOTTOM_RIGHT], (bx + bw, by + bh))
        self.assertEqual(handles[HANDLE_BOTTOM_CENTER], (bx + bw / 2.0, by + bh))
        self.assertEqual(handles[HANDLE_BOTTOM_LEFT], (bx, by + bh))
        self.assertEqual(handles[HANDLE_MIDDLE_LEFT], (bx, by + bh / 2.0))

    def test_geometry_and_manipulation(self) -> None:
        item = RectangleItem(10.0, 20.0, 30.0, 40.0, radius=5.0)
        self.assertEqual(item.get_geometry(), (10.0, 20.0, 30.0, 40.0))

        # set_geometry tuple
        self.assertTrue(item.set_geometry((50.0, 60.0, 70.0, 80.0)))
        self.assertEqual(item.get_geometry(), (50.0, 60.0, 70.0, 80.0))

        # set_geometry dict with radius
        self.assertTrue(item.set_geometry({"x": 5.0, "y": 6.0, "w": 7.0, "h": 8.0, "radius": 12.0}))
        self.assertEqual(item.get_geometry(), (5.0, 6.0, 7.0, 8.0))
        self.assertEqual(item.radius, 12.0)

        # move_by
        item.move_by(10.0, -5.0)
        self.assertEqual(item.get_geometry(), (15.0, 1.0, 7.0, 8.0))

    def test_clone_and_serialization(self) -> None:
        item = RectangleItem(
            15.0,
            25.0,
            120.0,
            90.0,
            stroke_color=(0.1, 0.5, 0.9, 1.0),
            stroke_width=6.0,
            fill_color=(0.9, 0.3, 0.1, 0.5),
            radius=16.0,
        )
        cloned = item.clone()
        self.assertIsInstance(cloned, RectangleItem)
        self.assertIsNot(cloned, item)
        self.assertEqual(cloned.get_geometry(), item.get_geometry())
        self.assertEqual(cloned.radius, item.radius)
        self.assertEqual(cloned.stroke_color, item.stroke_color)
        self.assertEqual(cloned.stroke_width, item.stroke_width)
        self.assertEqual(cloned.fill_color, item.fill_color)

        data = item.to_dict()
        self.assertEqual(data["type"], "rectangle")
        self.assertEqual(data["x"], 15.0)
        self.assertEqual(data["w"], 120.0)
        self.assertEqual(data["radius"], 16.0)

        restored = RectangleItem.from_dict(data)
        self.assertIsInstance(restored, RectangleItem)
        self.assertEqual(restored.get_geometry(), item.get_geometry())
        self.assertEqual(restored.radius, item.radius)
        self.assertEqual(restored.stroke_color, item.stroke_color)
        self.assertEqual(restored.stroke_width, item.stroke_width)
        self.assertEqual(restored.fill_color, item.fill_color)

    def test_cairo_draw_and_selection(self) -> None:
        # Sharp
        item_sharp = RectangleItem(20.0, 40.0, 100.0, 80.0, radius=0.0)
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 200, 200)
        cr = cairo.Context(surface)
        item_sharp.draw(cr)

        # Rounded
        item_rounded = RectangleItem(
            20.0,
            40.0,
            100.0,
            80.0,
            stroke_width=5.0,
            fill_color=(0.2, 0.6, 0.9, 0.5),
            radius=15.0,
        )
        item_rounded.draw(cr)

        # Selection rendering
        item_rounded.is_selected = True
        item_rounded.draw_selection(cr, scale=1.0)


class TestRectangleTool(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        Gtk.init()

    def setUp(self) -> None:
        self.canvas = Canvas()
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 400, 300)
        self.canvas.set_image_surface(surf, width=400, height=300)
        self.tool = RectangleTool(self.canvas)
        self.canvas.tool_manager.register_tool(self.tool)
        self.canvas.tool_manager.set_active_tool("rectangle")

    def test_tool_metadata(self) -> None:
        self.assertEqual(self.tool.tool_id, "rectangle")
        self.assertEqual(self.tool.name, "Rectangle")
        self.assertEqual(self.tool.shortcut, "R")
        self.assertEqual(self.tool.cursor_name, "crosshair")

    def test_drawing_lifecycle_outline(self) -> None:
        self.canvas.tool_manager.set_current_color((0.2, 0.4, 0.8, 1.0))
        self.canvas.tool_manager.set_stroke_width(8.0)
        self.canvas.tool_manager.set_fill_mode("outline")

        # Press
        self.assertTrue(self.tool.on_press(50.0, 40.0, 50.0, 40.0, Gdk.ModifierType(0)))
        self.assertEqual(self.tool.start_pos, (50.0, 40.0))
        self.assertEqual(self.tool.current_end, (50.0, 40.0))

        # Drag
        self.assertTrue(self.tool.on_drag(150.0, 120.0, 100.0, 80.0, 150.0, 120.0, Gdk.ModifierType(0)))
        self.assertEqual(self.tool.current_end, (150.0, 120.0))

        # Release
        doc = self.canvas.document
        initial_count = len(doc.items)
        self.assertTrue(self.tool.on_release(150.0, 120.0, 150.0, 120.0, Gdk.ModifierType(0)))

        self.assertEqual(len(doc.items), initial_count + 1)
        item = doc.items[-1]
        self.assertIsInstance(item, RectangleItem)
        self.assertEqual(item.get_geometry(), (50.0, 40.0, 100.0, 80.0))
        self.assertEqual(item.stroke_width, 8.0)
        self.assertEqual(item.stroke_color, (0.2, 0.4, 0.8, 1.0))
        self.assertIsNone(item.fill_color)

    def test_drawing_with_fill_and_corner_radius(self) -> None:
        mgr = self.canvas.tool_manager
        mgr.set_current_color((0.9, 0.3, 0.2, 1.0))
        mgr.set_stroke_width(4.0)
        mgr.set_fill_mode("semi")
        mgr.set_fill_opacity(0.40)
        mgr.set_corner_radius(12.0)

        self.tool.on_press(30.0, 30.0, 30.0, 30.0, Gdk.ModifierType(0))
        self.tool.on_drag(180.0, 130.0, 150.0, 100.0, 180.0, 130.0, Gdk.ModifierType(0))
        self.tool.on_release(180.0, 130.0, 180.0, 130.0, Gdk.ModifierType(0))

        item = self.canvas.document.items[-1]
        self.assertIsInstance(item, RectangleItem)
        self.assertEqual(item.get_geometry(), (30.0, 30.0, 150.0, 100.0))
        self.assertEqual(item.radius, 12.0)
        self.assertEqual(item.stroke_color, (0.9, 0.3, 0.2, 1.0))
        self.assertEqual(item.fill_color, (0.9, 0.3, 0.2, 0.40))

    def test_shift_square_constraint(self) -> None:
        # Dragging non-square (dx=100, dy=40) with Shift held constrains to 100x100 square
        self.tool.on_press(50.0, 50.0, 50.0, 50.0, Gdk.ModifierType(0))
        self.tool.on_drag(
            150.0, 90.0, 100.0, 40.0, 150.0, 90.0, Gdk.ModifierType.SHIFT_MASK
        )
        self.assertEqual(self.tool.current_end, (150.0, 150.0))

        self.tool.on_release(150.0, 90.0, 150.0, 90.0, Gdk.ModifierType.SHIFT_MASK)
        item = self.canvas.document.items[-1]
        self.assertIsInstance(item, RectangleItem)
        self.assertEqual(item.w, item.h)
        self.assertEqual((item.w, item.h), (100.0, 100.0))

    def test_drag_backwards_normalization(self) -> None:
        # Dragging from bottom-right (200, 200) up-left to (100, 120)
        self.tool.on_press(200.0, 200.0, 200.0, 200.0, Gdk.ModifierType(0))
        self.tool.on_drag(100.0, 120.0, -100.0, -80.0, 100.0, 120.0, Gdk.ModifierType(0))
        self.tool.on_release(100.0, 120.0, 100.0, 120.0, Gdk.ModifierType(0))

        item = self.canvas.document.items[-1]
        self.assertIsInstance(item, RectangleItem)
        self.assertEqual(item.x, 100.0)
        self.assertEqual(item.y, 120.0)
        self.assertEqual(item.w, 100.0)
        self.assertEqual(item.h, 80.0)

    def test_minimum_drag_threshold(self) -> None:
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

        # Undo removes rectangle
        self.canvas.undo()
        self.assertEqual(len(doc.items), 0)

        # Redo restores rectangle
        self.canvas.redo()
        self.assertEqual(len(doc.items), 1)
        self.assertIsInstance(doc.items[0], RectangleItem)

    def test_live_overlay_drawing(self) -> None:
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 200, 200)
        cr = cairo.Context(surface)

        # Before press: does nothing
        self.tool.draw_overlay(cr)

        # During drag: renders preview
        self.tool.on_press(20.0, 20.0, 20.0, 20.0, Gdk.ModifierType(0))
        self.tool.on_drag(80.0, 80.0, 60.0, 60.0, 80.0, 80.0, Gdk.ModifierType(0))
        self.tool.draw_overlay(cr)

    def test_select_tool_resize_handles_on_rectangle(self) -> None:
        rect = RectangleItem(50.0, 50.0, 100.0, 80.0, stroke_width=4.0)
        self.canvas.document.add_item(rect)

        select_tool = SelectTool(self.canvas)
        self.canvas.tool_manager.register_tool(select_tool)
        self.canvas.tool_manager.set_active_tool("select")

        rect.is_selected = True

        # Drag HANDLE_BOTTOM_RIGHT from (150, 130) to (180, 150) -> w=130, h=100
        select_tool._apply_handle_resize(
            rect,
            HANDLE_BOTTOM_RIGHT,
            initial_geom=rect.get_geometry(),
            dx=30.0,
            dy=20.0,
            lock_aspect=False,
        )
        self.assertEqual(rect.get_geometry(), (50.0, 50.0, 130.0, 100.0))

        # Drag HANDLE_TOP_LEFT by dx=10, dy=15 -> x=60, y=65, w=120, h=85
        select_tool._apply_handle_resize(
            rect,
            HANDLE_TOP_LEFT,
            initial_geom=rect.get_geometry(),
            dx=10.0,
            dy=15.0,
            lock_aspect=False,
        )
        self.assertEqual(rect.get_geometry(), (60.0, 65.0, 120.0, 85.0))


if __name__ == "__main__":
    unittest.main()
