from __future__ import annotations
from typing import TYPE_CHECKING, Callable
import cairo
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gtk, Gdk

from gobrush.compat.color import pick_color_dialog, rgba_from_floats
from gobrush.ui.property_bar import ContextPropertyBar, SIZE_OPTIONS, FILL_OPTIONS

if TYPE_CHECKING:
    from gobrush.tools.base import BaseTool, ToolManager

TOOL_DEFINITIONS = [
    {
        "id": "select",
        "label": "Select (S)",
        "tooltip": "Select Tool (S)",
        "icon": "edit-select-symbolic",
        "shortcut": "S",
    },
    {
        "id": "text",
        "label": "Text (T)",
        "tooltip": "Text Tool (T)",
        "icon": "insert-text-symbolic",
        "shortcut": "T",
    },
    {
        "id": "pen",
        "label": "Pen (P)",
        "tooltip": "Pen Tool (P)",
        "icon": "document-edit-symbolic",
        "shortcut": "P",
    },
    {
        "id": "highlighter",
        "label": "Highlighter (H)",
        "tooltip": "Highlighter Tool (H)",
        "icon": "marker-symbolic",
        "shortcut": "H",
    },
    {
        "id": "arrow",
        "label": "Arrow (A)",
        "tooltip": "Arrow Tool (A)",
        "icon": "go-next-symbolic",
        "shortcut": "A",
    },
    {
        "id": "line",
        "label": "Line (L)",
        "tooltip": "Line Tool (L)",
        "icon": "view-list-symbolic",
        "shortcut": "L",
    },
    {
        "id": "rectangle",
        "label": "Rectangle (R)",
        "tooltip": "Rectangle Tool (R)",
        "icon": "window-maximize-symbolic",
        "shortcut": "R",
    },
    {
        "id": "ellipse",
        "label": "Ellipse (C)",
        "tooltip": "Ellipse Tool (C)",
        "icon": "radio-checked-symbolic",
        "shortcut": "C",
    },
    {
        "id": "blur",
        "label": "Blur (B)",
        "tooltip": "Blur Tool (B)",
        "icon": "view-conceal-symbolic",
        "shortcut": "B",
    },
    {
        "id": "badge",
        "label": "Badge (N)",
        "tooltip": "Step Badge Tool (N)",
        "icon": "starred-symbolic",
        "shortcut": "N",
    },
    {
        "id": "checkmark",
        "label": "Checkmark (V)",
        "tooltip": "Checkmark Tool (V)",
        "icon": "emblem-ok-symbolic",
        "shortcut": "V",
    },
    {
        "id": "cross",
        "label": "Cross (X)",
        "tooltip": "Cross Tool (X)",
        "icon": "window-close-symbolic",
        "shortcut": "X",
    },
    {
        "id": "crop",
        "label": "Crop (K)",
        "tooltip": "Crop Canvas Tool (K)",
        "icon": "zoom-fit-best-symbolic",
        "shortcut": "K",
    },
]

CURATED_PALETTE_COLORS = [
    {"name": "Red", "hex": "#E01B24", "rgba": (224 / 255, 27 / 255, 36 / 255, 1.0)},
    {"name": "Orange", "hex": "#FF7800", "rgba": (255 / 255, 120 / 255, 0 / 255, 1.0)},
    {"name": "Yellow", "hex": "#F6D32D", "rgba": (246 / 255, 211 / 255, 45 / 255, 1.0)},
    {"name": "Green", "hex": "#33D17A", "rgba": (51 / 255, 209 / 255, 122 / 255, 1.0)},
    {"name": "Cyan", "hex": "#00C0E4", "rgba": (0 / 255, 192 / 255, 228 / 255, 1.0)},
    {"name": "Blue", "hex": "#1C71D8", "rgba": (28 / 255, 113 / 255, 216 / 255, 1.0)},
    {"name": "Violet", "hex": "#9141AC", "rgba": (145 / 255, 65 / 255, 172 / 255, 1.0)},
    {"name": "Black", "hex": "#241F31", "rgba": (36 / 255, 31 / 255, 49 / 255, 1.0)},
    {"name": "White", "hex": "#FFFFFF", "rgba": (1.0, 1.0, 1.0, 1.0)},
]


def colors_match(
    c1: tuple[float, float, float, float],
    c2: tuple[float, float, float, float],
    tolerance: float = 0.03,
) -> bool:
    return all(abs(a - b) <= tolerance for a, b in zip(c1[:3], c2[:3]))


_CSS_INITIALIZED = False


def ensure_palette_css() -> None:
    global _CSS_INITIALIZED
    if _CSS_INITIALIZED:
        return
    display = Gdk.Display.get_default()
    if display is None:
        return

    css_provider = Gtk.CssProvider()
    css_provider.load_from_data(b"""
        .tool-palette {
            padding: 6px 8px;
        }
        .tool-palette-header {
            font-weight: 700;
            margin-bottom: 2px;
        }
        .tool-button {
            padding: 4px 6px;
            border-radius: 6px;
            min-height: 28px;
            font-size: 13px;
            transition: all 120ms ease;
        }
        .tool-button:checked, .tool-button.is-active-tool {
            background-color: @theme_selected_bg_color;
            color: @theme_selected_fg_color;
            font-weight: 600;
        }
        .palette-separator {
            margin: 3px 0;
            opacity: 0.4;
        }
        .color-dot {
            min-width: 22px;
            min-height: 22px;
            padding: 0;
            border-radius: 9999px;
            border: 2px solid transparent;
            transition: transform 120ms ease, box-shadow 120ms ease;
        }
        .color-dot:hover {
            filter: brightness(1.15);
        }
        .color-dot-red { background-color: #E01B24; }
        .color-dot-orange { background-color: #FF7800; }
        .color-dot-yellow { background-color: #F6D32D; }
        .color-dot-green { background-color: #33D17A; }
        .color-dot-cyan { background-color: #00C0E4; }
        .color-dot-blue { background-color: #1C71D8; }
        .color-dot-violet { background-color: #9141AC; }
        .color-dot-black { background-color: #241F31; border-color: rgba(255, 255, 255, 0.25); }
        .color-dot-white { background-color: #FFFFFF; border-color: rgba(0, 0, 0, 0.25); }
        .color-dot.is-active-color {
            border: 2px solid #ffffff;
            box-shadow: 0 0 0 2px @theme_selected_bg_color;
        }
        .color-picker-button {
            padding: 4px 8px;
            border-radius: 6px;
            min-height: 28px;
            transition: all 120ms ease;
        }
        .color-picker-button.is-active-color {
            outline: 2px solid @theme_selected_bg_color;
            outline-offset: 1px;
        }
    """)
    Gtk.StyleContext.add_provider_for_display(
        display, css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )
    _CSS_INITIALIZED = True


class ToolPalette(Gtk.Box):
    def __init__(self, tool_manager: ToolManager | None = None) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        ensure_palette_css()

        self.add_css_class("tool-palette")
        self.set_size_request(260, -1)

        self._tool_manager: ToolManager | None = None
        self._buttons: dict[str, Gtk.ToggleButton] = {}
        self._first_button: Gtk.ToggleButton | None = None
        self._updating_ui: bool = False
        self._tool_changed_handler: Callable[[BaseTool | None], None] | None = None

        self._color_dots: dict[str, Gtk.Button] = {}
        self._color_changed_callbacks: list[Callable[[tuple[float, float, float, float]], None]] = []
        self._color_changed_handler: Callable[[tuple[float, float, float, float]], None] | None = None
        self._local_color: tuple[float, float, float, float] = (0.88, 0.11, 0.14, 1.0)

        self._build_header()
        self._build_grid()
        self._build_color_section()
        self._build_property_bar()

        if tool_manager is not None:
            self.set_tool_manager(tool_manager)
        else:
            self._sync_button_state("select")
            self._sync_color_state(self._local_color)

    @property
    def tool_manager(self) -> ToolManager | None:
        return self._tool_manager

    @property
    def active_tool_id(self) -> str | None:
        if self._tool_manager is not None:
            return self._tool_manager.active_tool_id
        for tid, btn in self._buttons.items():
            if btn.get_active():
                return tid
        return None

    @property
    def current_color(self) -> tuple[float, float, float, float]:
        if self._tool_manager is not None:
            return self._tool_manager.current_color
        return self._local_color

    def set_current_color(self, color: tuple[float, float, float, float]) -> None:
        if self._tool_manager is not None:
            self._tool_manager.set_current_color(color)
        else:
            if self._local_color == color:
                return
            self._local_color = color
            self._sync_color_state(color)
            self._notify_color_changed(color)

    @property
    def stroke_width(self) -> float:
        return self.property_bar.stroke_width

    def set_stroke_width(self, width: float) -> None:
        self.property_bar.set_stroke_width(width)

    @property
    def fill_mode(self) -> str:
        return self.property_bar.fill_mode

    def set_fill_mode(self, mode: str) -> None:
        self.property_bar.set_fill_mode(mode)

    def get_button(self, tool_id: str) -> Gtk.ToggleButton | None:
        return self._buttons.get(tool_id)

    def get_color_dot(self, name: str) -> Gtk.Button | None:
        return self._color_dots.get(name.lower())

    def get_size_button(self, key: str | float) -> Gtk.ToggleButton | None:
        return self.property_bar.get_size_button(key)

    def get_fill_button(self, key: str) -> Gtk.ToggleButton | None:
        return self.property_bar.get_fill_button(key)

    def add_color_changed_callback(
        self, cb: Callable[[tuple[float, float, float, float]], None]
    ) -> None:
        if cb not in self._color_changed_callbacks:
            self._color_changed_callbacks.append(cb)

    def remove_color_changed_callback(
        self, cb: Callable[[tuple[float, float, float, float]], None]
    ) -> None:
        if cb in self._color_changed_callbacks:
            self._color_changed_callbacks.remove(cb)

    def _notify_color_changed(self, color: tuple[float, float, float, float]) -> None:
        for cb in list(self._color_changed_callbacks):
            cb(color)

    def set_tool_manager(self, tool_manager: ToolManager | None) -> None:
        if self._tool_manager is not None:
            if self._tool_changed_handler is not None:
                self._tool_manager.remove_tool_changed_callback(self._tool_changed_handler)
                self._tool_changed_handler = None
            if self._color_changed_handler is not None:
                self._tool_manager.remove_color_changed_callback(self._color_changed_handler)
                self._color_changed_handler = None

        self._tool_manager = tool_manager

        if hasattr(self, "property_bar"):
            self.property_bar.set_tool_manager(tool_manager)

        if self._tool_manager is not None:
            self._tool_manager.register_default_tools()
            self._tool_changed_handler = self._on_tool_changed
            self._tool_manager.add_tool_changed_callback(self._tool_changed_handler)

            self._color_changed_handler = self._on_tool_manager_color_changed
            self._tool_manager.add_color_changed_callback(self._color_changed_handler)

            current_active = self._tool_manager.active_tool_id or "select"
            self.set_active_tool(current_active)
            self._sync_color_state(self._tool_manager.current_color)

    def set_active_tool(self, tool_id: str) -> bool:
        if tool_id not in self._buttons:
            return False

        if self._tool_manager is not None:
            if self._tool_manager.active_tool_id != tool_id:
                return self._tool_manager.set_active_tool(tool_id)
            else:
                self._sync_button_state(tool_id)
                return True
        else:
            self._sync_button_state(tool_id)
            return True

    def _sync_button_state(self, tool_id: str) -> None:
        self._updating_ui = True
        try:
            for tid, btn in self._buttons.items():
                if tid == tool_id:
                    btn.add_css_class("is-active-tool")
                    if not btn.get_active():
                        btn.set_active(True)
                else:
                    btn.remove_css_class("is-active-tool")
        finally:
            self._updating_ui = False

    def _on_tool_changed(self, tool: BaseTool | None) -> None:
        if tool is not None:
            self._sync_button_state(tool.tool_id)
            if hasattr(self, "property_bar"):
                self.property_bar.update_for_tool(tool.tool_id)

    def _on_button_clicked(self, button: Gtk.ToggleButton, tool_id: str) -> None:
        if self._updating_ui:
            return
        if not button.get_active():
            button.set_active(True)
            return

        if self._tool_manager is not None:
            self._tool_manager.set_active_tool(tool_id)

    def _build_header(self) -> None:
        self.label_tools = Gtk.Label(label="Tools", xalign=0.0)
        self.label_tools.add_css_class("title-4")
        self.label_tools.add_css_class("tool-palette-header")
        self.append(self.label_tools)

    def _build_grid(self) -> None:
        self.grid = Gtk.Grid(row_spacing=6, column_spacing=6, column_homogeneous=True)
        self.append(self.grid)

        for i, tool in enumerate(TOOL_DEFINITIONS):
            tid = tool["id"]
            btn = Gtk.ToggleButton()
            if self._first_button is None:
                self._first_button = btn
                btn.set_active(True)
            else:
                btn.set_group(self._first_button)

            box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            box.set_halign(Gtk.Align.CENTER)
            img = Gtk.Image.new_from_icon_name(tool["icon"])
            lbl = Gtk.Label(label=tool["label"])
            box.append(img)
            box.append(lbl)
            btn.set_child(box)
            btn.set_tooltip_text(tool["tooltip"])
            btn.add_css_class("tool-button")

            btn.connect("clicked", self._on_button_clicked, tid)
            self._buttons[tid] = btn

            if tid == "crop":
                self.grid.attach(btn, 0, 6, 2, 1)
            else:
                self.grid.attach(btn, i % 2, i // 2, 1, 1)

    def _build_color_section(self) -> None:
        self.separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        self.separator.add_css_class("palette-separator")
        self.append(self.separator)

        self.label_color = Gtk.Label(label="Color", xalign=0.0)
        self.label_color.add_css_class("title-4")
        self.label_color.add_css_class("tool-palette-header")
        self.append(self.label_color)

        self.dots_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=4)
        self.dots_box.set_halign(Gtk.Align.CENTER)
        self.append(self.dots_box)

        for c in CURATED_PALETTE_COLORS:
            b = Gtk.Button()
            b.add_css_class("color-dot")
            b.add_css_class(f"color-dot-{c['name'].lower()}")
            b.set_tooltip_text(c["name"])
            b.connect("clicked", self._on_color_dot_clicked, c["rgba"])
            self._color_dots[c["name"].lower()] = b
            self.dots_box.append(b)

        self.btn_color = Gtk.Button()
        self.btn_color.add_css_class("color-picker-button")
        self.btn_color.set_tooltip_text("Select Color...")

        cbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        cbox.set_halign(Gtk.Align.CENTER)

        self.swatch_preview = Gtk.DrawingArea()
        self.swatch_preview.set_size_request(16, 16)
        self.swatch_preview.set_valign(Gtk.Align.CENTER)
        self.swatch_preview.set_draw_func(self._draw_swatch)

        icon = Gtk.Image.new_from_icon_name("color-select-symbolic")
        lbl = Gtk.Label(label="Color")

        cbox.append(self.swatch_preview)
        cbox.append(icon)
        cbox.append(lbl)
        self.btn_color.set_child(cbox)
        self.btn_color.connect("clicked", self._on_color_button_clicked)
        self.append(self.btn_color)

    def _draw_swatch(
        self, area: Gtk.DrawingArea, cr: cairo.Context, width: int, height: int
    ) -> None:
        cr.arc(width / 2.0, height / 2.0, min(width, height) / 2.0 - 1.0, 0, 6.2831853)
        cr.set_source_rgba(*self.current_color)
        cr.fill_preserve()
        cr.set_source_rgba(0.0, 0.0, 0.0, 0.3)
        cr.set_line_width(1.0)
        cr.stroke()

    def _sync_color_state(self, color: tuple[float, float, float, float]) -> None:
        matched = False
        for c in CURATED_PALETTE_COLORS:
            btn = self._color_dots.get(c["name"].lower())
            if btn is not None:
                if not matched and colors_match(color, c["rgba"]):
                    btn.add_css_class("is-active-color")
                    matched = True
                else:
                    btn.remove_css_class("is-active-color")

        if not matched:
            self.btn_color.add_css_class("is-active-color")
        else:
            self.btn_color.remove_css_class("is-active-color")

        if hasattr(self, "swatch_preview"):
            self.swatch_preview.queue_draw()

    def _on_color_dot_clicked(
        self, _btn: Gtk.Button, rgba_tuple: tuple[float, float, float, float]
    ) -> None:
        self.set_current_color(rgba_tuple)

    def _on_color_button_clicked(self, _btn: Gtk.Button) -> None:
        root = self.get_root()
        parent_win = root if isinstance(root, Gtk.Window) else None
        current_rgba = rgba_from_floats(*self.current_color)
        pick_color_dialog(
            parent=parent_win,
            current=current_rgba,
            callback=self._on_custom_color_picked,
            title="Select Color",
            show=True,
        )

    def _on_custom_color_picked(self, rgba: Gdk.RGBA | None) -> None:
        if rgba is not None:
            self.set_current_color((rgba.red, rgba.green, rgba.blue, rgba.alpha))

    def _on_tool_manager_color_changed(
        self, color: tuple[float, float, float, float]
    ) -> None:
        self._sync_color_state(color)
        self._notify_color_changed(color)

    def _build_property_bar(self) -> None:
        sep = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        sep.add_css_class("palette-separator")
        self.append(sep)

        self.property_bar = ContextPropertyBar(self._tool_manager)
        self.append(self.property_bar)
