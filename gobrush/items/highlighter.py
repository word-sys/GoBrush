from __future__ import annotations
import math
from typing import Any, ClassVar
import cairo

from gobrush.items.pen import PenItem, build_smooth_path


class HighlighterItem(PenItem):
    type_name: ClassVar[str] = "highlighter"

    def __init__(
        self,
        points: list[tuple[float, float]] | None = None,
        stroke_color: tuple[float, float, float, float] = (0.95, 0.77, 0.06, 0.5),
        stroke_width: float = 16.0,
        fill_color: tuple[float, float, float, float] | None = None,
        item_id: str | None = None,
    ) -> None:
        super().__init__(
            points=points,
            stroke_color=stroke_color,
            stroke_width=stroke_width,
            fill_color=fill_color,
            item_id=item_id,
        )

    def draw(self, cr: cairo.Context) -> None:
        if not self.is_visible or not self.points:
            return

        cr.save()
        cr.set_operator(cairo.OPERATOR_MULTIPLY)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.set_line_join(cairo.LINE_JOIN_ROUND)
        cr.set_line_width(self.stroke_width)

        r, g, b, a = self.stroke_color
        eff_alpha = min(a, 0.55) if a > 0.6 else a
        cr.set_source_rgba(r, g, b, eff_alpha)

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
            cr.stroke()

        cr.restore()

    def clone(self) -> HighlighterItem:
        return HighlighterItem(
            points=list(self.points),
            stroke_color=self.stroke_color,
            stroke_width=self.stroke_width,
            fill_color=self.fill_color,
        )

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data["type"] = self.type_name
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HighlighterItem:
        return cls(
            points=[(float(p[0]), float(p[1])) for p in data.get("points", [])],
            stroke_color=tuple(data.get("stroke_color", (0.95, 0.77, 0.06, 0.5))),
            stroke_width=float(data.get("stroke_width", 16.0)),
            fill_color=tuple(data["fill_color"]) if data.get("fill_color") else None,
            item_id=data.get("item_id"),
        )
