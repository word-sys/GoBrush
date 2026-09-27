from __future__ import annotations
from typing import TYPE_CHECKING, Any
import cairo
import gi

gi.require_version("Gdk", "4.0")
from gi.repository import Gdk

from gobrush.tools.base import BaseTool
from gobrush.items.base import (
    AnnotationItem,
    HANDLE_TOP_LEFT,
    HANDLE_TOP_CENTER,
    HANDLE_TOP_RIGHT,
    HANDLE_MIDDLE_RIGHT,
    HANDLE_BOTTOM_RIGHT,
    HANDLE_BOTTOM_CENTER,
    HANDLE_BOTTOM_LEFT,
    HANDLE_MIDDLE_LEFT,
    HANDLE_START,
    HANDLE_END,
)
from gobrush.core.history import (
    DeleteAnnotationCommand,
    RestyleCommand,
    ResizeCommand,
)

if TYPE_CHECKING:
    from gobrush.ui.canvas import Canvas


HANDLE_CURSORS: dict[str, str] = {
    HANDLE_TOP_LEFT: "nwse-resize",
    HANDLE_BOTTOM_RIGHT: "nwse-resize",
    HANDLE_TOP_RIGHT: "nesw-resize",
    HANDLE_BOTTOM_LEFT: "nesw-resize",
    HANDLE_TOP_CENTER: "ns-resize",
    HANDLE_BOTTOM_CENTER: "ns-resize",
    HANDLE_MIDDLE_LEFT: "ew-resize",
    HANDLE_MIDDLE_RIGHT: "ew-resize",
    HANDLE_START: "crosshair",
    HANDLE_END: "crosshair",
}


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

        self._hovered_handle: str | None = None
        self._hovered_item: AnnotationItem | None = None
        self._active_handle: str | None = None
        self._resizing_item: AnnotationItem | None = None
        self._initial_geometry: Any = None
        self._initial_pos: tuple[float, float] | None = None

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
    def active_handle(self) -> str | None:
        return self._active_handle

    @property
    def hovered_handle(self) -> str | None:
        return self._hovered_handle

    @property
    def resizing_item(self) -> AnnotationItem | None:
        return self._resizing_item

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

    def hit_test_handle(self, ix: float, iy: float) -> tuple[AnnotationItem | None, str | None]:
        if not self.canvas or not self.canvas.document:
            return None, None
        zoom = self.canvas.zoom if self.canvas.zoom > 0 else 1.0
        handle_radius = 8.0 / max(0.01, zoom)

        for it in reversed(self.canvas.document.selected_items):
            h_id = it.get_handle_at(ix, iy, handle_radius=handle_radius)
            if h_id:
                return it, h_id
        return None, None

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

        # 1. Check if clicking on a resize handle of any currently selected item
        handle_item, handle_id = self.hit_test_handle(ix, iy)
        if handle_item and handle_id:
            self._active_handle = handle_id
            self._resizing_item = handle_item
            self._initial_geometry = handle_item.get_geometry()
            self._initial_pos = (ix, iy)
            self._hovered_item = handle_item
            self._hovered_handle = handle_id
            return True

        # 2. Check item hit
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

        # Handle active resize
        if self._active_handle and self._resizing_item and self._initial_pos and self._initial_geometry:
            total_dx = ix - self._initial_pos[0]
            total_dy = iy - self._initial_pos[1]
            lock_aspect = bool(state & Gdk.ModifierType.SHIFT_MASK)
            self._apply_handle_resize(
                self._resizing_item,
                self._active_handle,
                self._initial_geometry,
                total_dx,
                total_dy,
                lock_aspect,
            )
            if self.canvas:
                self.canvas.queue_draw()
            return True

        # Handle marquee drag
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

        # Complete handle resize
        if self._active_handle and self._resizing_item:
            item = self._resizing_item
            old_geom = self._initial_geometry
            new_geom = item.get_geometry()
            self._active_handle = None
            self._resizing_item = None
            self._initial_geometry = None
            self._initial_pos = None

            if old_geom != new_geom:
                cmd = ResizeCommand(item, old_geom, new_geom, document=doc)
                self.canvas.undo_manager.push(cmd, execute=False)

            self._reset_interaction()
            return True

        # Complete marquee selection
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
        if self._active_handle and self._resizing_item and self._initial_geometry:
            self._resizing_item.set_geometry(self._initial_geometry)
            if self.canvas and self.canvas.document:
                self.canvas.document.mark_dirty()
        self._reset_interaction()

    def on_motion(
        self, ix: float, iy: float, sx: float, sy: float, state: Gdk.ModifierType
    ) -> bool:
        if not self.canvas or not self.canvas.document:
            return False

        if self._active_handle:
            cursor = HANDLE_CURSORS.get(self._active_handle, "default")
            self.canvas.set_cursor_from_name(cursor)
            return True

        prev_hovered = (self._hovered_item, self._hovered_handle)
        handle_item, handle_id = self.hit_test_handle(ix, iy)

        if handle_item and handle_id:
            self._hovered_item = handle_item
            self._hovered_handle = handle_id
            cursor = HANDLE_CURSORS.get(handle_id, "default")
            self.canvas.set_cursor_from_name(cursor)
            if (self._hovered_item, self._hovered_handle) != prev_hovered:
                self.canvas.queue_draw()
            return True

        self._hovered_item = None
        self._hovered_handle = None

        hit = self.hit_test(ix, iy)
        if hit is not None:
            self.canvas.set_cursor_from_name("pointer")
        else:
            self.canvas.set_cursor(None)

        if prev_hovered != (None, None):
            self.canvas.queue_draw()

        return True

    def on_key_pressed(self, keyval: int, state: Gdk.ModifierType) -> bool:
        if not self.canvas or not self.canvas.document:
            return False

        doc = self.canvas.document
        is_ctrl = bool(state & Gdk.ModifierType.CONTROL_MASK)

        if keyval == Gdk.KEY_Escape:
            if self._active_handle and self._resizing_item and self._initial_geometry:
                self._resizing_item.set_geometry(self._initial_geometry)
                doc.mark_dirty()
                self._reset_interaction()
                return True
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
        zoom = self.canvas.zoom if self.canvas and self.canvas.zoom > 0 else 1.0

        # Draw active or hovered handle highlight indicator
        target_item = self._resizing_item or self._hovered_item
        target_handle = self._active_handle or self._hovered_handle

        if target_item and target_handle and target_item.is_selected and target_item.is_visible:
            handles = target_item.get_handles()
            if target_handle in handles:
                hx, hy = handles[target_handle]
                s = max(0.01, zoom)
                handle_size = 9.0 / s
                half_handle = handle_size / 2.0

                cr.save()
                cr.set_source_rgba(0.21, 0.52, 0.89, 1.0)
                cr.rectangle(hx - half_handle, hy - half_handle, handle_size, handle_size)
                cr.fill_preserve()
                cr.set_source_rgba(1.0, 1.0, 1.0, 1.0)
                cr.set_line_width(1.5 / s)
                cr.stroke()
                cr.restore()

        # Draw marquee box
        if self._is_marquee and self._has_dragged and self.canvas:
            x1 = min(self._marquee_start[0], self._marquee_end[0])
            y1 = min(self._marquee_start[1], self._marquee_end[1])
            w = abs(self._marquee_end[0] - self._marquee_start[0])
            h = abs(self._marquee_end[1] - self._marquee_start[1])

            cr.save()
            cr.set_source_rgba(0.21, 0.52, 0.89, 0.15)
            cr.rectangle(x1, y1, w, h)
            cr.fill_preserve()

            cr.set_source_rgba(0.21, 0.52, 0.89, 0.85)
            cr.set_line_width(1.0 / zoom)
            cr.set_dash([4.0 / zoom, 4.0 / zoom])
            cr.stroke()
            cr.restore()

    def _apply_handle_resize(
        self,
        item: AnnotationItem,
        handle: str,
        initial_geom: Any,
        dx: float,
        dy: float,
        lock_aspect: bool = False,
    ) -> None:
        if not isinstance(initial_geom, (tuple, list)) or len(initial_geom) != 4:
            return

        x0, y0, w0, h0 = initial_geom
        min_size = 6.0
        r0 = x0 + w0
        b0 = y0 + h0

        new_x, new_y, new_w, new_h = x0, y0, w0, h0

        if handle == HANDLE_BOTTOM_RIGHT:
            new_w = max(min_size, w0 + dx)
            new_h = max(min_size, h0 + dy)
            if lock_aspect and w0 > 0 and h0 > 0:
                scale = max(new_w / w0, new_h / h0)
                new_w = w0 * scale
                new_h = h0 * scale

        elif handle == HANDLE_BOTTOM_LEFT:
            new_x = min(r0 - min_size, x0 + dx)
            new_w = r0 - new_x
            new_h = max(min_size, h0 + dy)
            if lock_aspect and w0 > 0 and h0 > 0:
                scale = max(new_w / w0, new_h / h0)
                new_w = w0 * scale
                new_h = h0 * scale
                new_x = r0 - new_w

        elif handle == HANDLE_TOP_RIGHT:
            new_y = min(b0 - min_size, y0 + dy)
            new_w = max(min_size, w0 + dx)
            new_h = b0 - new_y
            if lock_aspect and w0 > 0 and h0 > 0:
                scale = max(new_w / w0, new_h / h0)
                new_w = w0 * scale
                new_h = h0 * scale
                new_y = b0 - new_h

        elif handle == HANDLE_TOP_LEFT:
            new_x = min(r0 - min_size, x0 + dx)
            new_y = min(b0 - min_size, y0 + dy)
            new_w = r0 - new_x
            new_h = b0 - new_y
            if lock_aspect and w0 > 0 and h0 > 0:
                scale = max(new_w / w0, new_h / h0)
                new_w = w0 * scale
                new_h = h0 * scale
                new_x = r0 - new_w
                new_y = b0 - new_h

        elif handle == HANDLE_TOP_CENTER:
            new_y = min(b0 - min_size, y0 + dy)
            new_h = b0 - new_y

        elif handle == HANDLE_BOTTOM_CENTER:
            new_h = max(min_size, h0 + dy)

        elif handle == HANDLE_MIDDLE_LEFT:
            new_x = min(r0 - min_size, x0 + dx)
            new_w = r0 - new_x

        elif handle == HANDLE_MIDDLE_RIGHT:
            new_w = max(min_size, w0 + dx)

        item.set_geometry((new_x, new_y, new_w, new_h))
        if self.canvas and self.canvas.document:
            self.canvas.document.mark_dirty()

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
        self._active_handle = None
        self._resizing_item = None
        self._initial_geometry = None
        self._initial_pos = None
        if self.canvas:
            self.canvas.queue_draw()
