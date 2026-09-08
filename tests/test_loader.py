from __future__ import annotations
import unittest
import io
import tempfile
from pathlib import Path
from PIL import Image
import cairo

from gobrush.core.loader import (
    load_image,
    pil_to_cairo_surface,
    cairo_surface_to_pil,
    is_supported_image,
    SUPPORTED_FORMATS,
    ImageLoadError,
)


class TestImageLoader(unittest.TestCase):
    def test_supported_formats(self) -> None:
        self.assertTrue(is_supported_image("photo.png"))
        self.assertTrue(is_supported_image("PHOTO.PNG"))
        self.assertTrue(is_supported_image("image.jpg"))
        self.assertTrue(is_supported_image("image.jpeg"))
        self.assertTrue(is_supported_image("image.webp"))
        self.assertTrue(is_supported_image("image.jfif"))
        self.assertFalse(is_supported_image("doc.pdf"))
        self.assertFalse(is_supported_image("text.txt"))

    def test_load_png_rgba(self) -> None:
        # Create an RGBA PNG with semi-transparency
        im = Image.new("RGBA", (40, 20), (200, 100, 50, 128))
        buf = io.BytesIO()
        im.save(buf, format="PNG")
        buf.seek(0)

        surf = load_image(buf)
        self.assertIsInstance(surf, cairo.ImageSurface)
        self.assertEqual(surf.get_width(), 40)
        self.assertEqual(surf.get_height(), 20)
        self.assertEqual(surf.get_format(), cairo.FORMAT_ARGB32)

        # Verify premultiplied data in memory
        data = surf.get_data()
        b, g, r, a = data[0], data[1], data[2], data[3]
        self.assertAlmostEqual(b, int(50 * 128 / 255), delta=1)
        self.assertAlmostEqual(g, int(100 * 128 / 255), delta=1)
        self.assertAlmostEqual(r, int(200 * 128 / 255), delta=1)
        self.assertEqual(a, 128)

    def test_load_jpeg_rgb(self) -> None:
        im = Image.new("RGB", (30, 30), (10, 120, 230))
        buf = io.BytesIO()
        im.save(buf, format="JPEG")
        raw_bytes = buf.getvalue()

        # Load from raw bytes
        surf = load_image(raw_bytes)
        self.assertEqual(surf.get_width(), 30)
        self.assertEqual(surf.get_height(), 30)
        self.assertEqual(surf.get_format(), cairo.FORMAT_ARGB32)

        data = surf.get_data()
        b, g, r, a = data[0], data[1], data[2], data[3]
        self.assertEqual(a, 255)
        self.assertAlmostEqual(r, 10, delta=15) # JPEG lossy tolerance
        self.assertAlmostEqual(g, 120, delta=15)
        self.assertAlmostEqual(b, 230, delta=15)

    def test_load_webp(self) -> None:
        im = Image.new("RGBA", (25, 25), (0, 255, 100, 255))
        buf = io.BytesIO()
        im.save(buf, format="WEBP")

        surf = load_image(buf.getvalue())
        self.assertEqual(surf.get_width(), 25)
        self.assertEqual(surf.get_height(), 25)

    def test_load_from_filepath(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            temp_path = f.name
            im = Image.new("RGB", (50, 60), (255, 255, 0))
            im.save(temp_path, format="PNG")

        try:
            surf = load_image(temp_path)
            self.assertEqual(surf.get_width(), 50)
            self.assertEqual(surf.get_height(), 60)

            surf_pathlib = load_image(Path(temp_path))
            self.assertEqual(surf_pathlib.get_width(), 50)
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_load_nonexistent_file(self) -> None:
        with self.assertRaises(ImageLoadError) as ctx:
            load_image("/nonexistent/path/to/missing_photo.png")
        self.assertIn("not found", str(ctx.exception).lower())

    def test_load_corrupt_data(self) -> None:
        corrupt_bytes = b"NOT_A_VALID_IMAGE_HEADER_12345"
        with self.assertRaises(ImageLoadError):
            load_image(corrupt_bytes)

    def test_load_invalid_source_type(self) -> None:
        with self.assertRaises(ImageLoadError):
            load_image(12345) # type: ignore

    def test_roundtrip_pil_cairo_pil(self) -> None:
        orig = Image.new("RGBA", (16, 16), (220, 140, 70, 200))
        surf = pil_to_cairo_surface(orig)
        restored = cairo_surface_to_pil(surf)

        self.assertEqual(restored.size, orig.size)
        r, g, b, a = restored.getpixel((0, 0))
        self.assertAlmostEqual(r, 220, delta=1)
        self.assertAlmostEqual(g, 140, delta=1)
        self.assertAlmostEqual(b, 70, delta=1)
        self.assertEqual(a, 200)

    def test_opaque_fast_path(self) -> None:
        orig = Image.new("RGB", (10, 10), (12, 34, 56))
        surf = pil_to_cairo_surface(orig)
        data = surf.get_data()
        # In BGRA memory: b=56, g=34, r=12, a=255
        self.assertEqual(data[0], 56)
        self.assertEqual(data[1], 34)
        self.assertEqual(data[2], 12)
        self.assertEqual(data[3], 255)


if __name__ == "__main__":
    unittest.main()
