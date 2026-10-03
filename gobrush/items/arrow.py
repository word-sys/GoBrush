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
from gobrush.items.line import snap_angle


def compute_arrowhead(
    x1: float, y1: float, x2: float, y2: float, stroke_width: float
) -> tuple[tuple[float, float], tuple[float, float], tuple[float, float], tuple[float, float]]:
    dx = x2 - x1
    dy = y2 - y1
    dist = math.hypot(dx, dy)
    if dist < 1e-6:
        return (x2, y2), (x2, y2), (x2, y2), (x2, y2)

    angle = math.atan2(dy, dx)
    head_len = max(14.0, min(64.0, stroke_width * 3.6))
    if dist < head_len * 1.2:
        head_len = dist * 0.8

    arrow_angle = math.radians(28.0)

    wing1_x = x2 - head_len * math.cos(angle - arrow_angle)
    wing1_y = y2 - head_len * math.sin(angle - arrow_angle)

    wing2_x = x2 - head_len * math.cos(angle + arrow_angle)
    wing2_y = y2 - head_len * math.sin(angle + arrow_angle)

    base_x = x2 - head_len * math.cos(angle)
    base_y = y2 - head_len * math.sin(angle)

    return (x2, y2), (wing1_x, wing1_y), (wing2_x, wing2_y), (base_x, base_y)


def point_in_triangle(
    px: float,
    py: float,
    t1: tuple[float, float],
    t2: tuple[float, float],
    t3: tuple[float, float],
) -> bool:
    def sign(p1x: float, p1y: float, p2x: float, p2y: float, p3x: float, p3y: float) -> float:
        return (p1x - p3x) * (p2y - p3y) - (p2x - p3x) * (p1y - p3y)

    d1 = sign(px, py, t1[0], t1[1], t2[0], t2[1])
    d2 = sign(px, py, t2[0], t2[1], t3[0], t3[1])
    d3 = sign(px, py, t3[0], t3[1], t1[0], t1[1])
    has_neg = (d1 < 0) or (d2 < 0) or (d3 < 0)
    has_pos = (d1 > 0) or (d2 > 0) or (d3 > 0)
    return not (has_neg and has_pos)


class ArrowItem(AnnotationItem):
    type_name: ClassVar[str] = "arrow"

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

    def _compute_arrowhead(
        self,
    ) -> tuple[tuple[float, float], tuple[float, float], tuple[float, float], tuple[float, float]]:
        return compute_arrowhead(self.x1, self.y1, self.x2, self.y2, self.stroke_width)

    def get_bounds(self) -> tuple[float, float, float, float]:
        tip, wing1, wing2, _ = self._compute_arrowhead()
        xs = [self.x1, self.x2, wing1[0], wing2[0]]
        ys = [self.y1, self.y2, wing1[1], wing2[1]]
        min_x = min(xs)
        max_x = max(xs)
        min_y = min(ys)
        max_y = max(ys)
        pad = self.stroke_width / 2.0 + 2.0
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
        tip, wing1, wing2, base = self._compute_arrowhead()

        # 1. Point in or near arrowhead triangle
        if point_in_triangle(x, y, tip, wing1, wing2):
            return True
        if distance_point_to_line_segment(x, y, tip[0], tip[1], wing1[0], wing1[1]) <= eff_tol:
            return True
        if distance_point_to_line_segment(x, y, wing1[0], wing1[1], wing2[0], wing2[1]) <= eff_tol:
            return True
        if distance_point_to_line_segment(x, y, wing2[0], wing2[1], tip[0], tip[1]) <= eff_tol:
            return True

        # 2. Point near arrow shaft
        dist_shaft = distance_point_to_line_segment(x, y, self.x1, self.y1, base[0], base[1])
        return dist_shaft <= eff_tol

    def draw(self, cr: cairo.Context) -> None:
        if not self.is_visible:
            return
        dist = math.hypot(self.x2 - self.x1, self.y2 - self.y1)
        if dist < 1e-4:
            return

        cr.save()
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.set_line_join(cairo.LINE_JOIN_ROUND)
        cr.set_source_rgba(*self.stroke_color)

        tip, wing1, wing2, base = self._compute_arrowhead()

        # Draw shaft with slight overlap into arrowhead to eliminate anti-aliasing seam
        angle = math.atan2(self.y2 - self.y1, self.x2 - self.x1)
        shaft_end_x = base[0] + (self.stroke_width * 0.5) * math.cos(angle)
        shaft_end_y = base[1] + (self.stroke_width * 0.5) * math.sin(angle)

        cr.set_line_width(self.stroke_width)
        cr.move_to(self.x1, self.y1)
        cr.line_to(shaft_end_x, shaft_end_y)
        cr.stroke()

        # Draw filled solid arrowhead
        cr.move_to(tip[0], tip[1])
        cr.line_to(wing1[0], wing1[1])
        cr.line_to(wing2[0], wing2[1])
        cr.close_path()
        cr.fill_preserve()
        cr.set_line_width(max(1.0, self.stroke_width * 0.5))
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
        cr.set_source_rgba(0.21, 0.52, 0.89, 0.9)
        cr.set_line_width(line_w)
        cr.set_dash([4.0 / s, 4.0 / s])
        cr.move_to(self.x1, self.y1)
        cr.line_to(self.x2, self.y2)
        cr.stroke()

        # Endpoint handles at tail and tip
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

    def clone(self) -> ArrowItem:
        return ArrowItem(
            self.x1,
            self.y1,
            self.x2,
            self.y2,
            stroke_color=self.stroke_color,
            stroke_width=self.stroke_width,
            fill_color=self.fill_color,
        )

    def to_dict(self) -> dict[str, Any]:
        d = super().to_dict()
        d.update({
            "type": self.type_name,
            "x1": self.x1,
            "y1": self.y1,
            "x2": self.x2,
            "y2": self.y2,
        })
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ArrowItem:
        color = tuple(data.get("stroke_color", (0.88, 0.11, 0.14, 1.0)))
        fill = data.get("fill_color")
        if fill is not None:
            fill = tuple(fill)
        return cls(
            x1=float(data.get("x1", 0.0)),
            y1=float(data.get("y1", 0.0)),
            x2=float(data.get("x2", 0.0)),
            y2=float(data.get("y2", 0.0)),
            stroke_color=color,
            stroke_width=float(data.get("stroke_width", 4.0)),
            fill_color=fill,
            item_id=data.get("id"),
        )
