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
from gobrush.items.ellipse import (
    EllipseItem,
    draw_ellipse,
    point_in_ellipse,
)
from gobrush.tools.ellipse import EllipseTool
from gobrush.tools.select import SelectTool
from gobrush.ui.canvas import Canvas


class TestEllipseItem(unittest.TestCase):
    def test_creation_and_defaults(self) -> None:
        item = EllipseItem(10.0, 20.0, 100.0, 80.0)
        self.assertEqual(item.x, 10.0)
        self.assertEqual(item.y, 20.0)
        self.assertEqual(item.w, 100.0)
        self.assertEqual(item.h, 80.0)
        self.assertEqual(item.type_name, "ellipse")
        self.assertEqual(item.stroke_width, 4.0)
        self.assertEqual(item.stroke_color, (0.88, 0.11, 0.14, 1.0))
        self.assertIsNone(item.fill_color)
        self.assertTrue(item.is_visible)
        self.assertFalse(item.is_selected)

    def test_coordinate_normalization(self) -> None:
        # Negative width and height (dragging backwards)
        item = EllipseItem(150.0, 120.0, -100.0, -80.0)
        self.assertEqual(item.x, 50.0)
        self.assertEqual(item.y, 40.0)
        self.assertEqual(item.w, 100.0)
        self.assertEqual(item.h, 80.0)

    def test_bounds(self) -> None:
        item = EllipseItem(20.0, 30.0, 100.0, 60.0, stroke_width=4.0)
        x, y, w, h = item.get_bounds()
        self.assertEqual(x, 18.0)
        self.assertEqual(y, 28.0)
        self.assertEqual(w, 104.0)
        self.assertEqual(h, 64.0)

    def test_hit_test_outline_only(self) -> None:
        # 100x100 circle centered at (100, 100) -> radius = 50
        item = EllipseItem(50.0, 50.0, 100.0, 100.0, stroke_width=4.0, fill_color=None)

        # On the perimeter points (top, bottom, left, right)
        self.assertTrue(item.hit_test(100.0, 50.0, tolerance=4.0))   # Top
        self.assertTrue(item.hit_test(100.0, 150.0, tolerance=4.0))  # Bottom
        self.assertTrue(item.hit_test(50.0, 100.0, tolerance=4.0))   # Left
        self.assertTrue(item.hit_test(150.0, 100.0, tolerance=4.0))  # Right

        # Far outside -> Miss
        self.assertFalse(item.hit_test(10.0, 10.0, tolerance=4.0))
        self.assertFalse(item.hit_test(200.0, 200.0, tolerance=4.0))

        # Corner of the bounding box at (55, 55): distance to center is hypot(45, 45) ≈ 63.6 > 50 + pad
        self.assertFalse(item.hit_test(55.0, 55.0, tolerance=2.0))

        # Inside hollow interior (center at 100, 100) -> Miss for outline only!
        self.assertFalse(item.hit_test(100.0, 100.0, tolerance=4.0))

    def test_hit_test_filled(self) -> None:
        # 100x100 filled circle centered at (100, 100)
        item = EllipseItem(
            50.0,
            50.0,
            100.0,
            100.0,
            stroke_width=4.0,
            fill_color=(0.2, 0.5, 0.8, 0.3),
        )

        # On the perimeter -> Hit
        self.assertTrue(item.hit_test(100.0, 50.0, tolerance=4.0))
        # Inside the interior / center -> Hit for filled item!
        self.assertTrue(item.hit_test(100.0, 100.0, tolerance=4.0))
        # Corner of bounding box outside circle -> Miss
        self.assertFalse(item.hit_test(52.0, 52.0, tolerance=2.0))
        # Far outside -> Miss
        self.assertFalse(item.hit_test(10.0, 10.0, tolerance=4.0))

    def test_handles(self) -> None:
        item = EllipseItem(10.0, 20.0, 100.0, 80.0, stroke_width=4.0)
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
        item = EllipseItem(10.0, 20.0, 30.0, 40.0)
        self.assertEqual(item.get_geometry(), (10.0, 20.0, 30.0, 40.0))

        # set_geometry tuple
        self.assertTrue(item.set_geometry((50.0, 60.0, 70.0, 80.0)))
        self.assertEqual(item.get_geometry(), (50.0, 60.0, 70.0, 80.0))

        # set_geometry dict
        self.assertTrue(item.set_geometry({"x": 5.0, "y": 6.0, "w": 7.0, "h": 8.0}))
        self.assertEqual(item.get_geometry(), (5.0, 6.0, 7.0, 8.0))

        # move_by
        item.move_by(10.0, -5.0)
        self.assertEqual(item.get_geometry(), (15.0, 1.0, 7.0, 8.0))

    def test_clone_and_serialization(self) -> None:
        item = EllipseItem(
            15.0,
            25.0,
            120.0,
            90.0,
            stroke_color=(0.1, 0.5, 0.9, 1.0),
            stroke_width=6.0,
            fill_color=(0.9, 0.3, 0.1, 0.5),
        )
        cloned = item.clone()
        self.assertIsInstance(cloned, EllipseItem)
        self.assertIsNot(cloned, item)
        self.assertEqual(cloned.get_geometry(), item.get_geometry())
        self.assertEqual(cloned.stroke_color, item.stroke_color)
        self.assertEqual(cloned.stroke_width, item.stroke_width)
        self.assertEqual(cloned.fill_color, item.fill_color)

        data = item.to_dict()
        self.assertEqual(data["type"], "ellipse")
        self.assertEqual(data["x"], 15.0)
        self.assertEqual(data["w"], 120.0)

        restored = EllipseItem.from_dict(data)
        self.assertIsInstance(restored, EllipseItem)
        self.assertEqual(restored.get_geometry(), item.get_geometry())
        self.assertEqual(restored.stroke_color, item.stroke_color)
        self.assertEqual(restored.stroke_width, item.stroke_width)
        self.assertEqual(restored.fill_color, item.fill_color)

    def test_cairo_draw_and_selection(self) -> None:
        # Outline
        item_outline = EllipseItem(20.0, 40.0, 100.0, 80.0)
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 200, 200)
        cr = cairo.Context(surface)
        item_outline.draw(cr)

        # Filled
        item_filled = EllipseItem(
            20.0,
            40.0,
            100.0,
            80.0,
            stroke_width=5.0,
            fill_color=(0.2, 0.6, 0.9, 0.5),
        )
        item_filled.draw(cr)

        # Selection rendering
        item_filled.is_selected = True
        item_filled.draw_selection(cr, scale=1.0)


class TestEllipseTool(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        Gtk.init()

    def setUp(self) -> None:
        self.canvas = Canvas()
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 400, 300)
        self.canvas.set_image_surface(surf, width=400, height=300)
        self.tool = EllipseTool(self.canvas)
        self.canvas.tool_manager.register_tool(self.tool)
        self.canvas.tool_manager.set_active_tool("ellipse")

    def test_tool_metadata(self) -> None:
        self.assertEqual(self.tool.tool_id, "ellipse")
        self.assertEqual(self.tool.name, "Ellipse")
        self.assertEqual(self.tool.shortcut, "C")
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
        self.assertIsInstance(item, EllipseItem)
        self.assertEqual(item.get_geometry(), (50.0, 40.0, 100.0, 80.0))
        self.assertEqual(item.stroke_width, 8.0)
        self.assertEqual(item.stroke_color, (0.2, 0.4, 0.8, 1.0))
        self.assertIsNone(item.fill_color)

    def test_drawing_with_fill(self) -> None:
        mgr = self.canvas.tool_manager
        mgr.set_current_color((0.9, 0.3, 0.2, 1.0))
        mgr.set_stroke_width(4.0)
        mgr.set_fill_mode("semi")
        mgr.set_fill_opacity(0.40)

        self.tool.on_press(30.0, 30.0, 30.0, 30.0, Gdk.ModifierType(0))
        self.tool.on_drag(180.0, 130.0, 150.0, 100.0, 180.0, 130.0, Gdk.ModifierType(0))
        self.tool.on_release(180.0, 130.0, 180.0, 130.0, Gdk.ModifierType(0))

        item = self.canvas.document.items[-1]
        self.assertIsInstance(item, EllipseItem)
        self.assertEqual(item.get_geometry(), (30.0, 30.0, 150.0, 100.0))
        self.assertEqual(item.stroke_color, (0.9, 0.3, 0.2, 1.0))
        self.assertEqual(item.fill_color, (0.9, 0.3, 0.2, 0.40))

    def test_shift_circular_constraint(self) -> None:
        # Dragging non-square (dx=100, dy=40) with Shift held constrains to 100x100 circle
        self.tool.on_press(50.0, 50.0, 50.0, 50.0, Gdk.ModifierType(0))
        self.tool.on_drag(
            150.0, 90.0, 100.0, 40.0, 150.0, 90.0, Gdk.ModifierType.SHIFT_MASK
        )
        self.assertEqual(self.tool.current_end, (150.0, 150.0))

        self.tool.on_release(150.0, 90.0, 150.0, 90.0, Gdk.ModifierType.SHIFT_MASK)
        item = self.canvas.document.items[-1]
        self.assertIsInstance(item, EllipseItem)
        self.assertEqual(item.w, item.h)
        self.assertEqual((item.w, item.h), (100.0, 100.0))

    def test_drag_backwards_normalization(self) -> None:
        # Dragging from bottom-right (200, 200) up-left to (100, 120)
        self.tool.on_press(200.0, 200.0, 200.0, 200.0, Gdk.ModifierType(0))
        self.tool.on_drag(100.0, 120.0, -100.0, -80.0, 100.0, 120.0, Gdk.ModifierType(0))
        self.tool.on_release(100.0, 120.0, 100.0, 120.0, Gdk.ModifierType(0))

        item = self.canvas.document.items[-1]
        self.assertIsInstance(item, EllipseItem)
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

        # Undo removes ellipse
        self.canvas.undo()
        self.assertEqual(len(doc.items), 0)

        # Redo restores ellipse
        self.canvas.redo()
        self.assertEqual(len(doc.items), 1)
        self.assertIsInstance(doc.items[0], EllipseItem)

    def test_live_overlay_drawing(self) -> None:
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 200, 200)
        cr = cairo.Context(surface)

        # Before press: does nothing
        self.tool.draw_overlay(cr)

        # During drag: renders preview
        self.tool.on_press(20.0, 20.0, 20.0, 20.0, Gdk.ModifierType(0))
        self.tool.on_drag(80.0, 80.0, 60.0, 60.0, 80.0, 80.0, Gdk.ModifierType(0))
        self.tool.draw_overlay(cr)

    def test_select_tool_resize_handles_on_ellipse(self) -> None:
        ellipse = EllipseItem(50.0, 50.0, 100.0, 80.0, stroke_width=4.0)
        self.canvas.document.add_item(ellipse)

        select_tool = SelectTool(self.canvas)
        self.canvas.tool_manager.register_tool(select_tool)
        self.canvas.tool_manager.set_active_tool("select")

        ellipse.is_selected = True

        # Drag HANDLE_BOTTOM_RIGHT from (150, 130) to (180, 150) -> w=130, h=100
        select_tool._apply_handle_resize(
            ellipse,
            HANDLE_BOTTOM_RIGHT,
            initial_geom=ellipse.get_geometry(),
            dx=30.0,
            dy=20.0,
            lock_aspect=False,
        )
        self.assertEqual(ellipse.get_geometry(), (50.0, 50.0, 130.0, 100.0))

        # Drag HANDLE_TOP_LEFT by dx=10, dy=15 -> x=60, y=65, w=120, h=85
        select_tool._apply_handle_resize(
            ellipse,
            HANDLE_TOP_LEFT,
            initial_geom=ellipse.get_geometry(),
            dx=10.0,
            dy=15.0,
            lock_aspect=False,
        )
        self.assertEqual(ellipse.get_geometry(), (60.0, 65.0, 120.0, 85.0))


if __name__ == "__main__":
    unittest.main()
