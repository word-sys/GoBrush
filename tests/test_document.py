from __future__ import annotations
import unittest
from unittest.mock import Mock
import cairo
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk

from gobrush.core.document import AnnotationDocument
from gobrush.items.base import AnnotationItem
from gobrush.ui.canvas import Canvas


class DummyRectItem(AnnotationItem):
    type_name = "dummy_rect"

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

    def clone(self) -> DummyRectItem:
        return DummyRectItem(
            self.x,
            self.y,
            self.w,
            self.h,
            stroke_color=self.stroke_color,
            stroke_width=self.stroke_width,
            fill_color=self.fill_color,
        )


class TestAnnotationDocument(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        Gtk.init()

    def test_document_init_empty(self) -> None:
        doc = AnnotationDocument()
        self.assertIsNone(doc.background_surface)
        self.assertEqual(doc.width, 0)
        self.assertEqual(doc.height, 0)
        self.assertTrue(doc.has_alpha)
        self.assertFalse(doc.has_image)
        self.assertIsNone(doc.file_path)
        self.assertEqual(doc.file_format, "png")
        self.assertEqual(doc.items, [])
        self.assertEqual(doc.item_count, 0)
        self.assertFalse(doc.is_dirty)

    def test_document_init_with_surface(self) -> None:
        surf = cairo.ImageSurface(cairo.FORMAT_RGB24, 640, 480)
        doc = AnnotationDocument(
            surface=surf,
            file_path="/tmp/test.jpg",
            file_format="jpeg",
        )
        self.assertIs(doc.background_surface, surf)
        self.assertEqual(doc.width, 640)
        self.assertEqual(doc.height, 480)
        self.assertFalse(doc.has_alpha)
        self.assertTrue(doc.has_image)
        self.assertEqual(doc.file_path, "/tmp/test.jpg")
        self.assertEqual(doc.file_format, "jpeg")

    def test_document_set_background_and_clear(self) -> None:
        doc = AnnotationDocument()
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 200, 150)
        cb = Mock()
        doc.add_change_callback(cb)

        doc.set_background(surf)
        self.assertIs(doc.background_surface, surf)
        self.assertEqual(doc.width, 200)
        self.assertEqual(doc.height, 150)
        self.assertTrue(doc.has_alpha)
        self.assertEqual(cb.call_count, 1)

        item = DummyRectItem(10, 10, 50, 50)
        doc.add_item(item)
        self.assertEqual(doc.item_count, 1)

        doc.clear()
        self.assertIsNone(doc.background_surface)
        self.assertEqual(doc.width, 0)
        self.assertEqual(doc.height, 0)
        self.assertEqual(doc.item_count, 0)
        self.assertFalse(doc.is_dirty)

    def test_item_addition_removal(self) -> None:
        doc = AnnotationDocument()
        cb = Mock()
        doc.add_change_callback(cb)

        item1 = DummyRectItem(0, 0, 10, 10)
        item2 = DummyRectItem(20, 20, 10, 10)
        item3 = DummyRectItem(40, 40, 10, 10)

        idx1 = doc.add_item(item1)
        self.assertEqual(idx1, 0)
        self.assertEqual(doc.item_count, 1)
        self.assertTrue(doc.is_dirty)

        idx2 = doc.add_item(item2)
        self.assertEqual(idx2, 1)

        # Insert at beginning
        idx3 = doc.add_item(item3, index=0)
        self.assertEqual(idx3, 0)
        self.assertEqual(doc.items, [item3, item1, item2])
        self.assertEqual(doc.index_of(item1), 1)

        # Retrieval by ID
        self.assertIs(doc.get_item_by_id(item1.item_id), item1)
        self.assertIsNone(doc.get_item_by_id("nonexistent_uuid"))

        # Remove item
        removed = doc.remove_item(item1)
        self.assertTrue(removed)
        self.assertEqual(doc.items, [item3, item2])
        self.assertFalse(doc.remove_item(item1))

        # Remove item at index
        popped = doc.remove_item_at(0)
        self.assertIs(popped, item3)
        self.assertEqual(doc.items, [item2])

        # Clear items
        doc.clear_items()
        self.assertEqual(doc.item_count, 0)

    def test_z_order_operations(self) -> None:
        doc = AnnotationDocument()
        item_a = DummyRectItem(0, 0, 10, 10)
        item_b = DummyRectItem(10, 10, 10, 10)
        item_c = DummyRectItem(20, 20, 10, 10)

        doc.add_item(item_a)
        doc.add_item(item_b)
        doc.add_item(item_c)
        # Order: [A, B, C]

        # Bring forward B -> [A, C, B]
        self.assertTrue(doc.bring_forward(item_b))
        self.assertEqual(doc.items, [item_a, item_c, item_b])
        # Bring forward B again (already at top) -> False
        self.assertFalse(doc.bring_forward(item_b))

        # Send backward B -> [A, B, C]
        self.assertTrue(doc.send_backward(item_b))
        self.assertEqual(doc.items, [item_a, item_b, item_c])

        # Bring to front A -> [B, C, A]
        self.assertTrue(doc.bring_to_front(item_a))
        self.assertEqual(doc.items, [item_b, item_c, item_a])
        self.assertFalse(doc.bring_to_front(item_a))

        # Send to back A -> [A, B, C]
        self.assertTrue(doc.send_to_back(item_a))
        self.assertEqual(doc.items, [item_a, item_b, item_c])
        self.assertFalse(doc.send_to_back(item_a))

    def test_hit_testing(self) -> None:
        doc = AnnotationDocument()
        # Item 1 at (0, 0) to (50, 50)
        item1 = DummyRectItem(0, 0, 50, 50)
        # Item 2 overlapping at (25, 25) to (75, 75)
        item2 = DummyRectItem(25, 25, 50, 50)

        doc.add_item(item1)
        doc.add_item(item2)

        # Hit outside both
        self.assertIsNone(doc.hit_test(200, 200))
        self.assertEqual(doc.hit_test_all(200, 200), [])

        # Hit inside only item1 (e.g. 10, 10)
        self.assertIs(doc.hit_test(10, 10), item1)

        # Hit inside overlap (e.g. 30, 30) -> topmost is item2
        self.assertIs(doc.hit_test(30, 30), item2)
        all_hits = doc.hit_test_all(30, 30)
        self.assertEqual(all_hits, [item2, item1])

        # Invisible items are not hit
        item2.is_visible = False
        self.assertIs(doc.hit_test(30, 30), item1)
        self.assertEqual(doc.hit_test_all(30, 30), [item1])

    def test_selection_management(self) -> None:
        doc = AnnotationDocument()
        item1 = DummyRectItem(0, 0, 10, 10)
        item2 = DummyRectItem(10, 10, 10, 10)
        doc.add_item(item1)
        doc.add_item(item2)

        self.assertIsNone(doc.selected_item)
        self.assertEqual(doc.selected_items, [])

        # Select item1 exclusively
        doc.select_item(item1)
        self.assertTrue(item1.is_selected)
        self.assertFalse(item2.is_selected)
        self.assertIs(doc.selected_item, item1)

        # Select item2 exclusively
        doc.select_item(item2)
        self.assertFalse(item1.is_selected)
        self.assertTrue(item2.is_selected)
        self.assertIs(doc.selected_item, item2)

        # Multi-select item1
        doc.select_item(item1, exclusive=False)
        self.assertTrue(item1.is_selected)
        self.assertTrue(item2.is_selected)
        self.assertEqual(len(doc.selected_items), 2)

        # Deselect all
        doc.deselect_all()
        self.assertFalse(item1.is_selected)
        self.assertFalse(item2.is_selected)
        self.assertEqual(doc.selected_items, [])

    def test_render_to_surface(self) -> None:
        bg_surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 100, 100)
        bg_cr = cairo.Context(bg_surf)
        bg_cr.set_source_rgba(0.0, 1.0, 0.0, 1.0)  # Green background
        bg_cr.paint()

        doc = AnnotationDocument(surface=bg_surf)
        item = DummyRectItem(10, 10, 20, 20, stroke_color=(1.0, 0.0, 0.0, 1.0), fill_color=(0.0, 0.0, 1.0, 1.0))
        doc.add_item(item)

        flat_surf = doc.render_to_surface(include_background=True)
        self.assertIsInstance(flat_surf, cairo.ImageSurface)
        self.assertEqual(flat_surf.get_width(), 100)
        self.assertEqual(flat_surf.get_height(), 100)

        # Offscreen without background
        transparent_surf = doc.render_to_surface(include_background=False)
        self.assertEqual(transparent_surf.get_width(), 100)

    def test_serialization(self) -> None:
        doc = AnnotationDocument(width=800, height=600, file_path="/path/test.png")
        item = DummyRectItem(5, 5, 20, 20)
        doc.add_item(item)

        data = doc.to_dict()
        self.assertEqual(data["width"], 800)
        self.assertEqual(data["height"], 600)
        self.assertEqual(data["file_path"], "/path/test.png")
        self.assertEqual(len(data["items"]), 1)
        self.assertEqual(data["items"][0]["type"], "dummy_rect")

    def test_canvas_document_integration(self) -> None:
        canvas = Canvas()
        self.assertIsInstance(canvas.document, AnnotationDocument)
        self.assertEqual(canvas.items, [])

        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 120, 80)
        canvas.set_image_surface(surf)
        self.assertEqual(canvas.document.width, 120)
        self.assertEqual(canvas.document.height, 80)
        self.assertIs(canvas.document.background_surface, surf)

        item = DummyRectItem(10, 10, 30, 30)
        canvas.document.add_item(item)
        self.assertEqual(len(canvas.items), 1)

        flattened = canvas.get_flattened_surface()
        self.assertIsNotNone(flattened)
        self.assertEqual(flattened.get_width(), 120)
        self.assertEqual(flattened.get_height(), 80)

        canvas.clear()
        self.assertEqual(canvas.document.width, 0)
        self.assertEqual(canvas.document.height, 0)
        self.assertEqual(canvas.items, [])
