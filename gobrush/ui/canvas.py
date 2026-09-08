from __future__ import annotations
from typing import Callable
import cairo
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gdk, GLib

from gobrush.core.transform import ViewportTransform
from gobrush.core.checkerboard import create_checkerboard_pattern


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

        # Transparency checkerboard & HiDPI support
        self._show_checkerboard: bool = True
        self._checkerboard_tile_size: int = 10
        self._checkerboard_pattern: cairo.SurfacePattern | None = None
        self._cached_scale_factor: int = 1

        self._view_changed_callbacks: list[Callable[[], None]] = []
        self._anim_tick_id: int | None = None

        # Cursor tracking and event controllers
        self._cursor_pos: tuple[float, float] | None = None
        self._motion_controller = Gtk.EventControllerMotion()
        self._motion_controller.connect("motion", self._on_motion_internal)
        self._motion_controller.connect("leave", self._on_leave_internal)
        self.add_controller(self._motion_controller)

        self._scroll_controller = Gtk.EventControllerScroll.new(
            Gtk.EventControllerScrollFlags.BOTH_AXES
        )
        self._scroll_controller.connect("scroll", self._on_scroll)
        self.add_controller(self._scroll_controller)

        self._key_controller = Gtk.EventControllerKey()
        self._key_controller.connect("key-pressed", self._on_key_pressed)
        self.add_controller(self._key_controller)

        self.connect("notify::scale-factor", self._on_scale_factor_changed)
        self.connect("unmap", lambda *_: self._cancel_animation())
        self.set_draw_func(self._on_draw)



    @property
    def background_color(self) -> tuple[float, float, float, float]:
        return self._background_color

    @background_color.setter
    def background_color(self, color: tuple[float, float, float, float]) -> None:
        self._background_color = color
        self.queue_draw()

    @property
    def show_checkerboard(self) -> bool:
        return self._show_checkerboard

    @show_checkerboard.setter
    def show_checkerboard(self, show: bool) -> None:
        self._show_checkerboard = show
        self.queue_draw()

    @property
    def scale_factor(self) -> int:
        factor = self.get_scale_factor()
        return max(1, factor)

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

    def add_view_changed_callback(self, cb: Callable[[], None]) -> None:
        if cb not in self._view_changed_callbacks:
            self._view_changed_callbacks.append(cb)

    def remove_view_changed_callback(self, cb: Callable[[], None]) -> None:
        if cb in self._view_changed_callbacks:
            self._view_changed_callbacks.remove(cb)

    def _notify_view_changed(self) -> None:
        for cb in self._view_changed_callbacks:
            cb()

    def _cancel_animation(self) -> None:
        if self._anim_tick_id is not None:
            self.remove_tick_callback(self._anim_tick_id)
            self._anim_tick_id = None

    def animate_to(
        self,
        target_zoom: float,
        target_pan_x: float,
        target_pan_y: float,
        duration_ms: float = 180.0,
    ) -> None:
        self._cancel_animation()
        if not self.get_mapped() or duration_ms <= 0:
            self.transform.zoom = target_zoom
            self.transform.pan_x = target_pan_x
            self.transform.pan_y = target_pan_y
            self.queue_draw()
            self._notify_view_changed()
            return

        start_zoom = self.transform.zoom
        start_pan_x = self.transform.pan_x
        start_pan_y = self.transform.pan_y
        start_time_us: int | None = None

        def _tick_callback(widget: Gtk.Widget, frame_clock: Gdk.FrameClock) -> bool:
            nonlocal start_time_us
            now_us = frame_clock.get_frame_time()
            if start_time_us is None:
                start_time_us = now_us
                return GLib.SOURCE_CONTINUE

            elapsed_ms = (now_us - start_time_us) / 1000.0
            progress = min(1.0, max(0.0, elapsed_ms / duration_ms))
            eased = 1.0 - (1.0 - progress) ** 3

            self.transform.zoom = start_zoom + (target_zoom - start_zoom) * eased
            self.transform.pan_x = start_pan_x + (target_pan_x - start_pan_x) * eased
            self.transform.pan_y = start_pan_y + (target_pan_y - start_pan_y) * eased

            self.queue_draw()
            self._notify_view_changed()

            if progress >= 1.0:
                self._anim_tick_id = None
                return GLib.SOURCE_REMOVE
            return GLib.SOURCE_CONTINUE

        self._anim_tick_id = self.add_tick_callback(_tick_callback)

    def set_zoom(self, zoom: float, pivot: tuple[float, float] | None = None) -> None:
        self._cancel_animation()
        self.transform.set_zoom(zoom, pivot)
        self.queue_draw()
        self._notify_view_changed()

    def zoom_by(self, factor: float, pivot: tuple[float, float] | None = None) -> None:
        self._cancel_animation()
        self.transform.zoom_by(factor, pivot)
        self.queue_draw()
        self._notify_view_changed()

    def set_pan(self, pan_x: float, pan_y: float) -> None:
        self._cancel_animation()
        self.transform.set_pan(pan_x, pan_y)
        self.queue_draw()
        self._notify_view_changed()

    def pan_by(self, dx: float, dy: float) -> None:
        self._cancel_animation()
        self.transform.pan_by(dx, dy)
        self.queue_draw()
        self._notify_view_changed()

    def screen_to_image(self, sx: float, sy: float) -> tuple[float, float]:
        return self.transform.screen_to_image(sx, sy)

    def image_to_screen(self, ix: float, iy: float) -> tuple[float, float]:
        return self.transform.image_to_screen(ix, iy)

    def get_fit_target(
        self,
        viewport_width: int | None = None,
        viewport_height: int | None = None,
        padding: float = 20.0,
        upscale: bool = False,
    ) -> tuple[float, float, float]:
        vw = viewport_width if viewport_width is not None else self.viewport_width
        vh = viewport_height if viewport_height is not None else self.viewport_height
        iw = self._image_width
        ih = self._image_height
        if iw <= 0 or ih <= 0 or vw <= 0 or vh <= 0:
            return 1.0, 0.0, 0.0

        avail_w = max(1.0, vw - 2 * padding)
        avail_h = max(1.0, vh - 2 * padding)
        scale = min(avail_w / iw, avail_h / ih)
        if not upscale:
            scale = min(1.0, scale)

        target_zoom = self.transform.clamp_zoom(scale)
        target_pan_x = (vw - iw * target_zoom) / 2.0
        target_pan_y = (vh - ih * target_zoom) / 2.0
        return target_zoom, target_pan_x, target_pan_y

    def zoom_fit(
        self,
        viewport_width: int | None = None,
        viewport_height: int | None = None,
        padding: float = 20.0,
        upscale: bool = False,
        animate: bool = True,
    ) -> None:
        if not self.has_image:
            self.reset_view()
            return

        target_zoom, target_pan_x, target_pan_y = self.get_fit_target(
            viewport_width=viewport_width,
            viewport_height=viewport_height,
            padding=padding,
            upscale=upscale,
        )
        if animate and self.get_mapped():
            self.animate_to(target_zoom, target_pan_x, target_pan_y)
        else:
            self._cancel_animation()
            self.transform.zoom = target_zoom
            self.transform.pan_x = target_pan_x
            self.transform.pan_y = target_pan_y
            self.queue_draw()
            self._notify_view_changed()

    def zoom_actual_size(
        self,
        viewport_width: int | None = None,
        viewport_height: int | None = None,
        animate: bool = True,
    ) -> None:
        if not self.has_image:
            self.set_zoom(1.0)
            return

        vw = viewport_width if viewport_width is not None else self.viewport_width
        vh = viewport_height if viewport_height is not None else self.viewport_height
        target_zoom = 1.0
        if vw > 0 and vh > 0:
            target_pan_x = (vw - self._image_width * target_zoom) / 2.0
            target_pan_y = (vh - self._image_height * target_zoom) / 2.0
        else:
            target_pan_x = self.pan_x
            target_pan_y = self.pan_y

        if animate and self.get_mapped():
            self.animate_to(target_zoom, target_pan_x, target_pan_y)
        else:
            self._cancel_animation()
            self.transform.zoom = target_zoom
            self.transform.pan_x = target_pan_x
            self.transform.pan_y = target_pan_y
            self.queue_draw()
            self._notify_view_changed()

    def zoom_in(self, factor: float = 1.25, pivot: tuple[float, float] | None = None) -> None:
        if pivot is None:
            pivot = self._cursor_pos or (self.viewport_width / 2.0, self.viewport_height / 2.0)
        self.zoom_by(factor, pivot=pivot)

    def zoom_out(self, factor: float = 1.25, pivot: tuple[float, float] | None = None) -> None:
        if pivot is None:
            pivot = self._cursor_pos or (self.viewport_width / 2.0, self.viewport_height / 2.0)
        self.zoom_by(1.0 / factor, pivot=pivot)

    def fit_to_viewport(
        self,
        viewport_width: int | None = None,
        viewport_height: int | None = None,
        padding: float = 20.0,
        upscale: bool = False,
    ) -> None:
        self.zoom_fit(
            viewport_width=viewport_width,
            viewport_height=viewport_height,
            padding=padding,
            upscale=upscale,
            animate=False,
        )

    def center_image(
        self,
        viewport_width: int | None = None,
        viewport_height: int | None = None,
    ) -> None:
        self._cancel_animation()
        vw = viewport_width if viewport_width is not None else self.viewport_width
        vh = viewport_height if viewport_height is not None else self.viewport_height
        self.transform.center_image(vw, vh, self._image_width, self._image_height)
        self.queue_draw()
        self._notify_view_changed()

    def reset_view(self) -> None:
        self._cancel_animation()
        self.transform.reset(
            self.viewport_width, self.viewport_height, self._image_width, self._image_height
        )
        self.queue_draw()
        self._notify_view_changed()

    def set_image_surface(
        self,
        surface: cairo.ImageSurface | None,
        width: int | None = None,
        height: int | None = None,
    ) -> None:
        self._cancel_animation()
        self._image_surface = surface
        if surface is not None:
            self._image_width = width if width is not None else surface.get_width()
            self._image_height = height if height is not None else surface.get_height()
        else:
            self._image_width = 0
            self._image_height = 0
            self.transform.reset()
        self.queue_draw()
        self._notify_view_changed()

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

    def _on_scale_factor_changed(self, *_) -> None:
        self._checkerboard_pattern = None
        self.queue_draw()

    def _get_checkerboard_pattern(self) -> cairo.SurfacePattern:
        scale = self.scale_factor
        if self._checkerboard_pattern is None or self._cached_scale_factor != scale:
            self._checkerboard_pattern = create_checkerboard_pattern(
                tile_size=self._checkerboard_tile_size,
                scale_factor=scale,
            )
            self._cached_scale_factor = scale
        return self._checkerboard_pattern

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
            # Render checkerboard behind transparent image pixels
            if self._show_checkerboard:
                cr.save()
                pattern = self._get_checkerboard_pattern()
                pat_matrix = cairo.Matrix()
                pat_matrix.scale(self.zoom, self.zoom)
                pattern.set_matrix(pat_matrix)
                cr.set_source(pattern)
                cr.rectangle(0, 0, self._image_width, self._image_height)
                cr.fill()
                cr.restore()

            # Render image surface
            cr.set_source_surface(self._image_surface, 0, 0)
            cr.paint()

            # Draw subtle image boundary outline
            cr.save()
            cr.set_line_width(1.0 / self.zoom)
            cr.set_source_rgba(0.0, 0.0, 0.0, 0.25)
            cr.rectangle(0, 0, self._image_width, self._image_height)
            cr.stroke()
            cr.restore()

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

    @property
    def cursor_pos(self) -> tuple[float, float] | None:
        return self._cursor_pos

    def _on_motion_internal(
        self, controller: Gtk.EventControllerMotion, x: float, y: float
    ) -> None:
        self._cursor_pos = (x, y)

    def _on_leave_internal(self, controller: Gtk.EventControllerMotion) -> None:
        self._cursor_pos = None

    def _on_scroll(
        self, controller: Gtk.EventControllerScroll, dx: float, dy: float
    ) -> bool:
        state = controller.get_current_event_state()
        is_ctrl = bool(state & Gdk.ModifierType.CONTROL_MASK)

        if is_ctrl:
            pivot = self._cursor_pos or (self.viewport_width / 2.0, self.viewport_height / 2.0)
            factor = 1.15 ** (-dy)
            self.zoom_by(factor, pivot=pivot)
            return True
        else:
            self.pan_by(-dx * 20.0, -dy * 20.0)
            return True

    def handle_keyboard_zoom(self, keyval: int, state: Gdk.ModifierType) -> bool:
        is_ctrl = bool(state & Gdk.ModifierType.CONTROL_MASK)
        is_alt = bool(state & Gdk.ModifierType.ALT_MASK)
        if not is_ctrl or is_alt:
            return False

        if keyval in (Gdk.KEY_plus, Gdk.KEY_equal, Gdk.KEY_KP_Add):
            self.zoom_in()
            return True
        elif keyval in (Gdk.KEY_minus, Gdk.KEY_KP_Subtract, Gdk.KEY_underscore):
            self.zoom_out()
            return True
        elif keyval in (Gdk.KEY_0, Gdk.KEY_KP_0):
            self.zoom_actual_size()
            return True
        elif keyval in (Gdk.KEY_9, Gdk.KEY_KP_9):
            self.zoom_fit()
            return True

        return False

    def _on_key_pressed(
        self, controller: Gtk.EventControllerKey, keyval: int, keycode: int, state: Gdk.ModifierType
    ) -> bool:
        return self.handle_keyboard_zoom(keyval, state)

