from __future__ import annotations
import math
from typing import Any, ClassVar
import cairo
import gi

try:
    gi.require_version("Pango", "1.0")
    gi.require_version("PangoCairo", "1.0")
    from gi.repository import Pango, PangoCairo
    _HAS_PANGO = True
except (ValueError, ImportError):
    _HAS_PANGO = False

from gobrush.items.base import AnnotationItem
from gobrush.items.rectangle import draw_rounded_rectangle


def measure_text_layout(
    text: str,
    font_size: float,
    font_family: str = "Sans",
    font_weight: str = "bold",
) -> tuple[float, float]:
    clean_text = text if text else " "
    if _HAS_PANGO:
        try:
            surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 1, 1)
            cr = cairo.Context(surf)
            layout = PangoCairo.create_layout(cr)
            pango_weight = (
                Pango.Weight.BOLD
                if font_weight.lower() in ("bold", "heavy")
                else Pango.Weight.NORMAL
            )
            desc = Pango.FontDescription()
            desc.set_family(font_family)
            desc.set_size(int(max(4.0, font_size) * Pango.SCALE))
            desc.set_weight(pango_weight)
            layout.set_font_description(desc)
            layout.set_text(clean_text, -1)
            PangoCairo.update_layout(cr, layout)
            w, h = layout.get_pixel_size()
            return float(max(10.0, w)), float(max(10.0, h))
        except Exception:
            pass

    # Cairo native fallback
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 1, 1)
    cr = cairo.Context(surf)
    cr.select_font_face(
        font_family,
        cairo.FONT_SLANT_NORMAL,
        cairo.FONT_WEIGHT_BOLD if font_weight.lower() in ("bold", "heavy") else cairo.FONT_WEIGHT_NORMAL,
    )
    cr.set_font_size(max(4.0, font_size))
    lines = clean_text.split("\n")
    line_h = font_size * 1.3
    max_w = 0.0
    for line in lines:
        ext = cr.text_extents(line if line else " ")
        max_w = max(max_w, ext.width)
    return float(max(10.0, max_w)), float(max(10.0, len(lines) * line_h))


def render_text_layout(
    cr: cairo.Context,
    text: str,
    font_size: float,
    font_family: str = "Sans",
    font_weight: str = "bold",
) -> tuple[float, float]:
    clean_text = text if text else " "
    if _HAS_PANGO:
        try:
            layout = PangoCairo.create_layout(cr)
            pango_weight = (
                Pango.Weight.BOLD
                if font_weight.lower() in ("bold", "heavy")
                else Pango.Weight.NORMAL
            )
            desc = Pango.FontDescription()
            desc.set_family(font_family)
            desc.set_size(int(max(4.0, font_size) * Pango.SCALE))
            desc.set_weight(pango_weight)
            layout.set_font_description(desc)
            layout.set_text(clean_text, -1)
            PangoCairo.update_layout(cr, layout)
            w, h = layout.get_pixel_size()
            PangoCairo.show_layout(cr, layout)
            return float(w), float(h)
        except Exception:
            pass

    # Cairo native fallback
    cr.save()
    cr.select_font_face(
        font_family,
        cairo.FONT_SLANT_NORMAL,
        cairo.FONT_WEIGHT_BOLD if font_weight.lower() in ("bold", "heavy") else cairo.FONT_WEIGHT_NORMAL,
    )
    cr.set_font_size(max(4.0, font_size))
    lines = clean_text.split("\n")
    line_h = font_size * 1.3
    curr_x, curr_y = cr.get_current_point()
    max_w = 0.0
    for i, line in enumerate(lines):
        ext = cr.text_extents(line if line else " ")
        max_w = max(max_w, ext.width)
        cr.move_to(curr_x, curr_y + (i + 0.85) * line_h)
        cr.show_text(line)
    cr.restore()
    return max_w, len(lines) * line_h


class TextItem(AnnotationItem):
    type_name: ClassVar[str] = "text"

    def __init__(
        self,
        x: float,
        y: float,
        text: str,
        font_size: float = 20.0,
        font_family: str = "Sans",
        font_weight: str = "bold",
        color: tuple[float, float, float, float] = (0.88, 0.11, 0.14, 1.0),
        fill_color: tuple[float, float, float, float] | None = None,
        background_style: str = "pill",
        shadow: bool = True,
        padding_x: float = 12.0,
        padding_y: float = 6.0,
        item_id: str | None = None,
    ) -> None:
        self.x: float = float(x)
        self.y: float = float(y)
        self.text: str = str(text)
        self.font_size: float = max(8.0, float(font_size))
        self.font_family: str = str(font_family)
        self.font_weight: str = str(font_weight)
        self.color: tuple[float, float, float, float] = color
        self.background_style: str = background_style  # "pill", "none", "box"
        self.shadow: bool = bool(shadow)
        self.padding_x: float = float(padding_x)
        self.padding_y: float = float(padding_y)

        super().__init__(
            stroke_color=color,
            stroke_width=self.font_size,
            fill_color=fill_color,
            item_id=item_id,
        )

    def get_text_size(self) -> tuple[float, float]:
        return measure_text_layout(
            self.text, self.font_size, self.font_family, self.font_weight
        )

    def get_bounds(self) -> tuple[float, float, float, float]:
        tw, th = self.get_text_size()
        if self.background_style in ("pill", "box"):
            return (
                self.x,
                self.y,
                tw + 2.0 * self.padding_x,
                th + 2.0 * self.padding_y,
            )
        return (self.x, self.y, tw, th)

    def hit_test(self, px: float, py: float, tolerance: float = 6.0) -> bool:
        bx, by, bw, bh = self.get_bounds()
        tol = max(0.0, float(tolerance))
        return (bx - tol <= px <= bx + bw + tol and by - tol <= py <= by + bh + tol)

    def draw(self, cr: cairo.Context) -> None:
        if not self.is_visible or not self.text:
            return

        tw, th = self.get_text_size()

        if self.background_style in ("pill", "box"):
            bw = tw + 2.0 * self.padding_x
            bh = th + 2.0 * self.padding_y
            radius = (bh / 2.0) if self.background_style == "pill" else 6.0

            # Drop shadow underneath badge
            if self.shadow:
                cr.save()
                draw_rounded_rectangle(cr, self.x, self.y + 2.0, bw, bh, radius)
                cr.set_source_rgba(0.0, 0.0, 0.0, 0.22)
                cr.fill()
                cr.restore()

            # Pill/Box background fill
            cr.save()
            draw_rounded_rectangle(cr, self.x, self.y, bw, bh, radius)
            if self.fill_color is not None:
                cr.set_source_rgba(*self.fill_color)
            else:
                # High-contrast auto badge
                r, g, b, _ = self.color
                lum = 0.299 * r + 0.587 * g + 0.114 * b
                if lum < 0.5:
                    cr.set_source_rgba(1.0, 1.0, 1.0, 0.95)
                else:
                    cr.set_source_rgba(0.12, 0.12, 0.14, 0.92)
            cr.fill_preserve()
            # Subtle crisp perimeter stroke
            cr.set_source_rgba(0.0, 0.0, 0.0, 0.12)
            cr.set_line_width(1.0)
            cr.stroke()
            cr.restore()

            # Render text centered in badge
            cr.save()
            cr.set_source_rgba(*self.color)
            cr.move_to(self.x + self.padding_x, self.y + self.padding_y)
            render_text_layout(
                cr, self.text, self.font_size, self.font_family, self.font_weight
            )
            cr.restore()

        else:
            # Transparent background (text only)
            if self.shadow:
                cr.save()
                cr.set_source_rgba(0.0, 0.0, 0.0, 0.45)
                cr.move_to(self.x + 1.5, self.y + 1.5)
                render_text_layout(
                    cr, self.text, self.font_size, self.font_family, self.font_weight
                )
                cr.restore()

            cr.save()
            cr.set_source_rgba(*self.color)
            cr.move_to(self.x, self.y)
            render_text_layout(
                cr, self.text, self.font_size, self.font_family, self.font_weight
            )
            cr.restore()

    def move_by(self, dx: float, dy: float) -> None:
        self.x += float(dx)
        self.y += float(dy)

    def get_geometry(self) -> tuple[float, float, float, float]:
        return self.get_bounds()

    def set_geometry(self, geometry: Any) -> bool:
        if isinstance(geometry, (tuple, list)) and len(geometry) == 4:
            gx, gy, gw, gh = geometry
            cur_x, cur_y, cur_w, cur_h = self.get_bounds()
            self.x = float(gx)
            self.y = float(gy)
            if gh > 10.0 and cur_h > 10.0:
                scale = float(gh) / cur_h
                if 0.2 < scale < 5.0 and abs(scale - 1.0) > 0.05:
                    self.font_size = max(8.0, min(144.0, self.font_size * scale))
                    self.stroke_width = self.font_size
            return True
        elif isinstance(geometry, dict):
            if "x" in geometry:
                self.x = float(geometry["x"])
            if "y" in geometry:
                self.y = float(geometry["y"])
            if "text" in geometry:
                self.text = str(geometry["text"])
            if "font_size" in geometry:
                self.font_size = max(8.0, float(geometry["font_size"]))
                self.stroke_width = self.font_size
            if "font_weight" in geometry:
                self.font_weight = str(geometry["font_weight"])
            if "background_style" in geometry:
                self.background_style = str(geometry["background_style"])
            return True
        return False

    def apply_style(
        self,
        stroke_color: tuple[float, float, float, float] | None = None,
        stroke_width: float | None = None,
        fill_color: tuple[float, float, float, float] | None = None,
        clear_fill: bool = False,
        **kwargs: Any,
    ) -> None:
        super().apply_style(
            stroke_color=stroke_color,
            stroke_width=stroke_width,
            fill_color=fill_color,
            clear_fill=clear_fill,
            **kwargs,
        )
        if stroke_color is not None:
            self.color = stroke_color
        if stroke_width is not None and stroke_width >= 8.0:
            self.font_size = float(stroke_width)
            self.stroke_width = self.font_size
        if clear_fill:
            self.fill_color = None
            self.background_style = "none"
        elif fill_color is not None:
            self.fill_color = fill_color
            self.background_style = "pill"
        if "text" in kwargs and kwargs["text"] is not None:
            self.text = str(kwargs["text"])
        if "font_size" in kwargs and kwargs["font_size"] is not None:
            self.font_size = max(8.0, float(kwargs["font_size"]))
            self.stroke_width = self.font_size
        if "font_weight" in kwargs and kwargs["font_weight"] is not None:
            self.font_weight = str(kwargs["font_weight"])
        if "background_style" in kwargs and kwargs["background_style"] is not None:
            self.background_style = str(kwargs["background_style"])

    def clone(self) -> TextItem:
        new_item = TextItem(
            self.x,
            self.y,
            self.text,
            font_size=self.font_size,
            font_family=self.font_family,
            font_weight=self.font_weight,
            color=self.color,
            fill_color=self.fill_color,
            background_style=self.background_style,
            shadow=self.shadow,
            padding_x=self.padding_x,
            padding_y=self.padding_y,
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
                "text": self.text,
                "font_size": self.font_size,
                "font_family": self.font_family,
                "font_weight": self.font_weight,
                "color": list(self.color),
                "background_style": self.background_style,
                "shadow": self.shadow,
                "padding_x": self.padding_x,
                "padding_y": self.padding_y,
            }
        )
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TextItem:
        raw_color = data.get("color") or data.get("stroke_color") or [0.88, 0.11, 0.14, 1.0]
        color = tuple(raw_color)
        fill_color = tuple(data["fill_color"]) if data.get("fill_color") else None
        item = cls(
            x=float(data.get("x", 0.0)),
            y=float(data.get("y", 0.0)),
            text=str(data.get("text", "")),
            font_size=float(data.get("font_size", 20.0)),
            font_family=str(data.get("font_family", "Sans")),
            font_weight=str(data.get("font_weight", "bold")),
            color=color,
            fill_color=fill_color,
            background_style=str(data.get("background_style", "pill")),
            shadow=bool(data.get("shadow", True)),
            padding_x=float(data.get("padding_x", 12.0)),
            padding_y=float(data.get("padding_y", 6.0)),
            item_id=data.get("item_id"),
        )
        item.is_visible = bool(data.get("is_visible", True))
        return item
