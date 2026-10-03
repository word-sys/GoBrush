from __future__ import annotations
from typing import TYPE_CHECKING, Any, Callable
import cairo
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gtk, Gdk

from gobrush.tools.base import BaseTool
from gobrush.items.text import TextItem
from gobrush.core.history import AddAnnotationCommand, ResizeCommand

if TYPE_CHECKING:
    from gobrush.ui.canvas import Canvas


class TextTool(BaseTool):
    tool_id: str = "text"
    name: str = "Text"
    shortcut: str = "T"
    icon_name: str = "insert-text-symbolic"
    cursor_name: str | None = "text"

    def __init__(self, canvas: Canvas | None = None) -> None:
        super().__init__(canvas)
        self._is_editing: bool = False
        self._edit_pos: tuple[float, float] = (0.0, 0.0)
        self._screen_pos: tuple[float, float] = (0.0, 0.0)
        self._current_text: str = ""
        self._editing_item: TextItem | None = None

        self._font_size: float = 20.0
        self._font_family: str = "Sans"
        self._font_weight: str = "bold"
        self._color: tuple[float, float, float, float] = (0.88, 0.11, 0.14, 1.0)
        self._fill_color: tuple[float, float, float, float] | None = None
        self._background_style: str = "pill"
        self._shadow: bool = True
        self._padding_x: float = 12.0
        self._padding_y: float = 6.0

        self._popover: Gtk.Popover | None = None
        self._entry: Gtk.Entry | None = None
        self._popover_closed_id: int | None = None
        self._is_committing: bool = False

        self._mgr_color_cb: Callable[..., None] | None = None
        self._mgr_style_cb: Callable[..., None] | None = None

    @property
    def is_editing(self) -> bool:
        return self._is_editing

    @property
    def edit_pos(self) -> tuple[float, float]:
        return self._edit_pos

    @property
    def current_text(self) -> str:
        return self._current_text

    @current_text.setter
    def current_text(self, text: str) -> None:
        self.set_text(text)

    def set_text(self, text: str) -> None:
        self._current_text = str(text)
        if self._entry is not None and self._entry.get_text() != self._current_text:
            self._entry.set_text(self._current_text)
        if self.canvas is not None:
            self.canvas.queue_draw()

    @property
    def font_size(self) -> float:
        return self._font_size

    @font_size.setter
    def font_size(self, size: float) -> None:
        self._font_size = max(8.0, float(size))

    @property
    def font_family(self) -> str:
        return self._font_family

    @font_family.setter
    def font_family(self, family: str) -> None:
        self._font_family = str(family)

    @property
    def font_weight(self) -> str:
        return self._font_weight

    @font_weight.setter
    def font_weight(self, weight: str) -> None:
        self._font_weight = str(weight)

    @property
    def color(self) -> tuple[float, float, float, float]:
        return self._color

    @color.setter
    def color(self, c: tuple[float, float, float, float]) -> None:
        self._color = c

    @property
    def fill_color(self) -> tuple[float, float, float, float] | None:
        return self._fill_color

    @fill_color.setter
    def fill_color(self, c: tuple[float, float, float, float] | None) -> None:
        self._fill_color = c

    @property
    def background_style(self) -> str:
        return self._background_style

    @background_style.setter
    def background_style(self, style: str) -> None:
        if style in ("pill", "none", "box"):
            self._background_style = style

    @property
    def shadow(self) -> bool:
        return self._shadow

    @shadow.setter
    def shadow(self, enabled: bool) -> None:
        self._shadow = bool(enabled)

    def activate(self) -> None:
        super().activate()
        self._sync_properties_from_manager()
        if self.canvas and self.canvas.tool_manager:
            mgr = self.canvas.tool_manager
            self._mgr_color_cb = self._on_manager_color_changed
            mgr.add_color_changed_callback(self._mgr_color_cb)
            self._mgr_style_cb = self._on_manager_style_changed
            mgr.add_style_changed_callback(self._mgr_style_cb)
        if self.canvas is not None:
            self._canvas_view_cb = self._on_canvas_view_changed
            self.canvas.add_view_changed_callback(self._canvas_view_cb)

    def deactivate(self) -> None:
        super().deactivate()
        if self._is_editing:
            self.commit_editing()
        self._teardown_popover()
        if self.canvas is not None and getattr(self, "_canvas_view_cb", None) is not None:
            self.canvas.remove_view_changed_callback(self._canvas_view_cb)
            self._canvas_view_cb = None
        if self.canvas and self.canvas.tool_manager:
            mgr = self.canvas.tool_manager
            if self._mgr_color_cb:
                mgr.remove_color_changed_callback(self._mgr_color_cb)
                self._mgr_color_cb = None
            if self._mgr_style_cb:
                mgr.remove_style_changed_callback(self._mgr_style_cb)
                self._mgr_style_cb = None

    def _on_canvas_view_changed(self) -> None:
        if self._is_editing and self._popover is not None and self.canvas is not None:
            sx, sy = self.canvas.image_to_screen(self._edit_pos[0], self._edit_pos[1])
            rect = Gdk.Rectangle()
            rect.x = max(0, int(round(sx)))
            rect.y = max(0, int(round(sy)))
            rect.width = 1
            rect.height = 1
            self._popover.set_pointing_to(rect)

    def _sync_properties_from_manager(self) -> None:
        if not self.canvas or not self.canvas.tool_manager:
            return
        mgr = self.canvas.tool_manager
        self._color = mgr.current_color
        if mgr.stroke_width < 12.0:
            mgr.set_stroke_width(20.0)
            self._font_size = 20.0
        else:
            self._font_size = float(mgr.stroke_width)
        self._fill_color = mgr.get_effective_fill_color()
        if mgr.fill_mode == "outline":
            self._background_style = "none"
        else:
            self._background_style = "pill"

    def _on_manager_color_changed(self, color: tuple[float, float, float, float]) -> None:
        self._color = color
        if self.canvas:
            self.canvas.queue_draw()

    def _on_manager_style_changed(
        self, width: float, fill_mode: str, opacity: float = 0.25, *args: Any
    ) -> None:
        if width >= 8.0:
            self._font_size = float(width)
        if fill_mode == "outline":
            self._background_style = "none"
            self._fill_color = None
        else:
            self._background_style = "pill"
            if self.canvas and self.canvas.tool_manager:
                self._fill_color = self.canvas.tool_manager.get_effective_fill_color()
        if self.canvas:
            self.canvas.queue_draw()

    def _get_default_edit_pos(self) -> tuple[float, float]:
        if self.canvas is not None:
            if self.canvas.cursor_pos is not None:
                return self.canvas.screen_to_image(*self.canvas.cursor_pos)
            vw = self.canvas.viewport_width / 2.0 if self.canvas.viewport_width > 0 else 200.0
            vh = self.canvas.viewport_height / 2.0 if self.canvas.viewport_height > 0 else 150.0
            return self.canvas.screen_to_image(vw, vh)
        return (100.0, 100.0)

    def on_press(
        self, ix: float, iy: float, sx: float, sy: float, state: Gdk.ModifierType
    ) -> bool:
        if not self.canvas or not self.canvas.has_image:
            return False

        if self._is_editing:
            self.commit_editing()

        self._sync_properties_from_manager()

        hit_item = None
        if self.canvas.document:
            hit_item = self.canvas.document.hit_test(ix, iy)

        if isinstance(hit_item, TextItem):
            self._editing_item = hit_item
            self.start_editing(
                hit_item.x,
                hit_item.y,
                sx=sx,
                sy=sy,
                initial_text=hit_item.text,
            )
            self._font_size = hit_item.font_size
            self._font_family = hit_item.font_family
            self._font_weight = hit_item.font_weight
            self._color = hit_item.color
            self._fill_color = hit_item.fill_color
            self._background_style = hit_item.background_style
            self._shadow = hit_item.shadow
        else:
            self._editing_item = None
            self.start_editing(ix, iy, sx=sx, sy=sy, initial_text="")

        return True

    def on_drag(
        self, ix: float, iy: float, dx: float, dy: float, sx: float, sy: float, state: Gdk.ModifierType
    ) -> bool:
        return self._is_editing

    def on_release(
        self, ix: float, iy: float, sx: float, sy: float, state: Gdk.ModifierType
    ) -> bool:
        return self._is_editing

    def on_cancel(self) -> None:
        if self._popover is not None or self._is_editing:
            return
        self.cancel_editing()

    def on_key_pressed(self, keyval: int, state: Gdk.ModifierType) -> bool:
        if not self._is_editing:
            return False

        is_ctrl = bool(state & Gdk.ModifierType.CONTROL_MASK)
        is_alt = bool(state & Gdk.ModifierType.ALT_MASK)

        if keyval == Gdk.KEY_Escape:
            self.cancel_editing()
            return True

        if keyval in (Gdk.KEY_Return, Gdk.KEY_KP_Enter):
            self.commit_editing()
            return True

        if not is_ctrl and not is_alt:
            if keyval in (Gdk.KEY_BackSpace, Gdk.KEY_Delete):
                if self._current_text:
                    self.set_text(self._current_text[:-1])
                return True

            ch = Gdk.keyval_to_unicode(keyval)
            if ch > 0 and chr(ch).isprintable():
                self.set_text(self._current_text + chr(ch))
                return True

        return False

    def start_editing(
        self,
        ix: float,
        iy: float,
        sx: float | None = None,
        sy: float | None = None,
        initial_text: str = "",
    ) -> None:
        self._is_editing = True
        self._edit_pos = (float(ix), float(iy))
        if sx is None or sy is None:
            if self.canvas is not None:
                try:
                    calc_sx, calc_sy = self.canvas.image_to_screen(ix, iy)
                    sx = calc_sx if sx is None else sx
                    sy = calc_sy if sy is None else sy
                except Exception:
                    sx = sx or ix
                    sy = sy or iy
            else:
                sx = sx or ix
                sy = sy or iy
        self._screen_pos = (float(sx), float(sy))
        self._current_text = str(initial_text)

        self._setup_popover(float(sx), float(sy), initial_text)

        if self.canvas:
            self.canvas.queue_draw()

    def _setup_popover(self, sx: float, sy: float, initial_text: str) -> None:
        self._teardown_popover()

        if self.canvas is None:
            return

        # Popovers in GTK4 require parent widget to be inside a toplevel/native container
        if not self.canvas.get_root() and not self.canvas.get_native():
            return

        try:
            popover = Gtk.Popover()
            popover.set_parent(self.canvas)
            popover.set_has_arrow(True)
            popover.set_position(Gtk.PositionType.BOTTOM)
            popover.add_css_class("text-editor-popover")

            rect = Gdk.Rectangle()
            rect.x = max(0, int(round(sx)))
            rect.y = max(0, int(round(sy)))
            rect.width = 1
            rect.height = 1
            popover.set_pointing_to(rect)

            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            box.set_margin_top(4)
            box.set_margin_bottom(4)
            box.set_margin_start(4)
            box.set_margin_end(4)

            entry = Gtk.Entry()
            entry.set_placeholder_text("Type text callout...")
            entry.set_text(initial_text)
            entry.set_width_chars(24)
            entry.connect("changed", self._on_entry_changed)
            entry.connect("activate", self._on_entry_activate)
            box.append(entry)

            btn_ok = Gtk.Button.new_from_icon_name("emblem-ok-symbolic")
            btn_ok.set_tooltip_text("Commit text (Enter)")
            btn_ok.add_css_class("suggested-action")
            btn_ok.connect("clicked", lambda _: self.commit_editing())
            box.append(btn_ok)

            btn_cancel = Gtk.Button.new_from_icon_name("window-close-symbolic")
            btn_cancel.set_tooltip_text("Cancel (Esc)")
            btn_cancel.add_css_class("flat")
            btn_cancel.connect("clicked", lambda _: self.cancel_editing())
            box.append(btn_cancel)

            popover.set_child(box)
            self._popover_closed_id = popover.connect("closed", self._on_popover_closed)

            self._popover = popover
            self._entry = entry

            popover.popup()
            entry.grab_focus()
        except Exception:
            self._popover = None
            self._entry = None

    def _on_entry_changed(self, entry: Gtk.Entry) -> None:
        self._current_text = entry.get_text()
        if self.canvas:
            self.canvas.queue_draw()

    def _on_entry_activate(self, entry: Gtk.Entry) -> None:
        self.commit_editing()

    def _on_popover_closed(self, popover: Gtk.Popover) -> None:
        if self._is_editing and not self._is_committing:
            self.commit_editing()
        self._teardown_popover()

    def _teardown_popover(self) -> None:
        if self._popover is not None:
            p = self._popover
            self._popover = None
            self._entry = None
            try:
                if self._popover_closed_id is not None:
                    p.disconnect(self._popover_closed_id)
                    self._popover_closed_id = None
            except Exception:
                pass
            try:
                p.popdown()
                p.unparent()
            except Exception:
                pass

    def commit_editing(self) -> TextItem | None:
        if not self._is_editing:
            return None

        self._is_committing = True
        try:
            text = (
                self._entry.get_text()
                if self._entry is not None
                else self._current_text
            )
            text = text.strip()

            created_or_updated: TextItem | None = None

            if not text:
                self.cancel_editing()
                return None

            if self.canvas and self.canvas.document:
                doc = self.canvas.document
                if self._editing_item is not None and self._editing_item in doc.items:
                    old_geom = {"text": self._editing_item.text}
                    new_geom = {"text": text}
                    cmd = ResizeCommand(
                        self._editing_item,
                        old_geom,
                        new_geom,
                        document=doc,
                        name="Edit Text",
                    )
                    self.canvas.execute_command(cmd)
                    created_or_updated = self._editing_item
                else:
                    item = TextItem(
                        x=self._edit_pos[0],
                        y=self._edit_pos[1],
                        text=text,
                        font_size=self._font_size,
                        font_family=self._font_family,
                        font_weight=self._font_weight,
                        color=self._color,
                        fill_color=self._fill_color,
                        background_style=self._background_style,
                        shadow=self._shadow,
                        padding_x=self._padding_x,
                        padding_y=self._padding_y,
                    )
                    cmd = AddAnnotationCommand(
                        doc,
                        item,
                        select=True,
                        name="Add Text Callout",
                    )
                    self.canvas.execute_command(cmd)
                    created_or_updated = item

            self._reset_editing_state()
            self._teardown_popover()

            if self.canvas:
                self.canvas.queue_draw()

            return created_or_updated
        finally:
            self._is_committing = False

    def commit_text(
        self,
        text: str,
        x: float | None = None,
        y: float | None = None,
        font_size: float | None = None,
        font_family: str | None = None,
        font_weight: str | None = None,
        color: tuple[float, float, float, float] | None = None,
        fill_color: tuple[float, float, float, float] | None = None,
        background_style: str | None = None,
    ) -> TextItem | None:
        px = self._edit_pos[0] if x is None else float(x)
        py = self._edit_pos[1] if y is None else float(y)
        fs = self._font_size if font_size is None else float(font_size)
        ff = self._font_family if font_family is None else str(font_family)
        fw = self._font_weight if font_weight is None else str(font_weight)
        col = self._color if color is None else color
        fc = self._fill_color if fill_color is None else fill_color
        bg = self._background_style if background_style is None else str(background_style)

        clean_text = str(text).strip()
        if not clean_text:
            return None

        item = TextItem(
            x=px,
            y=py,
            text=clean_text,
            font_size=fs,
            font_family=ff,
            font_weight=fw,
            color=col,
            fill_color=fc,
            background_style=bg,
            shadow=self._shadow,
            padding_x=self._padding_x,
            padding_y=self._padding_y,
        )

        if self.canvas and self.canvas.document:
            cmd = AddAnnotationCommand(
                self.canvas.document,
                item,
                select=True,
                name="Add Text Callout",
            )
            self.canvas.execute_command(cmd)

        self._reset_editing_state()
        self._teardown_popover()

        if self.canvas:
            self.canvas.queue_draw()

        return item

    def cancel_editing(self) -> None:
        self._reset_editing_state()
        self._teardown_popover()
        if self.canvas:
            self.canvas.queue_draw()

    def _reset_editing_state(self) -> None:
        self._is_editing = False
        self._current_text = ""
        self._editing_item = None

    def draw_overlay(self, cr: cairo.Context) -> None:
        if not self._is_editing:
            return

        x, y = self._edit_pos
        text = self._current_text

        if text.strip():
            preview_item = TextItem(
                x=x,
                y=y,
                text=text,
                font_size=self._font_size,
                font_family=self._font_family,
                font_weight=self._font_weight,
                color=self._color,
                fill_color=self._fill_color,
                background_style=self._background_style,
                shadow=self._shadow,
                padding_x=self._padding_x,
                padding_y=self._padding_y,
            )
            cr.save()
            preview_item.draw(cr)

            bx, by, bw, bh = preview_item.get_bounds()
            cr.set_source_rgba(0.21, 0.52, 0.89, 0.9)
            cr.set_line_width(1.5)
            cr.set_dash([4.0, 3.0])
            cr.rectangle(bx - 2.0, by - 2.0, bw + 4.0, bh + 4.0)
            cr.stroke()

            tw, th = preview_item.get_text_size()
            cur_x = (x + self._padding_x + tw) if self._background_style in ("pill", "box") else (x + tw)
            cur_y = (y + self._padding_y) if self._background_style in ("pill", "box") else y
            cr.set_source_rgba(0.21, 0.52, 0.89, 1.0)
            cr.set_line_width(2.0)
            cr.set_dash([])
            cr.move_to(cur_x + 2.0, cur_y)
            cr.line_to(cur_x + 2.0, cur_y + max(14.0, self._font_size))
            cr.stroke()
            cr.restore()
        else:
            cr.save()
            ph_h = max(24.0, self._font_size + 10.0)
            ph_w = max(180.0, self._font_size * 7.0)

            # Soft background
            cr.set_source_rgba(1.0, 1.0, 1.0, 0.92)
            cr.rectangle(x, y, ph_w, ph_h)
            cr.fill_preserve()

            # Accent dashed border
            cr.set_source_rgba(0.21, 0.52, 0.89, 0.85)
            cr.set_line_width(1.5)
            cr.set_dash([4.0, 3.0])
            cr.stroke()

            # Cursor
            cr.set_source_rgba(0.21, 0.52, 0.89, 1.0)
            cr.set_line_width(2.0)
            cr.set_dash([])
            cr.move_to(x + 10.0, y + 4.0)
            cr.line_to(x + 10.0, y + ph_h - 4.0)
            cr.stroke()

            # Placeholder prompt text
            cr.set_source_rgba(0.4, 0.45, 0.55, 0.65)
            cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
            cr.set_font_size(max(12.0, self._font_size * 0.75))
            cr.move_to(x + 18.0, y + ph_h * 0.68)
            cr.show_text("Type text here...")
            cr.restore()
