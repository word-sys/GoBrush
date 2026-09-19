from pathlib import Path
from typing import Callable
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Gdk, Adw


def _get_icon_texture() -> Gdk.Texture | None:
    icon_paths = [
        Path(__file__).resolve().parent.parent.parent / "icon" / "gobrush.svg",
        Path("/usr/share/icons/hicolor/scalable/apps/gobrush.svg"),
        Path("/usr/share/gobrush/icon/gobrush.svg"),
    ]
    for p in icon_paths:
        if p.is_file():
            try:
                return Gdk.Texture.new_from_filename(str(p))
            except Exception:
                pass
    return None


class EmptyStateView(Adw.Bin):
    def __init__(
        self,
        on_open: Callable[[], None] | None = None,
        on_paste: Callable[[], None] | None = None,
        on_new: Callable[[], None] | None = None,
    ) -> None:
        super().__init__()
        self.on_open = on_open
        self.on_paste = on_paste
        self.on_new = on_new

        root_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        tex = _get_icon_texture()
        if tex is not None:
            self.status_page = Adw.StatusPage(
                title="GoBrush",
                description="Simple, fast, and lightweight image annotator",
                paintable=tex,
            )
            img = self._find_image(self.status_page)
            if img is not None:
                img.set_pixel_size(220)
        else:
            self.status_page = Adw.StatusPage(
                title="GoBrush",
                description="Simple, fast, and lightweight image annotator",
                icon_name="image-x-generic-symbolic",
            )
        self.status_page.set_vexpand(True)
        self.status_page.set_hexpand(True)

        btn_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        btn_box.set_halign(Gtk.Align.CENTER)

        self.btn_new = Gtk.Button(label="New Canvas...")
        self.btn_new.add_css_class("suggested-action")
        self.btn_new.add_css_class("pill")
        self.btn_new.set_size_request(200, 40)
        if on_new:
            self.btn_new.connect("clicked", lambda _: on_new())
        btn_box.append(self.btn_new)

        self.btn_open = Gtk.Button(label="Open File...")
        self.btn_open.add_css_class("pill")
        self.btn_open.set_size_request(200, 40)
        if on_open:
            self.btn_open.connect("clicked", lambda _: on_open())
        btn_box.append(self.btn_open)

        self.btn_paste = Gtk.Button(label="Paste from Clipboard")
        self.btn_paste.add_css_class("pill")
        self.btn_paste.set_size_request(200, 40)
        if on_paste:
            self.btn_paste.connect("clicked", lambda _: on_paste())
        btn_box.append(self.btn_paste)

        self.status_page.set_child(btn_box)
        root_box.append(self.status_page)

        bottom_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        bottom_bar.set_margin_start(16)
        bottom_bar.set_margin_bottom(8)

        bottom_label = Gtk.Label(label="Open a file or drag and drop one here.")
        bottom_label.add_css_class("dim-label")
        bottom_bar.append(bottom_label)
        root_box.append(bottom_bar)

        self.set_child(root_box)

    @staticmethod
    def _find_image(widget: Gtk.Widget) -> Gtk.Image | None:
        if isinstance(widget, Gtk.Image):
            return widget
        child = widget.get_first_child()
        while child:
            res = EmptyStateView._find_image(child)
            if res is not None:
                return res
            child = child.get_next_sibling()
        return None
