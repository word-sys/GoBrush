from __future__ import annotations
import io
import tempfile
from pathlib import Path
import unittest
import cairo
from PIL import Image
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk

from gobrush.core.clipboard import (
    normalize_image_format,
    get_format_display_name,
    get_mime_types_for_format,
    encode_surface_for_format,
    create_clipboard_content_provider,
)


class TestCoreClipboard(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        Gtk.init()

    def test_normalize_image_format(self) -> None:
        self.assertEqual(normalize_image_format(None), "png")
        self.assertEqual(normalize_image_format(""), "png")
        self.assertEqual(normalize_image_format(".jpg"), "jpeg")
        self.assertEqual(normalize_image_format("JPEG"), "jpeg")
        self.assertEqual(normalize_image_format(".ico"), "ico")
        self.assertEqual(normalize_image_format(".svg"), "svg")
        self.assertEqual(normalize_image_format(".png"), "png")
        self.assertEqual(normalize_image_format(".webp"), "webp")
        self.assertEqual(normalize_image_format(".bmp"), "bmp")
        self.assertEqual(normalize_image_format(".tiff"), "tiff")
        self.assertEqual(normalize_image_format(".gif"), "gif")

    def test_get_format_display_name(self) -> None:
        self.assertEqual(get_format_display_name("jpeg"), "JPG")
        self.assertEqual(get_format_display_name("ico"), "ICO")
        self.assertEqual(get_format_display_name("svg"), "SVG")
        self.assertEqual(get_format_display_name("png"), "PNG")
        self.assertEqual(get_format_display_name("webp"), "WEBP")
        self.assertEqual(get_format_display_name("bmp"), "BMP")

    def test_get_mime_types_for_format(self) -> None:
        self.assertEqual(get_mime_types_for_format("jpeg"), ["image/jpeg", "image/jpg"])
        self.assertIn("image/x-icon", get_mime_types_for_format("ico"))
        self.assertIn("image/svg+xml", get_mime_types_for_format("svg"))
        self.assertEqual(get_mime_types_for_format("png"), ["image/png"])
        self.assertEqual(get_mime_types_for_format("webp"), ["image/webp"])

    def test_encode_surface_for_format_png(self) -> None:
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 20, 20)
        data, mimes = encode_surface_for_format(surf, "png")
        self.assertEqual(mimes, ["image/png"])
        self.assertTrue(data.startswith(b"\x89PNG\r\n\x1a\n"))

    def test_encode_surface_for_format_jpeg(self) -> None:
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 20, 20)
        data, mimes = encode_surface_for_format(surf, "jpeg")
        self.assertEqual(mimes, ["image/jpeg", "image/jpg"])
        self.assertTrue(data.startswith(b"\xff\xd8"))
        img = Image.open(io.BytesIO(data))
        self.assertEqual(img.format, "JPEG")

    def test_encode_surface_for_format_ico(self) -> None:
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 32, 32)
        data, mimes = encode_surface_for_format(surf, "ico")
        self.assertIn("image/x-icon", mimes)
        self.assertTrue(data.startswith(b"\x00\x00\x01\x00"))
        img = Image.open(io.BytesIO(data))
        self.assertEqual(img.format, "ICO")

    def test_encode_surface_for_format_svg(self) -> None:
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 25, 25)
        data, mimes = encode_surface_for_format(surf, "svg")
        self.assertIn("image/svg+xml", mimes)
        self.assertIn(b"<svg", data)

    def test_encode_surface_for_format_unmodified_file_passthrough(self) -> None:
        svg_content = b'<svg xmlns="http://www.w3.org/2000/svg" width="5" height="5"/>'
        with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as f:
            f.write(svg_content)
            tmp_path = f.name

        try:
            surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 5, 5)
            data, mimes = encode_surface_for_format(
                surf, "svg", file_path=tmp_path, has_annotations=False
            )
            self.assertEqual(data, svg_content)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_create_clipboard_content_provider_jpeg(self) -> None:
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 16, 16)
        cp, display_name = create_clipboard_content_provider(surf, "jpeg")
        self.assertEqual(display_name, "JPG")
        formats = cp.ref_formats()
        self.assertTrue(formats.contain_mime_type("image/jpeg"))
        self.assertTrue(formats.contain_mime_type("image/jpg"))
        mimes = formats.get_mime_types()
        self.assertEqual(mimes[0], "image/jpeg")
        self.assertTrue(formats.contain_mime_type("image/png"))

    def test_create_clipboard_content_provider_ico(self) -> None:
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 16, 16)
        cp, display_name = create_clipboard_content_provider(surf, "ico")
        self.assertEqual(display_name, "ICO")
        formats = cp.ref_formats()
        self.assertTrue(formats.contain_mime_type("image/x-icon"))
        mimes = formats.get_mime_types()
        self.assertEqual(mimes[0], "image/x-icon")
        self.assertTrue(formats.contain_mime_type("image/png"))

    def test_create_clipboard_content_provider_svg(self) -> None:
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 16, 16)
        cp, display_name = create_clipboard_content_provider(surf, "svg")
        self.assertEqual(display_name, "SVG")
        formats = cp.ref_formats()
        self.assertTrue(formats.contain_mime_type("image/svg+xml"))
        mimes = formats.get_mime_types()
        self.assertEqual(mimes[0], "image/svg+xml")
        self.assertTrue(formats.contain_mime_type("image/png"))

    def test_create_clipboard_content_provider_with_file(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(b"fake")
            path = f.name

        try:
            surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 16, 16)
            cp, _ = create_clipboard_content_provider(surf, "jpeg", file_path=path)
            formats = cp.ref_formats()
            self.assertTrue(formats.contain_mime_type("text/uri-list"))
            self.assertTrue(formats.contain_mime_type("x-special/gnome-copied-files"))
        finally:
            Path(path).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
