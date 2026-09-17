from __future__ import annotations
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from gobrush.core.document import AnnotationDocument
    from gobrush.items.base import AnnotationItem


class Command(ABC):
    name: str = "Command"

    @abstractmethod
    def execute(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def undo(self) -> None:
        raise NotImplementedError

    def redo(self) -> None:
        self.execute()

    def merge_with(self, other: Command) -> bool:
        return False


class AddAnnotationCommand(Command):
    def __init__(
        self,
        document: AnnotationDocument,
        item: AnnotationItem,
        index: int | None = None,
        select: bool = True,
        name: str = "Add Annotation",
    ) -> None:
        self.document = document
        self.item = item
        self.index = index
        self.select = select
        self.name = name
        self._actual_index: int = -1

    def execute(self) -> None:
        target_idx = self._actual_index if self._actual_index >= 0 else self.index
        self._actual_index = self.document.add_item(self.item, index=target_idx)
        if self.select:
            self.document.select_item(self.item, exclusive=True)

    def undo(self) -> None:
        if self.item.is_selected:
            self.document.select_item(None, exclusive=True)
        self.document.remove_item(self.item)

    def redo(self) -> None:
        self.execute()


class DeleteAnnotationCommand(Command):
    def __init__(
        self,
        document: AnnotationDocument,
        items: AnnotationItem | list[AnnotationItem],
        name: str = "Delete Annotation",
    ) -> None:
        self.document = document
        self.items: list[AnnotationItem] = [items] if hasattr(items, "item_id") else list(items)
        self.name = name
        self._saved_entries: list[tuple[int, AnnotationItem, bool]] = []

    def execute(self) -> None:
        self._saved_entries.clear()
        for it in self.items:
            idx = self.document.index_of(it)
            if idx >= 0:
                self._saved_entries.append((idx, it, it.is_selected))

        self._saved_entries.sort(key=lambda entry: entry[0])

        for _, it, _ in self._saved_entries:
            self.document.remove_item(it)

    def undo(self) -> None:
        for idx, it, was_selected in self._saved_entries:
            self.document.add_item(it, index=idx)
            if was_selected:
                self.document.select_item(it, exclusive=False)

    def redo(self) -> None:
        for _, it, _ in self._saved_entries:
            if it.is_selected:
                self.document.select_item(None, exclusive=True)
            self.document.remove_item(it)


class CompoundCommand(Command):
    def __init__(
        self,
        commands: list[Command] | None = None,
        name: str = "Multiple Actions",
    ) -> None:
        self.commands: list[Command] = list(commands) if commands else []
        self.name = name

    def add(self, command: Command) -> None:
        self.commands.append(command)

    def execute(self) -> None:
        for cmd in self.commands:
            cmd.execute()

    def undo(self) -> None:
        for cmd in reversed(self.commands):
            cmd.undo()

    def redo(self) -> None:
        for cmd in self.commands:
            cmd.redo()

    def __len__(self) -> int:
        return len(self.commands)


class MoveCommand(Command):
    def __init__(
        self,
        items: AnnotationItem | list[AnnotationItem],
        dx: float,
        dy: float,
        document: AnnotationDocument | None = None,
        name: str = "Move Annotation",
    ) -> None:
        self.items: list[AnnotationItem] = [items] if hasattr(items, "item_id") else list(items)
        self.dx = float(dx)
        self.dy = float(dy)
        self.document = document
        self.name = name

    def execute(self) -> None:
        for it in self.items:
            it.move_by(self.dx, self.dy)
        if self.document is not None:
            self.document.mark_dirty()

    def undo(self) -> None:
        for it in self.items:
            it.move_by(-self.dx, -self.dy)
        if self.document is not None:
            self.document.mark_dirty()

    def redo(self) -> None:
        self.execute()

    def merge_with(self, other: Command) -> bool:
        if isinstance(other, MoveCommand) and self.items == other.items and self.document is other.document:
            self.dx += other.dx
            self.dy += other.dy
            return True
        return False


class ResizeCommand(Command):
    def __init__(
        self,
        item: AnnotationItem,
        old_geometry: Any,
        new_geometry: Any,
        document: AnnotationDocument | None = None,
        name: str = "Resize Annotation",
    ) -> None:
        self.item = item
        self.old_geometry = old_geometry
        self.new_geometry = new_geometry
        self.document = document
        self.name = name

    def _apply(self, geometry: Any) -> None:
        if callable(geometry):
            geometry(self.item)
        elif hasattr(self.item, "set_geometry") and callable(self.item.set_geometry):
            handled = self.item.set_geometry(geometry)
            if not handled:
                if isinstance(geometry, dict):
                    for k, v in geometry.items():
                        if hasattr(self.item, k):
                            setattr(self.item, k, v)
                elif isinstance(geometry, (tuple, list)):
                    if len(geometry) == 4 and all(hasattr(self.item, attr) for attr in ("x", "y", "w", "h")):
                        self.item.x, self.item.y, self.item.w, self.item.h = geometry
                    elif hasattr(self.item, "set_bounds") and callable(self.item.set_bounds):
                        self.item.set_bounds(*geometry)
        elif isinstance(geometry, dict):
            for k, v in geometry.items():
                if hasattr(self.item, k):
                    setattr(self.item, k, v)
        elif isinstance(geometry, (tuple, list)):
            if len(geometry) == 4 and all(hasattr(self.item, attr) for attr in ("x", "y", "w", "h")):
                self.item.x, self.item.y, self.item.w, self.item.h = geometry
            elif hasattr(self.item, "set_bounds") and callable(self.item.set_bounds):
                self.item.set_bounds(*geometry)
        if self.document is not None:
            self.document.mark_dirty()

    def execute(self) -> None:
        self._apply(self.new_geometry)

    def undo(self) -> None:
        self._apply(self.old_geometry)

    def redo(self) -> None:
        self._apply(self.new_geometry)

    def merge_with(self, other: Command) -> bool:
        if isinstance(other, ResizeCommand) and self.item is other.item and self.document is other.document:
            self.new_geometry = other.new_geometry
            return True
        return False


class RestyleCommand(Command):
    def __init__(
        self,
        items: AnnotationItem | list[AnnotationItem],
        stroke_color: tuple[float, float, float, float] | None = None,
        stroke_width: float | None = None,
        fill_color: tuple[float, float, float, float] | None = None,
        clear_fill: bool = False,
        document: AnnotationDocument | None = None,
        name: str = "Change Style",
    ) -> None:
        self.items: list[AnnotationItem] = [items] if hasattr(items, "item_id") else list(items)
        self.stroke_color = stroke_color
        self.stroke_width = stroke_width
        self.fill_color = fill_color
        self.clear_fill = clear_fill
        self.document = document
        self.name = name
        self._previous_styles: list[
            tuple[AnnotationItem, tuple[float, float, float, float], float, tuple[float, float, float, float] | None]
        ] = [
            (it, it.stroke_color, it.stroke_width, it.fill_color)
            for it in self.items
        ]

    def execute(self) -> None:
        for it in self.items:
            it.apply_style(
                stroke_color=self.stroke_color,
                stroke_width=self.stroke_width,
                fill_color=self.fill_color,
                clear_fill=self.clear_fill,
            )
        if self.document is not None:
            self.document.mark_dirty()

    def undo(self) -> None:
        for it, stroke_color, stroke_width, fill_color in self._previous_styles:
            it.stroke_color = stroke_color
            it.stroke_width = stroke_width
            it.fill_color = fill_color
        if self.document is not None:
            self.document.mark_dirty()

    def redo(self) -> None:
        self.execute()


class UndoManager:
    def __init__(self, max_history: int = 100) -> None:
        self._max_history: int = max(1, int(max_history))
        self._undo_stack: list[Command] = []
        self._redo_stack: list[Command] = []
        self._callbacks: list[Callable[[], None]] = []

    @property
    def max_history(self) -> int:
        return self._max_history

    @property
    def can_undo(self) -> bool:
        return len(self._undo_stack) > 0

    @property
    def can_redo(self) -> bool:
        return len(self._redo_stack) > 0

    @property
    def undo_count(self) -> int:
        return len(self._undo_stack)

    @property
    def redo_count(self) -> int:
        return len(self._redo_stack)

    @property
    def undo_command_name(self) -> str | None:
        return self._undo_stack[-1].name if self._undo_stack else None

    @property
    def redo_command_name(self) -> str | None:
        return self._redo_stack[-1].name if self._redo_stack else None

    def push(self, command: Command, execute: bool = False) -> None:
        if execute:
            command.execute()

        if self._undo_stack and self._undo_stack[-1].merge_with(command):
            pass
        else:
            self._undo_stack.append(command)
            if len(self._undo_stack) > self._max_history:
                self._undo_stack.pop(0)

        self._redo_stack.clear()
        self._notify()

    def undo(self) -> bool:
        if not self._undo_stack:
            return False
        cmd = self._undo_stack.pop()
        cmd.undo()
        self._redo_stack.append(cmd)
        self._notify()
        return True

    def redo(self) -> bool:
        if not self._redo_stack:
            return False
        cmd = self._redo_stack.pop()
        cmd.redo()
        self._undo_stack.append(cmd)
        self._notify()
        return True

    def clear(self) -> None:
        if self._undo_stack or self._redo_stack:
            self._undo_stack.clear()
            self._redo_stack.clear()
            self._notify()

    def add_change_callback(self, cb: Callable[[], None]) -> None:
        if cb not in self._callbacks:
            self._callbacks.append(cb)

    def remove_change_callback(self, cb: Callable[[], None]) -> None:
        if cb in self._callbacks:
            self._callbacks.remove(cb)

    def _notify(self) -> None:
        for cb in self._callbacks:
            cb()


