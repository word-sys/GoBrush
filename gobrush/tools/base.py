from __future__ import annotations
from abc import ABC
from typing import TYPE_CHECKING, Callable
import cairo
import gi

gi.require_version("Gdk", "4.0")
from gi.repository import Gdk

if TYPE_CHECKING:
    from gobrush.ui.canvas import Canvas


class BaseTool(ABC):
    tool_id: str = "base"
    name: str = "Base Tool"
    cursor_name: str | None = "default"

    def __init__(self, canvas: Canvas | None = None) -> None:
        self.canvas: Canvas | None = canvas
        self.is_active: bool = False

    def activate(self) -> None:
        self.is_active = True

    def deactivate(self) -> None:
        self.is_active = False

    def on_press(
        self, ix: float, iy: float, sx: float, sy: float, state: Gdk.ModifierType
    ) -> bool:
        return False

    def on_drag(
        self, ix: float, iy: float, dx: float, dy: float, sx: float, sy: float, state: Gdk.ModifierType
    ) -> bool:
        return False

    def on_release(
        self, ix: float, iy: float, sx: float, sy: float, state: Gdk.ModifierType
    ) -> bool:
        return False

    def on_cancel(self) -> None:
        pass

    def on_motion(
        self, ix: float, iy: float, sx: float, sy: float, state: Gdk.ModifierType
    ) -> bool:
        return False

    def on_key_pressed(self, keyval: int, state: Gdk.ModifierType) -> bool:
        return False

    def on_key_released(self, keyval: int, state: Gdk.ModifierType) -> bool:
        return False

    def draw_overlay(self, cr: cairo.Context) -> None:
        pass

    def draw_screen_overlay(self, cr: cairo.Context, width: int, height: int) -> None:
        pass


class SelectTool(BaseTool):
    tool_id: str = "select"
    name: str = "Select"
    shortcut: str = "S"
    icon_name: str = "edit-select-symbolic"
    cursor_name: str | None = "default"


class TextTool(BaseTool):
    tool_id: str = "text"
    name: str = "Text"
    shortcut: str = "T"
    icon_name: str = "insert-text-symbolic"
    cursor_name: str | None = "text"


class PenTool(BaseTool):
    tool_id: str = "pen"
    name: str = "Pen"
    shortcut: str = "P"
    icon_name: str = "document-edit-symbolic"
    cursor_name: str | None = "crosshair"


class HighlighterTool(BaseTool):
    tool_id: str = "highlighter"
    name: str = "Highlighter"
    shortcut: str = "H"
    icon_name: str = "marker-symbolic"
    cursor_name: str | None = "crosshair"


class ArrowTool(BaseTool):
    tool_id: str = "arrow"
    name: str = "Arrow"
    shortcut: str = "A"
    icon_name: str = "go-next-symbolic"
    cursor_name: str | None = "crosshair"


class LineTool(BaseTool):
    tool_id: str = "line"
    name: str = "Line"
    shortcut: str = "L"
    icon_name: str = "view-list-symbolic"
    cursor_name: str | None = "crosshair"


class RectangleTool(BaseTool):
    tool_id: str = "rectangle"
    name: str = "Rectangle"
    shortcut: str = "R"
    icon_name: str = "window-maximize-symbolic"
    cursor_name: str | None = "crosshair"


class EllipseTool(BaseTool):
    tool_id: str = "ellipse"
    name: str = "Ellipse"
    shortcut: str = "C"
    icon_name: str = "radio-checked-symbolic"
    cursor_name: str | None = "crosshair"


class BlurTool(BaseTool):
    tool_id: str = "blur"
    name: str = "Blur"
    shortcut: str = "B"
    icon_name: str = "view-conceal-symbolic"
    cursor_name: str | None = "crosshair"


class BadgeTool(BaseTool):
    tool_id: str = "badge"
    name: str = "Badge"
    shortcut: str = "N"
    icon_name: str = "starred-symbolic"
    cursor_name: str | None = "crosshair"


class CheckmarkTool(BaseTool):
    tool_id: str = "checkmark"
    name: str = "Checkmark"
    shortcut: str = "V"
    icon_name: str = "emblem-ok-symbolic"
    cursor_name: str | None = "crosshair"


class CrossTool(BaseTool):
    tool_id: str = "cross"
    name: str = "Cross"
    shortcut: str = "X"
    icon_name: str = "window-close-symbolic"
    cursor_name: str | None = "crosshair"


class CropTool(BaseTool):
    tool_id: str = "crop"
    name: str = "Crop"
    shortcut: str = "K"
    icon_name: str = "zoom-fit-best-symbolic"
    cursor_name: str | None = "crosshair"


DEFAULT_TOOL_CLASSES = [
    SelectTool,
    TextTool,
    PenTool,
    HighlighterTool,
    ArrowTool,
    LineTool,
    RectangleTool,
    EllipseTool,
    BlurTool,
    BadgeTool,
    CheckmarkTool,
    CrossTool,
    CropTool,
]
TOOL_SHORTCUTS: dict[int, str] = {
    Gdk.KEY_s: "select",
    Gdk.KEY_S: "select",
    Gdk.KEY_t: "text",
    Gdk.KEY_T: "text",
    Gdk.KEY_p: "pen",
    Gdk.KEY_P: "pen",
    Gdk.KEY_h: "highlighter",
    Gdk.KEY_H: "highlighter",
    Gdk.KEY_a: "arrow",
    Gdk.KEY_A: "arrow",
    Gdk.KEY_l: "line",
    Gdk.KEY_L: "line",
    Gdk.KEY_r: "rectangle",
    Gdk.KEY_R: "rectangle",
    Gdk.KEY_c: "ellipse",
    Gdk.KEY_C: "ellipse",
    Gdk.KEY_b: "blur",
    Gdk.KEY_B: "blur",
    Gdk.KEY_n: "badge",
    Gdk.KEY_N: "badge",
    Gdk.KEY_v: "checkmark",
    Gdk.KEY_V: "checkmark",
    Gdk.KEY_x: "cross",
    Gdk.KEY_X: "cross",
    Gdk.KEY_k: "crop",
    Gdk.KEY_K: "crop",
}


class ToolManager:
    def __init__(self, canvas: Canvas | None = None) -> None:
        self.canvas: Canvas | None = canvas
        self._tools: dict[str, BaseTool] = {}
        self._active_tool: BaseTool | None = None
        self._tool_changed_callbacks: list[Callable[[BaseTool | None], None]] = []
        self._is_dragging: bool = False

    def register_default_tools(self) -> None:
        for tool_cls in DEFAULT_TOOL_CLASSES:
            if tool_cls.tool_id not in self._tools:
                self.register_tool(tool_cls(self.canvas))

    @property
    def active_tool(self) -> BaseTool | None:
        return self._active_tool

    @property
    def active_tool_id(self) -> str | None:
        return self._active_tool.tool_id if self._active_tool else None

    @property
    def is_dragging(self) -> bool:
        return self._is_dragging

    @property
    def tools(self) -> dict[str, BaseTool]:
        return dict(self._tools)

    def register_tool(self, tool: BaseTool) -> None:
        tool.canvas = self.canvas
        self._tools[tool.tool_id] = tool

    def get_tool(self, tool_id: str) -> BaseTool | None:
        return self._tools.get(tool_id)

    def set_active_tool(self, tool_or_id: str | BaseTool | None) -> bool:
        new_tool: BaseTool | None = None
        if tool_or_id is None:
            new_tool = None
        elif isinstance(tool_or_id, str):
            if tool_or_id not in self._tools:
                return False
            new_tool = self._tools[tool_or_id]
        elif isinstance(tool_or_id, BaseTool):
            new_tool = tool_or_id
            if new_tool.tool_id not in self._tools:
                self.register_tool(new_tool)
        else:
            return False

        if self._active_tool is new_tool:
            return True

        if self._is_dragging:
            self.handle_cancel()

        if self._active_tool is not None:
            self._active_tool.deactivate()

        self._active_tool = new_tool

        if self._active_tool is not None:
            self._active_tool.activate()
            if self.canvas is not None:
                self.canvas.tool_cursor_name = self._active_tool.cursor_name
        else:
            if self.canvas is not None:
                self.canvas.tool_cursor_name = None

        if self.canvas is not None:
            self.canvas.queue_draw()

        for cb in self._tool_changed_callbacks:
            cb(self._active_tool)

        return True

    def add_tool_changed_callback(self, cb: Callable[[BaseTool | None], None]) -> None:
        if cb not in self._tool_changed_callbacks:
            self._tool_changed_callbacks.append(cb)

    def remove_tool_changed_callback(self, cb: Callable[[BaseTool | None], None]) -> None:
        if cb in self._tool_changed_callbacks:
            self._tool_changed_callbacks.remove(cb)

    def handle_press(
        self, ix: float, iy: float, sx: float, sy: float, state: Gdk.ModifierType
    ) -> bool:
        self._is_dragging = True
        if self._active_tool is not None:
            return self._active_tool.on_press(ix, iy, sx, sy, state)
        return False

    def handle_drag(
        self, ix: float, iy: float, dx: float, dy: float, sx: float, sy: float, state: Gdk.ModifierType
    ) -> bool:
        if self._active_tool is not None and self._is_dragging:
            return self._active_tool.on_drag(ix, iy, dx, dy, sx, sy, state)
        return False

    def handle_release(
        self, ix: float, iy: float, sx: float, sy: float, state: Gdk.ModifierType
    ) -> bool:
        was_dragging = self._is_dragging
        self._is_dragging = False
        if self._active_tool is not None and was_dragging:
            return self._active_tool.on_release(ix, iy, sx, sy, state)
        return False

    def handle_cancel(self) -> None:
        if self._is_dragging:
            self._is_dragging = False
            if self._active_tool is not None:
                self._active_tool.on_cancel()
            if self.canvas is not None:
                self.canvas.queue_draw()

    def handle_motion(
        self, ix: float, iy: float, sx: float, sy: float, state: Gdk.ModifierType
    ) -> bool:
        if self._active_tool is not None and not self._is_dragging:
            return self._active_tool.on_motion(ix, iy, sx, sy, state)
        return False

    def handle_key_pressed(self, keyval: int, state: Gdk.ModifierType) -> bool:
        if keyval == Gdk.KEY_Escape:
            if self._is_dragging:
                self.handle_cancel()
                return True
            elif self._active_tool is not None and self._active_tool.tool_id != "select":
                if "select" in self._tools:
                    self.set_active_tool("select")
                    return True

        if self._active_tool is not None:
            if self._active_tool.on_key_pressed(keyval, state):
                return True

        if not self._is_dragging:
            is_ctrl = bool(state & Gdk.ModifierType.CONTROL_MASK)
            is_alt = bool(state & Gdk.ModifierType.ALT_MASK)
            is_super = bool(state & Gdk.ModifierType.SUPER_MASK) if hasattr(Gdk.ModifierType, "SUPER_MASK") else False
            if not is_ctrl and not is_alt and not is_super:
                tool_id = TOOL_SHORTCUTS.get(keyval)
                if tool_id is not None and tool_id in self._tools:
                    self.set_active_tool(tool_id)
                    return True

        return False

    def handle_key_released(self, keyval: int, state: Gdk.ModifierType) -> bool:
        if self._active_tool is not None:
            return self._active_tool.on_key_released(keyval, state)
        return False

    def draw_overlay(self, cr: cairo.Context) -> None:
        if self._active_tool is not None:
            cr.save()
            self._active_tool.draw_overlay(cr)
            cr.restore()

    def draw_screen_overlay(self, cr: cairo.Context, width: int, height: int) -> None:
        if self._active_tool is not None:
            cr.save()
            self._active_tool.draw_screen_overlay(cr, width, height)
            cr.restore()
