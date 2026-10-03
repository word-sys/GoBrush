from __future__ import annotations
from typing import TYPE_CHECKING, Callable
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gtk, Gdk

from gobrush.tools.base import (
    DEFAULT_STROKE_WIDTH,
    DEFAULT_FILL_MODE,
    DEFAULT_FILL_OPACITY,
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
    {"label": "24px", "value": 24.0},
    {"label": "32px", "value": 32.0},
]

FILL_OPTIONS = [
    {"label": "Outline", "value": "outline"},
    {"label": "Semi-Fill", "value": "semi"},
    {"label": "Solid", "value": "solid"},
]

OPACITY_OPTIONS = [
    {"label": "15%", "value": 0.15},
    {"label": "25%", "value": 0.25},
    {"label": "50%", "value": 0.50},
    {"label": "75%", "value": 0.75},
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
        .property-title {
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.4px;
            color: alpha(@theme_fg_color, 0.7);
        }
        .property-value-badge {
            background-color: alpha(@theme_fg_color, 0.08);
            color: @theme_fg_color;
            border-radius: 9999px;
            padding: 1px 5px;
            font-size: 10px;
            font-weight: 700;
            font-feature-settings: "tnum";
            min-width: 28px;
        }
        .property-slider {
            min-height: 16px;
            margin: 0;
            padding: 0;
        }
        .property-slider highlight {
            background-color: @theme_selected_bg_color;
        }
        .size-button {
            padding: 1px 2px;
            border-radius: 4px;
            min-height: 20px;
            font-size: 10px;
            font-weight: 600;
            transition: all 120ms ease;
        }
        .size-button:checked, .size-button.is-active-size {
            background-color: @theme_selected_bg_color;
            color: @theme_selected_fg_color;
        }
        .fill-button {
            padding: 2px 3px;
            border-radius: 4px;
            min-height: 22px;
            font-size: 10px;
            font-weight: 600;
            transition: all 120ms ease;
        }
        .fill-button:checked, .fill-button.is-active-fill {
            background-color: @theme_selected_bg_color;
            color: @theme_selected_fg_color;
        }
        .opacity-chip {
            padding: 1px 2px;
            border-radius: 4px;
            min-height: 18px;
            font-size: 9px;
            font-weight: 600;
            transition: all 120ms ease;
        }
        .opacity-chip:checked, .opacity-chip.is-active-opacity {
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
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        ensure_property_bar_css()
        self.add_css_class("context-property-bar")
        self.set_hexpand(False)

        self._tool_manager: ToolManager | None = None
        self._updating_ui: bool = False
        self._style_changed_callbacks: list[Callable[..., None]] = []

        self._local_stroke_width: float = DEFAULT_STROKE_WIDTH
        self._local_fill_mode: str = DEFAULT_FILL_MODE
        self._local_fill_opacity: float = DEFAULT_FILL_OPACITY

        self._tool_changed_handler: Callable[[BaseTool | None], None] | None = None
        self._style_changed_handler: Callable[..., None] | None = None

        self._size_buttons: dict[str, Gtk.ToggleButton] = {}
        self._fill_buttons: dict[str, Gtk.ToggleButton] = {}
        self._opacity_buttons: dict[str, Gtk.ToggleButton] = {}
        self._first_size_btn: Gtk.ToggleButton | None = None
        self._first_fill_btn: Gtk.ToggleButton | None = None
        self._first_opacity_btn: Gtk.ToggleButton | None = None

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
        clamped = max(0.5, min(128.0, float(width)))
        if self._tool_manager is not None:
            self._tool_manager.set_stroke_width(clamped)
        else:
            if abs(self._local_stroke_width - clamped) < 1e-4:
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

    @property
    def fill_opacity(self) -> float:
        if self._tool_manager is not None:
            return self._tool_manager.fill_opacity
        return self._local_fill_opacity

    def set_fill_opacity(self, opacity: float) -> None:
        clamped = max(0.0, min(1.0, float(opacity)))
        if self._tool_manager is not None:
            self._tool_manager.set_fill_opacity(clamped)
        else:
            if abs(self._local_fill_opacity - clamped) < 1e-4:
                return
            self._local_fill_opacity = clamped
            self._sync_fill_buttons(self._local_fill_mode)
            self._notify_style_changed()

    def get_size_button(self, key: str | float) -> Gtk.ToggleButton | None:
        if isinstance(key, (int, float)):
            k1 = f"{int(round(key))}px"
            k2 = str(int(round(key)))
            return self._size_buttons.get(k1) or self._size_buttons.get(k2)
        k = str(key).lower().strip()
        if k in self._size_buttons:
            return self._size_buttons[k]
        if k.endswith("px"):
            return self._size_buttons.get(k[:-2])
        return self._size_buttons.get(f"{k}px")

    def get_fill_button(self, key: str) -> Gtk.ToggleButton | None:
        return self._fill_buttons.get(str(key).lower().strip())

    def get_opacity_button(self, key: str | float) -> Gtk.ToggleButton | None:
        if isinstance(key, (int, float)):
            if key <= 1.0:
                k1 = f"{int(round(key * 100))}%"
                k2 = str(int(round(key * 100)))
            else:
                k1 = f"{int(round(key))}%"
                k2 = str(int(round(key)))
            return self._opacity_buttons.get(k1) or self._opacity_buttons.get(k2)
        k = str(key).lower().strip()
        if k in self._opacity_buttons:
            return self._opacity_buttons[k]
        if k.endswith("%"):
            return self._opacity_buttons.get(k[:-1])
        return self._opacity_buttons.get(f"{k}%")

    def add_style_changed_callback(
        self, cb: Callable[..., None]
    ) -> None:
        if cb not in self._style_changed_callbacks:
            self._style_changed_callbacks.append(cb)

    def remove_style_changed_callback(
        self, cb: Callable[..., None]
    ) -> None:
        if cb in self._style_changed_callbacks:
            self._style_changed_callbacks.remove(cb)

    def _notify_style_changed(self) -> None:
        for cb in list(self._style_changed_callbacks):
            try:
                cb(self.stroke_width, self.fill_mode, self.fill_opacity)
            except TypeError:
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
            is_semi = (self.fill_mode == "semi")
            self.box_opacity.set_sensitive(is_semi)
            self.box_opacity.set_visible(is_semi)

    def _build_ui(self) -> None:
        # Size Section (Compact 2-row layout)
        self.box_size = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)

        size_ctrl_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        self.label_size = Gtk.Label(label="Size", xalign=0.0)
        self.label_size.add_css_class("property-title")
        size_ctrl_row.append(self.label_size)

        adj_size = Gtk.Adjustment(
            value=4.0, lower=1.0, upper=64.0, step_increment=1.0, page_increment=4.0, page_size=0.0
        )
        self.scale_size = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=adj_size)
        self.scale_size.set_draw_value(False)
        self.scale_size.set_hexpand(True)
        self.scale_size.add_css_class("property-slider")
        self.scale_size.set_tooltip_text("Stroke Width: 1px - 64px")
        self.scale_size.connect("value-changed", self._on_scale_size_value_changed)
        size_ctrl_row.append(self.scale_size)

        self.badge_size = Gtk.Label(label="4 px", halign=Gtk.Align.END)
        self.badge_size.add_css_class("property-value-badge")
        size_ctrl_row.append(self.badge_size)
        self.box_size.append(size_ctrl_row)

        # Size Preset Chips
        self.size_btn_row = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL, spacing=2, homogeneous=True
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
            self._size_buttons[str(int(val))] = btn
            self.size_btn_row.append(btn)
        self.box_size.append(self.size_btn_row)
        self.append(self.box_size)

        # Fill Section (Compact layout)
        self.box_fill = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)

        fill_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.label_fill = Gtk.Label(label="Fill", xalign=0.0, hexpand=True)
        self.label_fill.add_css_class("property-title")
        fill_header.append(self.label_fill)

        self.badge_fill = Gtk.Label(label="Outline", halign=Gtk.Align.END)
        self.badge_fill.add_css_class("property-value-badge")
        fill_header.append(self.badge_fill)
        self.box_fill.append(fill_header)

        # Fill Mode Buttons
        self.fill_btn_row = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL, spacing=2, homogeneous=True
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
            self._fill_buttons[lbl.lower()] = btn
            self.fill_btn_row.append(btn)
        self.box_fill.append(self.fill_btn_row)

        # Single-row Opacity Slider (visible when Semi-Fill is selected)
        self.box_opacity = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)

        lbl_op = Gtk.Label(label="Opacity", xalign=0.0)
        lbl_op.add_css_class("property-title")
        self.box_opacity.append(lbl_op)

        adj_opacity = Gtk.Adjustment(
            value=25.0, lower=5.0, upper=100.0, step_increment=1.0, page_increment=5.0, page_size=0.0
        )
        self.scale_opacity = Gtk.Scale(orientation=Gtk.Orientation.HORIZONTAL, adjustment=adj_opacity)
        self.scale_opacity.set_draw_value(False)
        self.scale_opacity.set_hexpand(True)
        self.scale_opacity.add_css_class("property-slider")
        self.scale_opacity.set_tooltip_text("Fill Opacity: 5% - 100%")
        self.scale_opacity.connect("value-changed", self._on_scale_opacity_value_changed)
        self.box_opacity.append(self.scale_opacity)

        self.badge_opacity = Gtk.Label(label="25%", halign=Gtk.Align.END)
        self.badge_opacity.add_css_class("property-value-badge")
        self.box_opacity.append(self.badge_opacity)

        for opt in OPACITY_OPTIONS:
            lbl = opt["label"]
            val = opt["value"]
            btn = Gtk.ToggleButton(label=lbl)
            if self._first_opacity_btn is None:
                self._first_opacity_btn = btn
            else:
                btn.set_group(self._first_opacity_btn)
            btn.connect("clicked", self._on_opacity_button_clicked, val, lbl.lower())
            self._opacity_buttons[lbl.lower()] = btn
            self._opacity_buttons[str(int(round(val * 100)))] = btn

        self.box_opacity.set_visible(False)
        self.box_opacity.set_sensitive(False)
        self.box_fill.append(self.box_opacity)

        self.append(self.box_fill)

    def _sync_size_buttons(self, width: float) -> None:
        self._updating_ui = True
        try:
            if hasattr(self, "scale_size"):
                if abs(self.scale_size.get_value() - width) > 0.01:
                    self.scale_size.set_value(width)

            if hasattr(self, "badge_size"):
                disp = f"{int(round(width))} px" if abs(width - round(width)) < 1e-3 else f"{width:.1f} px"
                self.badge_size.set_text(disp)

            target_px = f"{int(round(width))}px"
            target_num = str(int(round(width)))
            found = False
            for key, btn in self._size_buttons.items():
                if key in (target_px, target_num):
                    btn.add_css_class("is-active-size")
                    if not btn.get_active():
                        btn.set_active(True)
                    found = True
                else:
                    btn.remove_css_class("is-active-size")
            if not found:
                for btn in self._size_buttons.values():
                    if btn.get_active():
                        btn.set_active(False)
        finally:
            self._updating_ui = False

    def _sync_fill_buttons(self, mode: str) -> None:
        self._updating_ui = True
        try:
            target_key = mode.lower()
            for key, btn in self._fill_buttons.items():
                if key == target_key:
                    btn.add_css_class("is-active-fill")
                    if not btn.get_active():
                        btn.set_active(True)
                else:
                    btn.remove_css_class("is-active-fill")

            op = self.fill_opacity
            pct = int(round(op * 100))

            if hasattr(self, "badge_fill"):
                if mode == "outline":
                    self.badge_fill.set_text("Outline")
                elif mode == "solid":
                    self.badge_fill.set_text("Solid")
                else:
                    self.badge_fill.set_text(f"{pct}%")

            is_semi = (mode == "semi")
            if hasattr(self, "box_opacity"):
                self.box_opacity.set_sensitive(is_semi)
                self.box_opacity.set_visible(is_semi)

            if hasattr(self, "scale_opacity"):
                if abs(self.scale_opacity.get_value() - pct) > 0.5:
                    self.scale_opacity.set_value(pct)

            if hasattr(self, "badge_opacity"):
                self.badge_opacity.set_text(f"{pct}%")

            target_op = f"{pct}%"
            target_num = str(pct)
            for key, btn in self._opacity_buttons.items():
                if key in (target_op, target_num) and is_semi:
                    btn.add_css_class("is-active-opacity")
                    if not btn.get_active():
                        btn.set_active(True)
                else:
                    btn.remove_css_class("is-active-opacity")
        finally:
            self._updating_ui = False

    def _on_scale_size_value_changed(self, scale: Gtk.Scale) -> None:
        if self._updating_ui:
            return
        val = float(round(scale.get_value()))
        self.set_stroke_width(val)

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

    def _on_scale_opacity_value_changed(self, scale: Gtk.Scale) -> None:
        if self._updating_ui:
            return
        val = float(scale.get_value()) / 100.0
        if self.fill_mode == "outline":
            self.set_fill_mode("semi")
        self.set_fill_opacity(val)

    def _on_opacity_button_clicked(
        self, button: Gtk.ToggleButton, value: float, key: str
    ) -> None:
        if self._updating_ui:
            return
        if not button.get_active():
            button.set_active(True)
            return
        if self.fill_mode == "outline":
            self.set_fill_mode("semi")
        self.set_fill_opacity(value)

    def _on_tool_manager_style_changed(
        self, width: float, fill: str, opacity: float = 0.25
    ) -> None:
        self._sync_size_buttons(width)
        self._sync_fill_buttons(fill)
        self._notify_style_changed()

    def _on_tool_manager_tool_changed(self, tool: BaseTool | None) -> None:
        tid = tool.tool_id if tool else None
        self.update_for_tool(tid)
