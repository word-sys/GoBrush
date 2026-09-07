from __future__ import annotations
import unittest
from unittest.mock import Mock
import cairo

from gobrush.core.transform import ViewportTransform
from gobrush.ui.canvas import Canvas


class TestViewportTransform(unittest.TestCase):
    def test_initial_state(self) -> None:
        t = ViewportTransform()
        self.assertEqual(t.zoom, 1.0)
        self.assertEqual(t.pan_x, 0.0)
        self.assertEqual(t.pan_y, 0.0)
        self.assertEqual(t.min_zoom, 0.1)
        self.assertEqual(t.max_zoom, 32.0)

    def test_screen_to_image_and_back(self) -> None:
        t = ViewportTransform()
        t.set_zoom(2.5)
        t.set_pan(100.0, 50.0)

        # Image point (20, 30) -> screen point
        sx, sy = t.image_to_screen(20.0, 30.0)
        self.assertAlmostEqual(sx, 20.0 * 2.5 + 100.0)
        self.assertAlmostEqual(sy, 30.0 * 2.5 + 50.0)

        # Roundtrip screen back to image
        ix, iy = t.screen_to_image(sx, sy)
        self.assertAlmostEqual(ix, 20.0)
        self.assertAlmostEqual(iy, 30.0)

        # Distance conversions
        self.assertAlmostEqual(t.screen_to_image_dist(25.0), 10.0)
        self.assertAlmostEqual(t.image_to_screen_dist(10.0), 25.0)

    def test_zoom_clamping(self) -> None:
        t = ViewportTransform(min_zoom=0.2, max_zoom=10.0)
        t.set_zoom(0.01)
        self.assertEqual(t.zoom, 0.2)

        t.set_zoom(50.0)
        self.assertEqual(t.zoom, 10.0)

    def test_zoom_at_pivot_keeps_point_stationary(self) -> None:
        t = ViewportTransform()
        t.set_pan(80.0, 60.0)
        t.set_zoom(1.2)

        pivot_screen = (300.0, 250.0)
        # Image point under pivot before zoom
        ix_before, iy_before = t.screen_to_image(*pivot_screen)

        # Zoom in at pivot
        t.zoom_by(2.0, pivot_screen=pivot_screen)

        # Image point under pivot after zoom must be identical
        ix_after, iy_after = t.screen_to_image(*pivot_screen)
        self.assertAlmostEqual(ix_before, ix_after, places=6)
        self.assertAlmostEqual(iy_before, iy_after, places=6)

        # Screen point of that image point must still match pivot
        sx_after, sy_after = t.image_to_screen(ix_before, iy_before)
        self.assertAlmostEqual(sx_after, pivot_screen[0], places=6)
        self.assertAlmostEqual(sy_after, pivot_screen[1], places=6)

    def test_pan_methods(self) -> None:
        t = ViewportTransform()
        t.set_pan(10.0, 20.0)
        self.assertEqual((t.pan_x, t.pan_y), (10.0, 20.0))

        t.pan_by(15.0, -5.0)
        self.assertEqual((t.pan_x, t.pan_y), (25.0, 15.0))

    def test_fit_to_viewport_downscale(self) -> None:
        t = ViewportTransform()
        # Large image 1000x800 in 500x400 viewport with padding 20
        # Avail: 460 x 360 -> scale = min(460/1000, 360/800) = min(0.46, 0.45) = 0.45
        t.fit_to_viewport(500, 400, 1000, 800, padding=20.0)
        self.assertAlmostEqual(t.zoom, 0.45)
        # Verify centered
        self.assertAlmostEqual(t.pan_x, (500 - 1000 * 0.45) / 2.0)
        self.assertAlmostEqual(t.pan_y, (400 - 800 * 0.45) / 2.0)

    def test_fit_to_viewport_upscale_flag(self) -> None:
        t = ViewportTransform()
        # Small image 100x100 in 800x600 viewport
        t.fit_to_viewport(800, 600, 100, 100, padding=20.0, upscale=False)
        self.assertEqual(t.zoom, 1.0)

        t.fit_to_viewport(800, 600, 100, 100, padding=20.0, upscale=True)
        # Avail: 760x560 -> scale = min(7.6, 5.6) = 5.6
        self.assertAlmostEqual(t.zoom, 5.6)

    def test_center_and_reset(self) -> None:
        t = ViewportTransform()
        t.set_zoom(2.0)
        t.center_image(600, 400, 200, 100)
        # pan_x = (600 - 400) / 2 = 100, pan_y = (400 - 200) / 2 = 100
        self.assertEqual(t.pan_x, 100.0)
        self.assertEqual(t.pan_y, 100.0)

        t.reset(600, 400, 200, 100)
        self.assertEqual(t.zoom, 1.0)
        self.assertEqual(t.pan_x, 200.0)
        self.assertEqual(t.pan_y, 150.0)

    def test_cairo_matrix_match(self) -> None:
        t = ViewportTransform()
        t.set_zoom(1.75)
        t.set_pan(45.0, 90.0)

        matrix = t.get_cairo_matrix()
        # Transform point through cairo matrix
        mx, my = matrix.transform_point(35.0, 70.0)
        sx, sy = t.image_to_screen(35.0, 70.0)
        self.assertAlmostEqual(mx, sx)
        self.assertAlmostEqual(my, sy)

    def test_canvas_coordinate_delegation(self) -> None:
        canvas = Canvas()
        canvas.set_pan(50.0, 25.0)
        canvas.set_zoom(2.0)

        self.assertEqual(canvas.pan_x, 50.0)
        self.assertEqual(canvas.pan_y, 25.0)
        self.assertEqual(canvas.zoom, 2.0)

        sx, sy = canvas.image_to_screen(10.0, 10.0)
        self.assertEqual(sx, 70.0)
        self.assertEqual(sy, 45.0)

        ix, iy = canvas.screen_to_image(70.0, 45.0)
        self.assertEqual(ix, 10.0)
        self.assertEqual(iy, 10.0)

    def test_canvas_image_draw_hook(self) -> None:
        canvas = Canvas()
        target_surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 100, 100)
        cr = cairo.Context(target_surface)

        mock_hook = Mock()
        canvas.add_image_draw_hook(mock_hook)
        canvas._on_draw(canvas, cr, 100, 100)
        mock_hook.assert_called_once_with(cr)

        mock_hook.reset_mock()
        canvas.remove_image_draw_hook(mock_hook)
        canvas._on_draw(canvas, cr, 100, 100)
        mock_hook.assert_not_called()


if __name__ == "__main__":
    unittest.main()
