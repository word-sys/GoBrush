from __future__ import annotations
import unittest
from unittest.mock import Mock
import cairo
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Gdk

from gobrush.tools.base import BaseTool, SelectTool, ToolManager
from gobrush.ui.canvas import Canvas


class RecordingTool(BaseTool):
    tool_id = "recording"
    name = "Recording Tool"
    cursor_name = "crosshair"

    def __init__(self, canvas: Canvas | None = None) -> None:
        super().__init__(canvas)
        self.presses: list[tuple[float, float, float, float]] = []
        self.drags: list[tuple[float, float, float, float]] = []
        self.releases: list[tuple[float, float, float, float]] = []
        self.cancels: int = 0
        self.motions: list[tuple[float, float]] = []
        self.key_presses: list[int] = []
        self.overlays_drawn: int = 0
        self.screen_overlays_drawn: int = 0

    def on_press(
        self, ix: float, iy: float, sx: float, sy: float, state: Gdk.ModifierType
    ) -> bool:
        self.presses.append((ix, iy, sx, sy))
        return True

    def on_drag(
        self, ix: float, iy: float, dx: float, dy: float, sx: float, sy: float, state: Gdk.ModifierType
    ) -> bool:
        self.drags.append((ix, iy, dx, dy))
        return True

    def on_release(
        self, ix: float, iy: float, sx: float, sy: float, state: Gdk.ModifierType
    ) -> bool:
        self.releases.append((ix, iy, sx, sy))
        return True

    def on_cancel(self) -> None:
        self.cancels += 1

    def on_motion(
        self, ix: float, iy: float, sx: float, sy: float, state: Gdk.ModifierType
    ) -> bool:
        self.motions.append((ix, iy))
        return True

    def on_key_pressed(self, keyval: int, state: Gdk.ModifierType) -> bool:
        self.key_presses.append(keyval)
        return True

    def draw_overlay(self, cr: cairo.Context) -> None:
        self.overlays_drawn += 1

    def draw_screen_overlay(self, cr: cairo.Context, width: int, height: int) -> None:
        self.screen_overlays_drawn += 1


class TestToolsBase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        Gtk.init()

    def test_base_tool_defaults(self) -> None:
        tool = BaseTool()
        self.assertEqual(tool.tool_id, "base")
        self.assertEqual(tool.name, "Base Tool")
        self.assertEqual(tool.cursor_name, "default")
        self.assertFalse(tool.is_active)
        self.assertIsNone(tool.canvas)

        tool.activate()
        self.assertTrue(tool.is_active)

        tool.deactivate()
        self.assertFalse(tool.is_active)

        # Default event handlers return False or do nothing
        self.assertFalse(tool.on_press(0, 0, 0, 0, Gdk.ModifierType(0)))
        self.assertFalse(tool.on_drag(0, 0, 0, 0, 0, 0, Gdk.ModifierType(0)))
        self.assertFalse(tool.on_release(0, 0, 0, 0, Gdk.ModifierType(0)))
        self.assertFalse(tool.on_motion(0, 0, 0, 0, Gdk.ModifierType(0)))
        self.assertFalse(tool.on_key_pressed(Gdk.KEY_a, Gdk.ModifierType(0)))
        self.assertFalse(tool.on_key_released(Gdk.KEY_a, Gdk.ModifierType(0)))
        tool.on_cancel()

    def test_select_tool(self) -> None:
        select_tool = SelectTool()
        self.assertEqual(select_tool.tool_id, "select")
        self.assertEqual(select_tool.name, "Select")
        self.assertEqual(select_tool.cursor_name, "default")

    def test_tool_manager_registration_and_switching(self) -> None:
        canvas = Canvas()
        mgr = ToolManager(canvas)

        tool1 = SelectTool()
        tool2 = RecordingTool()

        mgr.register_tool(tool1)
        mgr.register_tool(tool2)

        self.assertIs(tool1.canvas, canvas)
        self.assertIs(tool2.canvas, canvas)
        self.assertIs(mgr.get_tool("select"), tool1)
        self.assertIs(mgr.get_tool("recording"), tool2)
        self.assertIsNone(mgr.get_tool("unknown"))

        cb = Mock()
        mgr.add_tool_changed_callback(cb)

        # Set active tool by ID
        self.assertTrue(mgr.set_active_tool("recording"))
        self.assertIs(mgr.active_tool, tool2)
        self.assertEqual(mgr.active_tool_id, "recording")
        self.assertTrue(tool2.is_active)
        self.assertEqual(canvas.tool_cursor_name, "crosshair")
        self.assertEqual(cb.call_count, 1)

        # Switching to another tool deactivates previous
        self.assertTrue(mgr.set_active_tool("select"))
        self.assertIs(mgr.active_tool, tool1)
        self.assertFalse(tool2.is_active)
        self.assertTrue(tool1.is_active)
        self.assertEqual(canvas.tool_cursor_name, "default")
        self.assertEqual(cb.call_count, 2)

        # Set active to None
        self.assertTrue(mgr.set_active_tool(None))
        self.assertIsNone(mgr.active_tool)
        self.assertFalse(tool1.is_active)
        self.assertIsNone(canvas.tool_cursor_name)
        self.assertEqual(cb.call_count, 3)

        # Invalid tool ID
        self.assertFalse(mgr.set_active_tool("invalid_id"))

    def test_tool_manager_event_forwarding(self) -> None:
        canvas = Canvas()
        mgr = ToolManager(canvas)
        tool = RecordingTool()
        mgr.register_tool(tool)
        mgr.set_active_tool("recording")

        # Press
        self.assertFalse(mgr.is_dragging)
        res = mgr.handle_press(10.0, 20.0, 100.0, 200.0, Gdk.ModifierType(0))
        self.assertTrue(res)
        self.assertTrue(mgr.is_dragging)
        self.assertEqual(tool.presses, [(10.0, 20.0, 100.0, 200.0)])

        # Drag
        res = mgr.handle_drag(15.0, 25.0, 5.0, 5.0, 105.0, 205.0, Gdk.ModifierType(0))
        self.assertTrue(res)
        self.assertEqual(tool.drags, [(15.0, 25.0, 5.0, 5.0)])

        # Release
        res = mgr.handle_release(20.0, 30.0, 110.0, 210.0, Gdk.ModifierType(0))
        self.assertTrue(res)
        self.assertFalse(mgr.is_dragging)
        self.assertEqual(tool.releases, [(20.0, 30.0, 110.0, 210.0)])

        # Motion (hover)
        res = mgr.handle_motion(30.0, 40.0, 120.0, 220.0, Gdk.ModifierType(0))
        self.assertTrue(res)
        self.assertEqual(tool.motions, [(30.0, 40.0)])

        # Key pressed
        res = mgr.handle_key_pressed(Gdk.KEY_Delete, Gdk.ModifierType(0))
        self.assertTrue(res)
        self.assertEqual(tool.key_presses, [Gdk.KEY_Delete])

    def test_escape_cancels_drag(self) -> None:
        mgr = ToolManager()
        tool = RecordingTool()
        mgr.register_tool(tool)
        mgr.set_active_tool("recording")

        mgr.handle_press(10.0, 10.0, 10.0, 10.0, Gdk.ModifierType(0))
        self.assertTrue(mgr.is_dragging)

        # Pressing Escape cancels active drag
        handled = mgr.handle_key_pressed(Gdk.KEY_Escape, Gdk.ModifierType(0))
        self.assertTrue(handled)
        self.assertFalse(mgr.is_dragging)
        self.assertEqual(tool.cancels, 1)

    def test_tool_overlays(self) -> None:
        mgr = ToolManager()
        tool = RecordingTool()
        mgr.register_tool(tool)
        mgr.set_active_tool("recording")

        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 100, 100)
        cr = cairo.Context(surface)

        mgr.draw_overlay(cr)
        self.assertEqual(tool.overlays_drawn, 1)

        mgr.draw_screen_overlay(cr, 100, 100)
        self.assertEqual(tool.screen_overlays_drawn, 1)

    def test_canvas_tool_interaction(self) -> None:
        canvas = Canvas()
        tool = RecordingTool()
        canvas.tool_manager.register_tool(tool)
        canvas.tool_manager.set_active_tool("recording")

        gesture = canvas._primary_drag

        # Drag begin
        canvas._on_primary_drag_begin(gesture, 50.0, 50.0)
        self.assertFalse(canvas.is_panning)
        self.assertEqual(len(tool.presses), 1)

        # Drag update
        canvas._on_primary_drag_update(gesture, 20.0, 30.0)
        self.assertFalse(canvas.is_panning)
        self.assertEqual(len(tool.drags), 1)

        # Drag end
        canvas._on_primary_drag_end(gesture, 20.0, 30.0)
        self.assertFalse(canvas.is_panning)
        self.assertEqual(len(tool.releases), 1)
