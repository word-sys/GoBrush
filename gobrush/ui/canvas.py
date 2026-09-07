from __future__ import annotations
from typing import Callable
import cairo
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk


class Canvas(Gtk.DrawingArea):
    def __init__(self) -> None:
        super().__init__()
        self.set_hexpand(True)
        self.set_vexpand(True)
        self.set_focusable(True)

        self._background_color: tuple[float, float, float, float] = (0.12, 0.12, 0.14, 1.0)
        self._image_surface: cairo.ImageSurface | None = None
        self._image_width: int = 0
        self._image_height: int = 0
        self._draw_hooks: list[Callable[[cairo.Context, int, int], None]] = []

        self.set_draw_func(self._on_draw)

    @property
    def background_color(self) -> tuple[float, float, float, float]:
        return self._background_color

    @background_color.setter
    def background_color(self, color: tuple[float, float, float, float]) -> None:
        self._background_color = color
        self.queue_draw()

    @property
    def image_surface(self) -> cairo.ImageSurface | None:
        return self._image_surface

    @property
    def image_width(self) -> int:
        return self._image_width

    @property
    def image_height(self) -> int:
        return self._image_height

    @property
    def has_image(self) -> bool:
        return self._image_surface is not None

    def set_image_surface(
        self,
        surface: cairo.ImageSurface | None,
        width: int | None = None,
        height: int | None = None,
    ) -> None:
        self._image_surface = surface
        if surface is not None:
            self._image_width = width if width is not None else surface.get_width()
            self._image_height = height if height is not None else surface.get_height()
        else:
            self._image_width = 0
            self._image_height = 0
        self.queue_draw()

    def clear(self) -> None:
        self.set_image_surface(None)

    def add_draw_hook(self, hook: Callable[[cairo.Context, int, int], None]) -> None:
        if hook not in self._draw_hooks:
            self._draw_hooks.append(hook)
            self.queue_draw()

    def remove_draw_hook(self, hook: Callable[[cairo.Context, int, int], None]) -> None:
        if hook in self._draw_hooks:
            self._draw_hooks.remove(hook)
            self.queue_draw()

    def _on_draw(
        self, area: Gtk.DrawingArea, cr: cairo.Context, width: int, height: int
    ) -> None:
        # Clear viewport background
        cr.save()
        cr.set_source_rgba(*self._background_color)
        cr.paint()
        cr.restore()

        # Render base image surface if loaded
        if self._image_surface is not None:
            cr.save()
            cr.set_source_surface(self._image_surface, 0, 0)
            cr.paint()
            cr.restore()

        # Invoke attached drawing hooks (annotations, overlays, tools)
        for hook in self._draw_hooks:
            cr.save()
            hook(cr, width, height)
            cr.restore()
