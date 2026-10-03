from __future__ import annotations
import math
from typing import TYPE_CHECKING
import cairo
import gi

gi.require_version("Gdk", "4.0")
from gi.repository import Gdk

from gobrush.tools.base import BaseTool
from gobrush.items.arrow import ArrowItem, compute_arrowhead
from gobrush.items.line import snap_angle
from gobrush.core.history import AddAnnotationCommand

if TYPE_CHECKING:
    from gobrush.ui.canvas import Canvas


class ArrowTool(BaseTool):
    tool_id: str = "arrow"
    name: str = "Arrow"
    shortcut: str = "A"
    icon_name: str = "go-next-symbolic"
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
        if not self._is_drawing or self._start_pos is None:
            return False

        if state & Gdk.ModifierType.SHIFT_MASK:
            snapped_x, snapped_y = snap_angle(
                self._start_pos[0], self._start_pos[1], ix, iy, step_degrees=45.0
            )
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

        if state & Gdk.ModifierType.SHIFT_MASK:
            final_x, final_y = snap_angle(
                self._start_pos[0], self._start_pos[1], ix, iy, step_degrees=45.0
            )
        else:
            final_x, final_y = float(ix), float(iy)

        start_x, start_y = self._start_pos
        self._is_drawing = False
        self._start_pos = None
        self._current_end = None

        dist = math.hypot(final_x - start_x, final_y - start_y)
        if dist < 4.0:
            if self.canvas:
                self.canvas.queue_draw()
            return True

        arrow_item = ArrowItem(
            start_x,
            start_y,
            final_x,
            final_y,
            stroke_color=self._stroke_color,
            stroke_width=self._stroke_width,
        )

        if self.canvas and self.canvas.document:
            cmd = AddAnnotationCommand(
                self.canvas.document,
                arrow_item,
                select=False,
                name="Add Arrow",
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

        x1, y1 = self._start_pos
        x2, y2 = self._current_end

        dist = math.hypot(x2 - x1, y2 - y1)
        if dist < 1.0:
            return

        cr.save()
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.set_line_join(cairo.LINE_JOIN_ROUND)
        cr.set_source_rgba(*self._stroke_color)

        tip, wing1, wing2, base = compute_arrowhead(x1, y1, x2, y2, self._stroke_width)

        angle = math.atan2(y2 - y1, x2 - x1)
        shaft_end_x = base[0] + (self._stroke_width * 0.5) * math.cos(angle)
        shaft_end_y = base[1] + (self._stroke_width * 0.5) * math.sin(angle)

        cr.set_line_width(self._stroke_width)
        cr.move_to(x1, y1)
        cr.line_to(shaft_end_x, shaft_end_y)
        cr.stroke()

        cr.move_to(tip[0], tip[1])
        cr.line_to(wing1[0], wing1[1])
        cr.line_to(wing2[0], wing2[1])
        cr.close_path()
        cr.fill_preserve()
        cr.set_line_width(max(1.0, self._stroke_width * 0.5))
        cr.stroke()

        cr.restore()
