from __future__ import annotations
import math
from typing import TYPE_CHECKING
import cairo
import gi

gi.require_version("Gdk", "4.0")
from gi.repository import Gdk

from gobrush.tools.base import BaseTool
from gobrush.items.pen import PenItem, build_smooth_path
from gobrush.core.history import AddAnnotationCommand

if TYPE_CHECKING:
    from gobrush.ui.canvas import Canvas


class PenTool(BaseTool):
    tool_id: str = "pen"
    name: str = "Pen"
    shortcut: str = "P"
    icon_name: str = "document-edit-symbolic"
    cursor_name: str | None = "crosshair"

    def __init__(self, canvas: Canvas | None = None) -> None:
        super().__init__(canvas)
        self._is_drawing: bool = False
        self._points: list[tuple[float, float]] = []
        self._stroke_color: tuple[float, float, float, float] = (0.88, 0.11, 0.14, 1.0)
        self._stroke_width: float = 4.0
        self._fill_color: tuple[float, float, float, float] | None = None

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
            self._stroke_color = mgr.current_color
            self._stroke_width = mgr.stroke_width
            self._fill_color = mgr.get_effective_fill_color()

        self._is_drawing = True
        self._points = [(float(ix), float(iy))]
        self.canvas.queue_draw()
        return True

    def on_drag(
        self, ix: float, iy: float, dx: float, dy: float, sx: float, sy: float, state: Gdk.ModifierType
    ) -> bool:
        if not self._is_drawing or not self._points:
            return False

        zoom = self.canvas.zoom if self.canvas and self.canvas.zoom > 0 else 1.0
        min_dist = max(0.5, 1.0 / zoom)
        last_x, last_y = self._points[-1]
        dist = math.hypot(ix - last_x, iy - last_y)

        if dist >= min_dist:
            self._points.append((float(ix), float(iy)))
            if self.canvas:
                self.canvas.queue_draw()
        return True

    def on_release(
        self, ix: float, iy: float, sx: float, sy: float, state: Gdk.ModifierType
    ) -> bool:
        if not self._is_drawing:
            return False

        if self._points:
            last_x, last_y = self._points[-1]
            if math.hypot(ix - last_x, iy - last_y) > 0.1:
                self._points.append((float(ix), float(iy)))

        if len(self._points) >= 1 and self.canvas and self.canvas.document:
            pen_item = PenItem(
                points=list(self._points),
                stroke_color=self._stroke_color,
                stroke_width=self._stroke_width,
                fill_color=self._fill_color,
            )
            cmd = AddAnnotationCommand(
                self.canvas.document,
                pen_item,
                select=False,
                name="Draw Pen Stroke",
            )
            self.canvas.execute_command(cmd)

        self._is_drawing = False
        self._points = []
        if self.canvas:
            self.canvas.queue_draw()
        return True

    def on_cancel(self) -> None:
        if self._is_drawing:
            self._is_drawing = False
            self._points = []
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
            if self._fill_color is not None:
                cr.set_source_rgba(*self._fill_color)
                cr.fill_preserve()
                cr.set_source_rgba(*self._stroke_color)
            cr.stroke()

        cr.restore()
