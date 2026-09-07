from __future__ import annotations
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk


class CanvasStatusBar(Gtk.Box):
    def __init__(self) -> None:
        super().__init__(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.add_css_class("osd")
        self.add_css_class("toolbar")
        self.set_halign(Gtk.Align.END)
        self.set_valign(Gtk.Align.END)
        self.set_margin_bottom(12)
        self.set_margin_end(12)

        # Zoom level label
        self.lbl_zoom = Gtk.Label(label="100%")
        self.lbl_zoom.add_css_class("caption")
        self.lbl_zoom.add_css_class("numeric")
        self.append(self.lbl_zoom)

        # Separator 1
        self.sep_1 = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        self.append(self.sep_1)

        # Image dimensions label
        self.lbl_dimensions = Gtk.Label(label="")
        self.lbl_dimensions.add_css_class("caption")
        self.lbl_dimensions.add_css_class("numeric")
        self.lbl_dimensions.set_visible(False)
        self.append(self.lbl_dimensions)

        # Separator 2
        self.sep_2 = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)
        self.sep_2.set_visible(False)
        self.append(self.sep_2)

        # Cursor coordinates label
        self.lbl_coords = Gtk.Label(label="—, —")
        self.lbl_coords.add_css_class("caption")
        self.lbl_coords.add_css_class("numeric")
        self.append(self.lbl_coords)

    def set_zoom(self, zoom: float) -> None:
        self.lbl_zoom.set_text(f"{round(zoom * 100)}%")

    def set_dimensions(self, width: int, height: int) -> None:
        if width > 0 and height > 0:
            self.lbl_dimensions.set_text(f"{width} × {height} px")
            self.lbl_dimensions.set_visible(True)
            self.sep_2.set_visible(True)
        else:
            self.lbl_dimensions.set_text("")
            self.lbl_dimensions.set_visible(False)
            self.sep_2.set_visible(False)

    def set_cursor_position(self, x: int | None, y: int | None) -> None:
        if x is not None and y is not None:
            self.lbl_coords.set_text(f"{x}, {y} px")
        else:
            self.lbl_coords.set_text("—, —")
