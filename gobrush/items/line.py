from __future__ import annotations
import math
from typing import Any, ClassVar
import cairo

from gobrush.items.base import (
    AnnotationItem,
    HANDLE_START,
    HANDLE_END,
    distance_point_to_line_segment,
)


def snap_angle(
    origin_x: float,
    origin_y: float,
    target_x: float,
    target_y: float,
    step_degrees: float = 45.0,
) -> tuple[float, float]:
    dx = target_x - origin_x
    dy = target_y - origin_y
    dist = math.hypot(dx, dy)
    if dist < 1e-6:
        return target_x, target_y
    angle = math.atan2(dy, dx)
    step_rad = math.radians(step_degrees)
    snapped = round(angle / step_rad) * step_rad
    return origin_x + dist * math.cos(snapped), origin_y + dist * math.sin(snapped)


class LineItem(AnnotationItem):
    type_name: ClassVar[str] = "line"

    def __init__(
        self,
        x1: float = 0.0,
        y1: float = 0.0,
        x2: float = 0.0,
        y2: float = 0.0,
        stroke_color: tuple[float, float, float, float] = (0.88, 0.11, 0.14, 1.0),
        stroke_width: float = 4.0,
        fill_color: tuple[float, float, float, float] | None = None,
        item_id: str | None = None,
    ) -> None:
        super().__init__(
            stroke_color=stroke_color,
            stroke_width=stroke_width,
            fill_color=fill_color,
            item_id=item_id,
        )
        self.x1: float = float(x1)
        self.y1: float = float(y1)
        self.x2: float = float(x2)
        self.y2: float = float(y2)

    def get_bounds(self) -> tuple[float, float, float, float]:
        min_x = min(self.x1, self.x2)
        max_x = max(self.x1, self.x2)
        min_y = min(self.y1, self.y2)
        max_y = max(self.y1, self.y2)
        pad = self.stroke_width / 2.0 + 1.0
        x = min_x - pad
        y = min_y - pad
        w = max(1.0, (max_x - min_x) + 2.0 * pad)
        h = max(1.0, (max_y - min_y) + 2.0 * pad)
        return (x, y, w, h)

    def hit_test(self, x: float, y: float, tolerance: float = 6.0) -> bool:
        if not self.is_visible:
            return False
        bx, by, bw, bh = self.get_bounds()
        if not (bx - tolerance <= x <= bx + bw + tolerance and by - tolerance <= y <= by + bh + tolerance):
            return False
        eff_tol = tolerance + self.stroke_width / 2.0
        dist = distance_point_to_line_segment(x, y, self.x1, self.y1, self.x2, self.y2)
        return dist <= eff_tol

    def draw(self, cr: cairo.Context) -> None:
        if not self.is_visible:
            return
        cr.save()
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.set_line_width(self.stroke_width)
        cr.set_source_rgba(*self.stroke_color)
        cr.move_to(self.x1, self.y1)
        cr.line_to(self.x2, self.y2)
        cr.stroke()
        cr.restore()

    def move_by(self, dx: float, dy: float) -> None:
        if dx == 0.0 and dy == 0.0:
            return
        self.x1 += dx
        self.y1 += dy
        self.x2 += dx
        self.y2 += dy

    def get_geometry(self) -> tuple[float, float, float, float]:
        return (self.x1, self.y1, self.x2, self.y2)

    def set_geometry(self, geometry: Any) -> bool:
        if isinstance(geometry, (tuple, list)) and len(geometry) == 4:
            self.x1 = float(geometry[0])
            self.y1 = float(geometry[1])
            self.x2 = float(geometry[2])
            self.y2 = float(geometry[3])
            return True
        elif isinstance(geometry, dict):
            if all(k in geometry for k in ("x1", "y1", "x2", "y2")):
                self.x1 = float(geometry["x1"])
                self.y1 = float(geometry["y1"])
                self.x2 = float(geometry["x2"])
                self.y2 = float(geometry["y2"])
                return True
        return False

    def get_handles(self) -> dict[str, tuple[float, float]]:
        return {
            HANDLE_START: (self.x1, self.y1),
            HANDLE_END: (self.x2, self.y2),
        }

    def draw_selection(self, cr: cairo.Context, scale: float = 1.0) -> None:
        if not self.is_selected or not self.is_visible:
            return

        s = max(0.01, scale)
        line_w = 1.5 / s
        handle_size = 9.0 / s
        half_handle = handle_size / 2.0

        cr.save()

        # Selection guide line
        cr.set_source_rgba(0.21, 0.52, 0.89, 0.9)  # #3584e4
        cr.set_line_width(line_w)
        cr.set_dash([4.0 / s, 4.0 / s])
        cr.move_to(self.x1, self.y1)
        cr.line_to(self.x2, self.y2)
        cr.stroke()

        # Endpoint handles at start and end
        cr.set_dash([])
        handles = self.get_handles()
        for hx, hy in handles.values():
            cr.set_source_rgba(1.0, 1.0, 1.0, 1.0)
            cr.rectangle(hx - half_handle, hy - half_handle, handle_size, handle_size)
            cr.fill_preserve()
            cr.set_source_rgba(0.21, 0.52, 0.89, 1.0)
            cr.set_line_width(line_w)
            cr.stroke()

        cr.restore()

    def clone(self) -> LineItem:
        return LineItem(
            self.x1,
            self.y1,
            self.x2,
            self.y2,
            stroke_color=self.stroke_color,
            stroke_width=self.stroke_width,
            fill_color=self.fill_color,
        )

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data["x1"] = self.x1
        data["y1"] = self.y1
        data["x2"] = self.x2
        data["y2"] = self.y2
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LineItem:
        return cls(
            x1=float(data.get("x1", 0.0)),
            y1=float(data.get("y1", 0.0)),
            x2=float(data.get("x2", 0.0)),
            y2=float(data.get("y2", 0.0)),
            stroke_color=tuple(data.get("stroke_color", (0.88, 0.11, 0.14, 1.0))),
            stroke_width=float(data.get("stroke_width", 4.0)),
            fill_color=tuple(data["fill_color"]) if data.get("fill_color") else None,
            item_id=data.get("item_id"),
        )
