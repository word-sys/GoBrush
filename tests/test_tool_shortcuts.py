from __future__ import annotations
import unittest
import cairo
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Gdk

from gobrush.tools.base import ToolManager, TOOL_SHORTCUTS
from gobrush.ui.palette import ToolPalette
from gobrush.ui.canvas import Canvas
from gobrush.ui.window import MainWindow


class TestToolShortcuts(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        Gtk.init()

    def test_tool_shortcuts_dictionary(self) -> None:
        expected_mappings = {
            Gdk.KEY_s: "select",
            Gdk.KEY_S: "select",
            Gdk.KEY_t: "text",
            Gdk.KEY_T: "text",
            Gdk.KEY_p: "pen",
            Gdk.KEY_P: "pen",
            Gdk.KEY_h: "highlighter",
            Gdk.KEY_H: "highlighter",
            Gdk.KEY_a: "arrow",
            Gdk.KEY_A: "arrow",
            Gdk.KEY_l: "line",
            Gdk.KEY_L: "line",
            Gdk.KEY_r: "rectangle",
            Gdk.KEY_R: "rectangle",
            Gdk.KEY_c: "ellipse",
            Gdk.KEY_C: "ellipse",
            Gdk.KEY_b: "blur",
            Gdk.KEY_B: "blur",
            Gdk.KEY_n: "badge",
            Gdk.KEY_N: "badge",
            Gdk.KEY_v: "checkmark",
            Gdk.KEY_V: "checkmark",
            Gdk.KEY_x: "cross",
            Gdk.KEY_X: "cross",
            Gdk.KEY_k: "crop",
            Gdk.KEY_K: "crop",
        }
        for keyval, expected_id in expected_mappings.items():
            self.assertIn(keyval, TOOL_SHORTCUTS)
            self.assertEqual(TOOL_SHORTCUTS[keyval], expected_id)

    def test_single_key_shortcuts_lowercase(self) -> None:
        canvas = Canvas()
        mgr = ToolManager(canvas)
        mgr.register_default_tools()
        palette = ToolPalette(mgr)

        pairs = [
            (Gdk.KEY_p, "pen"),
            (Gdk.KEY_h, "highlighter"),
            (Gdk.KEY_a, "arrow"),
            (Gdk.KEY_l, "line"),
            (Gdk.KEY_r, "rectangle"),
            (Gdk.KEY_c, "ellipse"),
            (Gdk.KEY_b, "blur"),
            (Gdk.KEY_n, "badge"),
            (Gdk.KEY_v, "checkmark"),
            (Gdk.KEY_x, "cross"),
            (Gdk.KEY_k, "crop"),
            (Gdk.KEY_t, "text"),
            (Gdk.KEY_s, "select"),
        ]

        for keyval, expected_tool in pairs:
            handled = mgr.handle_key_pressed(keyval, Gdk.ModifierType(0))
            self.assertTrue(handled, f"Keyval {keyval} should be handled")
            self.assertEqual(mgr.active_tool_id, expected_tool)
            self.assertEqual(palette.active_tool_id, expected_tool)
            btn = palette.get_button(expected_tool)
            self.assertIsNotNone(btn)
            self.assertTrue(btn.get_active())
            self.assertTrue(btn.has_css_class("is-active-tool"))

    def test_single_key_shortcuts_uppercase(self) -> None:
        canvas = Canvas()
        mgr = ToolManager(canvas)
        mgr.register_default_tools()
        palette = ToolPalette(mgr)

        pairs = [
            (Gdk.KEY_P, "pen"),
            (Gdk.KEY_H, "highlighter"),
            (Gdk.KEY_A, "arrow"),
            (Gdk.KEY_L, "line"),
            (Gdk.KEY_R, "rectangle"),
            (Gdk.KEY_C, "ellipse"),
            (Gdk.KEY_B, "blur"),
            (Gdk.KEY_N, "badge"),
            (Gdk.KEY_V, "checkmark"),
            (Gdk.KEY_X, "cross"),
            (Gdk.KEY_K, "crop"),
            (Gdk.KEY_T, "text"),
            (Gdk.KEY_S, "select"),
        ]

        for keyval, expected_tool in pairs:
            handled = mgr.handle_key_pressed(keyval, Gdk.ModifierType.SHIFT_MASK)
            self.assertTrue(handled, f"Keyval {keyval} (Shift) should be handled")
            self.assertEqual(mgr.active_tool_id, expected_tool)
            self.assertEqual(palette.active_tool_id, expected_tool)

    def test_modifiers_prevent_tool_switching(self) -> None:
        canvas = Canvas()
        mgr = ToolManager(canvas)
        mgr.register_default_tools()
        mgr.set_active_tool("select")

        # Ctrl + S should NOT switch tool
        handled = mgr.handle_key_pressed(Gdk.KEY_s, Gdk.ModifierType.CONTROL_MASK)
        self.assertFalse(handled)
        self.assertEqual(mgr.active_tool_id, "select")

        # Alt + P should NOT switch tool
        handled = mgr.handle_key_pressed(Gdk.KEY_p, Gdk.ModifierType.ALT_MASK)
        self.assertFalse(handled)
        self.assertEqual(mgr.active_tool_id, "select")

        # Ctrl + C should NOT switch tool
        handled = mgr.handle_key_pressed(Gdk.KEY_c, Gdk.ModifierType.CONTROL_MASK)
        self.assertFalse(handled)
        self.assertEqual(mgr.active_tool_id, "select")

        # Ctrl + V should NOT switch tool
        handled = mgr.handle_key_pressed(Gdk.KEY_v, Gdk.ModifierType.CONTROL_MASK)
        self.assertFalse(handled)
        self.assertEqual(mgr.active_tool_id, "select")

    def test_escape_resets_to_select(self) -> None:
        canvas = Canvas()
        mgr = ToolManager(canvas)
        mgr.register_default_tools()

        mgr.set_active_tool("pen")
        self.assertEqual(mgr.active_tool_id, "pen")

        handled = mgr.handle_key_pressed(Gdk.KEY_Escape, Gdk.ModifierType(0))
        self.assertTrue(handled)
        self.assertEqual(mgr.active_tool_id, "select")

        # Escape while already on select returns False (allows higher-level handling)
        handled = mgr.handle_key_pressed(Gdk.KEY_Escape, Gdk.ModifierType(0))
        self.assertFalse(handled)
        self.assertEqual(mgr.active_tool_id, "select")

    def test_escape_cancels_drag_when_dragging(self) -> None:
        canvas = Canvas()
        mgr = ToolManager(canvas)
        mgr.register_default_tools()
        mgr.set_active_tool("arrow")

        # Start a drag gesture
        mgr.handle_press(10.0, 10.0, 10.0, 10.0, Gdk.ModifierType(0))
        mgr.handle_drag(50.0, 50.0, 40.0, 40.0, 50.0, 50.0, Gdk.ModifierType(0))
        self.assertTrue(mgr._is_dragging)

        # Escape cancels drag without resetting tool immediately
        handled = mgr.handle_key_pressed(Gdk.KEY_Escape, Gdk.ModifierType(0))
        self.assertTrue(handled)
        self.assertFalse(mgr._is_dragging)
        self.assertEqual(mgr.active_tool_id, "arrow")

        # Second escape resets to select
        handled = mgr.handle_key_pressed(Gdk.KEY_Escape, Gdk.ModifierType(0))
        self.assertTrue(handled)
        self.assertEqual(mgr.active_tool_id, "select")

    def test_unregistered_keys_ignored(self) -> None:
        canvas = Canvas()
        mgr = ToolManager(canvas)
        mgr.register_default_tools()
        mgr.set_active_tool("select")

        for keyval in (Gdk.KEY_q, Gdk.KEY_w, Gdk.KEY_e, Gdk.KEY_F1, Gdk.KEY_Tab):
            handled = mgr.handle_key_pressed(keyval, Gdk.ModifierType(0))
            self.assertFalse(handled)
            self.assertEqual(mgr.active_tool_id, "select")

    def test_main_window_key_routing(self) -> None:
        win = MainWindow()
        # Create a document so window is not empty
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 200, 200)
        win.load_surface(surface)
        self.assertFalse(win.is_empty())

        # Route single key via MainWindow._on_key_pressed
        handled = win._on_key_pressed(None, Gdk.KEY_p, 0, Gdk.ModifierType(0))
        self.assertTrue(handled)
        self.assertEqual(win.palette.active_tool_id, "pen")
        self.assertEqual(win.canvas.tool_manager.active_tool_id, "pen")

        # Switch to Rectangle via 'r'
        handled = win._on_key_pressed(None, Gdk.KEY_r, 0, Gdk.ModifierType(0))
        self.assertTrue(handled)
        self.assertEqual(win.palette.active_tool_id, "rectangle")

        # Reset via Escape
        handled = win._on_key_pressed(None, Gdk.KEY_Escape, 0, Gdk.ModifierType(0))
        self.assertTrue(handled)
        self.assertEqual(win.palette.active_tool_id, "select")


if __name__ == "__main__":
    unittest.main()
