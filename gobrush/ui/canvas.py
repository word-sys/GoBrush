from __future__ import annotations
from typing import Callable
import cairo
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from gobrush.core.transform import ViewportTransform


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
        self._viewport_width: int = 0
        self._viewport_height: int = 0

        self.transform = ViewportTransform()
        self._image_draw_hooks: list[Callable[[cairo.Context], None]] = []
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
    def viewport_width(self) -> int:
        return self._viewport_width or self.get_width()

    @property
    def viewport_height(self) -> int:
        return self._viewport_height or self.get_height()

    @property
    def has_image(self) -> bool:
        return self._image_surface is not None

    @property
    def zoom(self) -> float:
        return self.transform.zoom

    @zoom.setter
    def zoom(self, value: float) -> None:
        self.set_zoom(value)

    @property
    def pan_x(self) -> float:
        return self.transform.pan_x

    @property
    def pan_y(self) -> float:
        return self.transform.pan_y

    def set_zoom(self, zoom: float, pivot: tuple[float, float] | None = None) -> None:
        self.transform.set_zoom(zoom, pivot)
        self.queue_draw()

    def zoom_by(self, factor: float, pivot: tuple[float, float] | None = None) -> None:
        self.transform.zoom_by(factor, pivot)
        self.queue_draw()

    def set_pan(self, pan_x: float, pan_y: float) -> None:
        self.transform.set_pan(pan_x, pan_y)
        self.queue_draw()

    def pan_by(self, dx: float, dy: float) -> None:
        self.transform.pan_by(dx, dy)
        self.queue_draw()

    def screen_to_image(self, sx: float, sy: float) -> tuple[float, float]:
        return self.transform.screen_to_image(sx, sy)

    def image_to_screen(self, ix: float, iy: float) -> tuple[float, float]:
        return self.transform.image_to_screen(ix, iy)

    def fit_to_viewport(
        self,
        viewport_width: int | None = None,
        viewport_height: int | None = None,
        padding: float = 20.0,
        upscale: bool = False,
    ) -> None:
        vw = viewport_width if viewport_width is not None else self.viewport_width
        vh = viewport_height if viewport_height is not None else self.viewport_height
        self.transform.fit_to_viewport(
            vw, vh, self._image_width, self._image_height, padding=padding, upscale=upscale
        )
        self.queue_draw()

    def center_image(
        self,
        viewport_width: int | None = None,
        viewport_height: int | None = None,
    ) -> None:
        vw = viewport_width if viewport_width is not None else self.viewport_width
        vh = viewport_height if viewport_height is not None else self.viewport_height
        self.transform.center_image(vw, vh, self._image_width, self._image_height)
        self.queue_draw()

    def reset_view(self) -> None:
        self.transform.reset(
            self.viewport_width, self.viewport_height, self._image_width, self._image_height
        )
        self.queue_draw()

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
            self.transform.reset()
        self.queue_draw()

    def clear(self) -> None:
        self.set_image_surface(None)

    def add_image_draw_hook(self, hook: Callable[[cairo.Context], None]) -> None:
        if hook not in self._image_draw_hooks:
            self._image_draw_hooks.append(hook)
            self.queue_draw()

    def remove_image_draw_hook(self, hook: Callable[[cairo.Context], None]) -> None:
        if hook in self._image_draw_hooks:
            self._image_draw_hooks.remove(hook)
            self.queue_draw()

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
        self._viewport_width = width
        self._viewport_height = height

        # Clear viewport background
        cr.save()
        cr.set_source_rgba(*self._background_color)
        cr.paint()
        cr.restore()

        # Render transformed image and image-space layers
        cr.save()
        self.transform.apply_to_cairo(cr)
        if self._image_surface is not None:
            cr.set_source_surface(self._image_surface, 0, 0)
            cr.paint()
        for hook in self._image_draw_hooks:
            cr.save()
            hook(cr)
            cr.restore()
        cr.restore()

        # Render screen-space overlays
        for hook in self._draw_hooks:
            cr.save()
            hook(cr, width, height)
            cr.restore()
