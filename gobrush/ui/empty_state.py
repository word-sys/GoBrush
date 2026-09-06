from __future__ import annotations
from typing import Callable
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw


class EmptyStateView(Adw.Bin):
    def __init__(
        self,
        on_open: Callable[[], None] | None = None,
        on_paste: Callable[[], None] | None = None,
    ) -> None:
        super().__init__()
        self.on_open = on_open
        self.on_paste = on_paste

        self.status_page = Adw.StatusPage(
            title="GoBrush",
            description="Paste an image from clipboard, drag and drop, or open a file",
            icon_name="image-x-generic-symbolic",
        )

        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        btn_box.set_halign(Gtk.Align.CENTER)

        self.btn_open = Gtk.Button(label="Open Image")
        self.btn_open.set_icon_name("document-open-symbolic")
        self.btn_open.add_css_class("suggested-action")
        self.btn_open.add_css_class("pill")
        if on_open:
            self.btn_open.connect("clicked", lambda _: on_open())
        btn_box.append(self.btn_open)

        self.btn_paste = Gtk.Button(label="Paste from Clipboard")
        self.btn_paste.set_icon_name("edit-paste-symbolic")
        self.btn_paste.add_css_class("pill")
        if on_paste:
            self.btn_paste.connect("clicked", lambda _: on_paste())
        btn_box.append(self.btn_paste)

        self.status_page.set_child(btn_box)
        self.set_child(self.status_page)
