from __future__ import annotations
import unittest
from unittest.mock import Mock
import cairo

from gobrush.core.document import AnnotationDocument
from gobrush.core.history import (
    Command,
    AddAnnotationCommand,
    DeleteAnnotationCommand,
    CompoundCommand,
    MoveCommand,
    ResizeCommand,
    RestyleCommand,
)
from gobrush.items.base import AnnotationItem


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


class ConcreteTestCommand(Command):
    def __init__(self) -> None:
        self.executed: int = 0
        self.undone: int = 0

    def execute(self) -> None:
        self.executed += 1

    def undo(self) -> None:
        self.undone += 1


class TestHistoryCommands(unittest.TestCase):
    def test_base_command_abc(self) -> None:
        with self.assertRaises(TypeError):
            Command()  # type: ignore

        cmd = ConcreteTestCommand()
        self.assertEqual(cmd.executed, 0)
        self.assertEqual(cmd.undone, 0)
        self.assertFalse(cmd.merge_with(ConcreteTestCommand()))

        cmd.execute()
        self.assertEqual(cmd.executed, 1)

        cmd.undo()
        self.assertEqual(cmd.undone, 1)

        # Default redo calls execute
        cmd.redo()
        self.assertEqual(cmd.executed, 2)

    def test_add_annotation_command(self) -> None:
        doc = AnnotationDocument(width=400, height=300)
        item = DummyRectItem(10, 10, 50, 50)
        cmd = AddAnnotationCommand(doc, item, select=True)

        self.assertEqual(doc.item_count, 0)
        self.assertFalse(doc.is_dirty)

        # Execute
        cmd.execute()
        self.assertEqual(doc.item_count, 1)
        self.assertEqual(doc.items, [item])
        self.assertTrue(item.is_selected)
        self.assertIs(doc.selected_item, item)
        self.assertTrue(doc.is_dirty)

        # Undo
        cmd.undo()
        self.assertEqual(doc.item_count, 0)
        self.assertFalse(item.is_selected)
        self.assertIsNone(doc.selected_item)

        # Redo
        cmd.redo()
        self.assertEqual(doc.item_count, 1)
        self.assertEqual(doc.items, [item])
        self.assertTrue(item.is_selected)

    def test_add_annotation_command_with_index(self) -> None:
        doc = AnnotationDocument(width=400, height=300)
        existing1 = DummyRectItem(0, 0, 10, 10)
        existing2 = DummyRectItem(20, 20, 10, 10)
        doc.add_item(existing1)
        doc.add_item(existing2)

        # Insert in the middle at index 1
        middle = DummyRectItem(10, 10, 10, 10)
        cmd = AddAnnotationCommand(doc, middle, index=1, select=False)

        cmd.execute()
        self.assertEqual(doc.items, [existing1, middle, existing2])
        self.assertFalse(middle.is_selected)

        cmd.undo()
        self.assertEqual(doc.items, [existing1, existing2])

        cmd.redo()
        self.assertEqual(doc.items, [existing1, middle, existing2])

    def test_delete_annotation_command_single(self) -> None:
        doc = AnnotationDocument(width=400, height=300)
        item1 = DummyRectItem(0, 0, 10, 10)
        item2 = DummyRectItem(10, 10, 10, 10)
        item3 = DummyRectItem(20, 20, 10, 10)
        doc.add_item(item1)
        doc.add_item(item2)
        doc.add_item(item3)

        doc.select_item(item2)
        self.assertTrue(item2.is_selected)

        cmd = DeleteAnnotationCommand(doc, item2)

        # Execute
        cmd.execute()
        self.assertEqual(doc.items, [item1, item3])
        self.assertIsNone(doc.selected_item)

        # Undo
        cmd.undo()
        self.assertEqual(doc.items, [item1, item2, item3])
        self.assertTrue(item2.is_selected)
        self.assertIs(doc.selected_item, item2)

        # Redo
        cmd.redo()
        self.assertEqual(doc.items, [item1, item3])
        self.assertIsNone(doc.selected_item)

    def test_delete_annotation_command_multiple(self) -> None:
        doc = AnnotationDocument(width=400, height=300)
        items = [DummyRectItem(i * 10, i * 10, 10, 10) for i in range(5)]
        for it in items:
            doc.add_item(it)

        # Select item 1 and item 3
        doc.select_item(items[1], exclusive=False)
        doc.select_item(items[3], exclusive=False)

        cmd = DeleteAnnotationCommand(doc, [items[3], items[1]])

        # Execute delete
        cmd.execute()
        self.assertEqual(doc.items, [items[0], items[2], items[4]])
        self.assertEqual(doc.selected_items, [])

        # Undo restore
        cmd.undo()
        self.assertEqual(doc.items, items)
        self.assertTrue(items[1].is_selected)
        self.assertTrue(items[3].is_selected)

        # Redo
        cmd.redo()
        self.assertEqual(doc.items, [items[0], items[2], items[4]])

    def test_compound_command(self) -> None:
        doc = AnnotationDocument(width=400, height=300)
        item1 = DummyRectItem(0, 0, 10, 10)
        item2 = DummyRectItem(20, 20, 10, 10)

        cmd1 = AddAnnotationCommand(doc, item1, select=False)
        cmd2 = AddAnnotationCommand(doc, item2, select=False)
        compound = CompoundCommand([cmd1, cmd2], name="Add Multiple")

        self.assertEqual(len(compound), 2)
        self.assertEqual(doc.item_count, 0)

        compound.execute()
        self.assertEqual(doc.items, [item1, item2])

        compound.undo()
        self.assertEqual(doc.item_count, 0)

        compound.redo()
        self.assertEqual(doc.items, [item1, item2])

        cmd3 = DummyRectItem(40, 40, 10, 10)
        compound.add(AddAnnotationCommand(doc, cmd3, select=False))
        self.assertEqual(len(compound), 3)

    def test_move_command(self) -> None:
        doc = AnnotationDocument(width=400, height=300)
        item1 = DummyRectItem(10, 20, 30, 40)
        item2 = DummyRectItem(50, 60, 20, 20)
        doc.add_item(item1)
        doc.add_item(item2)
        doc.mark_clean()

        cmd = MoveCommand([item1, item2], dx=15, dy=-5, document=doc)
        self.assertEqual(cmd.name, "Move Annotation")

        # Execute
        cmd.execute()
        self.assertEqual((item1.x, item1.y), (25, 15))
        self.assertEqual((item2.x, item2.y), (65, 55))
        self.assertTrue(doc.is_dirty)

        # Undo
        cmd.undo()
        self.assertEqual((item1.x, item1.y), (10, 20))
        self.assertEqual((item2.x, item2.y), (50, 60))

        # Redo
        cmd.redo()
        self.assertEqual((item1.x, item1.y), (25, 15))
        self.assertEqual((item2.x, item2.y), (65, 55))

    def test_move_command_merge(self) -> None:
        doc = AnnotationDocument(width=400, height=300)
        item = DummyRectItem(0, 0, 10, 10)
        doc.add_item(item)

        cmd1 = MoveCommand(item, dx=10, dy=20, document=doc)
        cmd2 = MoveCommand(item, dx=5, dy=-5, document=doc)
        other_item = DummyRectItem(100, 100, 10, 10)
        cmd3 = MoveCommand(other_item, dx=1, dy=1, document=doc)

        self.assertTrue(cmd1.merge_with(cmd2))
        self.assertEqual(cmd1.dx, 15.0)
        self.assertEqual(cmd1.dy, 15.0)

        self.assertFalse(cmd1.merge_with(cmd3))

    def test_resize_command_tuple(self) -> None:
        doc = AnnotationDocument(width=400, height=300)
        item = DummyRectItem(10, 10, 20, 30)
        doc.add_item(item)
        doc.mark_clean()

        old_geom = (10, 10, 20, 30)
        new_geom = (10, 10, 50, 60)
        cmd = ResizeCommand(item, old_geom, new_geom, document=doc)

        # Execute
        cmd.execute()
        self.assertEqual((item.x, item.y, item.w, item.h), (10, 10, 50, 60))
        self.assertTrue(doc.is_dirty)

        # Undo
        cmd.undo()
        self.assertEqual((item.x, item.y, item.w, item.h), (10, 10, 20, 30))

        # Redo
        cmd.redo()
        self.assertEqual((item.x, item.y, item.w, item.h), (10, 10, 50, 60))

    def test_resize_command_dict_and_merge(self) -> None:
        doc = AnnotationDocument(width=400, height=300)
        item = DummyRectItem(0, 0, 10, 10)
        doc.add_item(item)

        cmd1 = ResizeCommand(item, {"w": 10, "h": 10}, {"w": 25, "h": 30}, document=doc)
        cmd2 = ResizeCommand(item, {"w": 25, "h": 30}, {"w": 50, "h": 60}, document=doc)

        self.assertTrue(cmd1.merge_with(cmd2))
        self.assertEqual(cmd1.new_geometry, {"w": 50, "h": 60})

        cmd1.execute()
        self.assertEqual(item.w, 50)
        self.assertEqual(item.h, 60)

        cmd1.undo()
        self.assertEqual(item.w, 10)
        self.assertEqual(item.h, 10)

    def test_restyle_command(self) -> None:
        doc = AnnotationDocument(width=400, height=300)
        item = DummyRectItem(0, 0, 10, 10, stroke_color=(1.0, 0.0, 0.0, 1.0), stroke_width=2.0)
        doc.add_item(item)
        doc.mark_clean()

        cmd = RestyleCommand(
            item,
            stroke_color=(0.0, 1.0, 0.0, 1.0),
            stroke_width=5.0,
            fill_color=(0.0, 0.0, 1.0, 0.8),
            document=doc,
        )

        # Execute
        cmd.execute()
        self.assertEqual(item.stroke_color, (0.0, 1.0, 0.0, 1.0))
        self.assertEqual(item.stroke_width, 5.0)
        self.assertEqual(item.fill_color, (0.0, 0.0, 1.0, 0.8))
        self.assertTrue(doc.is_dirty)

        # Undo
        cmd.undo()
        self.assertEqual(item.stroke_color, (1.0, 0.0, 0.0, 1.0))
        self.assertEqual(item.stroke_width, 2.0)
        self.assertIsNone(item.fill_color)

        # Redo
        cmd.redo()
        self.assertEqual(item.stroke_color, (0.0, 1.0, 0.0, 1.0))
        self.assertEqual(item.stroke_width, 5.0)
        self.assertEqual(item.fill_color, (0.0, 0.0, 1.0, 0.8))

    def test_restyle_command_clear_fill(self) -> None:
        doc = AnnotationDocument(width=400, height=300)
        item = DummyRectItem(0, 0, 10, 10, fill_color=(1.0, 1.0, 0.0, 1.0))
        doc.add_item(item)

        cmd = RestyleCommand(item, clear_fill=True, document=doc)
        cmd.execute()
        self.assertIsNone(item.fill_color)

        cmd.undo()
        self.assertEqual(item.fill_color, (1.0, 1.0, 0.0, 1.0))

