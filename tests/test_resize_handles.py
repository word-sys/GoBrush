from __future__ import annotations
import unittest
import cairo
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Gdk

from gobrush.items.base import (
    AnnotationItem,
    HANDLE_TOP_LEFT,
    HANDLE_TOP_CENTER,
    HANDLE_TOP_RIGHT,
    HANDLE_MIDDLE_RIGHT,
    HANDLE_BOTTOM_RIGHT,
    HANDLE_BOTTOM_CENTER,
    HANDLE_BOTTOM_LEFT,
    HANDLE_MIDDLE_LEFT,
)
from gobrush.tools.select import HANDLE_CURSORS
from gobrush.ui.canvas import Canvas


class DummyBox(AnnotationItem):
    type_name = "dummy_box"

    def __init__(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        stroke_color: tuple[float, float, float, float] = (0.88, 0.11, 0.14, 1.0),
        stroke_width: float = 4.0,
        fill_color: tuple[float, float, float, float] | None = None,
        item_id: str | None = None,
    ) -> None:
        super().__init__(
            stroke_color=stroke_color,
            stroke_width=stroke_width,
            fill_color=fill_color,
            item_id=item_id,
        )
        self.x = x
        self.y = y
        self.w = w
        self.h = h

    def get_bounds(self) -> tuple[float, float, float, float]:
        pad = self.stroke_width / 2.0
        return self.x - pad, self.y - pad, self.w + self.stroke_width, self.h + self.stroke_width

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


class TestResizeHandles(unittest.TestCase):
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

    def test_handle_cursors_mapping(self) -> None:
        self.assertEqual(HANDLE_CURSORS[HANDLE_TOP_LEFT], "nwse-resize")
        self.assertEqual(HANDLE_CURSORS[HANDLE_BOTTOM_RIGHT], "nwse-resize")
        self.assertEqual(HANDLE_CURSORS[HANDLE_TOP_RIGHT], "nesw-resize")
        self.assertEqual(HANDLE_CURSORS[HANDLE_BOTTOM_LEFT], "nesw-resize")
        self.assertEqual(HANDLE_CURSORS[HANDLE_TOP_CENTER], "ns-resize")
        self.assertEqual(HANDLE_CURSORS[HANDLE_BOTTOM_CENTER], "ns-resize")
        self.assertEqual(HANDLE_CURSORS[HANDLE_MIDDLE_LEFT], "ew-resize")
        self.assertEqual(HANDLE_CURSORS[HANDLE_MIDDLE_RIGHT], "ew-resize")

    def test_hit_test_handle_all_eight_handles(self) -> None:
        box = DummyBox(100.0, 100.0, 120.0, 80.0)
        self.canvas.document.add_item(box)

        # Unselected box returns no handle
        self.assertFalse(box.is_selected)
        it, h = self.select_tool.hit_test_handle(100.0, 100.0)
        self.assertIsNone(it)
        self.assertIsNone(h)

        # Select box
        self.select_tool.select_item(box)
        handles = box.get_handles()
        self.assertEqual(len(handles), 8)

        for handle_id, (hx, hy) in handles.items():
            hit_it, hit_h = self.select_tool.hit_test_handle(hx, hy)
            self.assertIs(hit_it, box)
            self.assertEqual(hit_h, handle_id)

    def test_hover_over_handle_sets_resize_cursor(self) -> None:
        box = DummyBox(100.0, 100.0, 120.0, 80.0)
        self.canvas.document.add_item(box)
        self.select_tool.select_item(box)
        handles = box.get_handles()

        # Hover each handle and assert cursor
        for handle_id, (hx, hy) in handles.items():
            self.select_tool.on_motion(hx, hy, hx, hy, Gdk.ModifierType(0))
            expected_cursor = HANDLE_CURSORS[handle_id]
            self.assertEqual(self.canvas.current_cursor_name, expected_cursor)
            self.assertEqual(self.select_tool.hovered_handle, handle_id)

        # Move to center of box -> pointer cursor
        self.select_tool.on_motion(160.0, 140.0, 160.0, 140.0, Gdk.ModifierType(0))
        self.assertEqual(self.canvas.current_cursor_name, "pointer")
        self.assertIsNone(self.select_tool.hovered_handle)

        # Move away to empty space -> None cursor
        self.select_tool.on_motion(500.0, 300.0, 500.0, 300.0, Gdk.ModifierType(0))
        self.assertIsNone(self.canvas.current_cursor_name)

    def test_resize_bottom_right_handle(self) -> None:
        box = DummyBox(100.0, 100.0, 100.0, 80.0)
        self.canvas.document.add_item(box)
        self.select_tool.select_item(box)
        handles = box.get_handles()
        br_x, br_y = handles[HANDLE_BOTTOM_RIGHT]

        # Press on BR handle
        handled = self.select_tool.on_press(br_x, br_y, br_x, br_y, Gdk.ModifierType(0))
        self.assertTrue(handled)
        self.assertEqual(self.select_tool.active_handle, HANDLE_BOTTOM_RIGHT)
        self.assertIs(self.select_tool.resizing_item, box)

        # Drag +20, +30
        self.select_tool.on_drag(br_x + 20.0, br_y + 30.0, 20.0, 30.0, br_x + 20.0, br_y + 30.0, Gdk.ModifierType(0))
        self.assertAlmostEqual(box.x, 100.0)
        self.assertAlmostEqual(box.y, 100.0)
        self.assertAlmostEqual(box.w, 120.0)
        self.assertAlmostEqual(box.h, 110.0)

        # Release to commit
        self.select_tool.on_release(br_x + 20.0, br_y + 30.0, br_x + 20.0, br_y + 30.0, Gdk.ModifierType(0))
        self.assertIsNone(self.select_tool.active_handle)
        self.assertAlmostEqual(box.w, 120.0)
        self.assertAlmostEqual(box.h, 110.0)

        # Undo reverses resize
        self.canvas.undo()
        self.assertAlmostEqual(box.w, 100.0)
        self.assertAlmostEqual(box.h, 80.0)

        # Redo restores resize
        self.canvas.redo()
        self.assertAlmostEqual(box.w, 120.0)
        self.assertAlmostEqual(box.h, 110.0)

    def test_resize_top_left_handle(self) -> None:
        box = DummyBox(100.0, 100.0, 100.0, 80.0)
        self.canvas.document.add_item(box)
        self.select_tool.select_item(box)
        handles = box.get_handles()
        tl_x, tl_y = handles[HANDLE_TOP_LEFT]

        # Press on TL handle
        self.select_tool.on_press(tl_x, tl_y, tl_x, tl_y, Gdk.ModifierType(0))

        # Drag by -20, -10 (enlarging towards top-left)
        self.select_tool.on_drag(tl_x - 20.0, tl_y - 10.0, -20.0, -10.0, tl_x - 20.0, tl_y - 10.0, Gdk.ModifierType(0))
        self.assertAlmostEqual(box.x, 80.0)
        self.assertAlmostEqual(box.y, 90.0)
        self.assertAlmostEqual(box.w, 120.0)
        self.assertAlmostEqual(box.h, 90.0)

        self.select_tool.on_release(tl_x - 20.0, tl_y - 10.0, tl_x - 20.0, tl_y - 10.0, Gdk.ModifierType(0))

        # Undo
        self.canvas.undo()
        self.assertAlmostEqual(box.x, 100.0)
        self.assertAlmostEqual(box.y, 100.0)
        self.assertAlmostEqual(box.w, 100.0)
        self.assertAlmostEqual(box.h, 80.0)

    def test_resize_side_handles(self) -> None:
        box = DummyBox(100.0, 100.0, 100.0, 80.0)
        self.canvas.document.add_item(box)
        self.select_tool.select_item(box)
        handles = box.get_handles()

        # Middle Right (mr)
        mr_x, mr_y = handles[HANDLE_MIDDLE_RIGHT]
        self.select_tool.on_press(mr_x, mr_y, mr_x, mr_y, Gdk.ModifierType(0))
        self.select_tool.on_drag(mr_x + 30.0, mr_y, 30.0, 0.0, mr_x + 30.0, mr_y, Gdk.ModifierType(0))
        self.assertAlmostEqual(box.w, 130.0)
        self.assertAlmostEqual(box.h, 80.0)
        self.select_tool.on_release(mr_x + 30.0, mr_y, mr_x + 30.0, mr_y, Gdk.ModifierType(0))

        # Bottom Center (bc)
        handles = box.get_handles()
        bc_x, bc_y = handles[HANDLE_BOTTOM_CENTER]
        self.select_tool.on_press(bc_x, bc_y, bc_x, bc_y, Gdk.ModifierType(0))
        self.select_tool.on_drag(bc_x, bc_y + 25.0, 0.0, 25.0, bc_x, bc_y + 25.0, Gdk.ModifierType(0))
        self.assertAlmostEqual(box.w, 130.0)
        self.assertAlmostEqual(box.h, 105.0)
        self.select_tool.on_release(bc_x, bc_y + 25.0, bc_x, bc_y + 25.0, Gdk.ModifierType(0))

    def test_resize_with_aspect_ratio_lock(self) -> None:
        box = DummyBox(100.0, 100.0, 100.0, 50.0)  # 2:1 ratio
        self.canvas.document.add_item(box)
        self.select_tool.select_item(box)
        handles = box.get_handles()
        br_x, br_y = handles[HANDLE_BOTTOM_RIGHT]

        # Drag BR handle with Shift held
        self.select_tool.on_press(br_x, br_y, br_x, br_y, Gdk.ModifierType.SHIFT_MASK)
        self.select_tool.on_drag(br_x + 60.0, br_y + 10.0, 60.0, 10.0, br_x + 60.0, br_y + 10.0, Gdk.ModifierType.SHIFT_MASK)

        # Ratio must be 2.0 (w = 160, h = 80)
        self.assertAlmostEqual(box.w / box.h, 2.0, places=3)
        self.assertAlmostEqual(box.w, 160.0)
        self.assertAlmostEqual(box.h, 80.0)
        self.select_tool.on_release(br_x + 60.0, br_y + 10.0, br_x + 60.0, br_y + 10.0, Gdk.ModifierType.SHIFT_MASK)

    def test_resize_minimum_size_clamp(self) -> None:
        box = DummyBox(100.0, 100.0, 50.0, 50.0)
        self.canvas.document.add_item(box)
        self.select_tool.select_item(box)
        handles = box.get_handles()
        br_x, br_y = handles[HANDLE_BOTTOM_RIGHT]

        # Drag BR handle backwards past top-left
        self.select_tool.on_press(br_x, br_y, br_x, br_y, Gdk.ModifierType(0))
        self.select_tool.on_drag(br_x - 100.0, br_y - 100.0, -100.0, -100.0, br_x - 100.0, br_y - 100.0, Gdk.ModifierType(0))

        # Clamped to min_size = 6.0
        self.assertGreaterEqual(box.w, 6.0)
        self.assertGreaterEqual(box.h, 6.0)
        self.select_tool.on_release(br_x - 100.0, br_y - 100.0, br_x - 100.0, br_y - 100.0, Gdk.ModifierType(0))

    def test_resize_cancel_reverts_geometry(self) -> None:
        box = DummyBox(100.0, 100.0, 100.0, 80.0)
        self.canvas.document.add_item(box)
        self.select_tool.select_item(box)
        handles = box.get_handles()
        br_x, br_y = handles[HANDLE_BOTTOM_RIGHT]

        self.select_tool.on_press(br_x, br_y, br_x, br_y, Gdk.ModifierType(0))
        self.select_tool.on_drag(br_x + 50.0, br_y + 50.0, 50.0, 50.0, br_x + 50.0, br_y + 50.0, Gdk.ModifierType(0))
        self.assertEqual(box.w, 150.0)

        # Cancel drag
        self.select_tool.on_cancel()
        self.assertAlmostEqual(box.w, 100.0)
        self.assertAlmostEqual(box.h, 80.0)
        self.assertIsNone(self.select_tool.active_handle)

    def test_draw_overlay_highlights_handle(self) -> None:
        box = DummyBox(100.0, 100.0, 100.0, 80.0)
        self.canvas.document.add_item(box)
        self.select_tool.select_item(box)
        handles = box.get_handles()
        tl_x, tl_y = handles[HANDLE_TOP_LEFT]

        # Hover TL handle
        self.select_tool.on_motion(tl_x, tl_y, tl_x, tl_y, Gdk.ModifierType(0))
        self.assertEqual(self.select_tool.hovered_handle, HANDLE_TOP_LEFT)

        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 200, 200)
        cr = cairo.Context(surf)
        self.select_tool.draw_overlay(cr)


if __name__ == "__main__":
    unittest.main()
