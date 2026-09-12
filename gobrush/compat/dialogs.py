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

    bmp_filter = Gtk.FileFilter()
    bmp_filter.set_name("BMP Image (*.bmp, *.dib)")
    bmp_filter.add_pattern("*.bmp")
    bmp_filter.add_pattern("*.dib")
    bmp_filter.add_pattern("*.BMP")
    bmp_filter.add_pattern("*.DIB")

    tiff_filter = Gtk.FileFilter()
    tiff_filter.set_name("TIFF Image (*.tiff, *.tif)")
    tiff_filter.add_pattern("*.tiff")
    tiff_filter.add_pattern("*.tif")
    tiff_filter.add_pattern("*.TIFF")
    tiff_filter.add_pattern("*.TIF")

    ico_filter = Gtk.FileFilter()
    ico_filter.set_name("ICO Icon (*.ico)")
    ico_filter.add_pattern("*.ico")
    ico_filter.add_pattern("*.ICO")

    gif_filter = Gtk.FileFilter()
    gif_filter.set_name("GIF Image (*.gif)")
    gif_filter.add_pattern("*.gif")
    gif_filter.add_pattern("*.GIF")

    all_files = Gtk.FileFilter()
    all_files.set_name("All Files (*.*)")
    all_files.add_pattern("*")

    return [
        all_supported,
        png_filter,
        jpg_filter,
        webp_filter,
        bmp_filter,
        tiff_filter,
        ico_filter,
        gif_filter,
        svg_filter,
        all_files,
    ]


def open_file_dialog(
    parent: Gtk.Window | None,
    callback: Callable[[str | None], None],
    title: str = "Open Image",
    show: bool = True,
) -> Gtk.FileChooserDialog:
    dialog = Gtk.FileChooserDialog(
        title=title,
        transient_for=parent,
        action=Gtk.FileChooserAction.OPEN,
    )
    dialog.add_buttons(
        "_Cancel", Gtk.ResponseType.CANCEL,
        "_Open", Gtk.ResponseType.ACCEPT,
    )
    dialog.set_modal(True)
    for f in _build_image_filters():
        dialog.add_filter(f)

    def _on_response(dlg: Gtk.FileChooserDialog, response: int) -> None:
        path: str | None = None
        if response == Gtk.ResponseType.ACCEPT:
            gfile = dlg.get_file()
            if gfile:
                path = gfile.get_path()
        dlg.destroy()
        if parent is not None and getattr(parent, "_active_file_dialog", None) is dlg:
            parent._active_file_dialog = None
        callback(path)

    dialog.connect("response", _on_response)
    if parent is not None:
        parent._active_file_dialog = dialog
    if show:
        dialog.present()
    return dialog


def save_file_dialog(
    parent: Gtk.Window | None,
    callback: Callable[[str | None], None],
    default_name: str = "Screenshot.png",
    title: str = "Save Image",
    show: bool = True,
) -> Gtk.FileChooserDialog:
    dialog = Gtk.FileChooserDialog(
        title=title,
        transient_for=parent,
        action=Gtk.FileChooserAction.SAVE,
    )
    dialog.add_buttons(
        "_Cancel", Gtk.ResponseType.CANCEL,
        "_Save", Gtk.ResponseType.ACCEPT,
    )
    dialog.set_modal(True)
    dialog.set_current_name(default_name)
    for f in _build_image_filters():
        dialog.add_filter(f)

    def _on_response(dlg: Gtk.FileChooserDialog, response: int) -> None:
        path: str | None = None
        if response == Gtk.ResponseType.ACCEPT:
            gfile = dlg.get_file()
            if gfile:
                path = gfile.get_path()
        dlg.destroy()
        if parent is not None and getattr(parent, "_active_file_dialog", None) is dlg:
            parent._active_file_dialog = None
        callback(path)

    dialog.connect("response", _on_response)
    if parent is not None:
        parent._active_file_dialog = dialog
    if show:
        dialog.present()
    return dialog
