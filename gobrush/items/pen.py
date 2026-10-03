from __future__ import annotations
import math
from typing import Any, ClassVar
import uuid
import cairo

from gobrush.items.base import AnnotationItem, distance_point_to_line_segment


def build_smooth_path(cr: cairo.Context, points: list[tuple[float, float]]) -> None:
    n = len(points)
    if n == 0:
        return
    if n == 1:
        cr.move_to(points[0][0], points[0][1])
        cr.line_to(points[0][0], points[0][1])
        return
    if n == 2:
        cr.move_to(points[0][0], points[0][1])
        cr.line_to(points[1][0], points[1][1])
        return

    ext = [points[0]] + list(points) + [points[-1]]
    cr.move_to(points[0][0], points[0][1])
    for i in range(1, len(ext) - 2):
        p0, p1, p2, p3 = ext[i - 1], ext[i], ext[i + 1], ext[i + 2]
        c1x = p1[0] + (p2[0] - p0[0]) / 6.0
        c1y = p1[1] + (p2[1] - p0[1]) / 6.0
        c2x = p2[0] - (p3[0] - p1[0]) / 6.0
        c2y = p2[1] - (p3[1] - p1[1]) / 6.0
        cr.curve_to(c1x, c1y, c2x, c2y, p2[0], p2[1])


class PenItem(AnnotationItem):
    type_name: ClassVar[str] = "pen"

    def __init__(
        self,
        points: list[tuple[float, float]] | None = None,
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
        self.points: list[tuple[float, float]] = [
            (float(p[0]), float(p[1])) for p in points
        ] if points else []

        self._base_points: list[tuple[float, float]] | None = None
        self._base_bounds: tuple[float, float, float, float] | None = None

    def add_point(self, x: float, y: float, min_distance: float = 1.0) -> bool:
        pt = (float(x), float(y))
        if not self.points:
            self.points.append(pt)
            self._invalidate_base()
            return True
        last_x, last_y = self.points[-1]
        if math.hypot(pt[0] - last_x, pt[1] - last_y) >= min_distance:
            self.points.append(pt)
            self._invalidate_base()
            return True
        return False

    def _invalidate_base(self) -> None:
        self._base_points = None
        self._base_bounds = None

    def get_bounds(self) -> tuple[float, float, float, float]:
        if not self.points:
            return (0.0, 0.0, 0.0, 0.0)
        xs = [p[0] for p in self.points]
        ys = [p[1] for p in self.points]
        min_x, max_x = min(xs), max(xs)
        min_y, max_y = min(ys), max(ys)
        padding = self.stroke_width / 2.0 + 1.0
        x = min_x - padding
        y = min_y - padding
        w = max(1.0, (max_x - min_x) + 2.0 * padding)
        h = max(1.0, (max_y - min_y) + 2.0 * padding)
        return (x, y, w, h)

    def hit_test(self, x: float, y: float, tolerance: float = 6.0) -> bool:
        if not self.is_visible or not self.points:
            return False

        bx, by, bw, bh = self.get_bounds()
        if not (bx - tolerance <= x <= bx + bw + tolerance and by - tolerance <= y <= by + bh + tolerance):
            return False

        eff_tol = tolerance + self.stroke_width / 2.0
        if len(self.points) == 1:
            return math.hypot(x - self.points[0][0], y - self.points[0][1]) <= eff_tol

        for i in range(len(self.points) - 1):
            p1 = self.points[i]
            p2 = self.points[i + 1]
            if distance_point_to_line_segment(x, y, p1[0], p1[1], p2[0], p2[1]) <= eff_tol:
                return True
        return False

    def draw(self, cr: cairo.Context) -> None:
        if not self.is_visible or not self.points:
            return

        cr.save()
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.set_line_join(cairo.LINE_JOIN_ROUND)
        cr.set_line_width(self.stroke_width)
        cr.set_source_rgba(*self.stroke_color)

        if len(self.points) == 1:
            px, py = self.points[0]
            cr.arc(px, py, max(0.5, self.stroke_width / 2.0), 0.0, 2.0 * math.pi)
            cr.fill()
        elif len(self.points) == 2:
            cr.move_to(self.points[0][0], self.points[0][1])
            cr.line_to(self.points[1][0], self.points[1][1])
            cr.stroke()
        else:
            build_smooth_path(cr, self.points)
            if self.fill_color is not None:
                cr.set_source_rgba(*self.fill_color)
                cr.fill_preserve()
                cr.set_source_rgba(*self.stroke_color)
            cr.stroke()

        cr.restore()

    def move_by(self, dx: float, dy: float) -> None:
        if dx == 0.0 and dy == 0.0:
            return
        self.points = [(px + dx, py + dy) for px, py in self.points]
        if self._base_points is not None:
            self._base_points = [(px + dx, py + dy) for px, py in self._base_points]
        if self._base_bounds is not None:
            bx, by, bw, bh = self._base_bounds
            self._base_bounds = (bx + dx, by + dy, bw, bh)

    def get_geometry(self) -> tuple[float, float, float, float]:
        self._base_points = list(self.points)
        self._base_bounds = self.get_bounds()
        return self._base_bounds

    def set_geometry(self, geometry: Any) -> bool:
        if isinstance(geometry, list):
            self.points = [(float(p[0]), float(p[1])) for p in geometry]
            self._invalidate_base()
            return True
        elif isinstance(geometry, dict) and "points" in geometry:
            self.points = [(float(p[0]), float(p[1])) for p in geometry["points"]]
            self._invalidate_base()
            return True
        elif isinstance(geometry, (tuple, list)) and len(geometry) == 4:
            new_x, new_y, new_w, new_h = float(geometry[0]), float(geometry[1]), float(geometry[2]), float(geometry[3])
            if not self.points:
                return True

            if self._base_bounds is None or self._base_points is None:
                self._base_bounds = self.get_bounds()
                self._base_points = list(self.points)

            bx, by, bw, bh = self._base_bounds
            pad = self.stroke_width / 2.0 + 1.0

            raw_min_x = min(p[0] for p in self._base_points)
            raw_max_x = max(p[0] for p in self._base_points)
            raw_min_y = min(p[1] for p in self._base_points)
            raw_max_y = max(p[1] for p in self._base_points)

            raw_w = raw_max_x - raw_min_x
            raw_h = raw_max_y - raw_min_y

            target_min_x = new_x + pad
            target_min_y = new_y + pad
            target_w = max(0.0, new_w - 2.0 * pad)
            target_h = max(0.0, nh_target := (new_h - 2.0 * pad))

            scaled: list[tuple[float, float]] = []
            for px, py in self._base_points:
                new_px = (target_min_x + (px - raw_min_x) * (target_w / raw_w)) if raw_w > 1e-6 else (new_x + new_w / 2.0)
                new_py = (target_min_y + (py - raw_min_y) * (target_h / raw_h)) if raw_h > 1e-6 else (new_y + new_h / 2.0)
                scaled.append((new_px, new_py))

            self.points = scaled
            return True
        return False

    def set_bounds(self, x: float, y: float, w: float, h: float) -> None:
        self.set_geometry((x, y, w, h))

    def commit_resize(self) -> None:
        self._invalidate_base()

    def clone(self) -> PenItem:
        return PenItem(
            points=list(self.points),
            stroke_color=self.stroke_color,
            stroke_width=self.stroke_width,
            fill_color=self.fill_color,
        )

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data["points"] = [list(p) for p in self.points]
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PenItem:
        return cls(
            points=[(float(p[0]), float(p[1])) for p in data.get("points", [])],
            stroke_color=tuple(data.get("stroke_color", (0.88, 0.11, 0.14, 1.0))),
            stroke_width=float(data.get("stroke_width", 4.0)),
            fill_color=tuple(data["fill_color"]) if data.get("fill_color") else None,
            item_id=data.get("item_id"),
        )
