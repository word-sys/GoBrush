from __future__ import annotations
from typing import Callable
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk


def _build_image_filters() -> list[Gtk.FileFilter]:
    all_supported = Gtk.FileFilter()
    all_supported.set_name("All Supported Images")
    patterns = [
        "*.png", "*.jpg", "*.jpeg", "*.webp", "*.svg",
        "*.bmp", "*.tiff", "*.tif", "*.ico", "*.gif",
    ]
    for p in patterns:
        all_supported.add_pattern(p)
        all_supported.add_pattern(p.upper())

    png_filter = Gtk.FileFilter()
    png_filter.set_name("PNG Image (*.png)")
    png_filter.add_pattern("*.png")
    png_filter.add_pattern("*.PNG")

    jpg_filter = Gtk.FileFilter()
    jpg_filter.set_name("JPEG Image (*.jpg, *.jpeg)")
    jpg_filter.add_pattern("*.jpg")
    jpg_filter.add_pattern("*.jpeg")
    jpg_filter.add_pattern("*.JPG")
    jpg_filter.add_pattern("*.JPEG")

    webp_filter = Gtk.FileFilter()
    webp_filter.set_name("WebP Image (*.webp)")
    webp_filter.add_pattern("*.webp")
    webp_filter.add_pattern("*.WEBP")

    svg_filter = Gtk.FileFilter()
    svg_filter.set_name("SVG Image (*.svg)")
    svg_filter.add_pattern("*.svg")
    svg_filter.add_pattern("*.SVG")

    all_files = Gtk.FileFilter()
    all_files.set_name("All Files (*.*)")
    all_files.add_pattern("*")

    return [all_supported, png_filter, jpg_filter, webp_filter, svg_filter, all_files]


def open_file_dialog(
    parent: Gtk.Window | None,
    callback: Callable[[str | None], None],
    title: str = "Open Image",
    show: bool = True,
) -> Gtk.FileChooserNative:
    dialog = Gtk.FileChooserNative.new(
        title, parent, Gtk.FileChooserAction.OPEN, "_Open", "_Cancel"
    )
    for f in _build_image_filters():
        dialog.add_filter(f)

    def _on_response(native: Gtk.FileChooserNative, response: int) -> None:
        path: str | None = None
        if response == Gtk.ResponseType.ACCEPT:
            gfile = native.get_file()
            if gfile:
                path = gfile.get_path()
        native.destroy()
        callback(path)

    dialog.connect("response", _on_response)
    if show:
        dialog.show()
    return dialog


def save_file_dialog(
    parent: Gtk.Window | None,
    callback: Callable[[str | None], None],
    default_name: str = "Screenshot.png",
    title: str = "Save Image",
    show: bool = True,
) -> Gtk.FileChooserNative:
    dialog = Gtk.FileChooserNative.new(
        title, parent, Gtk.FileChooserAction.SAVE, "_Save", "_Cancel"
    )
    dialog.set_current_name(default_name)
    for f in _build_image_filters():
        dialog.add_filter(f)

    def _on_response(native: Gtk.FileChooserNative, response: int) -> None:
        path: str | None = None
        if response == Gtk.ResponseType.ACCEPT:
            gfile = native.get_file()
            if gfile:
                path = gfile.get_path()
        native.destroy()
        callback(path)

    dialog.connect("response", _on_response)
    if show:
        dialog.show()
    return dialog
