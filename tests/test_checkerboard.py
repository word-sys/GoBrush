from __future__ import annotations
import unittest
import cairo

from gobrush.core.checkerboard import create_checkerboard_pattern
from gobrush.ui.canvas import Canvas


class TestCheckerboard(unittest.TestCase):
    def test_create_checkerboard_pattern_1x(self) -> None:
        pattern = create_checkerboard_pattern(tile_size=10, scale_factor=1)
        self.assertIsInstance(pattern, cairo.SurfacePattern)
        self.assertEqual(pattern.get_extend(), cairo.EXTEND_REPEAT)

        surface = pattern.get_surface()
        self.assertIsInstance(surface, cairo.ImageSurface)
        self.assertEqual(surface.get_width(), 20)
        self.assertEqual(surface.get_height(), 20)
        self.assertEqual(surface.get_device_scale(), (1.0, 1.0))

    def test_create_checkerboard_pattern_2x_hidpi(self) -> None:
        pattern = create_checkerboard_pattern(tile_size=12, scale_factor=2)
        surface = pattern.get_surface()
        self.assertEqual(surface.get_width(), 48)
        self.assertEqual(surface.get_height(), 48)
        self.assertEqual(surface.get_device_scale(), (2.0, 2.0))

    def test_canvas_checkerboard_toggle(self) -> None:
        canvas = Canvas()
        self.assertTrue(canvas.show_checkerboard)

        canvas.show_checkerboard = False
        self.assertFalse(canvas.show_checkerboard)

        canvas.show_checkerboard = True
        self.assertTrue(canvas.show_checkerboard)

    def test_canvas_scale_factor(self) -> None:
        canvas = Canvas()
        self.assertGreaterEqual(canvas.scale_factor, 1)

    def test_canvas_checkerboard_pattern_caching(self) -> None:
        canvas = Canvas()
        p1 = canvas._get_checkerboard_pattern()
        p2 = canvas._get_checkerboard_pattern()
        self.assertIs(p1, p2)

        # Invalidate via scale factor change signal
        canvas._on_scale_factor_changed()
        self.assertIsNone(canvas._checkerboard_pattern)
        p3 = canvas._get_checkerboard_pattern()
        self.assertIsNotNone(p3)

    def test_canvas_draw_with_checkerboard_and_transparent_image(self) -> None:
        canvas = Canvas()
        # Transparent 100x100 surface
        img = cairo.ImageSurface(cairo.FORMAT_ARGB32, 100, 100)
        canvas.set_image_surface(img)

        target = cairo.ImageSurface(cairo.FORMAT_ARGB32, 200, 200)
        cr = cairo.Context(target)

        # Draw with checkerboard enabled
        canvas.show_checkerboard = True
        canvas._on_draw(canvas, cr, 200, 200)

        # Draw with checkerboard disabled
        canvas.show_checkerboard = False
        canvas._on_draw(canvas, cr, 200, 200)


if __name__ == "__main__":
    unittest.main()
