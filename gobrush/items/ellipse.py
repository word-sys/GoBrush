from __future__ import annotations
import math
from typing import Any, ClassVar
import cairo

from gobrush.items.base import AnnotationItem


KAPPA = 0.5522847498307936


def draw_ellipse(
    cr: cairo.Context, x: float, y: float, w: float, h: float
) -> None:
    if w < 0:
        x += w
        w = -w
    if h < 0:
        y += h
        h = -h

    if w <= 0.0 or h <= 0.0:
        return

    cx = x + w / 2.0
    cy = y + h / 2.0
    rx = w / 2.0
    ry = h / 2.0
    kx = KAPPA * rx
    ky = KAPPA * ry

    cr.move_to(cx, cy - ry)
    cr.curve_to(cx + kx, cy - ry, cx + rx, cy - ky, cx + rx, cy)
    cr.curve_to(cx + rx, cy + ky, cx + kx, cy + ry, cx, cy + ry)
    cr.curve_to(cx - kx, cy + ry, cx - rx, cy + ky, cx - rx, cy)
    cr.curve_to(cx - rx, cy - ky, cx - kx, cy - ry, cx, cy - ry)
    cr.close_path()


def point_in_ellipse(
    px: float,
    py: float,
    x: float,
    y: float,
    w: float,
    h: float,
    tolerance: float = 0.0,
) -> bool:
    if w < 0:
        x += w
        w = -w
    if h < 0:
        y += h
        h = -h

    rx = w / 2.0 + max(0.0, float(tolerance))
    ry = h / 2.0 + max(0.0, float(tolerance))

    if rx <= 0.0 or ry <= 0.0:
        return False

    cx = x + w / 2.0
    cy = y + h / 2.0
    dx = px - cx
    dy = py - cy

    return ((dx / rx) ** 2 + (dy / ry) ** 2) <= 1.0


class EllipseItem(AnnotationItem):
    type_name: ClassVar[str] = "ellipse"

    def __init__(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        stroke_color: tuple[float, float, float, float] = (0.88, 0.11, 0.14, 1.0),
        stroke_width: float = 4.0,
        fill_color: tuple[float, float, float, float] | None = None,
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
            return point_in_ellipse(px, py, self.x, self.y, self.w, self.h, tolerance=pad)

        # Outline only: point must be within boundary stroke area and outside inner hollow area
        if not point_in_ellipse(px, py, self.x, self.y, self.w, self.h, tolerance=pad):
            return False

        inner_w = self.w - 2.0 * pad
        inner_h = self.h - 2.0 * pad
        if inner_w > 0.0 and inner_h > 0.0:
            if point_in_ellipse(px, py, self.x + pad, self.y + pad, inner_w, inner_h, tolerance=0.0):
                return False

        return True

    def draw(self, cr: cairo.Context) -> None:
        if not self.is_visible or (self.w <= 0.0 and self.h <= 0.0):
            return

        cr.save()
        draw_ellipse(cr, self.x, self.y, self.w, self.h)

        if self.fill_color is not None:
            cr.set_source_rgba(*self.fill_color)
            if self.stroke_width > 0.0 and self.stroke_color and self.stroke_color[3] > 0.0:
                cr.fill_preserve()
            else:
                cr.fill()

        if self.stroke_width > 0.0 and self.stroke_color and self.stroke_color[3] > 0.0:
            cr.set_source_rgba(*self.stroke_color)
            cr.set_line_width(self.stroke_width)
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
            return True
        return False

    def clone(self) -> EllipseItem:
        new_item = EllipseItem(
            self.x,
            self.y,
            self.w,
            self.h,
            stroke_color=self.stroke_color,
            stroke_width=self.stroke_width,
            fill_color=self.fill_color,
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
            }
        )
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EllipseItem:
        item = cls(
            x=float(data.get("x", 0.0)),
            y=float(data.get("y", 0.0)),
            w=float(data.get("w", 0.0)),
            h=float(data.get("h", 0.0)),
            stroke_color=tuple(data.get("stroke_color", [0.88, 0.11, 0.14, 1.0])),
            stroke_width=float(data.get("stroke_width", 4.0)),
            fill_color=tuple(data["fill_color"]) if data.get("fill_color") else None,
            item_id=data.get("item_id"),
        )
        item.is_visible = bool(data.get("is_visible", True))
        return item
