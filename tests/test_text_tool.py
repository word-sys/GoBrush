from __future__ import annotations
import unittest
import cairo
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gtk, Gdk

from gobrush.items.base import (
    HANDLE_TOP_LEFT,
    HANDLE_BOTTOM_RIGHT,
    ALL_BOX_HANDLES,
)
from gobrush.items.text import (
    TextItem,
    measure_text_layout,
    render_text_layout,
)
from gobrush.tools.text import TextTool
from gobrush.tools.select import SelectTool
from gobrush.ui.canvas import Canvas
from gobrush.ui.property_bar import ContextPropertyBar


class TestTextItem(unittest.TestCase):
    def test_creation_and_defaults(self) -> None:
        item = TextItem(20.0, 30.0, "API Endpoint")
        self.assertEqual(item.x, 20.0)
        self.assertEqual(item.y, 30.0)
        self.assertEqual(item.text, "API Endpoint")
        self.assertEqual(item.font_size, 20.0)
        self.assertEqual(item.font_family, "Sans")
        self.assertEqual(item.font_weight, "bold")
        self.assertEqual(item.color, (0.88, 0.11, 0.14, 1.0))
        self.assertIsNone(item.fill_color)
        self.assertEqual(item.background_style, "pill")
        self.assertTrue(item.shadow)
        self.assertEqual(item.type_name, "text")
        self.assertTrue(item.is_visible)
        self.assertFalse(item.is_selected)

    def test_measure_and_render_layout(self) -> None:
        w, h = measure_text_layout("Hello GoBrush", font_size=24.0, font_weight="bold")
        self.assertGreater(w, 20.0)
        self.assertGreater(h, 15.0)

        # Render onto a test surface
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 200, 100)
        cr = cairo.Context(surf)
        rw, rh = render_text_layout(cr, "Hello GoBrush", font_size=24.0)
        self.assertGreater(rw, 0.0)
        self.assertGreater(rh, 0.0)

    def test_bounds_pill_badge(self) -> None:
        item = TextItem(10.0, 15.0, "Badge", font_size=18.0, background_style="pill", padding_x=12.0, padding_y=6.0)
        bx, by, bw, bh = item.get_bounds()
        tw, th = item.get_text_size()
        self.assertEqual(bx, 10.0)
        self.assertEqual(by, 15.0)
        self.assertAlmostEqual(bw, tw + 24.0, delta=1.0)
        self.assertAlmostEqual(bh, th + 12.0, delta=1.0)

    def test_bounds_none_badge(self) -> None:
        item = TextItem(10.0, 15.0, "Plain Text", font_size=18.0, background_style="none")
        bx, by, bw, bh = item.get_bounds()
        tw, th = item.get_text_size()
        self.assertEqual(bx, 10.0)
        self.assertEqual(by, 15.0)
        self.assertAlmostEqual(bw, tw, delta=1.0)
        self.assertAlmostEqual(bh, th, delta=1.0)

    def test_hit_test(self) -> None:
        item = TextItem(50.0, 50.0, "Click Me", font_size=20.0, background_style="pill")
        bx, by, bw, bh = item.get_bounds()

        # Center inside bounds -> Hit
        self.assertTrue(item.hit_test(bx + bw / 2.0, by + bh / 2.0, tolerance=4.0))
        # Top-left corner -> Hit
        self.assertTrue(item.hit_test(bx, by, tolerance=4.0))
        # Slightly outside within tolerance -> Hit
        self.assertTrue(item.hit_test(bx - 3.0, by - 3.0, tolerance=6.0))
        # Far outside -> Miss
        self.assertFalse(item.hit_test(10.0, 10.0, tolerance=4.0))
        self.assertFalse(item.hit_test(300.0, 300.0, tolerance=4.0))

    def test_draw_pill_and_box(self) -> None:
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 300, 100)
        cr = cairo.Context(surf)

        # Pill with auto contrast badge
        item1 = TextItem(10.0, 10.0, "Auto Pill", background_style="pill", shadow=True)
        item1.draw(cr)

        # Box with explicit fill color
        item2 = TextItem(
            150.0,
            10.0,
            "Box Badge",
            background_style="box",
            fill_color=(0.2, 0.4, 0.9, 0.8),
            shadow=False,
        )
        item2.draw(cr)

    def test_draw_none_background_with_shadow(self) -> None:
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 200, 100)
        cr = cairo.Context(surf)

        item = TextItem(20.0, 20.0, "Shadow Text", background_style="none", shadow=True)
        item.draw(cr)

    def test_move_by(self) -> None:
        item = TextItem(10.0, 20.0, "Mover")
        item.move_by(15.0, -5.0)
        self.assertEqual(item.x, 25.0)
        self.assertEqual(item.y, 15.0)

    def test_geometry_tuple_scaling(self) -> None:
        item = TextItem(10.0, 20.0, "Scale Test", font_size=20.0)
        _, _, _, orig_h = item.get_bounds()
        # Scale 1.5x in height
        target_h = orig_h * 1.5
        item.set_geometry((30.0, 40.0, 100.0, target_h))
        self.assertEqual(item.x, 30.0)
        self.assertEqual(item.y, 40.0)
        self.assertAlmostEqual(item.font_size, 30.0, delta=2.0)

    def test_geometry_dict_update(self) -> None:
        item = TextItem(10.0, 20.0, "Old Text", font_size=20.0)
        item.set_geometry({"text": "New Text", "font_size": 28.0, "background_style": "none"})
        self.assertEqual(item.text, "New Text")
        self.assertEqual(item.font_size, 28.0)
        self.assertEqual(item.background_style, "none")

    def test_apply_style(self) -> None:
        item = TextItem(10.0, 20.0, "Style Me", font_size=16.0)
        item.apply_style(
            stroke_color=(0.1, 0.9, 0.2, 1.0),
            stroke_width=32.0,
            fill_color=(0.0, 0.0, 0.0, 0.5),
        )
        self.assertEqual(item.color, (0.1, 0.9, 0.2, 1.0))
        self.assertEqual(item.font_size, 32.0)
        self.assertEqual(item.fill_color, (0.0, 0.0, 0.0, 0.5))
        self.assertEqual(item.background_style, "pill")

        # Clear fill
        item.apply_style(clear_fill=True)
        self.assertIsNone(item.fill_color)
        self.assertEqual(item.background_style, "none")

    def test_clone(self) -> None:
        item = TextItem(15.0, 25.0, "Original", font_size=22.0, background_style="box")
        cloned = item.clone()
        self.assertIsNot(item, cloned)
        self.assertEqual(cloned.x, item.x)
        self.assertEqual(cloned.y, item.y)
        self.assertEqual(cloned.text, item.text)
        self.assertEqual(cloned.font_size, item.font_size)
        self.assertEqual(cloned.background_style, item.background_style)

        cloned.move_by(10.0, 10.0)
        self.assertEqual(item.x, 15.0)
        self.assertEqual(cloned.x, 25.0)

    def test_serialization(self) -> None:
        item = TextItem(
            30.0,
            40.0,
            "Serialized Callout",
            font_size=24.0,
            font_family="Monospace",
            font_weight="bold",
            color=(0.1, 0.2, 0.3, 1.0),
            fill_color=(0.9, 0.8, 0.7, 0.6),
            background_style="pill",
            shadow=True,
            padding_x=14.0,
            padding_y=8.0,
        )
        d = item.to_dict()
        self.assertEqual(d["type"], "text")
        self.assertEqual(d["text"], "Serialized Callout")
        self.assertEqual(d["font_size"], 24.0)
        self.assertEqual(d["background_style"], "pill")

        restored = TextItem.from_dict(d)
        self.assertEqual(restored.x, item.x)
        self.assertEqual(restored.y, item.y)
        self.assertEqual(restored.text, item.text)
        self.assertEqual(restored.font_size, item.font_size)
        self.assertEqual(restored.font_family, item.font_family)
        self.assertEqual(restored.fill_color, item.fill_color)
        self.assertEqual(restored.background_style, item.background_style)

    def test_handles_protocol(self) -> None:
        item = TextItem(50.0, 60.0, "Handle Test", font_size=20.0)
        item.is_selected = True
        handles = item.get_handles()
        self.assertEqual(len(handles), len(ALL_BOX_HANDLES))
        for h_name in (HANDLE_TOP_LEFT, HANDLE_BOTTOM_RIGHT):
            self.assertIn(h_name, handles)

        tl_x, tl_y = handles[HANDLE_TOP_LEFT]
        self.assertEqual(item.get_handle_at(tl_x, tl_y, handle_radius=8.0), HANDLE_TOP_LEFT)


class TestTextTool(unittest.TestCase):
    def setUp(self) -> None:
        self.canvas = Canvas()
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 600, 400)
        self.canvas.set_image_surface(surf)
        self.tool = self.canvas.tool_manager.get_tool("text")
        self.assertIsNotNone(self.tool)
        self.assertIsInstance(self.tool, TextTool)

    def test_metadata(self) -> None:
        self.assertEqual(self.tool.tool_id, "text")
        self.assertEqual(self.tool.name, "Text")
        self.assertEqual(self.tool.shortcut, "T")
        self.assertEqual(self.tool.cursor_name, "text")

    def test_activation_and_sync(self) -> None:
        mgr = self.canvas.tool_manager
        mgr.set_current_color((0.12, 0.34, 0.56, 1.0))
        mgr.set_stroke_width(24.0)
        mgr.set_fill_mode("semi")
        mgr.set_fill_opacity(0.4)

        mgr.set_active_tool("text")
        self.assertTrue(self.tool.is_active)
        self.assertEqual(self.tool.color, (0.12, 0.34, 0.56, 1.0))
        self.assertEqual(self.tool.font_size, 24.0)
        self.assertEqual(self.tool.background_style, "pill")
        self.assertIsNotNone(self.tool.fill_color)

    def test_commit_text_programmatic(self) -> None:
        self.canvas.tool_manager.set_active_tool("text")
        item = self.tool.commit_text("Important Notice", x=100.0, y=120.0, font_size=22.0)
        self.assertIsNotNone(item)
        self.assertIn(item, self.canvas.document.items)
        self.assertEqual(item.text, "Important Notice")
        self.assertEqual(item.x, 100.0)
        self.assertEqual(item.y, 120.0)
        self.assertEqual(item.font_size, 22.0)

    def test_start_and_commit_editing(self) -> None:
        self.canvas.tool_manager.set_active_tool("text")
        self.tool.start_editing(80.0, 90.0)
        self.assertTrue(self.tool.is_editing)
        self.assertEqual(self.tool.edit_pos, (80.0, 90.0))

        self.tool.set_text("Fix Database Query")
        self.assertEqual(self.tool.current_text, "Fix Database Query")

        item = self.tool.commit_editing()
        self.assertIsNotNone(item)
        self.assertFalse(self.tool.is_editing)
        self.assertEqual(item.text, "Fix Database Query")
        self.assertIn(item, self.canvas.document.items)
        self.assertTrue(item.is_selected)

    def test_cancel_editing(self) -> None:
        self.canvas.tool_manager.set_active_tool("text")
        self.tool.start_editing(50.0, 50.0)
        self.tool.set_text("Draft to discard")
        self.tool.cancel_editing()
        self.assertFalse(self.tool.is_editing)
        self.assertEqual(len(self.canvas.document.items), 0)

    def test_empty_text_ignored(self) -> None:
        self.canvas.tool_manager.set_active_tool("text")
        self.tool.start_editing(50.0, 50.0)
        self.tool.set_text("   ")
        item = self.tool.commit_editing()
        self.assertIsNone(item)
        self.assertEqual(len(self.canvas.document.items), 0)

    def test_on_press_creates_editing_session(self) -> None:
        self.canvas.tool_manager.set_active_tool("text")
        handled = self.tool.on_press(150.0, 160.0, 150.0, 160.0, Gdk.ModifierType(0))
        self.assertTrue(handled)
        self.assertTrue(self.tool.is_editing)
        self.assertEqual(self.tool.edit_pos, (150.0, 160.0))

        self.tool.set_text("Press Added")
        item = self.tool.commit_editing()
        self.assertIsNotNone(item)
        self.assertEqual(item.text, "Press Added")

    def test_on_press_existing_item_edits_it(self) -> None:
        # Pre-populate document with a text item
        item = TextItem(100.0, 100.0, "Original Note", font_size=20.0)
        self.canvas.document.add_item(item)

        self.canvas.tool_manager.set_active_tool("text")
        bx, by, bw, bh = item.get_bounds()
        # Click on existing item
        self.tool.on_press(bx + bw / 2.0, by + bh / 2.0, 100.0, 100.0, Gdk.ModifierType(0))
        self.assertTrue(self.tool.is_editing)
        self.assertEqual(self.tool.current_text, "Original Note")

        self.tool.set_text("Updated Note")
        self.tool.commit_editing()
        self.assertEqual(item.text, "Updated Note")
        self.assertEqual(len(self.canvas.document.items), 1)

    def test_undo_and_redo(self) -> None:
        self.canvas.tool_manager.set_active_tool("text")
        item = self.tool.commit_text("Undoable Text", 40.0, 40.0)
        self.assertEqual(len(self.canvas.document.items), 1)

        self.canvas.undo()
        self.assertEqual(len(self.canvas.document.items), 0)

        self.canvas.redo()
        self.assertEqual(len(self.canvas.document.items), 1)
        self.assertEqual(self.canvas.document.items[0].text, "Undoable Text")

    def test_draw_overlay(self) -> None:
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 400, 300)
        cr = cairo.Context(surf)

        self.canvas.tool_manager.set_active_tool("text")
        # Empty text -> renders insertion cursor
        self.tool.start_editing(50.0, 50.0)
        self.tool.draw_overlay(cr)

        # Non-empty text -> renders live badge preview
        self.tool.set_text("Live Previewing")
        self.tool.draw_overlay(cr)

    def test_key_press_events(self) -> None:
        self.canvas.tool_manager.set_active_tool("text")
        self.tool.start_editing(60.0, 60.0)
        self.tool.set_text("Escape Me")

        handled_esc = self.tool.on_key_pressed(Gdk.KEY_Escape, Gdk.ModifierType(0))
        self.assertTrue(handled_esc)
        self.assertFalse(self.tool.is_editing)
        self.assertEqual(len(self.canvas.document.items), 0)

        self.tool.start_editing(60.0, 60.0)
        self.tool.set_text("Enter Me")
        handled_enter = self.tool.on_key_pressed(Gdk.KEY_Return, Gdk.ModifierType(0))
        self.assertTrue(handled_enter)
        self.assertFalse(self.tool.is_editing)
        self.assertEqual(len(self.canvas.document.items), 1)

    def test_select_tool_resize_text_font_size(self) -> None:
        item = TextItem(50.0, 50.0, "Resize Font", font_size=20.0)
        self.canvas.document.add_item(item)
        self.canvas.document.select_item(item)

        select_tool = self.canvas.tool_manager.get_tool("select")
        self.canvas.tool_manager.set_active_tool("select")

        # Emulate dragging bottom right handle
        handles = item.get_handles()
        br_x, br_y = handles[HANDLE_BOTTOM_RIGHT]
        initial_geom = item.get_geometry()

        select_tool._apply_handle_resize(item, HANDLE_BOTTOM_RIGHT, initial_geom, dx=50.0, dy=40.0)
        self.assertGreater(item.font_size, 20.0)

    def test_select_tool_restyle_text(self) -> None:
        item = TextItem(50.0, 50.0, "Restyle Font", font_size=18.0)
        self.canvas.document.add_item(item)
        self.canvas.document.select_item(item)

        self.canvas.tool_manager.set_active_tool("select")
        mgr = self.canvas.tool_manager
        mgr.set_current_color((0.2, 0.8, 0.4, 1.0))
        mgr.set_stroke_width(32.0)

        self.assertEqual(item.color, (0.2, 0.8, 0.4, 1.0))
        self.assertEqual(item.font_size, 32.0)

    def test_property_bar_tool_labels(self) -> None:
        prop_bar = ContextPropertyBar()
        prop_bar.set_tool_manager(self.canvas.tool_manager)

        # Switch to text
        self.canvas.tool_manager.set_active_tool("text")
        self.assertEqual(prop_bar.label_size.get_text(), "Font Size")
        self.assertEqual(prop_bar.label_fill.get_text(), "Badge")

        # Switch to rectangle
        self.canvas.tool_manager.set_active_tool("rectangle")
        self.assertEqual(prop_bar.label_size.get_text(), "Size")
        self.assertEqual(prop_bar.label_fill.get_text(), "Fill")

    def test_on_cancel_does_not_abort_active_editing(self) -> None:
        self.canvas.tool_manager.set_active_tool("text")
        self.tool.start_editing(50.0, 50.0)
        self.assertTrue(self.tool.is_editing)

        # Trigger on_cancel (such as pointer leave or gesture drag cancel)
        self.tool.on_cancel()
        self.assertTrue(self.tool.is_editing)

        # Explicit cancel_editing DOES abort
        self.tool.cancel_editing()
        self.assertFalse(self.tool.is_editing)

    def test_shortcut_does_not_switch_tool_while_editing(self) -> None:
        self.canvas.tool_manager.set_active_tool("text")
        self.tool.start_editing(50.0, 50.0)
        self.assertTrue(self.tool.is_editing)

        # Pressing 'S' or 'P' while editing text should NOT switch tools
        handled = self.canvas.tool_manager.handle_key_pressed(Gdk.KEY_s, Gdk.ModifierType(0))
        self.assertEqual(self.canvas.tool_manager.active_tool_id, "text")
        self.assertTrue(self.tool.is_editing)

        handled = self.canvas.tool_manager.handle_key_pressed(Gdk.KEY_p, Gdk.ModifierType(0))
        self.assertEqual(self.canvas.tool_manager.active_tool_id, "text")
        self.assertTrue(self.tool.is_editing)


if __name__ == "__main__":
    unittest.main()
