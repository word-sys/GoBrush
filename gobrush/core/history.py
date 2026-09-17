from __future__ import annotations
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

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
