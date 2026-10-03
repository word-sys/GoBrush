from __future__ import annotations
import math
from typing import Any, ClassVar
import cairo

from gobrush.items.base import (
    AnnotationItem,
    compute_box_handles,
)


def draw_rounded_rectangle(
    cr: cairo.Context, x: float, y: float, w: float, h: float, radius: float
) -> None:
    if w < 0:
        x += w
        w = -w
    if h < 0:
        y += h
        h = -h

    r = max(0.0, min(float(radius), w / 2.0, h / 2.0))
    if r <= 0.001:
        cr.rectangle(x, y, w, h)
        return

    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2.0, 0.0)
    cr.arc(x + w - r, y + h - r, r, 0.0, math.pi / 2.0)
    cr.arc(x + r, y + h - r, r, math.pi / 2.0, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 1.5 * math.pi)
    cr.close_path()


def point_in_rounded_rectangle(
    px: float,
    py: float,
    x: float,
    y: float,
    w: float,
    h: float,
    radius: float,
    tolerance: float = 0.0,
) -> bool:
    if w < 0:
        x += w
        w = -w
    if h < 0:
        y += h
        h = -h

    pad = max(0.0, float(tolerance))
    if not (x - pad <= px <= x + w + pad and y - pad <= py <= y + h + pad):
        return False

    r = max(0.0, min(float(radius), w / 2.0, h / 2.0))
    if r <= 0.001:
        return True

    # Check the 4 corner exclusion zones
    # Top-left corner
    if px < x + r and py < y + r:
        return math.hypot(px - (x + r), py - (y + r)) <= (r + pad)
    # Top-right corner
    if px > x + w - r and py < y + r:
        return math.hypot(px - (x + w - r), py - (y + r)) <= (r + pad)
    # Bottom-left corner
    if px < x + r and py > y + h - r:
        return math.hypot(px - (x + r), py - (y + h - r)) <= (r + pad)
    # Bottom-right corner
    if px > x + w - r and py > y + h - r:
        return math.hypot(px - (x + w - r), py - (y + h - r)) <= (r + pad)

    return True


class RectangleItem(AnnotationItem):
    type_name: ClassVar[str] = "rectangle"

    def __init__(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        stroke_color: tuple[float, float, float, float] = (0.88, 0.11, 0.14, 1.0),
        stroke_width: float = 4.0,
        fill_color: tuple[float, float, float, float] | None = None,
        radius: float = 0.0,
        item_id: str | None = None,
    ) -> None:
        norm_x = min(float(x), float(x) + float(w))
        norm_y = min(float(y), float(y) + float(h))
        norm_w = abs(float(w))
        norm_h = abs(float(h))

        self.x: float = norm_x
        self.y: float = norm_y
        self.w: float = norm_w
        self.h: float = norm_h
        self.radius: float = max(0.0, float(radius))

        super().__init__(
            stroke_color=stroke_color,
            stroke_width=stroke_width,
            fill_color=fill_color,
            item_id=item_id,
        )

    def get_bounds(self) -> tuple[float, float, float, float]:
        pad = self.stroke_width / 2.0
        return (
            self.x - pad,
            self.y - pad,
            self.w + self.stroke_width,
            self.h + self.stroke_width,
        )

    def hit_test(self, px: float, py: float, tolerance: float = 6.0) -> bool:
        pad = self.stroke_width / 2.0 + tolerance

        if not (self.x - pad <= px <= self.x + self.w + pad and self.y - pad <= py <= self.y + self.h + pad):
            return False

        if self.fill_color is not None:
            return point_in_rounded_rectangle(
                px, py, self.x, self.y, self.w, self.h, self.radius, tolerance=pad
            )

        # Outline only: point must be within boundary stroke area and outside inner hollow area
        if not point_in_rounded_rectangle(
            px, py, self.x, self.y, self.w, self.h, self.radius, tolerance=pad
        ):
            return False

        inner_w = self.w - 2.0 * pad
        inner_h = self.h - 2.0 * pad
        if inner_w > 0.0 and inner_h > 0.0:
            inner_r = max(0.0, self.radius - pad)
            if point_in_rounded_rectangle(
                px, py, self.x + pad, self.y + pad, inner_w, inner_h, inner_r, tolerance=0.0
            ):
                return False

        return True

    def draw(self, cr: cairo.Context) -> None:
        if not self.is_visible or (self.w <= 0.0 and self.h <= 0.0):
            return

        cr.save()
        draw_rounded_rectangle(cr, self.x, self.y, self.w, self.h, self.radius)

        if self.fill_color is not None:
            cr.set_source_rgba(*self.fill_color)
            if self.stroke_width > 0.0 and self.stroke_color and self.stroke_color[3] > 0.0:
                cr.fill_preserve()
            else:
                cr.fill()

        if self.stroke_width > 0.0 and self.stroke_color and self.stroke_color[3] > 0.0:
            cr.set_source_rgba(*self.stroke_color)
            cr.set_line_width(self.stroke_width)
            cr.set_line_join(cairo.LINE_JOIN_ROUND if self.radius > 0.0 else cairo.LINE_JOIN_MITER)
            cr.stroke()
        else:
            cr.new_path()

        cr.restore()

    def move_by(self, dx: float, dy: float) -> None:
        self.x += float(dx)
        self.y += float(dy)

    def get_geometry(self) -> tuple[float, float, float, float]:
        return (self.x, self.y, self.w, self.h)

    def set_geometry(self, geometry: Any) -> bool:
        if isinstance(geometry, (tuple, list)) and len(geometry) == 4:
            gx, gy, gw, gh = geometry
            if gw < 0:
                gx += gw
                gw = -gw
            if gh < 0:
                gy += gh
                gh = -gh
            self.x = float(gx)
            self.y = float(gy)
            self.w = float(gw)
            self.h = float(gh)
            return True
        elif isinstance(geometry, dict):
            if "x" in geometry:
                self.x = float(geometry["x"])
            if "y" in geometry:
                self.y = float(geometry["y"])
            if "w" in geometry:
                self.w = abs(float(geometry["w"]))
            if "h" in geometry:
                self.h = abs(float(geometry["h"]))
            if "radius" in geometry:
                self.radius = max(0.0, float(geometry["radius"]))
            return True
        return False

    def apply_style(
        self,
        stroke_color: tuple[float, float, float, float] | None = None,
        stroke_width: float | None = None,
        fill_color: tuple[float, float, float, float] | None = None,
        clear_fill: bool = False,
        radius: float | None = None,
        **kwargs: Any,
    ) -> None:
        super().apply_style(
            stroke_color=stroke_color,
            stroke_width=stroke_width,
            fill_color=fill_color,
            clear_fill=clear_fill,
            **kwargs,
        )
        if radius is not None:
            self.radius = max(0.0, float(radius))

    def clone(self) -> RectangleItem:
        new_item = RectangleItem(
            self.x,
            self.y,
            self.w,
            self.h,
            stroke_color=self.stroke_color,
            stroke_width=self.stroke_width,
            fill_color=self.fill_color,
            radius=self.radius,
        )
        new_item.is_visible = self.is_visible
        return new_item

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data.update(
            {
                "type": self.type_name,
                "x": self.x,
                "y": self.y,
                "w": self.w,
                "h": self.h,
                "radius": self.radius,
            }
        )
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RectangleItem:
        item = cls(
            x=float(data.get("x", 0.0)),
            y=float(data.get("y", 0.0)),
            w=float(data.get("w", 0.0)),
            h=float(data.get("h", 0.0)),
            stroke_color=tuple(data.get("stroke_color", [0.88, 0.11, 0.14, 1.0])),
            stroke_width=float(data.get("stroke_width", 4.0)),
            fill_color=tuple(data["fill_color"]) if data.get("fill_color") else None,
            radius=float(data.get("radius", 0.0)),
            item_id=data.get("item_id"),
        )
        item.is_visible = bool(data.get("is_visible", True))
        return item
