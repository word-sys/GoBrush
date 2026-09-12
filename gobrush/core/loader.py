from __future__ import annotations
import os
import io
from pathlib import Path
from typing import Union
import cairo
from PIL import Image, ImageOps, UnidentifiedImageError

try:
    import numpy as np
    _HAVE_NUMPY = True
except ImportError:
    _HAVE_NUMPY = False


class ImageLoadError(Exception):
    pass


SUPPORTED_FORMATS: frozenset[str] = frozenset(
    {".png", ".jpg", ".jpeg", ".jpe", ".jfif", ".webp"}
)


def is_supported_image(path: Union[str, Path]) -> bool:
    ext = os.path.splitext(str(path))[1].lower()
    return ext in SUPPORTED_FORMATS


def pil_to_cairo_surface(im: Image.Image) -> cairo.ImageSurface:
    surface, _ = pil_to_cairo_surface_with_info(im)
    return surface


def pil_to_cairo_surface_with_info(im: Image.Image) -> tuple[cairo.ImageSurface, bool]:
    # Handle EXIF orientation tag if present
    im = ImageOps.exif_transpose(im)
    if im.mode != "RGBA":
        im = im.convert("RGBA")

    w, h = im.size
    # Check if image is fully opaque
    extrema = im.getextrema()
    is_opaque = len(extrema) >= 4 and extrema[3][0] == 255
    has_alpha = not is_opaque

    if is_opaque:
        # Fast path for opaque images: BGRA native byte order without premultiplication
        data = bytearray(im.tobytes("raw", "BGRA"))
    elif _HAVE_NUMPY:
        # Vectorized premultiplication: B = (B*A)/255, G = (G*A)/255, R = (R*A)/255
        arr = np.frombuffer(im.tobytes("raw", "RGBA"), dtype=np.uint8).reshape((h, w, 4)).copy()
        r = arr[:, :, 0].astype(np.uint32)
        g = arr[:, :, 1].astype(np.uint32)
        b = arr[:, :, 2].astype(np.uint32)
        a = arr[:, :, 3].astype(np.uint32)

        out = np.empty_like(arr)
        out[:, :, 0] = ((b * a + 127) // 255).astype(np.uint8)
        out[:, :, 1] = ((g * a + 127) // 255).astype(np.uint8)
        out[:, :, 2] = ((r * a + 127) // 255).astype(np.uint8)
        out[:, :, 3] = a.astype(np.uint8)
        data = bytearray(out.tobytes())
    else:
        # Pure Python fallback premultiplication
        raw = bytearray(im.tobytes("raw", "BGRA"))
        for i in range(0, len(raw), 4):
            a = raw[i + 3]
            if a != 255:
                raw[i] = (raw[i] * a + 127) // 255
                raw[i + 1] = (raw[i + 1] * a + 127) // 255
                raw[i + 2] = (raw[i + 2] * a + 127) // 255
        data = raw

    stride = cairo.ImageSurface.format_stride_for_width(cairo.FORMAT_ARGB32, w)
    temp = cairo.ImageSurface.create_for_data(data, cairo.FORMAT_ARGB32, w, h, stride)

    # Copy into native standalone surface so data buffer can be freed
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    cr = cairo.Context(surface)
    cr.set_source_surface(temp, 0, 0)
    cr.paint()
    return surface, has_alpha


def cairo_surface_to_pil(surface: cairo.ImageSurface) -> Image.Image:
    w, h = surface.get_width(), surface.get_height()
    fmt = surface.get_format()

    if fmt != cairo.FORMAT_ARGB32:
        temp = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
        cr = cairo.Context(temp)
        cr.set_source_surface(surface, 0, 0)
        cr.paint()
        surface = temp

    data = surface.get_data()

    if _HAVE_NUMPY:
        # Vectorized un-premultiplication: R = (R * 255) / A
        c_data = np.frombuffer(data, dtype=np.uint8).reshape((h, w, 4))
        cb = c_data[:, :, 0].astype(np.uint32)
        cg = c_data[:, :, 1].astype(np.uint32)
        cr = c_data[:, :, 2].astype(np.uint32)
        ca = c_data[:, :, 3].astype(np.uint32)

        safe_a = np.where(ca > 0, ca, 1)
        un_arr = np.empty_like(c_data)
        un_arr[:, :, 0] = np.clip((cr * 255 + safe_a // 2) // safe_a, 0, 255).astype(np.uint8)
        un_arr[:, :, 1] = np.clip((cg * 255 + safe_a // 2) // safe_a, 0, 255).astype(np.uint8)
        un_arr[:, :, 2] = np.clip((cb * 255 + safe_a // 2) // safe_a, 0, 255).astype(np.uint8)
        un_arr[:, :, 3] = ca.astype(np.uint8)
        return Image.fromarray(un_arr, "RGBA")
    else:
        raw = bytearray(data)
        for i in range(0, len(raw), 4):
            b, g, r, a = raw[i], raw[i + 1], raw[i + 2], raw[i + 3]
            if a == 255:
                raw[i], raw[i + 1], raw[i + 2] = r, g, b
            elif a == 0:
                raw[i] = raw[i + 1] = raw[i + 2] = 0
            else:
                raw[i] = min(255, (r * 255 + a // 2) // a)
                raw[i + 1] = min(255, (g * 255 + a // 2) // a)
                raw[i + 2] = min(255, (b * 255 + a // 2) // a)
        return Image.frombytes("RGBA", (w, h), bytes(raw), "raw", "RGBA")


def load_image(source: Union[str, Path, io.BytesIO, bytes]) -> cairo.ImageSurface:
    surface, _ = load_image_with_info(source)
    return surface


def load_image_with_info(
    source: Union[str, Path, io.BytesIO, bytes],
) -> tuple[cairo.ImageSurface, bool]:
    if isinstance(source, (str, Path)):
        p = Path(source).expanduser().resolve()
        if not p.is_file():
            raise ImageLoadError(f"File not found: {source}")
        try:
            with Image.open(p) as im:
                return pil_to_cairo_surface_with_info(im)
        except (UnidentifiedImageError, OSError, ValueError) as e:
            raise ImageLoadError(f"Cannot read image file '{source}': {e}") from e

    elif isinstance(source, (bytes, bytearray)):
        try:
            with Image.open(io.BytesIO(source)) as im:
                return pil_to_cairo_surface_with_info(im)
        except (UnidentifiedImageError, OSError, ValueError) as e:
            raise ImageLoadError(f"Cannot decode image bytes: {e}") from e

    elif hasattr(source, "read"):
        try:
            with Image.open(source) as im:
                return pil_to_cairo_surface_with_info(im)
        except (UnidentifiedImageError, OSError, ValueError) as e:
            raise ImageLoadError(f"Cannot decode image stream: {e}") from e

    raise ImageLoadError(f"Unsupported image source type: {type(source)}")

