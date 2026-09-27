from __future__ import annotations
import io
import unittest
import cairo
from PIL import Image
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk

from gobrush.ui.canvas import Canvas
from gobrush.core.loader import load_image_with_info, pil_to_cairo_surface_with_info


class TestCanvasPerformance(unittest.TestCase):
    def setUp(self) -> None:
        self.canvas = Canvas()
        self.surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 3000, 4000)
        self.canvas.set_image_surface(self.surface, 3000, 4000)

    def test_visible_rect_none_when_empty(self) -> None:
        empty_canvas = Canvas()
        self.assertIsNone(empty_canvas.get_visible_image_rect(800, 600))

    def test_visible_rect_standard_fit(self) -> None:
        self.canvas.set_pan(0.0, 0.0)
        self.canvas.set_zoom(1.0)
        rect = self.canvas.get_visible_image_rect(800, 600)
        self.assertIsNotNone(rect)
        vx, vy, vw, vh = rect
        self.assertAlmostEqual(vx, 0.0)
        self.assertAlmostEqual(vy, 0.0)
        self.assertAlmostEqual(vw, 800.0)
        self.assertAlmostEqual(vh, 600.0)

    def test_visible_rect_zoomed_and_panned(self) -> None:
        self.canvas.set_zoom(2.0)
        self.canvas.set_pan(-200.0, -300.0)
        rect = self.canvas.get_visible_image_rect(1000, 800)
        self.assertIsNotNone(rect)
        vx, vy, vw, vh = rect
        # screen (0, 0) -> image (100, 150)
        self.assertAlmostEqual(vx, 100.0)
        self.assertAlmostEqual(vy, 150.0)
        # screen (1000, 800) -> image (600, 550)
        self.assertAlmostEqual(vw, 500.0)
        self.assertAlmostEqual(vh, 400.0)

    def test_visible_rect_offscreen(self) -> None:
        # Panned completely to the right of viewport
        self.canvas.set_pan(2000.0, 0.0)
        self.assertIsNone(self.canvas.get_visible_image_rect(800, 600))

        # Panned completely past left of viewport
        self.canvas.set_pan(-10000.0, 0.0)
        self.assertIsNone(self.canvas.get_visible_image_rect(800, 600))

    def test_image_has_alpha_handling(self) -> None:
        self.assertTrue(self.canvas.image_has_alpha)

        self.canvas.set_image_surface(self.surface, 3000, 4000, has_alpha=False)
        self.assertFalse(self.canvas.image_has_alpha)

        self.canvas.image_has_alpha = True
        self.assertTrue(self.canvas.image_has_alpha)

    def test_draw_large_image_clipped(self) -> None:
        target = cairo.ImageSurface(cairo.FORMAT_ARGB32, 1920, 1080)
        cr = cairo.Context(target)
        self.canvas.set_zoom(1.5)
        self.canvas.set_pan(-500.0, -500.0)

        # Draw with transparent image (includes clipped checkerboard)
        self.canvas.image_has_alpha = True
        self.canvas._on_draw(self.canvas, cr, 1920, 1080)

        # Draw with opaque image (checkerboard bypassed)
        self.canvas.image_has_alpha = False
        self.canvas._on_draw(self.canvas, cr, 1920, 1080)

    def test_loader_alpha_detection(self) -> None:
        # Opaque image
        im_opaque = Image.new("RGBA", (50, 50), (255, 100, 50, 255))
        surf, has_alpha = pil_to_cairo_surface_with_info(im_opaque)
        self.assertFalse(has_alpha)

        # Transparent image
        im_trans = Image.new("RGBA", (50, 50), (255, 100, 50, 128))
        surf, has_alpha = pil_to_cairo_surface_with_info(im_trans)
        self.assertTrue(has_alpha)

        # Test with stream (JPEG is inherently opaque)
        buf = io.BytesIO()
        im_opaque.convert("RGB").save(buf, format="JPEG")
        buf.seek(0)
        surf, has_alpha = load_image_with_info(buf)
        self.assertFalse(has_alpha)

        # Test opaque PNG (alpha channel present, but all 255)
        buf_png = io.BytesIO()
        im_opaque.save(buf_png, format="PNG")
        buf_png.seek(0)
        surf, has_alpha = load_image_with_info(buf_png)
        self.assertFalse(has_alpha)

    def test_image_pyramid_generated_for_large_image(self) -> None:
        # Large image (3000x4000) should generate pyramid downsample levels (0.5, 0.25, 0.125)
        self.assertGreater(len(self.canvas._image_pyramid), 0)
        scales = [scale for scale, _ in self.canvas._image_pyramid]
        self.assertIn(0.5, scales)
        self.assertIn(0.25, scales)

    def test_select_draw_surface_low_zoom(self) -> None:
        # At 100% (1.0), main surface should be selected
        scale_100, surf_100 = self.canvas._select_draw_surface(1.0)
        self.assertIs(surf_100, self.surface)
        self.assertEqual(scale_100, 1.0)

        # At fit / low zoom (~0.32), a downsampled pyramid level should be selected
        scale_32, surf_32 = self.canvas._select_draw_surface(0.32)
        self.assertIsNot(surf_32, self.surface)
        self.assertLess(scale_32, 1.0)
        self.assertEqual(scale_32, 0.25)

    def test_interaction_adaptive_filter(self) -> None:
        self.canvas.set_zoom(0.32)
        # Stationary: filter should be FILTER_GOOD
        self.assertFalse(self.canvas._is_interacting)
        self.assertEqual(self.canvas.get_active_filter(), cairo.FILTER_GOOD)

        # Active interaction (panning/moving): filter should switch to FILTER_FAST
        self.canvas._set_interacting(True)
        self.assertTrue(self.canvas._is_interacting)
        self.assertEqual(self.canvas.get_active_filter(), cairo.FILTER_FAST)

        # Return to stationary
        self.canvas._set_interacting(False)
        self.assertFalse(self.canvas._is_interacting)
        self.assertEqual(self.canvas.get_active_filter(), cairo.FILTER_GOOD)


if __name__ == "__main__":
    unittest.main()
