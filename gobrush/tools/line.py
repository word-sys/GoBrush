from __future__ import annotations
import math
from typing import TYPE_CHECKING
import cairo
import gi

gi.require_version("Gdk", "4.0")
from gi.repository import Gdk

from gobrush.tools.base import BaseTool
from gobrush.items.line import LineItem, snap_angle
from gobrush.core.history import AddAnnotationCommand

if TYPE_CHECKING:
    from gobrush.ui.canvas import Canvas


class LineTool(BaseTool):
    tool_id: str = "line"
    name: str = "Line"
    shortcut: str = "L"
    icon_name: str = "view-list-symbolic"
    cursor_name: str | None = "crosshair"

    def __init__(self, canvas: Canvas | None = None) -> None:
        super().__init__(canvas)
        self._is_drawing: bool = False
        self._start_pos: tuple[float, float] | None = None
        self._current_end: tuple[float, float] | None = None
        self._stroke_color: tuple[float, float, float, float] = (0.88, 0.11, 0.14, 1.0)
        self._stroke_width: float = 4.0

    @property
    def is_drawing(self) -> bool:
        return self._is_drawing

    @property
    def start_pos(self) -> tuple[float, float] | None:
        return self._start_pos

    @property
    def current_end(self) -> tuple[float, float] | None:
        return self._current_end

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

        self._is_drawing = True
        self._start_pos = (float(ix), float(iy))
        self._current_end = (float(ix), float(iy))
        self.canvas.queue_draw()
        return True

    def on_drag(
        self, ix: float, iy: float, dx: float, dy: float, sx: float, sy: float, state: Gdk.ModifierType
    ) -> bool:
        if not self._is_drawing or not self._start_pos:
            return False

        is_shift = bool(state & Gdk.ModifierType.SHIFT_MASK)
        if is_shift:
            self._current_end = snap_angle(
                self._start_pos[0], self._start_pos[1], float(ix), float(iy)
            )
        else:
            self._current_end = (float(ix), float(iy))

        if self.canvas:
            self.canvas.queue_draw()
        return True

    def on_release(
        self, ix: float, iy: float, sx: float, sy: float, state: Gdk.ModifierType
    ) -> bool:
        if not self._is_drawing or not self._start_pos:
            return False

        is_shift = bool(state & Gdk.ModifierType.SHIFT_MASK)
        if is_shift:
            end_x, end_y = snap_angle(
                self._start_pos[0], self._start_pos[1], float(ix), float(iy)
            )
        else:
            end_x, end_y = float(ix), float(iy)

        dist = math.hypot(end_x - self._start_pos[0], end_y - self._start_pos[1])
        if dist >= 1.0 and self.canvas and self.canvas.document:
            line_item = LineItem(
                self._start_pos[0],
                self._start_pos[1],
                end_x,
                end_y,
                stroke_color=self._stroke_color,
                stroke_width=self._stroke_width,
            )
            cmd = AddAnnotationCommand(
                self.canvas.document,
                line_item,
                select=False,
                name="Draw Straight Line",
            )
            self.canvas.execute_command(cmd)

        self._is_drawing = False
        self._start_pos = None
        self._current_end = None
        if self.canvas:
            self.canvas.queue_draw()
        return True

    def on_cancel(self) -> None:
        if self._is_drawing:
            self._is_drawing = False
            self._start_pos = None
            self._current_end = None
            if self.canvas:
                self.canvas.queue_draw()

    def on_key_pressed(self, keyval: int, state: Gdk.ModifierType) -> bool:
        if keyval == Gdk.KEY_Escape:
            if self._is_drawing:
                self.on_cancel()
                return True
        return False

    def draw_overlay(self, cr: cairo.Context) -> None:
        if not self._is_drawing or not self._start_pos or not self._current_end:
            return

        cr.save()
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.set_line_width(self._stroke_width)
        cr.set_source_rgba(*self._stroke_color)
        cr.move_to(self._start_pos[0], self._start_pos[1])
        cr.line_to(self._current_end[0], self._current_end[1])
        cr.stroke()
        cr.restore()
