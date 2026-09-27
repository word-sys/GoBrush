from __future__ import annotations
import unittest
import cairo
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Gdk

from gobrush.items.base import AnnotationItem
from gobrush.tools.select import SelectTool
from gobrush.ui.canvas import Canvas


class DummyRect(AnnotationItem):
    type_name = "dummy_rect"

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

    def clone(self) -> DummyRect:
        return DummyRect(
            self.x,
            self.y,
            self.w,
            self.h,
            stroke_color=self.stroke_color,
            stroke_width=self.stroke_width,
            fill_color=self.fill_color,
        )


class TestSelectTool(unittest.TestCase):
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

    def test_select_tool_initialization(self) -> None:
        tool = self.select_tool
        self.assertEqual(tool.tool_id, "select")
        self.assertEqual(tool.name, "Select")
        self.assertEqual(tool.shortcut, "S")
        self.assertEqual(tool.icon_name, "edit-select-symbolic")
        self.assertEqual(tool.cursor_name, "default")
        self.assertFalse(tool.is_marquee)
        self.assertIsNone(tool.marquee_bounds)
        self.assertEqual(len(tool.selected_items), 0)
        self.assertIsNone(tool.selected_item)

    def test_click_on_annotation_selects_exclusively(self) -> None:
        item1 = DummyRect(20.0, 20.0, 60.0, 40.0)
        item2 = DummyRect(150.0, 150.0, 60.0, 40.0)
        self.canvas.document.add_item(item1)
        self.canvas.document.add_item(item2)

        # Click on item1
        handled = self.select_tool.on_press(30.0, 30.0, 30.0, 30.0, Gdk.ModifierType(0))
        self.assertTrue(handled)
        self.select_tool.on_release(30.0, 30.0, 30.0, 30.0, Gdk.ModifierType(0))

        self.assertTrue(item1.is_selected)
        self.assertFalse(item2.is_selected)
        self.assertIs(self.canvas.selected_item, item1)

        # Click on item2
        handled = self.select_tool.on_press(160.0, 160.0, 160.0, 160.0, Gdk.ModifierType(0))
        self.assertTrue(handled)
        self.select_tool.on_release(160.0, 160.0, 160.0, 160.0, Gdk.ModifierType(0))

        self.assertFalse(item1.is_selected)
        self.assertTrue(item2.is_selected)
        self.assertIs(self.canvas.selected_item, item2)

    def test_click_on_canvas_deselects_all(self) -> None:
        item = DummyRect(20.0, 20.0, 60.0, 40.0)
        self.canvas.document.add_item(item)
        self.select_tool.select_item(item)
        self.assertTrue(item.is_selected)

        # Click on empty area (400, 300)
        self.select_tool.on_press(400.0, 300.0, 400.0, 300.0, Gdk.ModifierType(0))
        self.select_tool.on_release(400.0, 300.0, 400.0, 300.0, Gdk.ModifierType(0))

        self.assertFalse(item.is_selected)
        self.assertEqual(len(self.canvas.selected_items), 0)

    def test_shift_click_multi_selection_and_toggle(self) -> None:
        item1 = DummyRect(20.0, 20.0, 50.0, 50.0)
        item2 = DummyRect(100.0, 20.0, 50.0, 50.0)
        self.canvas.document.add_item(item1)
        self.canvas.document.add_item(item2)

        # Normal click on item1
        self.select_tool.on_press(25.0, 25.0, 25.0, 25.0, Gdk.ModifierType(0))
        self.select_tool.on_release(25.0, 25.0, 25.0, 25.0, Gdk.ModifierType(0))
        self.assertTrue(item1.is_selected)
        self.assertFalse(item2.is_selected)

        # Shift-click on item2 -> both selected
        self.select_tool.on_press(110.0, 25.0, 110.0, 25.0, Gdk.ModifierType.SHIFT_MASK)
        self.select_tool.on_release(110.0, 25.0, 110.0, 25.0, Gdk.ModifierType.SHIFT_MASK)
        self.assertTrue(item1.is_selected)
        self.assertTrue(item2.is_selected)
        self.assertEqual(len(self.canvas.selected_items), 2)

        # Shift-click on item1 again -> toggles off item1, item2 remains
        self.select_tool.on_press(25.0, 25.0, 25.0, 25.0, Gdk.ModifierType.SHIFT_MASK)
        self.select_tool.on_release(25.0, 25.0, 25.0, 25.0, Gdk.ModifierType.SHIFT_MASK)
        self.assertFalse(item1.is_selected)
        self.assertTrue(item2.is_selected)
        self.assertEqual(len(self.canvas.selected_items), 1)

    def test_ctrl_click_multi_selection_and_toggle(self) -> None:
        item1 = DummyRect(20.0, 20.0, 50.0, 50.0)
        item2 = DummyRect(100.0, 20.0, 50.0, 50.0)
        self.canvas.document.add_item(item1)
        self.canvas.document.add_item(item2)

        # Select item1
        self.select_tool.select_item(item1)

        # Ctrl-click item2
        self.select_tool.on_press(110.0, 25.0, 110.0, 25.0, Gdk.ModifierType.CONTROL_MASK)
        self.select_tool.on_release(110.0, 25.0, 110.0, 25.0, Gdk.ModifierType.CONTROL_MASK)
        self.assertTrue(item1.is_selected)
        self.assertTrue(item2.is_selected)

        # Ctrl-click item2 again
        self.select_tool.on_press(110.0, 25.0, 110.0, 25.0, Gdk.ModifierType.CONTROL_MASK)
        self.select_tool.on_release(110.0, 25.0, 110.0, 25.0, Gdk.ModifierType.CONTROL_MASK)
        self.assertTrue(item1.is_selected)
        self.assertFalse(item2.is_selected)

    def test_marquee_box_selection(self) -> None:
        item1 = DummyRect(20.0, 20.0, 40.0, 40.0)
        item2 = DummyRect(80.0, 20.0, 40.0, 40.0)
        item3 = DummyRect(200.0, 200.0, 40.0, 40.0)
        self.canvas.document.add_item(item1)
        self.canvas.document.add_item(item2)
        self.canvas.document.add_item(item3)

        # Drag from (10, 10) to (130, 70) enclosing item1 and item2
        self.select_tool.on_press(10.0, 10.0, 10.0, 10.0, Gdk.ModifierType(0))
        self.assertTrue(self.select_tool.is_marquee)

        self.select_tool.on_drag(130.0, 70.0, 120.0, 60.0, 130.0, 70.0, Gdk.ModifierType(0))
        bounds = self.select_tool.marquee_bounds
        self.assertIsNotNone(bounds)
        self.assertAlmostEqual(bounds[0], 10.0)
        self.assertAlmostEqual(bounds[1], 10.0)
        self.assertAlmostEqual(bounds[2], 120.0)
        self.assertAlmostEqual(bounds[3], 60.0)

        # Release drag
        self.select_tool.on_release(130.0, 70.0, 130.0, 70.0, Gdk.ModifierType(0))
        self.assertFalse(self.select_tool.is_marquee)

        self.assertTrue(item1.is_selected)
        self.assertTrue(item2.is_selected)
        self.assertFalse(item3.is_selected)
        self.assertEqual(len(self.canvas.selected_items), 2)

    def test_marquee_draw_overlay(self) -> None:
        self.select_tool.on_press(10.0, 10.0, 10.0, 10.0, Gdk.ModifierType(0))
        self.select_tool.on_drag(100.0, 80.0, 90.0, 70.0, 100.0, 80.0, Gdk.ModifierType(0))

        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 200, 200)
        cr = cairo.Context(surf)
        self.select_tool.draw_overlay(cr)

        self.select_tool.on_release(100.0, 80.0, 100.0, 80.0, Gdk.ModifierType(0))

    def test_hover_motion_cursor(self) -> None:
        item = DummyRect(50.0, 50.0, 60.0, 40.0)
        self.canvas.document.add_item(item)

        # Hover over item
        self.select_tool.on_motion(60.0, 60.0, 60.0, 60.0, Gdk.ModifierType(0))
        self.assertEqual(self.canvas.current_cursor_name, "pointer")

        # Hover over empty canvas
        self.select_tool.on_motion(300.0, 300.0, 300.0, 300.0, Gdk.ModifierType(0))
        self.assertIsNone(self.canvas.current_cursor_name)

    def test_keyboard_escape_deselects_all(self) -> None:
        item = DummyRect(20.0, 20.0, 50.0, 50.0)
        self.canvas.document.add_item(item)
        self.select_tool.select_item(item)
        self.assertTrue(item.is_selected)

        handled = self.select_tool.on_key_pressed(Gdk.KEY_Escape, Gdk.ModifierType(0))
        self.assertTrue(handled)
        self.assertFalse(item.is_selected)

    def test_keyboard_ctrl_a_selects_all(self) -> None:
        item1 = DummyRect(20.0, 20.0, 50.0, 50.0)
        item2 = DummyRect(100.0, 20.0, 50.0, 50.0)
        self.canvas.document.add_item(item1)
        self.canvas.document.add_item(item2)

        handled = self.select_tool.on_key_pressed(Gdk.KEY_a, Gdk.ModifierType.CONTROL_MASK)
        self.assertTrue(handled)
        self.assertTrue(item1.is_selected)
        self.assertTrue(item2.is_selected)

    def test_keyboard_delete_selected_items(self) -> None:
        item1 = DummyRect(20.0, 20.0, 50.0, 50.0)
        item2 = DummyRect(100.0, 20.0, 50.0, 50.0)
        self.canvas.document.add_item(item1)
        self.canvas.document.add_item(item2)
        self.select_tool.select_item(item1)

        handled = self.select_tool.on_key_pressed(Gdk.KEY_Delete, Gdk.ModifierType(0))
        self.assertTrue(handled)
        self.assertEqual(self.canvas.document.item_count, 1)
        self.assertIs(self.canvas.document.items[0], item2)

        # Undo restores item1
        self.canvas.undo()
        self.assertEqual(self.canvas.document.item_count, 2)
        self.assertIn(item1, self.canvas.document.items)

    def test_style_sync_and_restyle_command(self) -> None:
        item = DummyRect(
            20.0,
            20.0,
            50.0,
            50.0,
            stroke_color=(0.1, 0.4, 0.8, 1.0),
            stroke_width=8.0,
            fill_color=(0.1, 0.4, 0.8, 0.25),
        )
        self.canvas.document.add_item(item)

        # Selecting item syncs to ToolManager
        self.select_tool.select_item(item)
        mgr = self.canvas.tool_manager
        self.assertEqual(mgr.current_color, (0.1, 0.4, 0.8, 1.0))
        self.assertEqual(mgr.stroke_width, 8.0)
        self.assertEqual(mgr.fill_mode, "semi")

        # Mutating color on ToolManager restyles selected item via RestyleCommand
        new_color = (0.2, 0.8, 0.2, 1.0)
        mgr.set_current_color(new_color)
        self.assertEqual(item.stroke_color, new_color)

        # Mutating stroke width
        mgr.set_stroke_width(16.0)
        self.assertEqual(item.stroke_width, 16.0)

        # Undo reverses mutations
        self.canvas.undo()
        self.assertEqual(item.stroke_width, 8.0)
        self.canvas.undo()
        self.assertEqual(item.stroke_color, (0.1, 0.4, 0.8, 1.0))

    def test_canvas_primary_drag_delegates_to_select_tool(self) -> None:
        item = DummyRect(40.0, 40.0, 50.0, 50.0)
        self.canvas.document.add_item(item)

        gesture = self.canvas._primary_drag
        self.canvas._on_primary_drag_begin(gesture, 50.0, 50.0)
        self.assertTrue(item.is_selected)

        self.canvas._on_primary_drag_end(gesture, 0.0, 0.0)
        self.assertTrue(item.is_selected)


if __name__ == "__main__":
    unittest.main()
