from __future__ import annotations
from typing import Any, Callable
import cairo

from gobrush.items.base import AnnotationItem


class AnnotationDocument:
    """Document model managing the base image and layered vector annotations."""

    def __init__(
        self,
        surface: cairo.ImageSurface | None = None,
        width: int | None = None,
        height: int | None = None,
        has_alpha: bool | None = None,
        file_path: str | None = None,
        file_format: str = "png",
    ) -> None:
        self._background_surface: cairo.ImageSurface | None = None
        self._width: int = 0
        self._height: int = 0
        self._has_alpha: bool = True
        self._file_path: str | None = file_path
        self._file_format: str = file_format
        self._items: list[AnnotationItem] = []
        self._is_dirty: bool = False
        self._change_callbacks: list[Callable[[], None]] = []

        if surface is not None or width is not None or height is not None:
            self.set_background(
                surface,
                width=width,
                height=height,
                has_alpha=has_alpha,
                file_path=file_path,
                file_format=file_format,
            )

    @property
    def background_surface(self) -> cairo.ImageSurface | None:
        return self._background_surface

    @property
    def width(self) -> int:
        return self._width

    @property
    def height(self) -> int:
        return self._height

    @property
    def has_alpha(self) -> bool:
        return self._has_alpha

    @property
    def has_image(self) -> bool:
        return self._background_surface is not None and self._width > 0 and self._height > 0

    @property
    def file_path(self) -> str | None:
        return self._file_path

    @file_path.setter
    def file_path(self, path: str | None) -> None:
        self._file_path = path

    @property
    def file_format(self) -> str:
        return self._file_format

    @file_format.setter
    def file_format(self, fmt: str) -> None:
        self._file_format = fmt

    @property
    def items(self) -> list[AnnotationItem]:
        return list(self._items)

    @property
    def item_count(self) -> int:
        return len(self._items)

    @property
    def is_dirty(self) -> bool:
        return self._is_dirty

    def mark_clean(self) -> None:
        self._is_dirty = False

    def mark_dirty(self) -> None:
        self._is_dirty = True
        self.notify_changed()

    def set_background(
        self,
        surface: cairo.ImageSurface | None,
        width: int | None = None,
        height: int | None = None,
        has_alpha: bool | None = None,
        file_path: str | None = None,
        file_format: str | None = None,
    ) -> None:
        self._background_surface = surface
        if surface is not None:
            self._width = width if width is not None else surface.get_width()
            self._height = height if height is not None else surface.get_height()
            if has_alpha is not None:
                self._has_alpha = bool(has_alpha)
            else:
                self._has_alpha = surface.get_format() == cairo.FORMAT_ARGB32
        else:
            self._width = width if width is not None else 0
            self._height = height if height is not None else 0
            self._has_alpha = bool(has_alpha) if has_alpha is not None else True

        if file_path is not None:
            self._file_path = file_path
        if file_format is not None:
            self._file_format = file_format

        self.notify_changed()

    def clear(self) -> None:
        self.set_background(None)
        self.clear_items()
        self._file_path = None
        self._file_format = "png"
        self._is_dirty = False

    # -------------------------------------------------------------------------
    # Layer / Item Management
    # -------------------------------------------------------------------------

    def add_item(self, item: AnnotationItem, index: int | None = None) -> int:
        """Add an annotation item to the document, returning its new z-index."""
        if index is None or index >= len(self._items):
            self._items.append(item)
            new_idx = len(self._items) - 1
        else:
            insert_idx = max(0, index)
            self._items.insert(insert_idx, item)
            new_idx = insert_idx

        self.mark_dirty()
        return new_idx

    def remove_item(self, item: AnnotationItem) -> bool:
        """Remove item from document. Returns True if removed."""
        if item in self._items:
            self._items.remove(item)
            self.mark_dirty()
            return True
        return False

    def remove_item_at(self, index: int) -> AnnotationItem | None:
        """Remove item at index."""
        if 0 <= index < len(self._items):
            item = self._items.pop(index)
            self.mark_dirty()
            return item
        return None

    def clear_items(self) -> None:
        """Remove all annotation items."""
        if self._items:
            self._items.clear()
            self.mark_dirty()

    def get_item_by_id(self, item_id: str) -> AnnotationItem | None:
        """Find item by unique UUID string."""
        for it in self._items:
            if it.item_id == item_id:
                return it
        return None

    def index_of(self, item: AnnotationItem) -> int:
        """Return z-index of item, or -1 if not in document."""
        try:
            return self._items.index(item)
        except ValueError:
            return -1

    def bring_to_front(self, item: AnnotationItem) -> bool:
        """Move item to the very top (end of list)."""
        idx = self.index_of(item)
        if idx != -1 and idx < len(self._items) - 1:
            self._items.pop(idx)
            self._items.append(item)
            self.mark_dirty()
            return True
        return False

    def send_to_back(self, item: AnnotationItem) -> bool:
        """Move item to the very bottom (start of list)."""
        idx = self.index_of(item)
        if idx > 0:
            self._items.pop(idx)
            self._items.insert(0, item)
            self.mark_dirty()
            return True
        return False

    def bring_forward(self, item: AnnotationItem) -> bool:
        """Move item one step up in z-order."""
        idx = self.index_of(item)
        if idx != -1 and idx < len(self._items) - 1:
            self._items[idx], self._items[idx + 1] = self._items[idx + 1], self._items[idx]
            self.mark_dirty()
            return True
        return False

    def send_backward(self, item: AnnotationItem) -> bool:
        """Move item one step down in z-order."""
        idx = self.index_of(item)
        if idx > 0:
            self._items[idx], self._items[idx - 1] = self._items[idx - 1], self._items[idx]
            self.mark_dirty()
            return True
        return False

    # -------------------------------------------------------------------------
    # Hit Testing & Selection
    # -------------------------------------------------------------------------

    def hit_test(self, x: float, y: float, tolerance: float = 6.0) -> AnnotationItem | None:
        """Return topmost item intersecting point (x, y), or None."""
        for it in reversed(self._items):
            if it.is_visible and it.hit_test(x, y, tolerance):
                return it
        return None

    def hit_test_all(self, x: float, y: float, tolerance: float = 6.0) -> list[AnnotationItem]:
        """Return all items intersecting point (x, y) from top to bottom."""
        return [it for it in reversed(self._items) if it.is_visible and it.hit_test(x, y, tolerance)]

    def select_item(self, item: AnnotationItem | None, exclusive: bool = True) -> None:
        """Select an item. If exclusive, deselects all other items."""
        changed = False
        if exclusive:
            for it in self._items:
                if it is not item and it.is_selected:
                    it.is_selected = False
                    changed = True

        if item is not None and not item.is_selected:
            item.is_selected = True
            changed = True

        if changed:
            self.notify_changed()

    def deselect_all(self) -> None:
        """Deselect all items."""
        changed = False
        for it in self._items:
            if it.is_selected:
                it.is_selected = False
                changed = True
        if changed:
            self.notify_changed()

    @property
    def selected_items(self) -> list[AnnotationItem]:
        """Return list of all currently selected items."""
        return [it for it in self._items if it.is_selected]

    @property
    def selected_item(self) -> AnnotationItem | None:
        """Return the primary (first) selected item, or None."""
        items = self.selected_items
        return items[0] if items else None

    # -------------------------------------------------------------------------
    # Rendering
    # -------------------------------------------------------------------------

    def draw(self, cr: cairo.Context, scale: float = 1.0, draw_selection_handles: bool = True) -> None:
        """Draw all visible annotation items onto the Cairo context in image coordinates."""
        for it in self._items:
            if it.is_visible:
                cr.save()
                it.draw(cr)
                cr.restore()

        if draw_selection_handles:
            for it in self._items:
                if it.is_visible and it.is_selected:
                    cr.save()
                    it.draw_selection(cr, scale)
                    cr.restore()

    def render_to_surface(self, include_background: bool = True) -> cairo.ImageSurface:
        """Render base image + all annotations onto an offscreen ARGB32 surface."""
        w = max(1, self._width)
        h = max(1, self._height)
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
        cr = cairo.Context(surf)

        if include_background and self._background_surface is not None:
            cr.set_source_surface(self._background_surface, 0, 0)
            cr.paint()

        self.draw(cr, scale=1.0, draw_selection_handles=False)
        return surf

    # -------------------------------------------------------------------------
    # Change Observers
    # -------------------------------------------------------------------------

    def add_change_callback(self, cb: Callable[[], None]) -> None:
        if cb not in self._change_callbacks:
            self._change_callbacks.append(cb)

    def remove_change_callback(self, cb: Callable[[], None]) -> None:
        if cb in self._change_callbacks:
            self._change_callbacks.remove(cb)

    def notify_changed(self) -> None:
        for cb in self._change_callbacks:
            cb()

    # -------------------------------------------------------------------------
    # Serialization
    # -------------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialize document metadata and annotation items to dict."""
        return {
            "width": self._width,
            "height": self._height,
            "has_alpha": self._has_alpha,
            "file_path": self._file_path,
            "file_format": self._file_format,
            "items": [it.to_dict() for it in self._items],
        }
