from __future__ import annotations
from typing import TYPE_CHECKING, Callable
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
from gi.repository import Gtk, Gdk

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
            padding: 10px 8px;
        }
        .tool-palette-header {
            font-weight: 700;
            margin-bottom: 4px;
        }
        .tool-button {
            padding: 6px 8px;
            border-radius: 8px;
            min-height: 34px;
        }
        .tool-button:checked {
            background-color: @theme_selected_bg_color;
            color: @theme_selected_fg_color;
        }
    """)
    Gtk.StyleContext.add_provider_for_display(
        display, css_provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )
    _CSS_INITIALIZED = True


class ToolPalette(Gtk.Box):
    def __init__(self, tool_manager: ToolManager | None = None) -> None:
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        ensure_palette_css()

        self.add_css_class("tool-palette")
        self.set_size_request(260, -1)

        self._tool_manager: ToolManager | None = None
        self._buttons: dict[str, Gtk.ToggleButton] = {}
        self._first_button: Gtk.ToggleButton | None = None
        self._updating_ui: bool = False
        self._tool_changed_handler: Callable[[BaseTool | None], None] | None = None

        self._build_header()
        self._build_grid()

        if tool_manager is not None:
            self.set_tool_manager(tool_manager)

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

    def get_button(self, tool_id: str) -> Gtk.ToggleButton | None:
        return self._buttons.get(tool_id)

    def set_tool_manager(self, tool_manager: ToolManager | None) -> None:
        if self._tool_manager is not None and self._tool_changed_handler is not None:
            self._tool_manager.remove_tool_changed_callback(self._tool_changed_handler)
            self._tool_changed_handler = None

        self._tool_manager = tool_manager

        if self._tool_manager is not None:
            self._tool_manager.register_default_tools()
            self._tool_changed_handler = self._on_tool_changed
            self._tool_manager.add_tool_changed_callback(self._tool_changed_handler)

            current_active = self._tool_manager.active_tool_id or "select"
            self.set_active_tool(current_active)

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
        target_btn = self._buttons.get(tool_id)
        if target_btn is not None and not target_btn.get_active():
            self._updating_ui = True
            try:
                target_btn.set_active(True)
            finally:
                self._updating_ui = False

    def _on_tool_changed(self, tool: BaseTool | None) -> None:
        if tool is not None:
            self._sync_button_state(tool.tool_id)

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
