from __future__ import annotations
import math
from typing import TYPE_CHECKING
import cairo
import gi

gi.require_version("Gdk", "4.0")
from gi.repository import Gdk

from gobrush.tools.base import BaseTool
from gobrush.items.rectangle import RectangleItem, draw_rounded_rectangle
from gobrush.core.history import AddAnnotationCommand

if TYPE_CHECKING:
    from gobrush.ui.canvas import Canvas


class RectangleTool(BaseTool):
    tool_id: str = "rectangle"
    name: str = "Rectangle"
    shortcut: str = "R"
    icon_name: str = "window-maximize-symbolic"
    cursor_name: str | None = "crosshair"

    def __init__(self, canvas: Canvas | None = None) -> None:
        super().__init__(canvas)
        self._is_drawing: bool = False
        self._start_pos: tuple[float, float] | None = None
        self._current_end: tuple[float, float] | None = None
        self._stroke_color: tuple[float, float, float, float] = (0.88, 0.11, 0.14, 1.0)
        self._stroke_width: float = 4.0
        self._fill_color: tuple[float, float, float, float] | None = None
        self._corner_radius: float = 0.0

    @property
    def is_drawing(self) -> bool:
        return self._is_drawing

    @property
    def start_pos(self) -> tuple[float, float] | None:
        return self._start_pos

    @property
    def current_end(self) -> tuple[float, float] | None:
        return self._current_end

    @property
    def corner_radius(self) -> float:
        return self._corner_radius

    @corner_radius.setter
    def corner_radius(self, radius: float) -> None:
        self._corner_radius = max(0.0, float(radius))

    def on_press(
        self, ix: float, iy: float, sx: float, sy: float, state: Gdk.ModifierType
    ) -> bool:
        if not self.canvas or not self.canvas.has_image:
            return False

        if self.canvas.document:
            self.canvas.document.deselect_all()

        if self.canvas.tool_manager:
            mgr = self.canvas.tool_manager
            self._stroke_color = mgr.current_color
            self._stroke_width = mgr.stroke_width
            self._fill_color = mgr.get_effective_fill_color()
            if hasattr(mgr, "corner_radius"):
                self._corner_radius = mgr.corner_radius

        self._is_drawing = True
        self._start_pos = (float(ix), float(iy))
        self._current_end = (float(ix), float(iy))

        self.canvas.queue_draw()
        return True

    def on_drag(
        self, ix: float, iy: float, dx: float, dy: float, sx: float, sy: float, state: Gdk.ModifierType
    ) -> bool:
        if not self._is_drawing or self._start_pos is None:
            return False

        if state & Gdk.ModifierType.SHIFT_MASK:
            start_x, start_y = self._start_pos
            diff_x = ix - start_x
            diff_y = iy - start_y
            side = max(abs(diff_x), abs(diff_y))
            snapped_x = start_x + (side if diff_x >= 0 else -side)
            snapped_y = start_y + (side if diff_y >= 0 else -side)
            self._current_end = (snapped_x, snapped_y)
        else:
            self._current_end = (float(ix), float(iy))

        if self.canvas:
            self.canvas.queue_draw()
        return True

    def on_release(
        self, ix: float, iy: float, sx: float, sy: float, state: Gdk.ModifierType
    ) -> bool:
        if not self._is_drawing or self._start_pos is None:
            return False

        start_x, start_y = self._start_pos

        if state & Gdk.ModifierType.SHIFT_MASK:
            diff_x = ix - start_x
            diff_y = iy - start_y
            side = max(abs(diff_x), abs(diff_y))
            final_x = start_x + (side if diff_x >= 0 else -side)
            final_y = start_y + (side if diff_y >= 0 else -side)
        else:
            final_x, final_y = float(ix), float(iy)

        self._is_drawing = False
        self._start_pos = None
        self._current_end = None

        w = abs(final_x - start_x)
        h = abs(final_y - start_y)
        if max(w, h) < 4.0:
            if self.canvas:
                self.canvas.queue_draw()
            return True

        norm_x = min(start_x, final_x)
        norm_y = min(start_y, final_y)

        rect_item = RectangleItem(
            norm_x,
            norm_y,
            w,
            h,
            stroke_color=self._stroke_color,
            stroke_width=self._stroke_width,
            fill_color=self._fill_color,
            radius=self._corner_radius,
        )

        if self.canvas and self.canvas.document:
            cmd = AddAnnotationCommand(
                self.canvas.document,
                rect_item,
                select=False,
                name="Add Rectangle",
            )
            self.canvas.execute_command(cmd)

        if self.canvas:
            self.canvas.queue_draw()
        return True

    def on_cancel(self) -> None:
        self._is_drawing = False
        self._start_pos = None
        self._current_end = None
        if self.canvas:
            self.canvas.queue_draw()

    def on_key_pressed(self, keyval: int, state: Gdk.ModifierType) -> bool:
        if keyval == Gdk.KEY_Escape:
            if self._is_drawing or self._start_pos is not None:
                self.on_cancel()
                return True
        return False

    def draw_overlay(self, cr: cairo.Context) -> None:
        if not self._is_drawing or self._start_pos is None or self._current_end is None:
            return

        start_x, start_y = self._start_pos
        end_x, end_y = self._current_end

        w = abs(end_x - start_x)
        h = abs(end_y - start_y)
        if w < 1.0 and h < 1.0:
            return

        norm_x = min(start_x, end_x)
        norm_y = min(start_y, end_y)

        cr.save()
        draw_rounded_rectangle(cr, norm_x, norm_y, w, h, self._corner_radius)

        if self._fill_color is not None:
            cr.set_source_rgba(*self._fill_color)
            if self._stroke_width > 0.0:
                cr.fill_preserve()
            else:
                cr.fill()

        if self._stroke_width > 0.0:
            cr.set_source_rgba(*self._stroke_color)
            cr.set_line_width(self._stroke_width)
            cr.set_line_join(cairo.LINE_JOIN_ROUND if self._corner_radius > 0.0 else cairo.LINE_JOIN_MITER)
            cr.stroke()
        else:
            cr.new_path()

        cr.restore()
