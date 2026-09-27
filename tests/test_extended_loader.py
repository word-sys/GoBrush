from __future__ import annotations
import io
import tempfile
import unittest
from pathlib import Path
from PIL import Image
import cairo

from gobrush.core.loader import (
    load_image,
    load_image_with_info,
    pil_to_cairo_surface,
    pil_to_cairo_surface_with_info,
    is_supported_image,
    SUPPORTED_FORMATS,
    ImageLoadError,
)


class TestExtendedImageLoader(unittest.TestCase):
    def test_extended_supported_formats(self) -> None:
        for ext in [".bmp", ".dib", ".tiff", ".tif", ".ico", ".gif"]:
            self.assertIn(ext, SUPPORTED_FORMATS)
            self.assertTrue(is_supported_image(f"test{ext}"))
            self.assertTrue(is_supported_image(f"TEST{ext.upper()}"))

    def test_load_bmp_rgb(self) -> None:
        im = Image.new("RGB", (32, 24), (200, 100, 50))
        buf = io.BytesIO()
        im.save(buf, format="BMP")
        buf.seek(0)

        surf, has_alpha = load_image_with_info(buf)
        self.assertIsInstance(surf, cairo.ImageSurface)
        self.assertEqual(surf.get_width(), 32)
        self.assertEqual(surf.get_height(), 24)
        self.assertFalse(has_alpha)

        data = surf.get_data()
        self.assertEqual(data[0], 50)
        self.assertEqual(data[1], 100)
        self.assertEqual(data[2], 200)
        self.assertEqual(data[3], 255)

    def test_load_bmp_file(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".bmp", delete=False) as tmp:
            im = Image.new("RGB", (20, 20), (10, 20, 30))
            im.save(tmp.name, format="BMP")
            path = tmp.name

        try:
            surf = load_image(path)
            self.assertEqual(surf.get_width(), 20)
            self.assertEqual(surf.get_height(), 20)
        finally:
            Path(path).unlink(missing_ok=True)

    def test_load_tiff_single_and_cmyk(self) -> None:
        # Standard RGB TIFF
        im_rgb = Image.new("RGB", (48, 48), (0, 120, 240))
        buf_rgb = io.BytesIO()
        im_rgb.save(buf_rgb, format="TIFF")
        buf_rgb.seek(0)

        surf, has_alpha = load_image_with_info(buf_rgb)
        self.assertEqual(surf.get_width(), 48)
        self.assertEqual(surf.get_height(), 48)
        self.assertFalse(has_alpha)

        # CMYK TIFF conversion to RGBA
        im_cmyk = Image.new("CMYK", (30, 30), (50, 100, 0, 20))
        buf_cmyk = io.BytesIO()
        im_cmyk.save(buf_cmyk, format="TIFF")
        buf_cmyk.seek(0)

        surf_cmyk, _ = load_image_with_info(buf_cmyk)
        self.assertEqual(surf_cmyk.get_width(), 30)
        self.assertEqual(surf_cmyk.get_height(), 30)

    def test_load_tiff_multipage_reads_first_page(self) -> None:
        page0 = Image.new("RGB", (80, 40), (255, 0, 0))
        page1 = Image.new("RGB", (40, 80), (0, 255, 0))
        buf = io.BytesIO()
        page0.save(buf, format="TIFF", save_all=True, append_images=[page1])
        buf.seek(0)

        surf = load_image(buf)
        self.assertEqual(surf.get_width(), 80)
        self.assertEqual(surf.get_height(), 40)

    def test_load_gif_static_and_transparent(self) -> None:
        # GIF with transparent background
        im_trans = Image.new("RGBA", (25, 25), (0, 0, 0, 0))
        im_trans.putpixel((12, 12), (255, 0, 0, 255))
        buf_trans = io.BytesIO()
        im_trans.save(buf_trans, format="GIF", transparency=0)
        buf_trans.seek(0)

        surf, has_alpha = load_image_with_info(buf_trans)
        self.assertEqual(surf.get_width(), 25)
        self.assertEqual(surf.get_height(), 25)
        self.assertTrue(has_alpha)

        # GIF fully opaque
        im_opaque = Image.new("RGB", (25, 25), (100, 150, 200))
        buf_opaque = io.BytesIO()
        im_opaque.save(buf_opaque, format="GIF")
        buf_opaque.seek(0)

        _, has_alpha_opaque = load_image_with_info(buf_opaque)
        self.assertFalse(has_alpha_opaque)

    def test_load_gif_animated_reads_first_frame(self) -> None:
        f0 = Image.new("RGB", (50, 30), (255, 128, 0))
        f1 = Image.new("RGB", (50, 30), (0, 128, 255))
        buf = io.BytesIO()
        f0.save(buf, format="GIF", save_all=True, append_images=[f1], duration=100)
        buf.seek(0)

        surf = load_image(buf)
        self.assertEqual(surf.get_width(), 50)
        self.assertEqual(surf.get_height(), 30)

    def test_load_ico_selects_highest_resolution(self) -> None:
        im = Image.new("RGBA", (64, 64), (0, 200, 100, 255))
        buf = io.BytesIO()
        im.save(buf, format="ICO", sizes=[(16, 16), (32, 32), (64, 64)])
        buf.seek(0)

        surf, has_alpha = load_image_with_info(buf)
        self.assertEqual(surf.get_width(), 64)
        self.assertEqual(surf.get_height(), 64)
        self.assertFalse(has_alpha)

    def test_load_ico_with_transparency(self) -> None:
        im = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
        im.putpixel((10, 10), (255, 255, 0, 255))
        buf = io.BytesIO()
        im.save(buf, format="ICO")
        buf.seek(0)

        surf, has_alpha = load_image_with_info(buf)
        self.assertEqual(surf.get_width(), 32)
        self.assertTrue(has_alpha)

    def test_load_pil_image_directly(self) -> None:
        im = Image.new("RGB", (15, 15), (70, 80, 90))
        surf, has_alpha = load_image_with_info(im)
        self.assertEqual(surf.get_width(), 15)
        self.assertEqual(surf.get_height(), 15)
        self.assertFalse(has_alpha)

    def test_corrupt_files_raise_image_load_error(self) -> None:
        # Corrupt BMP
        corrupt_bmp = b"BM" + b"\x00" * 20
        with self.assertRaises(ImageLoadError):
            load_image(corrupt_bmp)

        # Corrupt GIF
        corrupt_gif = b"GIF89a" + b"\x00" * 10
        with self.assertRaises(ImageLoadError):
            load_image(corrupt_gif)

    def test_invalid_dimensions_raise_image_load_error(self) -> None:
        im = Image.new("RGBA", (1, 1))
        # Modify size to 0
        im._size = (0, 0)
        with self.assertRaises(ImageLoadError):
            pil_to_cairo_surface_with_info(im)


if __name__ == "__main__":
    unittest.main()
