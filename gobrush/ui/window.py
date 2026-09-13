from __future__ import annotations
import io
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

        self._action_copy = Gio.SimpleAction.new("copy-clipboard", None)
        self._action_copy.connect("activate", lambda *_: self.copy_to_clipboard())
        self.add_action(self._action_copy)

    def _on_scroll_to_zoom_changed(self, action: Gio.SimpleAction, value: GLib.Variant) -> None:
        action.set_state(value)
        is_active = value.get_boolean()
        self.canvas.scroll_to_zoom = is_active
        if hasattr(self, "switch_scroll_zoom") and self.switch_scroll_zoom.get_active() != is_active:
            self.switch_scroll_zoom.set_active(is_active)

    def _on_switch_scroll_zoom_active(self, switch: Gtk.Switch, _pspec: Any) -> None:
        is_active = switch.get_active()
        self.canvas.scroll_to_zoom = is_active
        if hasattr(self, "_action_scroll_to_zoom"):
            self._action_scroll_to_zoom.set_state(GLib.Variant.new_boolean(is_active))

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
        self.btn_copy.connect("clicked", lambda _: self.copy_to_clipboard())
        self.header_bar.pack_end(self.btn_copy)

    def _build_menu(self) -> None:
        self.menu_popover = Gtk.Popover()
        self.menu_popover.add_css_class("menu-popover")

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        vbox.set_margin_top(10)
        vbox.set_margin_bottom(10)
        vbox.set_margin_start(10)
        vbox.set_margin_end(10)

        lbl_zoom = Gtk.Label(label="Zoom", xalign=0.0)
        lbl_zoom.add_css_class("dim-label")
        vbox.append(lbl_zoom)

        quick_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        quick_box.add_css_class("linked")
        quick_box.set_homogeneous(True)

        self.btn_zoom_out = Gtk.Button(label="−", tooltip_text="Zoom Out (-)")
        self.btn_zoom_out.connect("clicked", lambda _: self.canvas.zoom_out())
        quick_box.append(self.btn_zoom_out)

        self.btn_zoom_fit = Gtk.Button(label="Fit", tooltip_text="Fit to Window (F)")
        self.btn_zoom_fit.connect("clicked", lambda _: (self.canvas.zoom_fit(), self.menu_popover.popdown()))
        quick_box.append(self.btn_zoom_fit)

        self.btn_zoom_100 = Gtk.Button(label="100%", tooltip_text="Actual Size 100% (1)")
        self.btn_zoom_100.connect("clicked", lambda _: (self.canvas.set_zoom_level(1.0), self.menu_popover.popdown()))
        quick_box.append(self.btn_zoom_100)

        self.btn_zoom_in = Gtk.Button(label="+", tooltip_text="Zoom In (+)")
        self.btn_zoom_in.connect("clicked", lambda _: self.canvas.zoom_in())
        quick_box.append(self.btn_zoom_in)

        vbox.append(quick_box)

        presets_grid = Gtk.Grid()
        presets_grid.set_column_spacing(6)
        presets_grid.set_row_spacing(6)
        presets_grid.set_column_homogeneous(True)

        self.preset_buttons: dict[int, Gtk.Button] = {}
        presets = [
            (25, 0.25, 0, 0),
            (50, 0.50, 1, 0),
            (75, 0.75, 2, 0),
            (100, 1.00, 0, 1),
            (150, 1.50, 1, 1),
            (200, 2.00, 2, 1),
        ]
        for pct, val, col, row in presets:
            btn = Gtk.Button(label=f"{pct}%", tooltip_text=f"Zoom to {pct}%")
            btn.add_css_class("flat")
            btn.connect(
                "clicked",
                lambda _, z=val: (self.canvas.set_zoom_level(z), self.menu_popover.popdown()),
            )
            presets_grid.attach(btn, col, row, 1, 1)
            self.preset_buttons[pct] = btn

        vbox.append(presets_grid)
        vbox.append(Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL))

        self.btn_menu_paste = Gtk.Button()
        self.btn_menu_paste.add_css_class("flat")
        paste_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        paste_box.append(Gtk.Image.new_from_icon_name("edit-paste-symbolic"))
        lbl_paste = Gtk.Label(label="Paste from Clipboard", xalign=0.0, hexpand=True)
        paste_box.append(lbl_paste)
        lbl_paste_accel = Gtk.Label(label="Ctrl+V")
        lbl_paste_accel.add_css_class("dim-label")
        paste_box.append(lbl_paste_accel)
        self.btn_menu_paste.set_child(paste_box)
        self.btn_menu_paste.connect(
            "clicked",
            lambda _: (self.paste_from_clipboard(), self.menu_popover.popdown()),
        )
        vbox.append(self.btn_menu_paste)

        scroll_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        lbl_scroll = Gtk.Label(label="Zoom on Scroll", xalign=0.0, hexpand=True)
        scroll_box.append(lbl_scroll)
        self.switch_scroll_zoom = Gtk.Switch()
        self.switch_scroll_zoom.set_valign(Gtk.Align.CENTER)
        self.switch_scroll_zoom.set_active(self.canvas.scroll_to_zoom)
        self.switch_scroll_zoom.connect("notify::active", self._on_switch_scroll_zoom_active)
        scroll_box.append(self.switch_scroll_zoom)
        vbox.append(scroll_box)

        self.menu_popover.set_child(vbox)

        self.menu_btn = Gtk.MenuButton(
            icon_name="open-menu-symbolic",
            tooltip_text="Main Menu",
            popover=self.menu_popover,
        )
        self.header_bar.pack_end(self.menu_btn)

    def set_has_image(self, has_image: bool) -> None:
        self.btn_copy.set_sensitive(has_image)
        self.btn_save.set_sensitive(has_image)
        if hasattr(self, "btn_zoom_fit"):
            self.btn_zoom_fit.set_sensitive(has_image)
            self.btn_zoom_100.set_sensitive(has_image)
            self.btn_zoom_in.set_sensitive(has_image)
            self.btn_zoom_out.set_sensitive(has_image)
            for btn in self.preset_buttons.values():
                btn.set_sensitive(has_image)

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

    @property
    def action_copy(self) -> Gio.SimpleAction:
        return self._action_copy

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

    def copy_to_clipboard(
        self,
        clipboard: Gdk.Clipboard | None = None,
        callback: Callable[[bool], None] | None = None,
    ) -> bool:
        if not self.canvas.has_image:
            self.show_toast("No image to copy")
            if callback:
                callback(False)
            return False

        surface = self.canvas.get_flattened_surface()
        if surface is None:
            self.show_toast("Failed to copy image")
            if callback:
                callback(False)
            return False

        try:
            cb = clipboard if clipboard is not None else self.get_clipboard()
        except Exception:
            cb = None

        if cb is None:
            self.show_toast("No clipboard available")
            if callback:
                callback(False)
            return False

        try:
            png_buf = io.BytesIO()
            surface.write_to_png(png_buf)
            gbytes = GLib.Bytes.new(png_buf.getvalue())

            pixbuf = Gdk.pixbuf_get_from_surface(
                surface, 0, 0, surface.get_width(), surface.get_height()
            )
            texture = Gdk.Texture.new_for_pixbuf(pixbuf)

            cp_bytes = Gdk.ContentProvider.new_for_bytes("image/png", gbytes)
            cp_pixbuf = Gdk.ContentProvider.new_for_value(pixbuf)
            cp_tex = Gdk.ContentProvider.new_for_value(texture)
            content_provider = Gdk.ContentProvider.new_union([cp_bytes, cp_pixbuf, cp_tex])

            self._clipboard_content_provider = content_provider

            if hasattr(cb, "set_content"):
                cb.set_content(content_provider)
            else:
                cb.set(texture)

            self.show_toast("Copied to clipboard")
            if callback:
                callback(True)
            return True
        except Exception as e:
            self.show_toast(f"Error copying image: {e}")
            if callback:
                callback(False)
            return False

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

        if is_ctrl and keyval in (Gdk.KEY_c, Gdk.KEY_C):
            self.copy_to_clipboard()
            return True

        if not self.is_empty():
            return self.canvas.handle_key_pressed(keyval, state)
        return False

    def _on_key_released(
        self, controller: Gtk.EventControllerKey, keyval: int, keycode: int, state: Gdk.ModifierType
    ) -> None:
        if not self.is_empty():
            self.canvas.handle_key_released(keyval, state)
