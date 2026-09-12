from __future__ import annotations
import os
import io
from pathlib import Path
from typing import Union
import cairo
import warnings
from PIL import Image, ImageOps, UnidentifiedImageError

try:
    import gi
    gi.require_version("Rsvg", "2.0")
    from gi.repository import Rsvg, GLib
    _HAVE_RSVG = True
except (ImportError, ValueError):
    _HAVE_RSVG = False

try:
    import numpy as np
    _HAVE_NUMPY = True
except ImportError:
    _HAVE_NUMPY = False


class ImageLoadError(Exception):
    pass


SUPPORTED_FORMATS: frozenset[str] = frozenset(
    {
        ".png",
        ".jpg",
        ".jpeg",
        ".jpe",
        ".jfif",
        ".webp",
        ".bmp",
        ".dib",
        ".tiff",
        ".tif",
        ".ico",
        ".gif",
        ".svg",
    }
)


def is_supported_image(path: Union[str, Path]) -> bool:
    ext = os.path.splitext(str(path))[1].lower()
    return ext in SUPPORTED_FORMATS


def pil_to_cairo_surface(im: Image.Image) -> cairo.ImageSurface:
    surface, _ = pil_to_cairo_surface_with_info(im)
    return surface


def pil_to_cairo_surface_with_info(im: Image.Image) -> tuple[cairo.ImageSurface, bool]:
    w, h = getattr(im, "size", (0, 0))
    if w <= 0 or h <= 0:
        raise ImageLoadError(f"Image has invalid dimensions: {w}x{h}")

    # Handle multi-frame formats (animated GIF, multi-page TIFF) by reading first frame
    if getattr(im, "n_frames", 1) > 1:
        try:
            im.seek(0)
        except (EOFError, OSError):
            pass

    # For multi-resolution ICO files, pick highest-resolution icon
    if hasattr(im, "ico") and hasattr(im.ico, "sizes"):
        try:
            sizes = sorted(im.ico.sizes(), key=lambda s: s[0] * s[1])
            if sizes:
                im = im.ico.getimage(sizes[-1])
        except Exception:
            pass

    # Handle EXIF orientation tag if present
    try:
        im = ImageOps.exif_transpose(im)
    except Exception:
        pass

    if im.mode != "RGBA":
        im = im.convert("RGBA")

    w, h = im.size
    if w <= 0 or h <= 0:
        raise ImageLoadError(f"Image has invalid dimensions: {w}x{h}")

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


def _is_svg_bytes(data: bytes) -> bool:
    prefix = data[:1024].lstrip()
    return (
        prefix.startswith(b"<svg")
        or (prefix.startswith(b"<?xml") and b"<svg" in prefix)
        or (prefix.startswith(b"<!--") and b"<svg" in data[:2048])
    )


def _get_svg_dimensions(handle: Rsvg.Handle) -> tuple[int, int]:
    if hasattr(handle, "get_intrinsic_size_in_pixels"):
        try:
            ok, w, h = handle.get_intrinsic_size_in_pixels()
            if ok and w > 0 and h > 0:
                return max(1, int(round(w))), max(1, int(round(h)))
        except Exception:
            pass
    if hasattr(handle, "get_dimensions"):
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", DeprecationWarning)
                dim = handle.get_dimensions()
                if dim.width > 0 and dim.height > 0:
                    return max(1, int(dim.width)), max(1, int(dim.height))
        except Exception:
            pass
    return 800, 600


def load_svg(
    source: Union[str, Path, io.BytesIO, bytes],
    scale: float = 1.0,
    max_dim: int = 8192,
) -> cairo.ImageSurface:
    surface, _ = load_svg_with_info(source, scale=scale, max_dim=max_dim)
    return surface


def load_svg_with_info(
    source: Union[str, Path, io.BytesIO, bytes],
    scale: float = 1.0,
    max_dim: int = 8192,
) -> tuple[cairo.ImageSurface, bool]:
    if not _HAVE_RSVG:
        raise ImageLoadError("SVG format requires librsvg (Rsvg 2.0)")

    if isinstance(source, (str, Path)):
        p = Path(source).expanduser().resolve()
        if not p.is_file():
            raise ImageLoadError(f"File not found: {source}")
        try:
            raw_bytes = p.read_bytes()
        except OSError as e:
            raise ImageLoadError(f"Cannot read SVG file '{source}': {e}") from e
    elif isinstance(source, (bytes, bytearray)):
        raw_bytes = bytes(source)
    elif hasattr(source, "read"):
        try:
            content = source.read()
            raw_bytes = content.encode("utf-8") if isinstance(content, str) else bytes(content)
        except Exception as e:
            raise ImageLoadError(f"Cannot read SVG stream: {e}") from e
    else:
        raise ImageLoadError(f"Unsupported SVG source type: {type(source)}")

    if not raw_bytes.strip():
        raise ImageLoadError("Empty SVG content")

    try:
        handle = Rsvg.Handle.new_from_data(raw_bytes)
    except Exception as e:
        raise ImageLoadError(f"Failed to parse SVG: {e}") from e

    orig_w, orig_h = _get_svg_dimensions(handle)
    target_w = max(1, int(round(orig_w * scale)))
    target_h = max(1, int(round(orig_h * scale)))

    if target_w > max_dim or target_h > max_dim:
        clamp_factor = min(max_dim / target_w, max_dim / target_h)
        target_w = max(1, int(round(target_w * clamp_factor)))
        target_h = max(1, int(round(target_h * clamp_factor)))

    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, target_w, target_h)
    cr = cairo.Context(surface)

    if hasattr(Rsvg, "Rectangle") and hasattr(handle, "render_document"):
        rect = Rsvg.Rectangle()
        rect.x, rect.y, rect.width, rect.height = 0, 0, target_w, target_h
        handle.render_document(cr, rect)
    else:
        scale_x = target_w / orig_w
        scale_y = target_h / orig_h
        if scale_x != 1.0 or scale_y != 1.0:
            cr.scale(scale_x, scale_y)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            handle.render_cairo(cr)

    data = surface.get_data()
    if _HAVE_NUMPY:
        has_alpha = bool(np.any(np.frombuffer(data, dtype=np.uint8)[3::4] != 255))
    else:
        has_alpha = False
        for i in range(3, len(data), 4):
            if data[i] != 255:
                has_alpha = True
                break

    return surface, has_alpha


def load_image(source: Union[str, Path, io.BytesIO, bytes]) -> cairo.ImageSurface:
    surface, _ = load_image_with_info(source)
    return surface


def load_image_with_info(
    source: Union[str, Path, io.BytesIO, bytes, Image.Image],
) -> tuple[cairo.ImageSurface, bool]:
    if isinstance(source, (str, Path)):
        p = Path(source).expanduser().resolve()
        if not p.is_file():
            raise ImageLoadError(f"File not found: {source}")
        if p.suffix.lower() == ".svg":
            return load_svg_with_info(p)
        try:
            with Image.open(p) as im:
                return pil_to_cairo_surface_with_info(im)
        except (UnidentifiedImageError, OSError, ValueError) as e:
            raise ImageLoadError(f"Cannot read image file '{source}': {e}") from e

    elif isinstance(source, (bytes, bytearray)):
        b = bytes(source)
        if _is_svg_bytes(b):
            return load_svg_with_info(b)
        try:
            with Image.open(io.BytesIO(b)) as im:
                return pil_to_cairo_surface_with_info(im)
        except (UnidentifiedImageError, OSError, ValueError) as e:
            raise ImageLoadError(f"Cannot decode image bytes: {e}") from e

    elif hasattr(source, "read"):
        if getattr(source, "name", "").lower().endswith(".svg"):
            return load_svg_with_info(source)
        try:
            content = source.read()
            b = content.encode("utf-8") if isinstance(content, str) else bytes(content)
            if _is_svg_bytes(b):
                return load_svg_with_info(b)
            with Image.open(io.BytesIO(b)) as im:
                return pil_to_cairo_surface_with_info(im)
        except (UnidentifiedImageError, OSError, ValueError) as e:
            raise ImageLoadError(f"Cannot decode image stream: {e}") from e

    elif isinstance(source, Image.Image):
        try:
            return pil_to_cairo_surface_with_info(source)
        except ImageLoadError:
            raise
        except Exception as e:
            raise ImageLoadError(f"Cannot convert image: {e}") from e

    raise ImageLoadError(f"Unsupported image source type: {type(source)}")

