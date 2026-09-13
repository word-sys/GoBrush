from __future__ import annotations
import base64
import io
from pathlib import Path
from typing import Any
import cairo
from PIL import Image
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gdk, GLib

from gobrush.core.loader import cairo_surface_to_pil


def normalize_image_format(fmt: str | None) -> str:
    if not fmt:
        return "png"
    f = fmt.lower().lstrip(".")
    if f in ("jpg", "jpeg", "jpe", "jfif"):
        return "jpeg"
    if f == "ico":
        return "ico"
    if f == "svg":
        return "svg"
    if f in ("bmp", "dib"):
        return "bmp"
    if f in ("tif", "tiff"):
        return "tiff"
    if f == "webp":
        return "webp"
    if f == "gif":
        return "gif"
    if f == "png":
        return "png"
    return f


def get_format_display_name(fmt: str) -> str:
    norm = normalize_image_format(fmt)
    mapping = {
        "jpeg": "JPG",
        "ico": "ICO",
        "svg": "SVG",
        "png": "PNG",
        "webp": "WEBP",
        "bmp": "BMP",
        "tiff": "TIFF",
        "gif": "GIF",
    }
    return mapping.get(norm, norm.upper())


def get_mime_types_for_format(fmt: str) -> list[str]:
    norm = normalize_image_format(fmt)
    if norm == "jpeg":
        return ["image/jpeg", "image/jpg"]
    if norm == "ico":
        return ["image/x-icon", "image/vnd.microsoft.icon", "image/ico"]
    if norm == "svg":
        return ["image/svg+xml", "image/svg", "text/xml", "text/plain;charset=utf-8"]
    if norm == "png":
        return ["image/png"]
    if norm == "webp":
        return ["image/webp"]
    if norm == "bmp":
        return ["image/bmp", "image/x-bmp", "image/x-MS-bmp"]
    if norm == "tiff":
        return ["image/tiff", "image/tif"]
    if norm == "gif":
        return ["image/gif"]
    return [f"image/{norm}"]


def encode_surface_for_format(
    surface: cairo.ImageSurface,
    fmt: str = "png",
    file_path: str | None = None,
    has_annotations: bool = False,
) -> tuple[bytes, list[str]]:
    norm_fmt = normalize_image_format(fmt)
    mime_types = get_mime_types_for_format(norm_fmt)

    # For unmodified SVG files, pass through exact vector XML bytes
    if norm_fmt == "svg" and file_path and not has_annotations:
        p = Path(file_path)
        if p.is_file() and p.suffix.lower() == ".svg":
            try:
                return p.read_bytes(), mime_types
            except Exception:
                pass

    # For all raster formats (JPEG, ICO, PNG, WEBP, BMP, etc.), encode directly
    # from the surface so pixel orientation is physically upright, avoiding
    # any 90-degree camera EXIF rotation issues across processes.
    if norm_fmt == "png":
        buf = io.BytesIO()
        surface.write_to_png(buf)
        return buf.getvalue(), mime_types

    if norm_fmt == "svg":
        buf = io.BytesIO()
        surface.write_to_png(buf)
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        w, h = surface.get_width(), surface.get_height()
        svg_xml = (
            f'<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">\n'
            f'  <image width="{w}" height="{h}" href="data:image/png;base64,{b64}"/>\n'
            f'</svg>\n'
        ).encode("utf-8")
        return svg_xml, mime_types

    im = cairo_surface_to_pil(surface)
    out = io.BytesIO()

    if norm_fmt == "jpeg":
        if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
            bg = Image.new("RGB", im.size, (255, 255, 255))
            if im.mode != "RGBA":
                im = im.convert("RGBA")
            bg.paste(im, mask=im.split()[3])
            bg.save(out, format="JPEG", quality=95)
        else:
            im.convert("RGB").save(out, format="JPEG", quality=95)
        return out.getvalue(), mime_types

    if norm_fmt == "ico":
        w, h = im.size
        if w > 256 or h > 256:
            im = im.resize((min(256, w), min(256, h)), Image.Resampling.LANCZOS)
        im.save(out, format="ICO")
        return out.getvalue(), mime_types

    if norm_fmt == "webp":
        im.save(out, format="WEBP")
        return out.getvalue(), mime_types

    if norm_fmt == "bmp":
        im.save(out, format="BMP")
        return out.getvalue(), mime_types

    if norm_fmt == "tiff":
        im.save(out, format="TIFF")
        return out.getvalue(), mime_types

    if norm_fmt == "gif":
        im.save(out, format="GIF")
        return out.getvalue(), mime_types

    buf = io.BytesIO()
    surface.write_to_png(buf)
    return buf.getvalue(), ["image/png"]


def create_clipboard_content_provider(
    surface: cairo.ImageSurface,
    fmt: str = "png",
    file_path: str | None = None,
    has_annotations: bool = False,
) -> tuple[Gdk.ContentProvider, str]:
    norm_fmt = normalize_image_format(fmt)
    display_name = get_format_display_name(norm_fmt)
    data, mime_types = encode_surface_for_format(
        surface, norm_fmt, file_path=file_path, has_annotations=has_annotations
    )
    gbytes = GLib.Bytes.new(data)

    providers: list[Gdk.ContentProvider] = []

    # 1. Primary format MIME types first (e.g. image/jpeg, image/x-icon, image/svg+xml)
    for mime in mime_types:
        providers.append(Gdk.ContentProvider.new_for_bytes(mime, gbytes))

    # 2. File URI support for file managers (Nautilus, Dolphin, Thunar) and file drop targets
    if file_path and not has_annotations:
        p = Path(file_path).resolve()
        if p.is_file():
            uri_list = f"{p.as_uri()}\r\n".encode("utf-8")
            gnome_copied = f"copy\n{p.as_uri()}\n".encode("utf-8")
            providers.append(Gdk.ContentProvider.new_for_bytes("text/uri-list", GLib.Bytes.new(uri_list)))
            providers.append(Gdk.ContentProvider.new_for_bytes("x-special/gnome-copied-files", GLib.Bytes.new(gnome_copied)))

    # 3. Universal PNG fallback for web browsers, Electron apps (Discord, Slack), and apps
    # that only implement image/png clipboard support
    if norm_fmt != "png":
        png_buf = io.BytesIO()
        surface.write_to_png(png_buf)
        png_gbytes = GLib.Bytes.new(png_buf.getvalue())
        providers.append(Gdk.ContentProvider.new_for_bytes("image/png", png_gbytes))

    # 4. Native GdkTexture for internal GTK4 applications
    try:
        pixbuf = Gdk.pixbuf_get_from_surface(
            surface, 0, 0, surface.get_width(), surface.get_height()
        )
        if pixbuf is not None:
            texture = Gdk.Texture.new_for_pixbuf(pixbuf)
            if texture is not None:
                providers.append(Gdk.ContentProvider.new_for_value(texture))
    except Exception:
        pass

    if len(providers) == 1:
        return providers[0], display_name
    return Gdk.ContentProvider.new_union(providers), display_name
