from __future__ import annotations
import math
import unittest
import cairo

from gobrush.items.base import (
    AnnotationItem,
    HANDLE_TOP_LEFT,
    HANDLE_TOP_CENTER,
    HANDLE_TOP_RIGHT,
    HANDLE_MIDDLE_RIGHT,
    HANDLE_BOTTOM_RIGHT,
    HANDLE_BOTTOM_CENTER,
    HANDLE_BOTTOM_LEFT,
    HANDLE_MIDDLE_LEFT,
    ALL_BOX_HANDLES,
    compute_box_handles,
    distance_point_to_line_segment,
)


class MockBoxItem(AnnotationItem):
    """Concrete implementation of AnnotationItem for testing base protocols."""

    type_name = "mock_box"

    def __init__(
        self,
        x: float,
        y: float,
        width: float,
        height: float,
        stroke_color: tuple[float, float, float, float] = (1.0, 0.0, 0.0, 1.0),
        stroke_width: float = 2.0,
        fill_color: tuple[float, float, float, float] | None = None,
        item_id: str | None = None,
    ) -> None:
        super().__init__(
            stroke_color=stroke_color,
            stroke_width=stroke_width,
            fill_color=fill_color,
            item_id=item_id,
        )
        self.x = float(x)
        self.y = float(y)
        self.width = float(width)
        self.height = float(height)

    def get_bounds(self) -> tuple[float, float, float, float]:
        half = self.stroke_width / 2.0
        return (
            self.x - half,
            self.y - half,
            self.width + self.stroke_width,
            self.height + self.stroke_width,
        )

    def hit_test(self, x: float, y: float, tolerance: float = 6.0) -> bool:
        bx, by, bw, bh = self.get_bounds()
        return (
            bx - tolerance <= x <= bx + bw + tolerance
            and by - tolerance <= y <= by + bh + tolerance
        )

    def draw(self, cr: cairo.Context) -> None:
        cr.save()
        if self.fill_color:
            cr.set_source_rgba(*self.fill_color)
            cr.rectangle(self.x, self.y, self.width, self.height)
            cr.fill_preserve()
        cr.set_source_rgba(*self.stroke_color)
        cr.set_line_width(self.stroke_width)
        cr.rectangle(self.x, self.y, self.width, self.height)
        cr.stroke()
        cr.restore()

    def move_by(self, dx: float, dy: float) -> None:
        self.x += dx
        self.y += dy

    def clone(self) -> MockBoxItem:
        cloned = MockBoxItem(
            x=self.x,
            y=self.y,
            width=self.width,
            height=self.height,
            stroke_color=self.stroke_color,
            stroke_width=self.stroke_width,
            fill_color=self.fill_color,
        )
        cloned.is_visible = self.is_visible
        return cloned

    @classmethod
    def from_dict(cls, data: dict) -> MockBoxItem:
        return cls(
            x=data.get("x", 0.0),
            y=data.get("y", 0.0),
            width=data.get("width", 10.0),
            height=data.get("height", 10.0),
            stroke_color=tuple(data.get("stroke_color", [1.0, 0.0, 0.0, 1.0])),
            stroke_width=data.get("stroke_width", 2.0),
            fill_color=tuple(data["fill_color"]) if data.get("fill_color") else None,
            item_id=data.get("item_id"),
        )


class TestAnnotationItemBase(unittest.TestCase):
    def test_abstract_class_cannot_be_instantiated(self) -> None:
        with self.assertRaises(TypeError):
            AnnotationItem()  # type: ignore

    def test_item_initialization_defaults(self) -> None:
        item = MockBoxItem(10, 20, 100, 80)
        self.assertIsNotNone(item.item_id)
        self.assertEqual(len(item.item_id), 32)  # hex uuid
        self.assertEqual(item.stroke_color, (1.0, 0.0, 0.0, 1.0))
        self.assertEqual(item.stroke_width, 2.0)
        self.assertIsNone(item.fill_color)
        self.assertFalse(item.is_selected)
        self.assertTrue(item.is_visible)

    def test_item_custom_attributes(self) -> None:
        item = MockBoxItem(
            0,
            0,
            50,
            50,
            stroke_color=(0.1, 0.2, 0.3, 0.8),
            stroke_width=6.0,
            fill_color=(0.5, 0.5, 0.5, 0.5),
            item_id="custom-123",
        )
        self.assertEqual(item.item_id, "custom-123")
        self.assertEqual(item.stroke_color, (0.1, 0.2, 0.3, 0.8))
        self.assertEqual(item.stroke_width, 6.0)
        self.assertEqual(item.fill_color, (0.5, 0.5, 0.5, 0.5))

    def test_stroke_width_minimum_clamped(self) -> None:
        item = MockBoxItem(0, 0, 10, 10, stroke_width=0.01)
        self.assertEqual(item.stroke_width, 0.5)

    def test_get_bounds_includes_stroke(self) -> None:
        item = MockBoxItem(10, 20, 100, 80, stroke_width=4.0)
        bx, by, bw, bh = item.get_bounds()
        self.assertEqual(bx, 8.0)
        self.assertEqual(by, 18.0)
        self.assertEqual(bw, 104.0)
        self.assertEqual(bh, 84.0)

    def test_hit_test(self) -> None:
        item = MockBoxItem(50, 50, 100, 100, stroke_width=4.0)
        # Inside
        self.assertTrue(item.hit_test(100, 100))
        # Just inside tolerance
        self.assertTrue(item.hit_test(45, 100, tolerance=6.0))
        # Far outside
        self.assertFalse(item.hit_test(10, 10, tolerance=6.0))

    def test_move_by(self) -> None:
        item = MockBoxItem(10, 20, 30, 40)
        item.move_by(15, -5)
        self.assertEqual(item.x, 25)
        self.assertEqual(item.y, 15)

    def test_clone_creates_distinct_id_and_deep_copy(self) -> None:
        item = MockBoxItem(10, 20, 30, 40, fill_color=(0, 1, 0, 1))
        cloned = item.clone()
        self.assertNotEqual(item.item_id, cloned.item_id)
        self.assertEqual(cloned.x, 10)
        self.assertEqual(cloned.y, 20)
        self.assertEqual(cloned.fill_color, (0, 1, 0, 1))

        # Modifying original does not affect clone
        item.move_by(100, 100)
        self.assertEqual(cloned.x, 10)
        self.assertEqual(cloned.y, 20)

    def test_compute_box_handles(self) -> None:
        handles = compute_box_handles(100, 200, 40, 60)
        self.assertEqual(len(handles), 8)
        for h_id in ALL_BOX_HANDLES:
            self.assertIn(h_id, handles)

        self.assertEqual(handles[HANDLE_TOP_LEFT], (100, 200))
        self.assertEqual(handles[HANDLE_TOP_CENTER], (120, 200))
        self.assertEqual(handles[HANDLE_TOP_RIGHT], (140, 200))
        self.assertEqual(handles[HANDLE_MIDDLE_RIGHT], (140, 230))
        self.assertEqual(handles[HANDLE_BOTTOM_RIGHT], (140, 260))
        self.assertEqual(handles[HANDLE_BOTTOM_CENTER], (120, 260))
        self.assertEqual(handles[HANDLE_BOTTOM_LEFT], (100, 260))
        self.assertEqual(handles[HANDLE_MIDDLE_LEFT], (100, 230))

    def test_get_handle_at_selection_state(self) -> None:
        item = MockBoxItem(100, 100, 50, 50, stroke_width=0.0)
        # Not selected -> handles should not be detected
        item.is_selected = False
        self.assertIsNone(item.get_handle_at(100, 100, handle_radius=6.0))

        # Selected -> handle detected
        item.is_selected = True
        self.assertEqual(item.get_handle_at(100, 100, handle_radius=6.0), HANDLE_TOP_LEFT)
        self.assertEqual(item.get_handle_at(150, 150, handle_radius=6.0), HANDLE_BOTTOM_RIGHT)
        self.assertEqual(item.get_handle_at(125, 100, handle_radius=6.0), HANDLE_TOP_CENTER)
        # Point between handles
        self.assertIsNone(item.get_handle_at(110, 100, handle_radius=2.0))

    def test_distance_point_to_line_segment(self) -> None:
        # Perpendicular distance to horizontal line
        dist = distance_point_to_line_segment(50, 20, 0, 0, 100, 0)
        self.assertAlmostEqual(dist, 20.0)

        # Point past end of line
        dist_end = distance_point_to_line_segment(130, 40, 0, 0, 100, 0)
        self.assertAlmostEqual(dist_end, 50.0)  # hypot(30, 40) = 50

        # Point before start of line
        dist_start = distance_point_to_line_segment(-30, 40, 0, 0, 100, 0)
        self.assertAlmostEqual(dist_start, 50.0)

        # Degenerate point line (x1, y1) == (x2, y2)
        dist_point = distance_point_to_line_segment(10, 10, 0, 0, 0, 0)
        self.assertAlmostEqual(dist_point, math.hypot(10, 10))

    def test_draw_and_selection_cairo_rendering(self) -> None:
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 200, 200)
        cr = cairo.Context(surf)
        item = MockBoxItem(20, 20, 60, 40, fill_color=(0, 0, 1, 0.5))

        # Normal draw
        item.draw(cr)

        # Selection draw when not selected -> nothing drawn
        item.is_selected = False
        item.draw_selection(cr, scale=1.0)

        # Selection draw when selected
        item.is_selected = True
        item.draw_selection(cr, scale=1.5)

    def test_apply_style(self) -> None:
        item = MockBoxItem(0, 0, 10, 10)
        item.apply_style(stroke_color=(0, 1, 0, 1), stroke_width=8.0, fill_color=(1, 1, 0, 0.5))
        self.assertEqual(item.stroke_color, (0, 1, 0, 1))
        self.assertEqual(item.stroke_width, 8.0)
        self.assertEqual(item.fill_color, (1, 1, 0, 0.5))

        # Clear fill
        item.apply_style(clear_fill=True)
        self.assertIsNone(item.fill_color)

    def test_to_dict(self) -> None:
        item = MockBoxItem(10, 10, 20, 20, stroke_color=(1, 0, 0, 1), stroke_width=3.0)
        data = item.to_dict()
        self.assertEqual(data["type"], "mock_box")
        self.assertEqual(data["item_id"], item.item_id)
        self.assertEqual(data["stroke_color"], [1.0, 0.0, 0.0, 1.0])
        self.assertEqual(data["stroke_width"], 3.0)
        self.assertIsNone(data["fill_color"])
        self.assertTrue(data["is_visible"])


if __name__ == "__main__":
    unittest.main()
