from __future__ import annotations
import io
import tempfile
import unittest
from pathlib import Path
import cairo

from gobrush.core.loader import (
    load_image,
    load_image_with_info,
    load_svg,
    load_svg_with_info,
    is_supported_image,
    SUPPORTED_FORMATS,
    ImageLoadError,
)


class TestSvgLoader(unittest.TestCase):
    def test_svg_supported_format(self) -> None:
        self.assertIn(".svg", SUPPORTED_FORMATS)
        self.assertTrue(is_supported_image("diagram.svg"))
        self.assertTrue(is_supported_image("ICON.SVG"))

    def test_load_svg_from_bytes(self) -> None:
        svg_xml = b"""<svg width="200" height="100" xmlns="http://www.w3.org/2000/svg">
            <rect width="200" height="100" fill="#ff0000"/>
        </svg>"""
        surf, has_alpha = load_svg_with_info(svg_xml)
        self.assertIsInstance(surf, cairo.ImageSurface)
        self.assertEqual(surf.get_width(), 200)
        self.assertEqual(surf.get_height(), 100)
        self.assertEqual(surf.get_format(), cairo.FORMAT_ARGB32)
        self.assertFalse(has_alpha)

        data = surf.get_data()
        # ARGB32 in memory (BGRA): B=0, G=0, R=255, A=255
        self.assertEqual(data[0], 0)
        self.assertEqual(data[1], 0)
        self.assertEqual(data[2], 255)
        self.assertEqual(data[3], 255)

    def test_load_svg_from_file(self) -> None:
        svg_content = """<svg width="120" height="80" xmlns="http://www.w3.org/2000/svg">
            <rect width="120" height="80" fill="#0000ff"/>
        </svg>"""
        with tempfile.NamedTemporaryFile(suffix=".svg", delete=False, mode="w") as tmp:
            tmp.write(svg_content)
            path = tmp.name

        try:
            surf_str = load_image(path)
            self.assertEqual(surf_str.get_width(), 120)
            self.assertEqual(surf_str.get_height(), 80)

            surf_path = load_image(Path(path))
            self.assertEqual(surf_path.get_width(), 120)
            self.assertEqual(surf_path.get_height(), 80)
        finally:
            Path(path).unlink(missing_ok=True)

    def test_load_svg_with_transparency(self) -> None:
        svg_xml = b"""<svg width="60" height="60" xmlns="http://www.w3.org/2000/svg">
            <circle cx="30" cy="30" r="15" fill="#00ff00"/>
        </svg>"""
        surf, has_alpha = load_svg_with_info(svg_xml)
        self.assertEqual(surf.get_width(), 60)
        self.assertEqual(surf.get_height(), 60)
        self.assertTrue(has_alpha)

        data = surf.get_data()
        # Corner pixel should be transparent
        self.assertEqual(data[3], 0)

        # Center pixel (30, 30) should be green (B=0, G=255, R=0, A=255)
        center_idx = (30 * 60 + 30) * 4
        self.assertEqual(data[center_idx + 1], 255) # Green
        self.assertEqual(data[center_idx + 3], 255) # Alpha

    def test_load_svg_with_viewbox_only(self) -> None:
        svg_xml = b"""<svg viewBox="0 0 350 250" xmlns="http://www.w3.org/2000/svg">
            <rect width="350" height="250" fill="#ffff00"/>
        </svg>"""
        surf = load_svg(svg_xml)
        self.assertEqual(surf.get_width(), 350)
        self.assertEqual(surf.get_height(), 250)

    def test_load_svg_scale(self) -> None:
        svg_xml = b"""<svg width="40" height="30" xmlns="http://www.w3.org/2000/svg">
            <rect width="40" height="30" fill="#000000"/>
        </svg>"""
        surf = load_svg(svg_xml, scale=3.0)
        self.assertEqual(surf.get_width(), 120)
        self.assertEqual(surf.get_height(), 90)

    def test_load_svg_automatic_routing(self) -> None:
        svg_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
        <svg width="50" height="50" xmlns="http://www.w3.org/2000/svg">
            <rect width="50" height="50" fill="#123456"/>
        </svg>"""
        # Load through general load_image_with_info bytes dispatch
        surf, has_alpha = load_image_with_info(svg_xml)
        self.assertEqual(surf.get_width(), 50)
        self.assertEqual(surf.get_height(), 50)

    def test_load_svg_stream(self) -> None:
        svg_stream = io.BytesIO(b"""<svg width="35" height="35" xmlns="http://www.w3.org/2000/svg">
            <rect width="35" height="35" fill="#abcdef"/>
        </svg>""")
        surf = load_image(svg_stream)
        self.assertEqual(surf.get_width(), 35)
        self.assertEqual(surf.get_height(), 35)

    def test_corrupt_svg_raises_error(self) -> None:
        with self.assertRaises(ImageLoadError):
            load_svg(b"<svg><unclosed tag without closing")

    def test_empty_svg_raises_error(self) -> None:
        with self.assertRaises(ImageLoadError):
            load_svg(b"")

    def test_nonexistent_svg_file_raises_error(self) -> None:
        with self.assertRaises(ImageLoadError):
            load_svg("/path/to/definitely/nonexistent/graphic.svg")


if __name__ == "__main__":
    unittest.main()
