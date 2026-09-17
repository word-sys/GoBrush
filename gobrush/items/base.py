from __future__ import annotations
from abc import ABC, abstractmethod
import math
from typing import Any, ClassVar
import uuid
import cairo


# Handle identifier constants for 8-point box resizing & 2-point line endpoints
HANDLE_TOP_LEFT = "tl"
HANDLE_TOP_CENTER = "tc"
HANDLE_TOP_RIGHT = "tr"
HANDLE_MIDDLE_RIGHT = "mr"
HANDLE_BOTTOM_RIGHT = "br"
HANDLE_BOTTOM_CENTER = "bc"
HANDLE_BOTTOM_LEFT = "bl"
HANDLE_MIDDLE_LEFT = "ml"

HANDLE_START = "start"
HANDLE_END = "end"

ALL_BOX_HANDLES = (
    HANDLE_TOP_LEFT,
    HANDLE_TOP_CENTER,
    HANDLE_TOP_RIGHT,
    HANDLE_MIDDLE_RIGHT,
    HANDLE_BOTTOM_RIGHT,
    HANDLE_BOTTOM_CENTER,
    HANDLE_BOTTOM_LEFT,
    HANDLE_MIDDLE_LEFT,
)


def compute_box_handles(x: float, y: float, w: float, h: float) -> dict[str, tuple[float, float]]:
    """Return dictionary mapping handle names to (hx, hy) coordinate tuples."""
    x2 = x + w
    y2 = y + h
    cx = x + w / 2.0
    cy = y + h / 2.0
    return {
        HANDLE_TOP_LEFT: (x, y),
        HANDLE_TOP_CENTER: (cx, y),
        HANDLE_TOP_RIGHT: (x2, y),
        HANDLE_MIDDLE_RIGHT: (x2, cy),
        HANDLE_BOTTOM_RIGHT: (x2, y2),
        HANDLE_BOTTOM_CENTER: (cx, y2),
        HANDLE_BOTTOM_LEFT: (x, y2),
        HANDLE_MIDDLE_LEFT: (x, cy),
    }


def distance_point_to_line_segment(
    px: float, py: float, x1: float, y1: float, x2: float, y2: float
) -> float:
    """Calculate perpendicular Euclidean distance from point (px, py) to line segment (x1, y1)-(x2, y2)."""
    dx = x2 - x1
    dy = y2 - y1
    seg_len_sq = dx * dx + dy * dy
    if seg_len_sq == 0.0:
        return math.hypot(px - x1, py - y1)

    # Project point onto segment, clamping t to [0, 1]
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / seg_len_sq))
    proj_x = x1 + t * dx
    proj_y = y1 + t * dy
    return math.hypot(px - proj_x, py - proj_y)


class AnnotationItem(ABC):
    """Abstract Base Class for all vector markup and annotation items in GoBrush."""

    type_name: ClassVar[str] = "base"

    def __init__(
        self,
        stroke_color: tuple[float, float, float, float] = (0.88, 0.11, 0.14, 1.0),
        stroke_width: float = 4.0,
        fill_color: tuple[float, float, float, float] | None = None,
        item_id: str | None = None,
    ) -> None:
        self.item_id: str = item_id or uuid.uuid4().hex
        self.stroke_color: tuple[float, float, float, float] = stroke_color
        self.stroke_width: float = max(0.5, float(stroke_width))
        self.fill_color: tuple[float, float, float, float] | None = fill_color
        self.is_selected: bool = False
        self.is_visible: bool = True

    # -------------------------------------------------------------------------
    # Core Abstract Protocols
    # -------------------------------------------------------------------------

    @abstractmethod
    def get_bounds(self) -> tuple[float, float, float, float]:
        """Return (x, y, width, height) bounding box in image coordinates including stroke padding."""
        raise NotImplementedError

    @abstractmethod
    def hit_test(self, x: float, y: float, tolerance: float = 6.0) -> bool:
        """Return True if point (x, y) intersects the item within tolerance."""
        raise NotImplementedError

    @abstractmethod
    def draw(self, cr: cairo.Context) -> None:
        """Render the vector item onto the given Cairo context in image space."""
        raise NotImplementedError

    @abstractmethod
    def move_by(self, dx: float, dy: float) -> None:
        """Translate item position by (dx, dy) in image coordinates."""
        raise NotImplementedError

    @abstractmethod
    def clone(self) -> AnnotationItem:
        """Return a deep copy of this annotation item with a new unique ID."""
        raise NotImplementedError

    def get_geometry(self) -> Any:
        return self.get_bounds()

    def set_geometry(self, geometry: Any) -> bool:
        if isinstance(geometry, dict):
            for k, v in geometry.items():
                if hasattr(self, k):
                    setattr(self, k, v)
            return True
        elif isinstance(geometry, (tuple, list)):
            if len(geometry) == 4 and all(hasattr(self, attr) for attr in ("x", "y", "w", "h")):
                self.x, self.y, self.w, self.h = geometry
                return True
            elif hasattr(self, "set_bounds") and callable(getattr(self, "set_bounds")):
                getattr(self, "set_bounds")(*geometry)
                return True
        return False

    # -------------------------------------------------------------------------
    # Selection & Handles Protocol
    # -------------------------------------------------------------------------

    def get_handles(self) -> dict[str, tuple[float, float]]:
        """Return dictionary of resize handle points for this item."""
        x, y, w, h = self.get_bounds()
        return compute_box_handles(x, y, w, h)

    def get_handle_at(
        self, x: float, y: float, handle_radius: float = 6.0
    ) -> str | None:
        """Return the identifier of the handle under (x, y), or None."""
        if not self.is_selected:
            return None
        handles = self.get_handles()
        r_sq = handle_radius * handle_radius
        for handle_id, (hx, hy) in handles.items():
            dx = x - hx
            dy = y - hy
            if dx * dx + dy * dy <= r_sq:
                return handle_id
        return None

    def draw_selection(self, cr: cairo.Context, scale: float = 1.0) -> None:
        """Draw bounding box selection frame and resize handle dots."""
        if not self.is_selected or not self.is_visible:
            return

        x, y, w, h = self.get_bounds()
        s = max(0.01, scale)
        line_w = 1.5 / s
        handle_size = 8.0 / s
        half_handle = handle_size / 2.0

        cr.save()

        # Selection rectangle outline (dashed Libadwaita accent blue)
        cr.set_source_rgba(0.21, 0.52, 0.89, 0.9)  # #3584e4
        cr.set_line_width(line_w)
        cr.set_dash([4.0 / s, 4.0 / s])
        cr.rectangle(x, y, w, h)
        cr.stroke()

        # Selection handle dots (solid white box with blue border)
        cr.set_dash([])  # clear dashes
        handles = self.get_handles()
        for hx, hy in handles.values():
            # White fill
            cr.set_source_rgba(1.0, 1.0, 1.0, 1.0)
            cr.rectangle(hx - half_handle, hy - half_handle, handle_size, handle_size)
            cr.fill_preserve()
            # Blue border
            cr.set_source_rgba(0.21, 0.52, 0.89, 1.0)
            cr.set_line_width(line_w)
            cr.stroke()

        cr.restore()

    # -------------------------------------------------------------------------
    # Styling & Serialization Helpers
    # -------------------------------------------------------------------------

    def apply_style(
        self,
        stroke_color: tuple[float, float, float, float] | None = None,
        stroke_width: float | None = None,
        fill_color: tuple[float, float, float, float] | None = None,
        clear_fill: bool = False,
    ) -> None:
        """Update styling attributes."""
        if stroke_color is not None:
            self.stroke_color = stroke_color
        if stroke_width is not None:
            self.stroke_width = max(0.5, float(stroke_width))
        if clear_fill:
            self.fill_color = None
        elif fill_color is not None:
            self.fill_color = fill_color

    def to_dict(self) -> dict[str, Any]:
        """Serialize item attributes to a dictionary."""
        return {
            "type": self.type_name,
            "item_id": self.item_id,
            "stroke_color": list(self.stroke_color),
            "stroke_width": self.stroke_width,
            "fill_color": list(self.fill_color) if self.fill_color else None,
            "is_visible": self.is_visible,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AnnotationItem:
        """Reconstruct annotation item from dictionary. Subclasses should override or extend."""
        raise NotImplementedError
