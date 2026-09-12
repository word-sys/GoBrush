from __future__ import annotations
import os
import urllib.parse
from pathlib import Path
from typing import Any, Callable
import cairo
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Gdk, Adw, Gio, GLib, GObject

from gobrush import __version__
from gobrush.compat.dialogs import open_file_dialog
from gobrush.core.loader import load_image_with_info, is_supported_image, ImageLoadError
from gobrush.ui.empty_state import EmptyStateView
from gobrush.ui.canvas import Canvas
from gobrush.ui.canvas_view import CanvasView


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
        self._current_file_path: str | None = None
        self.canvas_view = CanvasView()
        self.canvas = self.canvas_view.canvas
        self.status_bar = self.canvas_view.status_bar

        self._build_actions()
        self._build_menu()
        self._build_header_actions()

        self.empty_state = EmptyStateView(
            on_open=self._on_open_action,
            on_paste=self._on_paste_action,
        )
        self.show_empty_state()

        self._key_controller = Gtk.EventControllerKey()
        self._key_controller.set_propagation_phase(Gtk.PropagationPhase.BUBBLE)
        self._key_controller.connect("key-pressed", self._on_key_pressed)
        self._key_controller.connect("key-released", self._on_key_released)
        self.add_controller(self._key_controller)

        # Drag-and-drop target accepting file drops across window
        self._drop_target = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        self._drop_target.set_gtypes([Gdk.FileList, Gio.File, GObject.TYPE_STRING])
        self._drop_target.connect("drop", self._on_drop)
        self.add_controller(self._drop_target)

    def _build_actions(self) -> None:
        self._action_scroll_to_zoom = Gio.SimpleAction.new_stateful(
            "scroll-to-zoom",
            None,
            GLib.Variant.new_boolean(self.canvas.scroll_to_zoom),
        )
        self._action_scroll_to_zoom.connect("change-state", self._on_scroll_to_zoom_changed)
        self.add_action(self._action_scroll_to_zoom)

        self._action_paste = Gio.SimpleAction.new("paste-clipboard", None)
        self._action_paste.connect("activate", lambda *_: self.paste_from_clipboard())
        self.add_action(self._action_paste)

    def _on_scroll_to_zoom_changed(self, action: Gio.SimpleAction, value: GLib.Variant) -> None:
        action.set_state(value)
        self.canvas.scroll_to_zoom = value.get_boolean()

    def _build_header_actions(self) -> None:
        self.btn_open = Gtk.Button(
            label="Open",
            tooltip_text="Open Image (Ctrl+O)",
        )
        self.btn_open.connect("clicked", lambda _: self._on_open_action())
        self.header_bar.pack_start(self.btn_open)

        self.btn_save = Gtk.Button(
            label="Save",
            tooltip_text="Save Image (Ctrl+S)",
            sensitive=False,
        )
        self.btn_save.add_css_class("suggested-action")
        self.header_bar.pack_start(self.btn_save)

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
        self.header_bar.pack_end(self.btn_copy)

    def _build_menu(self) -> None:
        menu = Gio.Menu()
        menu.append("Paste from Clipboard", "win.paste-clipboard")
        menu.append("Zoom on Scroll", "win.scroll-to-zoom")
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
        escaped_title = GLib.markup_escape_text(str(title))
        toast = Adw.Toast.new(escaped_title)
        toast.set_timeout(timeout)
        self.toast_overlay.add_toast(toast)
        return toast

    def show_toast_with_action(
        self, title: str, button_label: str, action_name: str, timeout: int = 5
    ) -> Adw.Toast:
        escaped_title = GLib.markup_escape_text(str(title))
        toast = Adw.Toast.new(escaped_title)
        toast.set_button_label(button_label)
        toast.set_action_name(action_name)
        toast.set_timeout(timeout)
        self.toast_overlay.add_toast(toast)
        return toast

    def show_empty_state(self) -> None:
        self.content_bin.set_child(self.empty_state)
        self.set_has_image(False)

    def show_canvas(self) -> None:
        self.show_content(self.canvas_view)

    def show_content(self, widget: Gtk.Widget) -> None:
        self.content_bin.set_child(widget)
        self.set_has_image(True)

    def is_empty(self) -> bool:
        return self.content_bin.get_child() == self.empty_state

    def _on_open_action(self) -> None:
        open_file_dialog(self, self._on_file_selected)

    @property
    def current_file_path(self) -> str | None:
        return self._current_file_path

    @property
    def drop_target(self) -> Gtk.DropTarget:
        return self._drop_target

    @property
    def action_scroll_to_zoom(self) -> Gio.SimpleAction:
        return self._action_scroll_to_zoom

    @property
    def action_paste(self) -> Gio.SimpleAction:
        return self._action_paste

    def load_surface(
        self,
        surface: cairo.ImageSurface,
        has_alpha: bool = True,
        title: str = "Pasted Image - GoBrush",
        file_path: str | None = None,
    ) -> None:
        self.canvas.set_image_surface(
            surface,
            surface.get_width(),
            surface.get_height(),
            has_alpha=has_alpha,
        )
        self.show_canvas()
        self.canvas.zoom_fit()
        self._current_file_path = file_path
        self.set_title(title)

    def load_pasted_image(self, source: Any) -> bool:
        try:
            surface, has_alpha = load_image_with_info(source)
        except ImageLoadError as e:
            self.show_toast(f"Failed to paste image: {e}")
            return False
        except Exception as e:
            self.show_toast(f"Error pasting image: {e}")
            return False

        self.load_surface(surface, has_alpha=has_alpha, title="Pasted Image - GoBrush", file_path=None)
        self.show_toast("Image pasted from clipboard")
        return True

    def paste_from_clipboard(
        self,
        clipboard: Gdk.Clipboard | None = None,
        callback: Callable[[bool], None] | None = None,
    ) -> None:
        try:
            cb = clipboard if clipboard is not None else self.get_clipboard()
        except Exception:
            cb = None

        if cb is None:
            self.show_toast("No clipboard available")
            if callback:
                callback(False)
            return

        def _on_texture_read(source: Gdk.Clipboard, result: Gio.AsyncResult) -> None:
            texture = None
            try:
                texture = source.read_texture_finish(result)
            except Exception:
                pass

            if texture is not None:
                ok = self.load_pasted_image(texture)
                if callback:
                    callback(ok)
                return

            def _on_text_read(text_source: Gdk.Clipboard, text_result: Gio.AsyncResult) -> None:
                text = None
                try:
                    text = text_source.read_text_finish(text_result)
                except Exception:
                    pass

                if text:
                    paths = self._extract_paths_from_drop_value(text)
                    for p in paths:
                        if is_supported_image(p):
                            if self.open_file(p):
                                self.show_toast("Image pasted from clipboard")
                                if callback:
                                    callback(True)
                                return

                self.show_toast("No image found in clipboard")
                if callback:
                    callback(False)

            try:
                source.read_text_async(None, _on_text_read)
            except Exception:
                self.show_toast("No image found in clipboard")
                if callback:
                    callback(False)

        try:
            cb.read_texture_async(None, _on_texture_read)
        except Exception:
            self.show_toast("No image found in clipboard")
            if callback:
                callback(False)

    def open_file(self, path: str | Path) -> bool:
        p = Path(path).expanduser().resolve()
        if not p.is_file():
            self.show_toast(f"File not found: {p.name}")
            return False

        if not is_supported_image(p):
            self.show_toast(f"Unsupported image format: {p.suffix or p.name}")
            return False

        try:
            surface, has_alpha = load_image_with_info(p)
        except ImageLoadError as e:
            self.show_toast(f"Failed to open image: {e}")
            return False
        except Exception as e:
            self.show_toast(f"Error opening image: {e}")
            return False

        self.load_surface(surface, has_alpha=has_alpha, title=f"{p.name} - GoBrush", file_path=str(p))
        return True

    def close_file(self) -> None:
        self.canvas.clear()
        self._current_file_path = None
        self.set_title("GoBrush")
        self.show_empty_state()

    @staticmethod
    def _extract_paths_from_drop_value(value: Any) -> list[str]:
        paths: list[str] = []
        if value is None:
            return paths

        if hasattr(value, "get_files"):
            try:
                for gfile in value.get_files():
                    p = gfile.get_path()
                    if p:
                        paths.append(p)
                    else:
                        uri = gfile.get_uri()
                        if uri and uri.startswith("file://"):
                            parsed = urllib.parse.urlparse(uri)
                            paths.append(urllib.parse.unquote(parsed.path))
            except Exception:
                pass
        elif isinstance(value, (list, tuple)):
            for item in value:
                if hasattr(item, "get_path"):
                    p = item.get_path()
                    if p:
                        paths.append(p)
                elif isinstance(item, str):
                    paths.extend(MainWindow._extract_paths_from_drop_value(item))
        elif hasattr(value, "get_path"):
            p = value.get_path()
            if p:
                paths.append(p)
            elif hasattr(value, "get_uri"):
                uri = value.get_uri()
                if uri and uri.startswith("file://"):
                    parsed = urllib.parse.urlparse(uri)
                    paths.append(urllib.parse.unquote(parsed.path))
        elif isinstance(value, str):
            for line in value.strip().splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("file://"):
                    parsed = urllib.parse.urlparse(line)
                    paths.append(urllib.parse.unquote(parsed.path))
                elif os.path.isabs(line):
                    paths.append(line)
        return paths

    def _on_drop(self, target: Gtk.DropTarget, value: Any, x: float, y: float) -> bool:
        paths = self._extract_paths_from_drop_value(value)
        if not paths:
            self.show_toast("No dropped files detected")
            return False

        first_image_path: str | None = None
        for p in paths:
            if is_supported_image(p):
                first_image_path = p
                break

        if not first_image_path:
            ext = os.path.splitext(paths[0])[1] or Path(paths[0]).name
            self.show_toast(f"Unsupported file format: {ext}")
            return False

        return self.open_file(first_image_path)

    def _on_file_selected(self, path: str | None) -> None:
        if path:
            self.open_file(path)

    def _on_paste_action(self) -> None:
        self.paste_from_clipboard()

    def _on_key_pressed(
        self, controller: Gtk.EventControllerKey, keyval: int, keycode: int, state: Gdk.ModifierType
    ) -> bool:
        is_ctrl = bool(state & Gdk.ModifierType.CONTROL_MASK) and not bool(state & Gdk.ModifierType.ALT_MASK)
        if is_ctrl and keyval in (Gdk.KEY_o, Gdk.KEY_O):
            self._on_open_action()
            return True

        if is_ctrl and keyval in (Gdk.KEY_v, Gdk.KEY_V):
            self.paste_from_clipboard()
            return True

        if not self.is_empty():
            return self.canvas.handle_key_pressed(keyval, state)
        return False

    def _on_key_released(
        self, controller: Gtk.EventControllerKey, keyval: int, keycode: int, state: Gdk.ModifierType
    ) -> None:
        if not self.is_empty():
            self.canvas.handle_key_released(keyval, state)
