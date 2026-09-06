from __future__ import annotations
from typing import Callable
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk


def rgba_from_floats(r: float, g: float, b: float, a: float = 1.0) -> Gdk.RGBA:
    rgba = Gdk.RGBA()
    rgba.red = max(0.0, min(1.0, float(r)))
    rgba.green = max(0.0, min(1.0, float(g)))
    rgba.blue = max(0.0, min(1.0, float(b)))
    rgba.alpha = max(0.0, min(1.0, float(a)))
    return rgba


def rgba_from_hex(hex_str: str) -> Gdk.RGBA:
    rgba = Gdk.RGBA()
    if not rgba.parse(hex_str):
        rgba.parse("#E01B24")
    return rgba


def rgba_to_hex(rgba: Gdk.RGBA, include_alpha: bool = False) -> str:
    r = int(round(rgba.red * 255))
    g = int(round(rgba.green * 255))
    b = int(round(rgba.blue * 255))
    if include_alpha:
        a = int(round(rgba.alpha * 255))
        return f"#{r:02X}{g:02X}{b:02X}{a:02X}"
    return f"#{r:02X}{g:02X}{b:02X}"


def rgba_to_cairo(rgba: Gdk.RGBA) -> tuple[float, float, float, float]:
    return (rgba.red, rgba.green, rgba.blue, rgba.alpha)


def pick_color_dialog(
    parent: Gtk.Window | None,
    current: Gdk.RGBA,
    callback: Callable[[Gdk.RGBA | None], None],
    title: str = "Select Color",
    show: bool = True,
) -> Gtk.ColorChooserDialog:
    dialog = Gtk.ColorChooserDialog.new(title, parent)
    dialog.set_rgba(current)
    dialog.set_use_alpha(True)

    def _on_response(d: Gtk.ColorChooserDialog, response: int) -> None:
        color: Gdk.RGBA | None = None
        if response == Gtk.ResponseType.OK:
            color = d.get_rgba()
        d.destroy()
        callback(color)

    dialog.connect("response", _on_response)
    if show:
        dialog.show()
    return dialog
