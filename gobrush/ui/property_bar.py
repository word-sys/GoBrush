from __future__ import annotations
from typing import TYPE_CHECKING, Callable
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gtk, Gdk

from gobrush.tools.base import (
    DEFAULT_STROKE_WIDTH,
    DEFAULT_FILL_MODE,
    SUPPORTED_STROKE_WIDTHS,
    SUPPORTED_FILL_MODES,
)

if TYPE_CHECKING:
    from gobrush.tools.base import BaseTool, ToolManager

SIZE_OPTIONS = [
    {"label": "2px", "value": 2.0},
    {"label": "4px", "value": 4.0},
    {"label": "8px", "value": 8.0},
    {"label": "16px", "value": 16.0},
]

FILL_OPTIONS = [
    {"label": "Outline", "value": "outline"},
    {"label": "Semi-Fill", "value": "semi"},
    {"label": "Solid", "value": "solid"},
]

_CSS_INITIALIZED = False


def ensure_property_bar_css() -> None:
    global _CSS_INITIALIZED
    if _CSS_INITIALIZED:
        return
    display = Gdk.Display.get_default()
    if display is None:
        return

    css_provider = Gtk.CssProvider()
    css_provider.load_from_data(b"""
        .context-property-bar {
            padding: 0;
        }
        .size-button, .fill-button {
            padding: 4px 6px;
            border-radius: 6px;
            min-height: 30px;
            font-size: 12px;
            font-weight: 600;
            transition: all 120ms ease;
        }
        .size-button:checked, .size-button.is-active-size {
            background-color: @theme_selected_bg_color;
            color: @theme_selected_fg_color;
        }
        .fill-button:checked, .fill-button.is-active-fill {
            background-color: @theme_selected_bg_color;
            color: @theme_selected_fg_color;
        }
    """)
    Gtk.StyleContext.add_provider_for_display(
        display, css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )
    _CSS_INITIALIZED = True


class ContextPropertyBar(Gtk.Box):
    def __init__(self, tool_manager: ToolManager | None = None) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        ensure_property_bar_css()
        self.add_css_class("context-property-bar")

        self._tool_manager: ToolManager | None = None
        self._updating_ui: bool = False
        self._style_changed_callbacks: list[Callable[[float, str], None]] = []

        self._local_stroke_width: float = DEFAULT_STROKE_WIDTH
        self._local_fill_mode: str = DEFAULT_FILL_MODE

        self._tool_changed_handler: Callable[[BaseTool | None], None] | None = None
        self._style_changed_handler: Callable[[float, str], None] | None = None

        self._size_buttons: dict[str, Gtk.ToggleButton] = {}
        self._fill_buttons: dict[str, Gtk.ToggleButton] = {}
        self._first_size_btn: Gtk.ToggleButton | None = None
        self._first_fill_btn: Gtk.ToggleButton | None = None

        self._build_ui()

        if tool_manager is not None:
            self.set_tool_manager(tool_manager)
        else:
            self._sync_size_buttons(self._local_stroke_width)
            self._sync_fill_buttons(self._local_fill_mode)

    @property
    def tool_manager(self) -> ToolManager | None:
        return self._tool_manager

    @property
    def stroke_width(self) -> float:
        if self._tool_manager is not None:
            return self._tool_manager.stroke_width
        return self._local_stroke_width

    def set_stroke_width(self, width: float) -> None:
        if self._tool_manager is not None:
            self._tool_manager.set_stroke_width(width)
        else:
            clamped = max(0.5, float(width))
            if self._local_stroke_width == clamped:
                return
            self._local_stroke_width = clamped
            self._sync_size_buttons(clamped)
            self._notify_style_changed()

    @property
    def fill_mode(self) -> str:
        if self._tool_manager is not None:
            return self._tool_manager.fill_mode
        return self._local_fill_mode

    def set_fill_mode(self, mode: str) -> None:
        if mode not in SUPPORTED_FILL_MODES:
            return
        if self._tool_manager is not None:
            self._tool_manager.set_fill_mode(mode)
        else:
            if self._local_fill_mode == mode:
                return
            self._local_fill_mode = mode
            self._sync_fill_buttons(mode)
            self._notify_style_changed()

    def get_size_button(self, key: str | float) -> Gtk.ToggleButton | None:
        if isinstance(key, (int, float)):
            key = f"{int(key)}px"
        return self._size_buttons.get(str(key).lower())

    def get_fill_button(self, key: str) -> Gtk.ToggleButton | None:
        return self._fill_buttons.get(str(key).lower())

    def add_style_changed_callback(
        self, cb: Callable[[float, str], None]
    ) -> None:
        if cb not in self._style_changed_callbacks:
            self._style_changed_callbacks.append(cb)

    def remove_style_changed_callback(
        self, cb: Callable[[float, str], None]
    ) -> None:
        if cb in self._style_changed_callbacks:
            self._style_changed_callbacks.remove(cb)

    def _notify_style_changed(self) -> None:
        for cb in list(self._style_changed_callbacks):
            cb(self.stroke_width, self.fill_mode)

    def set_tool_manager(self, tool_manager: ToolManager | None) -> None:
        if self._tool_manager is not None:
            if self._style_changed_handler is not None:
                self._tool_manager.remove_style_changed_callback(self._style_changed_handler)
                self._style_changed_handler = None
            if self._tool_changed_handler is not None:
                self._tool_manager.remove_tool_changed_callback(self._tool_changed_handler)
                self._tool_changed_handler = None

        self._tool_manager = tool_manager

        if self._tool_manager is not None:
            self._style_changed_handler = self._on_tool_manager_style_changed
            self._tool_manager.add_style_changed_callback(self._style_changed_handler)

            self._tool_changed_handler = self._on_tool_manager_tool_changed
            self._tool_manager.add_tool_changed_callback(self._tool_changed_handler)

            self._sync_size_buttons(self._tool_manager.stroke_width)
            self._sync_fill_buttons(self._tool_manager.fill_mode)
            self.update_for_tool(self._tool_manager.active_tool_id)

    def update_for_tool(self, tool_id: str | None) -> None:
        if tool_id in ("crop", "blur"):
            self.box_size.set_sensitive(False)
            self.box_fill.set_sensitive(False)
        elif tool_id in ("pen", "highlighter", "line", "arrow"):
            self.box_size.set_sensitive(True)
            self.box_fill.set_sensitive(False)
        else:
            self.box_size.set_sensitive(True)
            self.box_fill.set_sensitive(True)

    def _build_ui(self) -> None:
        # Size Section
        self.box_size = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.label_size = Gtk.Label(label="Size", xalign=0.0)
        self.label_size.add_css_class("title-4")
        self.label_size.add_css_class("tool-palette-header")
        self.box_size.append(self.label_size)

        self.size_btn_row = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL, spacing=4, homogeneous=True
        )
        for opt in SIZE_OPTIONS:
            lbl = opt["label"]
            val = opt["value"]
            btn = Gtk.ToggleButton(label=lbl)
            btn.add_css_class("size-button")
            btn.set_tooltip_text(f"Stroke Width: {lbl}")
            if self._first_size_btn is None:
                self._first_size_btn = btn
            else:
                btn.set_group(self._first_size_btn)

            btn.connect("clicked", self._on_size_button_clicked, val, lbl.lower())
            self._size_buttons[lbl.lower()] = btn
            self.size_btn_row.append(btn)
        self.box_size.append(self.size_btn_row)
        self.append(self.box_size)

        # Fill Section
        self.box_fill = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.label_fill = Gtk.Label(label="Fill", xalign=0.0)
        self.label_fill.add_css_class("title-4")
        self.label_fill.add_css_class("tool-palette-header")
        self.box_fill.append(self.label_fill)

        self.fill_btn_row = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL, spacing=4, homogeneous=True
        )
        for opt in FILL_OPTIONS:
            lbl = opt["label"]
            val = opt["value"]
            btn = Gtk.ToggleButton(label=lbl)
            btn.add_css_class("fill-button")
            btn.set_tooltip_text(f"Fill Style: {lbl}")
            if self._first_fill_btn is None:
                self._first_fill_btn = btn
            else:
                btn.set_group(self._first_fill_btn)

            btn.connect("clicked", self._on_fill_button_clicked, val, val.lower())
            self._fill_buttons[val.lower()] = btn
            self.fill_btn_row.append(btn)
        self.box_fill.append(self.fill_btn_row)
        self.append(self.box_fill)

    def _sync_size_buttons(self, width: float) -> None:
        target_key = f"{int(round(width))}px"
        self._updating_ui = True
        try:
            for key, btn in self._size_buttons.items():
                if key == target_key:
                    btn.add_css_class("is-active-size")
                    if not btn.get_active():
                        btn.set_active(True)
                else:
                    btn.remove_css_class("is-active-size")
        finally:
            self._updating_ui = False

    def _sync_fill_buttons(self, mode: str) -> None:
        target_key = mode.lower()
        self._updating_ui = True
        try:
            for key, btn in self._fill_buttons.items():
                if key == target_key:
                    btn.add_css_class("is-active-fill")
                    if not btn.get_active():
                        btn.set_active(True)
                else:
                    btn.remove_css_class("is-active-fill")
        finally:
            self._updating_ui = False

    def _on_size_button_clicked(
        self, button: Gtk.ToggleButton, value: float, key: str
    ) -> None:
        if self._updating_ui:
            return
        if not button.get_active():
            button.set_active(True)
            return
        self.set_stroke_width(value)

    def _on_fill_button_clicked(
        self, button: Gtk.ToggleButton, value: str, key: str
    ) -> None:
        if self._updating_ui:
            return
        if not button.get_active():
            button.set_active(True)
            return
        self.set_fill_mode(value)

    def _on_tool_manager_style_changed(self, width: float, fill: str) -> None:
        self._sync_size_buttons(width)
        self._sync_fill_buttons(fill)
        self._notify_style_changed()

    def _on_tool_manager_tool_changed(self, tool: BaseTool | None) -> None:
        tid = tool.tool_id if tool else None
        self.update_for_tool(tid)
