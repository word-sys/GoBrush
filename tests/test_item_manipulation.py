from __future__ import annotations
import unittest
import cairo
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk

from gobrush.ui.canvas import Canvas
from gobrush.items.base import AnnotationItem, HANDLE_TOP_LEFT, HANDLE_BOTTOM_RIGHT


class DummyBox(AnnotationItem):
    def __init__(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        stroke_color: tuple[float, float, float, float] = (1.0, 0.0, 0.0, 1.0),
        stroke_width: float = 2.0,
        fill_color: tuple[float, float, float, float] | None = None,
    ) -> None:
        super().__init__(
            stroke_color=stroke_color,
            stroke_width=stroke_width,
            fill_color=fill_color,
        )
        self.x = float(x)
        self.y = float(y)
        self.w = float(w)
        self.h = float(h)

    def get_bounds(self) -> tuple[float, float, float, float]:
        return self.x, self.y, self.w, self.h

    def get_geometry(self) -> tuple[float, float, float, float]:
        return self.x, self.y, self.w, self.h

    def set_geometry(self, geometry: tuple[float, float, float, float]) -> bool:
        if isinstance(geometry, (tuple, list)) and len(geometry) == 4:
            self.x, self.y, self.w, self.h = geometry
            return True
        return False

    def hit_test(self, x: float, y: float, tolerance: float = 6.0) -> bool:
        bx, by, bw, bh = self.get_bounds()
        return (bx - tolerance) <= x <= (bx + bw + tolerance) and (by - tolerance) <= y <= (by + bh + tolerance)

    def draw(self, cr: cairo.Context) -> None:
        cr.rectangle(self.x, self.y, self.w, self.h)
        if self.fill_color:
            cr.set_source_rgba(*self.fill_color)
            cr.fill_preserve()
        cr.set_source_rgba(*self.stroke_color)
        cr.set_line_width(self.stroke_width)
        cr.stroke()

    def move_by(self, dx: float, dy: float) -> None:
        self.x += dx
        self.y += dy

    def clone(self) -> DummyBox:
        return DummyBox(
            self.x,
            self.y,
            self.w,
            self.h,
            stroke_color=self.stroke_color,
            stroke_width=self.stroke_width,
            fill_color=self.fill_color,
        )


class TestItemManipulation(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        Gtk.init()

    def setUp(self) -> None:
        self.canvas = Canvas()
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 600, 400)
        self.canvas.set_image_surface(surf, 600, 400)
        self.canvas.tool_manager.set_active_tool("select")
        self.select_tool = self.canvas.select_tool
        self.assertIsNotNone(self.select_tool)

    def test_drag_single_item_moves_and_records_undo(self) -> None:
        box = DummyBox(50.0, 50.0, 60.0, 40.0)
        self.canvas.document.add_item(box)

        # Press on item
        handled = self.select_tool.on_press(60.0, 60.0, 60.0, 60.0, Gdk.ModifierType(0))
        self.assertTrue(handled)
        self.assertTrue(self.select_tool.is_moving_items)
        self.assertEqual(self.select_tool.moving_items, [box])

        # Drag by +30, +40
        self.select_tool.on_drag(90.0, 100.0, 30.0, 40.0, 90.0, 100.0, Gdk.ModifierType(0))
        self.assertAlmostEqual(box.x, 80.0)
        self.assertAlmostEqual(box.y, 90.0)

        # Release
        self.select_tool.on_release(90.0, 100.0, 90.0, 100.0, Gdk.ModifierType(0))
        self.assertFalse(self.select_tool.is_moving_items)
        self.assertAlmostEqual(box.x, 80.0)
        self.assertAlmostEqual(box.y, 90.0)
        self.assertTrue(self.canvas.undo_manager.can_undo)

        # Undo returns to initial position
        self.canvas.undo()
        self.assertAlmostEqual(box.x, 50.0)
        self.assertAlmostEqual(box.y, 50.0)

        # Redo moves back to target position
        self.canvas.redo()
        self.assertAlmostEqual(box.x, 80.0)
        self.assertAlmostEqual(box.y, 90.0)

    def test_drag_multiple_selected_items(self) -> None:
        box1 = DummyBox(50.0, 50.0, 40.0, 40.0)
        box2 = DummyBox(200.0, 200.0, 60.0, 60.0)
        self.canvas.document.add_item(box1)
        self.canvas.document.add_item(box2)

        # Select both
        self.select_tool.select_item(box1)
        self.select_tool.select_item(box2, exclusive=False)
        self.assertEqual(len(self.canvas.document.selected_items), 2)

        # Press on box1 and drag by +20, -10
        self.select_tool.on_press(60.0, 60.0, 60.0, 60.0, Gdk.ModifierType(0))
        self.assertEqual(len(self.select_tool.moving_items), 2)

        self.select_tool.on_drag(80.0, 50.0, 20.0, -10.0, 80.0, 50.0, Gdk.ModifierType(0))
        self.assertAlmostEqual(box1.x, 70.0)
        self.assertAlmostEqual(box1.y, 40.0)
        self.assertAlmostEqual(box2.x, 220.0)
        self.assertAlmostEqual(box2.y, 190.0)

        # Release
        self.select_tool.on_release(80.0, 50.0, 80.0, 50.0, Gdk.ModifierType(0))
        self.assertAlmostEqual(box1.x, 70.0)
        self.assertAlmostEqual(box1.y, 40.0)
        self.assertAlmostEqual(box2.x, 220.0)
        self.assertAlmostEqual(box2.y, 190.0)

        # Undo reverses both
        self.canvas.undo()
        self.assertAlmostEqual(box1.x, 50.0)
        self.assertAlmostEqual(box1.y, 50.0)
        self.assertAlmostEqual(box2.x, 200.0)
        self.assertAlmostEqual(box2.y, 200.0)

        # Redo reapplies both
        self.canvas.redo()
        self.assertAlmostEqual(box1.x, 70.0)
        self.assertAlmostEqual(box1.y, 40.0)
        self.assertAlmostEqual(box2.x, 220.0)
        self.assertAlmostEqual(box2.y, 190.0)

    def test_cancel_drag_reverts_positions(self) -> None:
        box = DummyBox(50.0, 50.0, 60.0, 40.0)
        self.canvas.document.add_item(box)

        self.select_tool.on_press(60.0, 60.0, 60.0, 60.0, Gdk.ModifierType(0))
        self.select_tool.on_drag(100.0, 110.0, 40.0, 50.0, 100.0, 110.0, Gdk.ModifierType(0))
        self.assertAlmostEqual(box.x, 90.0)

        self.select_tool.on_cancel()
        self.assertAlmostEqual(box.x, 50.0)
        self.assertAlmostEqual(box.y, 50.0)
        self.assertFalse(self.canvas.undo_manager.can_undo)

    def test_escape_key_during_drag_reverts_positions(self) -> None:
        box = DummyBox(50.0, 50.0, 60.0, 40.0)
        self.canvas.document.add_item(box)

        self.select_tool.on_press(60.0, 60.0, 60.0, 60.0, Gdk.ModifierType(0))
        self.select_tool.on_drag(100.0, 110.0, 40.0, 50.0, 100.0, 110.0, Gdk.ModifierType(0))
        self.assertAlmostEqual(box.x, 90.0)

        handled = self.select_tool.on_key_pressed(Gdk.KEY_Escape, Gdk.ModifierType(0))
        self.assertTrue(handled)
        self.assertAlmostEqual(box.x, 50.0)
        self.assertAlmostEqual(box.y, 50.0)
        self.assertFalse(self.canvas.undo_manager.can_undo)

    def test_cursor_changes_to_grabbing_during_drag(self) -> None:
        box = DummyBox(50.0, 50.0, 60.0, 40.0)
        self.canvas.document.add_item(box)

        self.select_tool.on_press(60.0, 60.0, 60.0, 60.0, Gdk.ModifierType(0))
        self.select_tool.on_drag(80.0, 80.0, 20.0, 20.0, 80.0, 80.0, Gdk.ModifierType(0))
        self.assertEqual(self.canvas.current_cursor_name, "grabbing")

        self.select_tool.on_release(80.0, 80.0, 80.0, 80.0, Gdk.ModifierType(0))
        self.assertEqual(self.canvas.current_cursor_name, "pointer")

    def test_delete_selected_items(self) -> None:
        box1 = DummyBox(10.0, 10.0, 20.0, 20.0)
        box2 = DummyBox(50.0, 50.0, 20.0, 20.0)
        box3 = DummyBox(100.0, 100.0, 20.0, 20.0)
        self.canvas.document.add_item(box1)
        self.canvas.document.add_item(box2)
        self.canvas.document.add_item(box3)

        self.select_tool.select_item(box2)
        self.assertTrue(self.select_tool.delete_selected())
        self.assertEqual(self.canvas.document.items, [box1, box3])
        self.assertEqual(self.canvas.document.selected_items, [])

        # Undo restores box2 at original index 1
        self.canvas.undo()
        self.assertEqual(self.canvas.document.items, [box1, box2, box3])
        self.assertTrue(box2.is_selected)

        # Redo deletes box2 again
        self.canvas.redo()
        self.assertEqual(self.canvas.document.items, [box1, box3])

    def test_delete_key_shortcuts(self) -> None:
        box = DummyBox(10.0, 10.0, 20.0, 20.0)
        self.canvas.document.add_item(box)
        self.select_tool.select_item(box)

        handled = self.select_tool.on_key_pressed(Gdk.KEY_Delete, Gdk.ModifierType(0))
        self.assertTrue(handled)
        self.assertEqual(self.canvas.document.items, [])

        self.canvas.undo()
        self.assertEqual(self.canvas.document.items, [box])

        handled = self.select_tool.on_key_pressed(Gdk.KEY_BackSpace, Gdk.ModifierType(0))
        self.assertTrue(handled)
        self.assertEqual(self.canvas.document.items, [])

    def test_arrow_key_nudging(self) -> None:
        box = DummyBox(100.0, 100.0, 50.0, 50.0)
        self.canvas.document.add_item(box)
        self.select_tool.select_item(box)

        # Right arrow: +1.0 px
        self.select_tool.on_key_pressed(Gdk.KEY_Right, Gdk.ModifierType(0))
        self.assertAlmostEqual(box.x, 101.0)
        self.assertAlmostEqual(box.y, 100.0)

        # Down arrow: +1.0 px
        self.select_tool.on_key_pressed(Gdk.KEY_Down, Gdk.ModifierType(0))
        self.assertAlmostEqual(box.x, 101.0)
        self.assertAlmostEqual(box.y, 101.0)

        # Shift + Up: -10.0 px
        self.select_tool.on_key_pressed(Gdk.KEY_Up, Gdk.ModifierType.SHIFT_MASK)
        self.assertAlmostEqual(box.x, 101.0)
        self.assertAlmostEqual(box.y, 91.0)

        # Shift + Left: -10.0 px
        self.select_tool.on_key_pressed(Gdk.KEY_Left, Gdk.ModifierType.SHIFT_MASK)
        self.assertAlmostEqual(box.x, 91.0)
        self.assertAlmostEqual(box.y, 91.0)

        # Undo moves back
        self.canvas.undo()
        # Because nudges merged on same item, single undo restores starting pos
        self.assertAlmostEqual(box.x, 100.0)
        self.assertAlmostEqual(box.y, 100.0)

    def test_z_order_bring_to_front_and_send_to_back(self) -> None:
        a = DummyBox(10, 10, 10, 10)
        b = DummyBox(20, 20, 10, 10)
        c = DummyBox(30, 30, 10, 10)
        d = DummyBox(40, 40, 10, 10)
        for it in (a, b, c, d):
            self.canvas.document.add_item(it)

        # Bring B (index 1) to front -> [A, C, D, B]
        self.select_tool.select_item(b)
        self.assertTrue(self.select_tool.bring_to_front())
        self.assertEqual(self.canvas.document.items, [a, c, d, b])

        # Undo -> [A, B, C, D]
        self.canvas.undo()
        self.assertEqual(self.canvas.document.items, [a, b, c, d])

        # Redo -> [A, C, D, B]
        self.canvas.redo()
        self.assertEqual(self.canvas.document.items, [a, c, d, b])

        # Send B to back -> [B, A, C, D]
        self.assertTrue(self.select_tool.send_to_back())
        self.assertEqual(self.canvas.document.items, [b, a, c, d])

        # Undo -> [A, C, D, B]
        self.canvas.undo()
        self.assertEqual(self.canvas.document.items, [a, c, d, b])

    def test_z_order_bring_forward_and_send_backward(self) -> None:
        a = DummyBox(10, 10, 10, 10)
        b = DummyBox(20, 20, 10, 10)
        c = DummyBox(30, 30, 10, 10)
        for it in (a, b, c):
            self.canvas.document.add_item(it)

        # B is at index 1. Bring forward -> swaps with C -> [A, C, B]
        self.select_tool.select_item(b)
        self.assertTrue(self.select_tool.bring_forward())
        self.assertEqual(self.canvas.document.items, [a, c, b])

        # Send backward -> swaps back with C -> [A, B, C]
        self.assertTrue(self.select_tool.send_backward())
        self.assertEqual(self.canvas.document.items, [a, b, c])

        # Send backward again -> swaps with A -> [B, A, C]
        self.assertTrue(self.select_tool.send_backward())
        self.assertEqual(self.canvas.document.items, [b, a, c])

        self.canvas.undo()
        self.assertEqual(self.canvas.document.items, [a, b, c])

    def test_z_order_multiple_selected_preserves_relative_order(self) -> None:
        a = DummyBox(10, 10, 10, 10)
        b = DummyBox(20, 20, 10, 10)
        c = DummyBox(30, 30, 10, 10)
        d = DummyBox(40, 40, 10, 10)
        e = DummyBox(50, 50, 10, 10)
        for it in (a, b, c, d, e):
            self.canvas.document.add_item(it)

        # Select A (0) and C (2)
        self.select_tool.select_item(a)
        self.select_tool.select_item(c, exclusive=False)

        # Bring to front: [B, D, E, A, C]
        self.assertTrue(self.select_tool.bring_to_front())
        self.assertEqual(self.canvas.document.items, [b, d, e, a, c])

        # Send to back: [A, C, B, D, E]
        self.assertTrue(self.select_tool.send_to_back())
        self.assertEqual(self.canvas.document.items, [a, c, b, d, e])

        # Undo returns to [B, D, E, A, C]
        self.canvas.undo()
        self.assertEqual(self.canvas.document.items, [b, d, e, a, c])

        # Undo again returns to original [A, B, C, D, E]
        self.canvas.undo()
        self.assertEqual(self.canvas.document.items, [a, b, c, d, e])

    def test_z_order_keyboard_shortcuts(self) -> None:
        a = DummyBox(10, 10, 10, 10)
        b = DummyBox(20, 20, 10, 10)
        c = DummyBox(30, 30, 10, 10)
        for it in (a, b, c):
            self.canvas.document.add_item(it)

        self.select_tool.select_item(a)

        # Page_Up -> bring_forward: [B, A, C]
        handled = self.select_tool.on_key_pressed(Gdk.KEY_Page_Up, Gdk.ModifierType(0))
        self.assertTrue(handled)
        self.assertEqual(self.canvas.document.items, [b, a, c])

        # Page_Down -> send_backward: [A, B, C]
        handled = self.select_tool.on_key_pressed(Gdk.KEY_Page_Down, Gdk.ModifierType(0))
        self.assertTrue(handled)
        self.assertEqual(self.canvas.document.items, [a, b, c])

        # Shift + Page_Up -> bring_to_front: [B, C, A]
        handled = self.select_tool.on_key_pressed(Gdk.KEY_Page_Up, Gdk.ModifierType.SHIFT_MASK)
        self.assertTrue(handled)
        self.assertEqual(self.canvas.document.items, [b, c, a])

        # Shift + Page_Down -> send_to_back: [A, B, C]
        handled = self.select_tool.on_key_pressed(Gdk.KEY_Page_Down, Gdk.ModifierType.SHIFT_MASK)
        self.assertTrue(handled)
        self.assertEqual(self.canvas.document.items, [a, b, c])

        # Ctrl + bracketright -> bring_forward: [B, A, C]
        handled = self.select_tool.on_key_pressed(Gdk.KEY_bracketright, Gdk.ModifierType.CONTROL_MASK)
        self.assertTrue(handled)
        self.assertEqual(self.canvas.document.items, [b, a, c])

        # Ctrl + bracketleft -> send_backward: [A, B, C]
        handled = self.select_tool.on_key_pressed(Gdk.KEY_bracketleft, Gdk.ModifierType.CONTROL_MASK)
        self.assertTrue(handled)
        self.assertEqual(self.canvas.document.items, [a, b, c])

    def test_canvas_helper_methods(self) -> None:
        a = DummyBox(10, 10, 10, 10)
        b = DummyBox(20, 20, 10, 10)
        self.canvas.document.add_item(a)
        self.canvas.document.add_item(b)

        self.canvas.select_item(a)
        self.assertTrue(self.canvas.bring_to_front())
        self.assertEqual(self.canvas.document.items, [b, a])

        self.assertTrue(self.canvas.send_to_back())
        self.assertEqual(self.canvas.document.items, [a, b])

        self.assertTrue(self.canvas.bring_forward())
        self.assertEqual(self.canvas.document.items, [b, a])

        self.assertTrue(self.canvas.send_backward())
        self.assertEqual(self.canvas.document.items, [a, b])

        self.assertTrue(self.canvas.delete_selected())
        self.assertEqual(self.canvas.document.items, [b])


if __name__ == "__main__":
    unittest.main()
