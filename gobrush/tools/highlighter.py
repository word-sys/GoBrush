from __future__ import annotations
import math
from typing import TYPE_CHECKING
import cairo
import gi

gi.require_version("Gdk", "4.0")
from gi.repository import Gdk

from gobrush.tools.base import BaseTool
from gobrush.items.pen import build_smooth_path
from gobrush.items.highlighter import HighlighterItem
from gobrush.core.history import AddAnnotationCommand

if TYPE_CHECKING:
    from gobrush.ui.canvas import Canvas


class HighlighterTool(BaseTool):
    tool_id: str = "highlighter"
    name: str = "Highlighter"
    shortcut: str = "H"
    icon_name: str = "marker-symbolic"
    cursor_name: str | None = "crosshair"

    def __init__(self, canvas: Canvas | None = None) -> None:
        super().__init__(canvas)
        self._is_drawing: bool = False
        self._points: list[tuple[float, float]] = []
        self._start_pos: tuple[float, float] | None = None
        self._stroke_color: tuple[float, float, float, float] = (0.95, 0.77, 0.06, 0.5)
        self._stroke_width: float = 16.0

    def activate(self) -> None:
        super().activate()
        if self.canvas and self.canvas.tool_manager:
            if self.canvas.tool_manager.stroke_width <= 4.0:
                self.canvas.tool_manager.set_stroke_width(16.0)
            self._stroke_width = self.canvas.tool_manager.stroke_width

    @property
    def is_drawing(self) -> bool:
        return self._is_drawing

    @property
    def current_points(self) -> list[tuple[float, float]]:
        return list(self._points)

    def on_press(
        self, ix: float, iy: float, sx: float, sy: float, state: Gdk.ModifierType
    ) -> bool:
        if not self.canvas or not self.canvas.has_image:
            return False

        if self.canvas.document:
            self.canvas.document.deselect_all()

        if self.canvas.tool_manager:
            mgr = self.canvas.tool_manager
            r, g, b, a = mgr.current_color
            eff_alpha = min(a, 0.55) if a > 0.6 else a
            self._stroke_color = (r, g, b, eff_alpha)
            self._stroke_width = mgr.stroke_width

        self._is_drawing = True
        self._start_pos = (float(ix), float(iy))
        self._points = [(float(ix), float(iy))]
        self.canvas.queue_draw()
        return True

    def on_drag(
        self, ix: float, iy: float, dx: float, dy: float, sx: float, sy: float, state: Gdk.ModifierType
    ) -> bool:
        if not self._is_drawing or not self._points:
            return False

        is_shift = bool(state & Gdk.ModifierType.SHIFT_MASK)
        if is_shift and self._start_pos:
            sx0, sy0 = self._start_pos
            if abs(ix - sx0) >= abs(iy - sy0):
                target_pt = (float(ix), sy0)
            else:
                target_pt = (sx0, float(iy))
        else:
            target_pt = (float(ix), float(iy))

        zoom = self.canvas.zoom if self.canvas and self.canvas.zoom > 0 else 1.0
        min_dist = max(0.5, 1.0 / zoom)
        last_x, last_y = self._points[-1]
        dist = math.hypot(target_pt[0] - last_x, target_pt[1] - last_y)

        if dist >= min_dist:
            self._points.append(target_pt)
            if self.canvas:
                self.canvas.queue_draw()
        return True

    def on_release(
        self, ix: float, iy: float, sx: float, sy: float, state: Gdk.ModifierType
    ) -> bool:
        if not self._is_drawing:
            return False

        is_shift = bool(state & Gdk.ModifierType.SHIFT_MASK)
        if is_shift and self._start_pos:
            sx0, sy0 = self._start_pos
            if abs(ix - sx0) >= abs(iy - sy0):
                target_pt = (float(ix), sy0)
            else:
                target_pt = (sx0, float(iy))
        else:
            target_pt = (float(ix), float(iy))

        if self._points:
            last_x, last_y = self._points[-1]
            if math.hypot(target_pt[0] - last_x, target_pt[1] - last_y) > 0.1:
                self._points.append(target_pt)

        if len(self._points) >= 1 and self.canvas and self.canvas.document:
            hl_item = HighlighterItem(
                points=list(self._points),
                stroke_color=self._stroke_color,
                stroke_width=self._stroke_width,
            )
            cmd = AddAnnotationCommand(
                self.canvas.document,
                hl_item,
                select=False,
                name="Highlight Text",
            )
            self.canvas.execute_command(cmd)

        self._is_drawing = False
        self._points = []
        self._start_pos = None
        if self.canvas:
            self.canvas.queue_draw()
        return True

    def on_cancel(self) -> None:
        if self._is_drawing:
            self._is_drawing = False
            self._points = []
            self._start_pos = None
            if self.canvas:
                self.canvas.queue_draw()

    def on_key_pressed(self, keyval: int, state: Gdk.ModifierType) -> bool:
        if keyval == Gdk.KEY_Escape:
            if self._is_drawing:
                self.on_cancel()
                return True
        return False

    def draw_overlay(self, cr: cairo.Context) -> None:
        if not self._is_drawing or not self._points:
            return

        cr.save()
        cr.set_operator(cairo.OPERATOR_MULTIPLY)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.set_line_join(cairo.LINE_JOIN_ROUND)
        cr.set_line_width(self._stroke_width)
        cr.set_source_rgba(*self._stroke_color)

        if len(self._points) == 1:
            px, py = self._points[0]
            cr.arc(px, py, max(0.5, self._stroke_width / 2.0), 0.0, 2.0 * math.pi)
            cr.fill()
        elif len(self._points) == 2:
            cr.move_to(self._points[0][0], self._points[0][1])
            cr.line_to(self._points[1][0], self._points[1][1])
            cr.stroke()
        else:
            build_smooth_path(cr, self._points)
            cr.stroke()

        cr.restore()
