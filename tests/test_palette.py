from __future__ import annotations
import unittest
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk

from gobrush.tools.base import ToolManager, SelectTool
from gobrush.ui.palette import ToolPalette, TOOL_DEFINITIONS
from gobrush.ui.canvas import Canvas
from gobrush.ui.window import MainWindow


class TestToolPalette(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        Gtk.init()

    def test_palette_creation_and_defaults(self) -> None:
        palette = ToolPalette()
        self.assertEqual(len(palette._buttons), 13)

        expected_ids = [
            "select", "text", "pen", "highlighter", "arrow",
            "line", "rectangle", "ellipse", "blur", "badge",
            "checkmark", "cross", "crop"
        ]
        for tid in expected_ids:
            btn = palette.get_button(tid)
            self.assertIsNotNone(btn, f"Button for {tid} should exist")
            self.assertIsInstance(btn, Gtk.ToggleButton)

        select_btn = palette.get_button("select")
        self.assertTrue(select_btn.get_active())
        self.assertEqual(palette.active_tool_id, "select")

        # Non-existent button
        self.assertIsNone(palette.get_button("unknown_tool"))

    def test_palette_tool_definitions(self) -> None:
        self.assertEqual(len(TOOL_DEFINITIONS), 13)
        for tdef in TOOL_DEFINITIONS:
            self.assertIn("id", tdef)
            self.assertIn("label", tdef)
            self.assertIn("tooltip", tdef)
            self.assertIn("icon", tdef)
            self.assertIn("shortcut", tdef)
            self.assertTrue(tdef["label"].endswith(f"({tdef['shortcut']})"))

    def test_palette_with_tool_manager(self) -> None:
        canvas = Canvas()
        mgr = ToolManager(canvas)
        palette = ToolPalette(mgr)

        self.assertIs(palette.tool_manager, mgr)
        self.assertEqual(palette.active_tool_id, "select")
        self.assertTrue(palette.get_button("select").get_active())

        # Switch tool via palette
        self.assertTrue(palette.set_active_tool("pen"))
        self.assertEqual(mgr.active_tool_id, "pen")
        self.assertEqual(palette.active_tool_id, "pen")
        self.assertTrue(palette.get_button("pen").get_active())
        self.assertFalse(palette.get_button("select").get_active())

        # Invalid tool returns False
        self.assertFalse(palette.set_active_tool("nonexistent"))

    def test_tool_manager_sync_to_palette(self) -> None:
        canvas = Canvas()
        mgr = ToolManager(canvas)
        palette = ToolPalette(mgr)

        # Programmatic switch via ToolManager directly
        mgr.set_active_tool("highlighter")
        self.assertEqual(palette.active_tool_id, "highlighter")
        self.assertTrue(palette.get_button("highlighter").get_active())
        self.assertFalse(palette.get_button("select").get_active())

    def test_button_clicked_event(self) -> None:
        canvas = Canvas()
        mgr = ToolManager(canvas)
        palette = ToolPalette(mgr)

        arrow_btn = palette.get_button("arrow")
        arrow_btn.set_active(True)
        arrow_btn.emit("clicked")

        self.assertEqual(mgr.active_tool_id, "arrow")
        self.assertEqual(palette.active_tool_id, "arrow")

    def test_cannot_untoggle_active_tool(self) -> None:
        canvas = Canvas()
        mgr = ToolManager(canvas)
        palette = ToolPalette(mgr)

        select_btn = palette.get_button("select")
        self.assertTrue(select_btn.get_active())

        # Attempt to deactivate active button by clicking while inactive
        select_btn.set_active(False)
        select_btn.emit("clicked")

        self.assertTrue(select_btn.get_active())
        self.assertEqual(mgr.active_tool_id, "select")

    def test_main_window_palette_integration(self) -> None:
        win = MainWindow()
        self.assertIsInstance(win.palette, ToolPalette)
        self.assertEqual(win.palette.active_tool_id, "select")
        self.assertIs(win.palette.tool_manager, win.canvas.tool_manager)

        win.palette.set_active_tool("crop")
        self.assertEqual(win.canvas.tool_manager.active_tool_id, "crop")


if __name__ == "__main__":
    unittest.main()
