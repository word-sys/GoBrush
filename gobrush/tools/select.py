from __future__ import annotations
from typing import TYPE_CHECKING
import cairo
import gi

gi.require_version("Gdk", "4.0")
from gi.repository import Gdk

from gobrush.tools.base import BaseTool
from gobrush.items.base import AnnotationItem
from gobrush.core.history import DeleteAnnotationCommand, RestyleCommand

if TYPE_CHECKING:
    from gobrush.ui.canvas import Canvas


class SelectTool(BaseTool):
    tool_id: str = "select"
    name: str = "Select"
    shortcut: str = "S"
    icon_name: str = "edit-select-symbolic"
    cursor_name: str | None = "default"

    def __init__(self, canvas: Canvas | None = None) -> None:
        super().__init__(canvas)
        self._press_pos: tuple[float, float] | None = None
        self._press_screen: tuple[float, float] | None = None
        self._hit_item: AnnotationItem | None = None
        self._has_dragged: bool = False
        self._selected_on_press_was_already_selected: bool = False
        self._is_marquee: bool = False
        self._marquee_start: tuple[float, float] = (0.0, 0.0)
        self._marquee_end: tuple[float, float] = (0.0, 0.0)
        self._is_syncing_style: bool = False

    def activate(self) -> None:
        super().activate()
        if self.canvas and self.canvas.tool_manager:
            mgr = self.canvas.tool_manager
            mgr.add_color_changed_callback(self._on_manager_color_changed)
            mgr.add_style_changed_callback(self._on_manager_style_changed)
        self._sync_style_from_selection()

    def deactivate(self) -> None:
        super().deactivate()
        if self.canvas and self.canvas.tool_manager:
            mgr = self.canvas.tool_manager
            mgr.remove_color_changed_callback(self._on_manager_color_changed)
            mgr.remove_style_changed_callback(self._on_manager_style_changed)
        if self.canvas:
            self.canvas.set_cursor(None)
        self._reset_interaction()

    @property
    def is_marquee(self) -> bool:
        return self._is_marquee

    @property
    def marquee_bounds(self) -> tuple[float, float, float, float] | None:
        if not self._is_marquee:
            return None
        x1 = min(self._marquee_start[0], self._marquee_end[0])
        y1 = min(self._marquee_start[1], self._marquee_end[1])
        w = abs(self._marquee_end[0] - self._marquee_start[0])
        h = abs(self._marquee_end[1] - self._marquee_start[1])
        return x1, y1, w, h

    @property
    def selected_items(self) -> list[AnnotationItem]:
        if self.canvas and self.canvas.document:
            return self.canvas.document.selected_items
        return []

    @property
    def selected_item(self) -> AnnotationItem | None:
        if self.canvas and self.canvas.document:
            return self.canvas.document.selected_item
        return None

    def select_item(self, item: AnnotationItem | None, exclusive: bool = True) -> None:
        if self.canvas and self.canvas.document:
            self.canvas.document.select_item(item, exclusive=exclusive)
            self._sync_style_from_selection()

    def deselect_all(self) -> None:
        if self.canvas and self.canvas.document:
            self.canvas.document.deselect_all()

    def hit_test(self, ix: float, iy: float, tolerance: float | None = None) -> AnnotationItem | None:
        if not self.canvas or not self.canvas.document:
            return None
        if tolerance is None:
            zoom = self.canvas.zoom if self.canvas.zoom > 0 else 1.0
            tolerance = 6.0 / max(0.01, zoom)
        return self.canvas.document.hit_test(ix, iy, tolerance=tolerance)

    def on_press(
        self, ix: float, iy: float, sx: float, sy: float, state: Gdk.ModifierType
    ) -> bool:
        self._press_pos = (ix, iy)
        self._press_screen = (sx, sy)
        self._has_dragged = False
        self._selected_on_press_was_already_selected = False

        if not self.canvas or not self.canvas.document:
            return False

        doc = self.canvas.document
        hit = self.hit_test(ix, iy)
        self._hit_item = hit

        is_shift = bool(state & Gdk.ModifierType.SHIFT_MASK)
        is_ctrl = bool(state & Gdk.ModifierType.CONTROL_MASK)

        if hit is not None:
            if is_shift or is_ctrl:
                if hit.is_selected:
                    hit.is_selected = False
                    doc.notify_changed()
                else:
                    doc.select_item(hit, exclusive=False)
            else:
                if hit.is_selected:
                    self._selected_on_press_was_already_selected = True
                else:
                    doc.select_item(hit, exclusive=True)
            self._sync_style_from_selection()
            return True
        else:
            if not is_shift and not is_ctrl:
                self._is_marquee = True
                self._marquee_start = (ix, iy)
                self._marquee_end = (ix, iy)
            return True

    def on_drag(
        self, ix: float, iy: float, dx: float, dy: float, sx: float, sy: float, state: Gdk.ModifierType
    ) -> bool:
        if self._press_screen is not None:
            if abs(sx - self._press_screen[0]) > 3.0 or abs(sy - self._press_screen[1]) > 3.0:
                self._has_dragged = True

        if self._is_marquee:
            self._marquee_end = (ix, iy)
            if self.canvas:
                self.canvas.queue_draw()
            return True

        return False

    def on_release(
        self, ix: float, iy: float, sx: float, sy: float, state: Gdk.ModifierType
    ) -> bool:
        if not self.canvas or not self.canvas.document:
            self._reset_interaction()
            return False

        doc = self.canvas.document
        is_shift = bool(state & Gdk.ModifierType.SHIFT_MASK)
        is_ctrl = bool(state & Gdk.ModifierType.CONTROL_MASK)

        if self._is_marquee:
            if self._has_dragged:
                x1 = min(self._marquee_start[0], self._marquee_end[0])
                y1 = min(self._marquee_start[1], self._marquee_end[1])
                x2 = max(self._marquee_start[0], self._marquee_end[0])
                y2 = max(self._marquee_end[1], self._marquee_end[1])

                changed = False
                for it in doc.items:
                    if not it.is_visible:
                        continue
                    bx, by, bw, bh = it.get_bounds()
                    intersects = not (bx + bw < x1 or bx > x2 or by + bh < y1 or by > y2)
                    if intersects:
                        if not it.is_selected:
                            it.is_selected = True
                            changed = True
                    elif not is_shift and not is_ctrl:
                        if it.is_selected:
                            it.is_selected = False
                            changed = True
                if changed:
                    doc.notify_changed()
            else:
                if not is_shift and not is_ctrl:
                    doc.deselect_all()
        elif not self._has_dragged:
            if self._hit_item is not None and self._selected_on_press_was_already_selected:
                if not is_shift and not is_ctrl:
                    doc.select_item(self._hit_item, exclusive=True)

        self._sync_style_from_selection()
        self._reset_interaction()
        return True

    def on_cancel(self) -> None:
        self._reset_interaction()

    def on_motion(
        self, ix: float, iy: float, sx: float, sy: float, state: Gdk.ModifierType
    ) -> bool:
        if not self.canvas or not self.canvas.document:
            return False
        hit = self.hit_test(ix, iy)
        if hit is not None:
            self.canvas.set_cursor_from_name("pointer")
        else:
            self.canvas.set_cursor(None)
        return True

    def on_key_pressed(self, keyval: int, state: Gdk.ModifierType) -> bool:
        if not self.canvas or not self.canvas.document:
            return False

        doc = self.canvas.document
        is_ctrl = bool(state & Gdk.ModifierType.CONTROL_MASK)

        if keyval == Gdk.KEY_Escape:
            if self._is_marquee:
                self._reset_interaction()
                return True
            if doc.selected_items:
                doc.deselect_all()
                return True

        if is_ctrl and keyval in (Gdk.KEY_a, Gdk.KEY_A):
            changed = False
            for it in doc.items:
                if it.is_visible and not it.is_selected:
                    it.is_selected = True
                    changed = True
            if changed:
                doc.notify_changed()
            return True

        if keyval in (Gdk.KEY_Delete, Gdk.KEY_BackSpace):
            selected = doc.selected_items
            if selected:
                cmd = DeleteAnnotationCommand(doc, selected)
                self.canvas.execute_command(cmd)
                return True

        return False

    def draw_overlay(self, cr: cairo.Context) -> None:
        if self._is_marquee and self._has_dragged and self.canvas:
            x1 = min(self._marquee_start[0], self._marquee_end[0])
            y1 = min(self._marquee_start[1], self._marquee_end[1])
            w = abs(self._marquee_end[0] - self._marquee_start[0])
            h = abs(self._marquee_end[1] - self._marquee_start[1])

            zoom = self.canvas.zoom if self.canvas.zoom > 0 else 1.0

            cr.save()
            cr.set_source_rgba(0.21, 0.52, 0.89, 0.15)
            cr.rectangle(x1, y1, w, h)
            cr.fill_preserve()

            cr.set_source_rgba(0.21, 0.52, 0.89, 0.85)
            cr.set_line_width(1.0 / zoom)
            cr.set_dash([4.0 / zoom, 4.0 / zoom])
            cr.stroke()
            cr.restore()

    def _sync_style_from_selection(self) -> None:
        if not self.canvas or not self.canvas.document or not self.canvas.tool_manager:
            return
        selected = self.canvas.document.selected_items
        if not selected:
            return

        item = selected[-1]
        mgr = self.canvas.tool_manager
        self._is_syncing_style = True
        try:
            mgr.set_current_color(item.stroke_color)
            mgr.set_stroke_width(item.stroke_width)
            if item.fill_color is None:
                mgr.set_fill_mode("outline")
            elif item.fill_color[3] < 0.9:
                mgr.set_fill_mode("semi")
            else:
                mgr.set_fill_mode("solid")
        finally:
            self._is_syncing_style = False

    def _on_manager_color_changed(self, color: tuple[float, float, float, float]) -> None:
        if self._is_syncing_style or not self.canvas or not self.canvas.document:
            return
        selected = self.canvas.document.selected_items
        if selected and self.is_active:
            mgr = self.canvas.tool_manager
            fill_mode = mgr.fill_mode if mgr else "outline"
            effective_fill = None
            if fill_mode == "semi":
                effective_fill = (color[0], color[1], color[2], 0.25)
            elif fill_mode == "solid":
                effective_fill = (color[0], color[1], color[2], 1.0)

            cmd = RestyleCommand(
                selected,
                stroke_color=color,
                fill_color=effective_fill if fill_mode != "outline" else None,
                clear_fill=(fill_mode == "outline"),
                document=self.canvas.document,
            )
            self.canvas.execute_command(cmd)

    def _on_manager_style_changed(self, width: float, fill_mode: str) -> None:
        if self._is_syncing_style or not self.canvas or not self.canvas.document:
            return
        selected = self.canvas.document.selected_items
        if selected and self.is_active:
            mgr = self.canvas.tool_manager
            curr_color = mgr.current_color if mgr else (0.88, 0.11, 0.14, 1.0)
            effective_fill = None
            if fill_mode == "semi":
                effective_fill = (curr_color[0], curr_color[1], curr_color[2], 0.25)
            elif fill_mode == "solid":
                effective_fill = (curr_color[0], curr_color[1], curr_color[2], 1.0)

            cmd = RestyleCommand(
                selected,
                stroke_width=width,
                fill_color=effective_fill,
                clear_fill=(fill_mode == "outline"),
                document=self.canvas.document,
            )
            self.canvas.execute_command(cmd)

    def _reset_interaction(self) -> None:
        self._is_marquee = False
        self._hit_item = None
        self._press_pos = None
        self._press_screen = None
        self._has_dragged = False
        self._selected_on_press_was_already_selected = False
        if self.canvas:
            self.canvas.queue_draw()
