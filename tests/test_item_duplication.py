from __future__ import annotations
import unittest
import cairo
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Gdk, Adw

from gobrush.ui.canvas import Canvas
from gobrush.ui.window import MainWindow
from gobrush.items.base import AnnotationItem
from gobrush.core.clipboard import AnnotationClipboard


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
        item_id: str | None = None,
    ) -> None:
        super().__init__(
            stroke_color=stroke_color,
            stroke_width=stroke_width,
            fill_color=fill_color,
            item_id=item_id,
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


class TestItemDuplication(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        Gtk.init()

    def setUp(self) -> None:
        AnnotationClipboard.get_instance().clear()
        self.canvas = Canvas()
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 600, 400)
        self.canvas.set_image_surface(surf, 600, 400)
        self.canvas.tool_manager.set_active_tool("select")
        self.select_tool = self.canvas.select_tool
        self.assertIsNotNone(self.select_tool)

    def tearDown(self) -> None:
        AnnotationClipboard.get_instance().clear()

    def test_duplicate_single_item(self) -> None:
        box = DummyBox(50.0, 60.0, 100.0, 80.0)
        self.canvas.document.add_item(box)
        self.select_tool.select_item(box)

        # Duplicate via canvas
        res = self.canvas.duplicate_selected()
        self.assertTrue(res)
        self.assertEqual(len(self.canvas.document.items), 2)

        # Original item is deselected
        self.assertFalse(box.is_selected)

        # New item is selected and offset by (20, 20)
        new_box = self.canvas.document.items[1]
        self.assertTrue(new_box.is_selected)
        self.assertNotEqual(new_box.item_id, box.item_id)
        self.assertAlmostEqual(new_box.x, 70.0)
        self.assertAlmostEqual(new_box.y, 80.0)
        self.assertAlmostEqual(new_box.w, 100.0)
        self.assertAlmostEqual(new_box.h, 80.0)

        # Undo removes duplicate and restores original selection
        self.canvas.undo()
        self.assertEqual(len(self.canvas.document.items), 1)
        self.assertTrue(box.is_selected)

        # Redo restores duplicate and selects it
        self.canvas.redo()
        self.assertEqual(len(self.canvas.document.items), 2)
        self.assertFalse(box.is_selected)
        self.assertTrue(self.canvas.document.items[1].is_selected)

    def test_duplicate_multiple_items(self) -> None:
        b1 = DummyBox(10.0, 10.0, 30.0, 30.0)
        b2 = DummyBox(100.0, 100.0, 40.0, 40.0)
        self.canvas.document.add_item(b1)
        self.canvas.document.add_item(b2)
        self.select_tool.select_item(b1)
        self.select_tool.select_item(b2, exclusive=False)

        res = self.canvas.duplicate_selected()
        self.assertTrue(res)
        self.assertEqual(len(self.canvas.document.items), 4)

        # First two deselected, new two selected
        self.assertFalse(b1.is_selected)
        self.assertFalse(b2.is_selected)

        new1 = self.canvas.document.items[2]
        new2 = self.canvas.document.items[3]
        self.assertTrue(new1.is_selected)
        self.assertTrue(new2.is_selected)
        self.assertAlmostEqual(new1.x, 30.0)
        self.assertAlmostEqual(new1.y, 30.0)
        self.assertAlmostEqual(new2.x, 120.0)
        self.assertAlmostEqual(new2.y, 120.0)

        # Undo restores original two items selected
        self.canvas.undo()
        self.assertEqual(len(self.canvas.document.items), 2)
        self.assertTrue(b1.is_selected)
        self.assertTrue(b2.is_selected)

    def test_duplicate_cascade(self) -> None:
        box = DummyBox(50.0, 50.0, 40.0, 40.0)
        self.canvas.document.add_item(box)
        self.select_tool.select_item(box)

        # Duplicate 1
        self.canvas.duplicate_selected()
        copy1 = self.canvas.selected_item
        self.assertAlmostEqual(copy1.x, 70.0)

        # Duplicate 2 (duplicates copy1)
        self.canvas.duplicate_selected()
        copy2 = self.canvas.selected_item
        self.assertAlmostEqual(copy2.x, 90.0)

        # Duplicate 3 (duplicates copy2)
        self.canvas.duplicate_selected()
        copy3 = self.canvas.selected_item
        self.assertAlmostEqual(copy3.x, 110.0)

        self.assertEqual(len(self.canvas.document.items), 4)

    def test_duplicate_nothing_selected_returns_false(self) -> None:
        box = DummyBox(50.0, 50.0, 40.0, 40.0)
        self.canvas.document.add_item(box)
        self.assertFalse(box.is_selected)

        res = self.canvas.duplicate_selected()
        self.assertFalse(res)
        self.assertEqual(len(self.canvas.document.items), 1)

    def test_copy_and_paste_single_item(self) -> None:
        box = DummyBox(30.0, 40.0, 50.0, 60.0)
        self.canvas.document.add_item(box)
        self.select_tool.select_item(box)

        # Copy
        self.assertTrue(self.canvas.copy_selected())
        clip = AnnotationClipboard.get_instance()
        self.assertTrue(clip.has_items)
        self.assertEqual(clip.item_count, 1)

        # Paste
        self.assertTrue(self.canvas.paste_selected())
        self.assertEqual(len(self.canvas.document.items), 2)
        pasted = self.canvas.document.items[1]
        self.assertTrue(pasted.is_selected)
        self.assertFalse(box.is_selected)
        self.assertAlmostEqual(pasted.x, 50.0)
        self.assertAlmostEqual(pasted.y, 60.0)

        # Undo / Redo
        self.canvas.undo()
        self.assertEqual(len(self.canvas.document.items), 1)
        self.assertTrue(box.is_selected)

        self.canvas.redo()
        self.assertEqual(len(self.canvas.document.items), 2)
        self.assertTrue(self.canvas.document.items[1].is_selected)

    def test_repeated_paste_incremental_offset(self) -> None:
        box = DummyBox(100.0, 100.0, 50.0, 50.0)
        self.canvas.document.add_item(box)
        self.select_tool.select_item(box)

        self.canvas.copy_selected()

        # Paste 1: +20, +20
        self.canvas.paste_selected()
        p1 = self.canvas.document.items[1]
        self.assertAlmostEqual(p1.x, 120.0)
        self.assertAlmostEqual(p1.y, 120.0)

        # Paste 2: +40, +40 from original
        self.canvas.paste_selected()
        p2 = self.canvas.document.items[2]
        self.assertAlmostEqual(p2.x, 140.0)
        self.assertAlmostEqual(p2.y, 140.0)

        # Paste 3: +60, +60 from original
        self.canvas.paste_selected()
        p3 = self.canvas.document.items[3]
        self.assertAlmostEqual(p3.x, 160.0)
        self.assertAlmostEqual(p3.y, 160.0)

        self.assertEqual(len(self.canvas.document.items), 4)

    def test_cut_selected_item(self) -> None:
        box = DummyBox(20.0, 20.0, 40.0, 40.0)
        self.canvas.document.add_item(box)
        self.select_tool.select_item(box)

        # Cut
        self.assertTrue(self.canvas.cut_selected())
        self.assertEqual(len(self.canvas.document.items), 0)
        self.assertTrue(AnnotationClipboard.get_instance().has_items)

        # Paste cut item
        self.assertTrue(self.canvas.paste_selected())
        self.assertEqual(len(self.canvas.document.items), 1)
        pasted = self.canvas.document.items[0]
        self.assertAlmostEqual(pasted.x, 40.0)
        self.assertAlmostEqual(pasted.y, 40.0)

    def test_select_tool_shortcuts_ctrl_d_c_v_x(self) -> None:
        box = DummyBox(20.0, 20.0, 40.0, 40.0)
        self.canvas.document.add_item(box)
        self.select_tool.select_item(box)

        # Ctrl+D
        handled = self.select_tool.on_key_pressed(Gdk.KEY_d, Gdk.ModifierType.CONTROL_MASK)
        self.assertTrue(handled)
        self.assertEqual(len(self.canvas.document.items), 2)

        # Ctrl+C
        handled = self.select_tool.on_key_pressed(Gdk.KEY_c, Gdk.ModifierType.CONTROL_MASK)
        self.assertTrue(handled)
        self.assertTrue(AnnotationClipboard.get_instance().has_items)

        # Ctrl+V
        handled = self.select_tool.on_key_pressed(Gdk.KEY_v, Gdk.ModifierType.CONTROL_MASK)
        self.assertTrue(handled)
        self.assertEqual(len(self.canvas.document.items), 3)

        # Ctrl+X
        handled = self.select_tool.on_key_pressed(Gdk.KEY_x, Gdk.ModifierType.CONTROL_MASK)
        self.assertTrue(handled)
        self.assertEqual(len(self.canvas.document.items), 2)

    def test_window_ctrl_d_and_clipboard_integration(self) -> None:
        app = Adw.Application(application_id="org.word_sys.GoBrush.DuplTest")
        win = MainWindow(application=app)
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 600, 400)
        win.load_surface(surf, title="Duplication Test")

        box = DummyBox(50.0, 50.0, 60.0, 40.0)
        win.canvas.document.add_item(box)
        win.canvas.select_tool.select_item(box)

        # Trigger Ctrl+D in MainWindow
        handled = win._on_key_pressed(None, Gdk.KEY_d, 0, Gdk.ModifierType.CONTROL_MASK)
        self.assertTrue(handled)
        self.assertEqual(len(win.canvas.document.items), 2)

        # Trigger Ctrl+C with item selected
        handled = win._on_key_pressed(None, Gdk.KEY_c, 0, Gdk.ModifierType.CONTROL_MASK)
        self.assertTrue(handled)
        self.assertTrue(AnnotationClipboard.get_instance().has_items)

        # Trigger Ctrl+V
        handled = win._on_key_pressed(None, Gdk.KEY_v, 0, Gdk.ModifierType.CONTROL_MASK)
        self.assertTrue(handled)
        self.assertEqual(len(win.canvas.document.items), 3)

        # Trigger Ctrl+X
        handled = win._on_key_pressed(None, Gdk.KEY_x, 0, Gdk.ModifierType.CONTROL_MASK)
        self.assertTrue(handled)
        self.assertEqual(len(win.canvas.document.items), 2)

        win.close()


if __name__ == "__main__":
    unittest.main()
