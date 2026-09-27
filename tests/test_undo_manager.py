from __future__ import annotations
import unittest
from unittest.mock import Mock
import cairo
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Gdk

from gobrush.core.document import AnnotationDocument
from gobrush.core.history import (
    Command,
    AddAnnotationCommand,
    DeleteAnnotationCommand,
    MoveCommand,
    UndoManager,
)
from gobrush.items.base import AnnotationItem
from gobrush.ui.canvas import Canvas
from gobrush.ui.window import MainWindow


class DummyItem(AnnotationItem):
    type_name = "dummy_item"

    def __init__(self, x: float = 0.0, y: float = 0.0) -> None:
        super().__init__()
        self.x = x
        self.y = y

    def get_bounds(self) -> tuple[float, float, float, float]:
        return self.x, self.y, 20.0, 20.0

    def hit_test(self, x: float, y: float, tolerance: float = 6.0) -> bool:
        return self.x <= x <= self.x + 20.0 and self.y <= y <= self.y + 20.0

    def draw(self, cr: cairo.Context) -> None:
        cr.rectangle(self.x, self.y, 20.0, 20.0)
        cr.stroke()

    def move_by(self, dx: float, dy: float) -> None:
        self.x += dx
        self.y += dy

    def clone(self) -> DummyItem:
        return DummyItem(self.x, self.y)


class SimpleTestCommand(Command):
    def __init__(self, name: str = "Simple Action") -> None:
        self.name = name
        self.executed: int = 0
        self.undone: int = 0

    def execute(self) -> None:
        self.executed += 1

    def undo(self) -> None:
        self.undone += 1


class TestUndoManager(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        Gtk.init()

    def test_initial_state(self) -> None:
        mgr = UndoManager(max_history=50)
        self.assertEqual(mgr.max_history, 50)
        self.assertFalse(mgr.can_undo)
        self.assertFalse(mgr.can_redo)
        self.assertEqual(mgr.undo_count, 0)
        self.assertEqual(mgr.redo_count, 0)
        self.assertIsNone(mgr.undo_command_name)
        self.assertIsNone(mgr.redo_command_name)

    def test_push_and_execute(self) -> None:
        mgr = UndoManager()
        cb = Mock()
        mgr.add_change_callback(cb)

        cmd = SimpleTestCommand("First Action")
        mgr.push(cmd, execute=True)

        self.assertEqual(cmd.executed, 1)
        self.assertEqual(cmd.undone, 0)
        self.assertTrue(mgr.can_undo)
        self.assertFalse(mgr.can_redo)
        self.assertEqual(mgr.undo_count, 1)
        self.assertEqual(mgr.undo_command_name, "First Action")
        self.assertEqual(cb.call_count, 1)

    def test_undo_and_redo_cycle(self) -> None:
        mgr = UndoManager()
        cmd = SimpleTestCommand("Custom Command")
        mgr.push(cmd, execute=True)

        # Undo
        self.assertTrue(mgr.undo())
        self.assertEqual(cmd.undone, 1)
        self.assertFalse(mgr.can_undo)
        self.assertTrue(mgr.can_redo)
        self.assertEqual(mgr.redo_command_name, "Custom Command")

        # Second undo should fail
        self.assertFalse(mgr.undo())

        # Redo
        self.assertTrue(mgr.redo())
        self.assertEqual(cmd.executed, 2)
        self.assertTrue(mgr.can_undo)
        self.assertFalse(mgr.can_redo)

        # Second redo should fail
        self.assertFalse(mgr.redo())

    def test_push_clears_redo_stack(self) -> None:
        mgr = UndoManager()
        cmd1 = SimpleTestCommand("1")
        cmd2 = SimpleTestCommand("2")
        mgr.push(cmd1, execute=True)
        mgr.undo()
        self.assertTrue(mgr.can_redo)

        # New command pushed must clear redo stack
        mgr.push(cmd2, execute=True)
        self.assertFalse(mgr.can_redo)
        self.assertEqual(mgr.undo_count, 1)
        self.assertEqual(mgr.undo_command_name, "2")

    def test_max_history_limit(self) -> None:
        mgr = UndoManager(max_history=3)
        for i in range(5):
            mgr.push(SimpleTestCommand(f"Cmd {i}"), execute=True)

        self.assertEqual(mgr.undo_count, 3)
        self.assertEqual(mgr.undo_command_name, "Cmd 4")

    def test_merge_commands(self) -> None:
        doc = AnnotationDocument(width=200, height=200)
        item = DummyItem(10, 10)
        doc.add_item(item)

        mgr = UndoManager()
        cmd1 = MoveCommand(item, dx=5, dy=0, document=doc)
        cmd2 = MoveCommand(item, dx=10, dy=5, document=doc)

        mgr.push(cmd1, execute=True)
        mgr.push(cmd2, execute=True)

        # Since cmd1 and cmd2 affect the same item, they merge
        self.assertEqual(mgr.undo_count, 1)
        self.assertEqual((item.x, item.y), (25, 15))

        mgr.undo()
        self.assertEqual((item.x, item.y), (10, 10))

    def test_clear(self) -> None:
        mgr = UndoManager()
        mgr.push(SimpleTestCommand(), execute=True)
        cb = Mock()
        mgr.add_change_callback(cb)

        mgr.clear()
        self.assertFalse(mgr.can_undo)
        self.assertFalse(mgr.can_redo)
        self.assertEqual(cb.call_count, 1)

    def test_canvas_integration(self) -> None:
        canvas = Canvas()
        self.assertIsInstance(canvas.undo_manager, UndoManager)

        item = DummyItem(0, 0)
        cmd = AddAnnotationCommand(canvas.document, item)
        canvas.execute_command(cmd)

        self.assertEqual(canvas.document.item_count, 1)
        self.assertTrue(canvas.undo_manager.can_undo)

        # Undo on canvas
        self.assertTrue(canvas.undo())
        self.assertEqual(canvas.document.item_count, 0)

        # Redo on canvas
        self.assertTrue(canvas.redo())
        self.assertEqual(canvas.document.item_count, 1)

        # Clear canvas clears undo
        canvas.clear()
        self.assertFalse(canvas.undo_manager.can_undo)
        self.assertFalse(canvas.undo_manager.can_redo)

    def test_window_ui_binding(self) -> None:
        win = MainWindow()

        # Initially, buttons and actions are insensitive
        self.assertFalse(win.btn_undo.get_sensitive())
        self.assertFalse(win.btn_redo.get_sensitive())
        self.assertFalse(win.lookup_action("undo").get_enabled())
        self.assertFalse(win.lookup_action("redo").get_enabled())

        # Load a canvas
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 200, 200)
        win.load_surface(surf, title="Test")

        self.assertFalse(win.btn_undo.get_sensitive())
        self.assertFalse(win.btn_redo.get_sensitive())

        # Execute command on canvas
        item = DummyItem(10, 10)
        cmd = AddAnnotationCommand(win.canvas.document, item, name="Shape")
        win.canvas.execute_command(cmd)

        # Undo button and action become sensitive with descriptive tooltip
        self.assertTrue(win.btn_undo.get_sensitive())
        self.assertFalse(win.btn_redo.get_sensitive())
        self.assertTrue(win.lookup_action("undo").get_enabled())
        self.assertFalse(win.lookup_action("redo").get_enabled())
        self.assertIn("Undo Shape", win.btn_undo.get_tooltip_text())

        # Perform Undo via window.undo()
        self.assertTrue(win.undo())
        self.assertEqual(win.canvas.document.item_count, 0)
        self.assertFalse(win.btn_undo.get_sensitive())
        self.assertTrue(win.btn_redo.get_sensitive())
        self.assertIn("Redo Shape", win.btn_redo.get_tooltip_text())

        # Perform Redo via window.redo()
        self.assertTrue(win.redo())
        self.assertEqual(win.canvas.document.item_count, 1)
        self.assertTrue(win.btn_undo.get_sensitive())
        self.assertFalse(win.btn_redo.get_sensitive())

    def test_window_keyboard_shortcuts(self) -> None:
        win = MainWindow()
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 100, 100)
        win.load_surface(surf, title="Test")

        item = DummyItem(5, 5)
        cmd = AddAnnotationCommand(win.canvas.document, item)
        win.canvas.execute_command(cmd)

        self.assertEqual(win.canvas.document.item_count, 1)

        # Press Ctrl+Z -> Undo
        handled = win._on_key_pressed(None, Gdk.KEY_z, 0, Gdk.ModifierType.CONTROL_MASK)
        self.assertTrue(handled)
        self.assertEqual(win.canvas.document.item_count, 0)

        # Press Ctrl+Shift+Z -> Redo
        handled = win._on_key_pressed(None, Gdk.KEY_z, 0, Gdk.ModifierType.CONTROL_MASK | Gdk.ModifierType.SHIFT_MASK)
        self.assertTrue(handled)
        self.assertEqual(win.canvas.document.item_count, 1)

        # Press Ctrl+Z -> Undo
        win._on_key_pressed(None, Gdk.KEY_z, 0, Gdk.ModifierType.CONTROL_MASK)
        self.assertEqual(win.canvas.document.item_count, 0)

        # Press Ctrl+Y -> Redo
        handled = win._on_key_pressed(None, Gdk.KEY_y, 0, Gdk.ModifierType.CONTROL_MASK)
        self.assertTrue(handled)
        self.assertEqual(win.canvas.document.item_count, 1)
