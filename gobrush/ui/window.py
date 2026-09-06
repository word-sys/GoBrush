from __future__ import annotations
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio, GLib

from gobrush import __version__


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.set_title("GoBrush")
        self.set_default_size(960, 640)
        self.set_size_request(480, 360)

        self._main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(self._main_box)

        self.header_bar = Adw.HeaderBar()
        self._main_box.append(self.header_bar)

        self.toast_overlay = Adw.ToastOverlay()
        self.toast_overlay.set_vexpand(True)
        self.toast_overlay.set_hexpand(True)
        self._main_box.append(self.toast_overlay)

        self.content_bin = Adw.Bin()
        self.toast_overlay.set_child(self.content_bin)

        self._build_header_actions()
        self._build_menu()

    def _build_header_actions(self) -> None:
        self.btn_open = Gtk.Button(
            icon_name="document-open-symbolic",
            tooltip_text="Open Image (Ctrl+O)",
        )
        self.header_bar.pack_start(self.btn_open)

        self.btn_undo = Gtk.Button(
            icon_name="edit-undo-symbolic",
            tooltip_text="Undo (Ctrl+Z)",
            sensitive=False,
        )
        self.header_bar.pack_start(self.btn_undo)

        self.btn_redo = Gtk.Button(
            icon_name="edit-redo-symbolic",
            tooltip_text="Redo (Ctrl+Shift+Z / Ctrl+Y)",
            sensitive=False,
        )
        self.header_bar.pack_start(self.btn_redo)

        self.btn_copy = Gtk.Button(
            icon_name="edit-copy-symbolic",
            tooltip_text="Copy to Clipboard (Ctrl+C)",
            sensitive=False,
        )
        self.btn_copy.add_css_class("suggested-action")
        self.header_bar.pack_end(self.btn_copy)

        self.btn_save = Gtk.Button(
            icon_name="document-save-symbolic",
            tooltip_text="Save Image (Ctrl+S)",
            sensitive=False,
        )
        self.header_bar.pack_end(self.btn_save)

    def _build_menu(self) -> None:
        menu = Gio.Menu()
        menu.append("Paste from Clipboard", "app.paste-clipboard")
        menu.append("Keyboard Shortcuts", "app.shortcuts")
        menu.append("About GoBrush", "app.about")

        self.menu_btn = Gtk.MenuButton(
            icon_name="open-menu-symbolic",
            tooltip_text="Main Menu",
            menu_model=menu,
        )
        self.header_bar.pack_end(self.menu_btn)

    def set_has_image(self, has_image: bool) -> None:
        self.btn_copy.set_sensitive(has_image)
        self.btn_save.set_sensitive(has_image)

    def set_undo_sensitive(self, sensitive: bool) -> None:
        self.btn_undo.set_sensitive(sensitive)

    def set_redo_sensitive(self, sensitive: bool) -> None:
        self.btn_redo.set_sensitive(sensitive)

    def show_toast(self, title: str, timeout: int = 2) -> Adw.Toast:
        toast = Adw.Toast.new(title)
        toast.set_timeout(timeout)
        self.toast_overlay.add_toast(toast)
        return toast

    def show_toast_with_action(
        self, title: str, button_label: str, action_name: str, timeout: int = 5
    ) -> Adw.Toast:
        toast = Adw.Toast.new(title)
        toast.set_button_label(button_label)
        toast.set_action_name(action_name)
        toast.set_timeout(timeout)
        self.toast_overlay.add_toast(toast)
        return toast
