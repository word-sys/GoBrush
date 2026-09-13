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
        self._pending_fit: bool = True

        self.transform = ViewportTransform()
        self._image_draw_hooks: list[Callable[[cairo.Context], None]] = []
        self._draw_hooks: list[Callable[[cairo.Context, int, int], None]] = []

        self._show_checkerboard: bool = True
        self._checkerboard_tile_size: int = 10
        self._checkerboard_pattern: cairo.SurfacePattern | None = None
        self._cached_scale_factor: int = 1
        self._crisp_zoom: bool = True
        self._image_has_alpha: bool = True

        self._view_changed_callbacks: list[Callable[[], None]] = []
        self._anim_tick_id: int | None = None

        self._is_panning: bool = False
        self._is_space_panning: bool = False
        self._space_pressed: bool = False
        self._drag_start_pan: tuple[float, float] = (0.0, 0.0)
        self._tool_cursor_name: str | None = None
        self._drag_to_pan: bool = True

        self._scroll_to_zoom: bool = True
        self._last_scroll_was_pan: bool = True

        self._is_pinching: bool = False
        self._last_gesture_scale: float = 1.0

        self._cursor_pos: tuple[float, float] | None = None
        self._motion_controller = Gtk.EventControllerMotion()
        self._motion_controller.connect("motion", self._on_motion_internal)
        self._motion_controller.connect("leave", self._on_leave_internal)
        self.add_controller(self._motion_controller)

        self._scroll_controller = Gtk.EventControllerScroll.new(
            Gtk.EventControllerScrollFlags.BOTH_AXES | Gtk.EventControllerScrollFlags.KINETIC
        )
        self._scroll_controller.connect("scroll", self._on_scroll)
        self._scroll_controller.connect("decelerate", self._on_scroll_decelerate)
        self.add_controller(self._scroll_controller)

        self._zoom_gesture = Gtk.GestureZoom()
        self._zoom_gesture.connect("begin", self._on_zoom_gesture_begin)
        self._zoom_gesture.connect("scale-changed", self._on_zoom_gesture_scale_changed)
        self._zoom_gesture.connect("end", self._on_zoom_gesture_end)
        self._zoom_gesture.connect("cancel", self._on_zoom_gesture_cancel)
        self.add_controller(self._zoom_gesture)

        self._middle_drag = Gtk.GestureDrag()
        self._middle_drag.set_button(Gdk.BUTTON_MIDDLE)
        self._middle_drag.connect("drag-begin", self._on_middle_drag_begin)
        self._middle_drag.connect("drag-update", self._on_middle_drag_update)
        self._middle_drag.connect("drag-end", self._on_middle_drag_end)
        self._middle_drag.connect("cancel", self._on_middle_drag_cancel)
        self.add_controller(self._middle_drag)

        self._primary_drag = Gtk.GestureDrag()
        self._primary_drag.set_button(Gdk.BUTTON_PRIMARY)
        self._primary_drag.connect("drag-begin", self._on_primary_drag_begin)
        self._primary_drag.connect("drag-update", self._on_primary_drag_update)
        self._primary_drag.connect("drag-end", self._on_primary_drag_end)
        self._primary_drag.connect("cancel", self._on_primary_drag_cancel)
        self.add_controller(self._primary_drag)

        self._key_controller = Gtk.EventControllerKey()
        self._key_controller.connect("key-pressed", self._on_key_pressed)
        self._key_controller.connect("key-released", self._on_key_released)
        self.add_controller(self._key_controller)

        self._focus_controller = Gtk.EventControllerFocus()
        self._focus_controller.connect("leave", self._on_focus_leave)
        self.add_controller(self._focus_controller)

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
    def crisp_zoom(self) -> bool:
        return self._crisp_zoom

    @crisp_zoom.setter
    def crisp_zoom(self, enabled: bool) -> None:
        if self._crisp_zoom != enabled:
            self._crisp_zoom = bool(enabled)
            self.queue_draw()

    def get_active_filter(self) -> int:
        # Nearest-neighbor when magnified prevents bilinear interpolation blur
        if self._crisp_zoom and self.zoom >= 1.0:
            return cairo.FILTER_NEAREST
        return cairo.FILTER_GOOD

    @property
    def image_has_alpha(self) -> bool:
        return self._image_has_alpha

    @image_has_alpha.setter
    def image_has_alpha(self, has_alpha: bool) -> None:
        if self._image_has_alpha != has_alpha:
            self._image_has_alpha = bool(has_alpha)
            self.queue_draw()

    def get_visible_image_rect(
        self,
        viewport_width: int | None = None,
        viewport_height: int | None = None,
    ) -> tuple[float, float, float, float] | None:
        if not self.has_image or self._image_width <= 0 or self._image_height <= 0:
            return None

        vw = viewport_width if viewport_width is not None else self.viewport_width
        vh = viewport_height if viewport_height is not None else self.viewport_height
        if vw <= 0 or vh <= 0:
            return None

        sx0, sy0 = self.transform.screen_to_image(0.0, 0.0)
        sx1, sy1 = self.transform.screen_to_image(float(vw), float(vh))

        vx0 = max(0.0, sx0)
        vy0 = max(0.0, sy0)
        vx1 = min(float(self._image_width), sx1)
        vy1 = min(float(self._image_height), sy1)

        if vx1 <= vx0 or vy1 <= vy0:
            return None

        return vx0, vy0, vx1 - vx0, vy1 - vy0

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

    @property
    def is_panning(self) -> bool:
        return self._is_panning or self._is_space_panning

    @property
    def is_pinching(self) -> bool:
        return self._is_pinching

    @property
    def is_space_pressed(self) -> bool:
        return self._space_pressed

    @property
    def scroll_to_zoom(self) -> bool:
        return self._scroll_to_zoom

    @scroll_to_zoom.setter
    def scroll_to_zoom(self, enabled: bool) -> None:
        self._scroll_to_zoom = bool(enabled)

    @property
    def drag_to_pan(self) -> bool:
        return self._drag_to_pan

    @drag_to_pan.setter
    def drag_to_pan(self, enabled: bool) -> None:
        self._drag_to_pan = bool(enabled)

    @property
    def current_cursor_name(self) -> str | None:
        cursor = self.get_cursor()
        return cursor.get_name() if cursor else None

    @property
    def tool_cursor_name(self) -> str | None:
        return self._tool_cursor_name

    @tool_cursor_name.setter
    def tool_cursor_name(self, name: str | None) -> None:
        self._tool_cursor_name = name
        self._update_cursor()

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
        self._pending_fit = False
        self._cancel_animation()
        self.transform.set_zoom(zoom, pivot)
        self.queue_draw()
        self._notify_view_changed()

    def zoom_by(self, factor: float, pivot: tuple[float, float] | None = None) -> None:
        self._pending_fit = False
        self._cancel_animation()
        self.transform.zoom_by(factor, pivot)
        self.queue_draw()
        self._notify_view_changed()

    def set_pan(self, pan_x: float, pan_y: float) -> None:
        self._pending_fit = False
        self._cancel_animation()
        self.transform.set_pan(pan_x, pan_y)
        self.queue_draw()
        self._notify_view_changed()

    def pan_by(self, dx: float, dy: float) -> None:
        self._pending_fit = False
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

        vw = viewport_width if viewport_width is not None else self.viewport_width
        vh = viewport_height if viewport_height is not None else self.viewport_height
        if vw <= 0 or vh <= 0:
            self._pending_fit = True
            return

        self._pending_fit = False
        target_zoom, target_pan_x, target_pan_y = self.get_fit_target(
            viewport_width=vw,
            viewport_height=vh,
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

    def set_zoom_level(
        self,
        zoom: float,
        viewport_width: int | None = None,
        viewport_height: int | None = None,
        animate: bool = False,
    ) -> None:
        if not self.has_image:
            self.set_zoom(zoom)
            return

        self._pending_fit = False
        target_zoom = self.transform.clamp_zoom(zoom)
        vw = viewport_width if viewport_width is not None else self.viewport_width
        vh = viewport_height if viewport_height is not None else self.viewport_height

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

    def zoom_actual_size(
        self,
        viewport_width: int | None = None,
        viewport_height: int | None = None,
        animate: bool = True,
    ) -> None:
        self.set_zoom_level(
            1.0,
            viewport_width=viewport_width,
            viewport_height=viewport_height,
            animate=animate,
        )

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
        has_alpha: bool | None = None,
    ) -> None:
        self._cancel_animation()
        self._image_surface = surface
        if surface is not None:
            self._image_width = width if width is not None else surface.get_width()
            self._image_height = height if height is not None else surface.get_height()
            if has_alpha is not None:
                self._image_has_alpha = bool(has_alpha)
            else:
                self._image_has_alpha = surface.get_format() == cairo.FORMAT_ARGB32

            vw = self.viewport_width
            vh = self.viewport_height
            if vw > 0 and vh > 0:
                target_zoom, target_pan_x, target_pan_y = self.get_fit_target(vw, vh)
                self.transform.zoom = target_zoom
                self.transform.pan_x = target_pan_x
                self.transform.pan_y = target_pan_y
                self._pending_fit = False
            else:
                self._pending_fit = True
        else:
            self._image_width = 0
            self._image_height = 0
            self._image_has_alpha = True
            self.transform.reset()
            self._pending_fit = True
        self.queue_draw()
        self._notify_view_changed()

    def clear(self) -> None:
        self.set_image_surface(None)

    def get_flattened_surface(self) -> cairo.ImageSurface | None:
        if not self.has_image or self._image_width <= 0 or self._image_height <= 0:
            return None

        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, self._image_width, self._image_height)
        cr = cairo.Context(surface)

        if self._image_surface is not None:
            cr.set_source_surface(self._image_surface, 0, 0)
            cr.paint()

        for hook in self._image_draw_hooks:
            cr.save()
            hook(cr)
            cr.restore()

        return surface

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

        if self._pending_fit and self.has_image and width > 0 and height > 0:
            target_zoom, target_pan_x, target_pan_y = self.get_fit_target(width, height)
            self.transform.zoom = target_zoom
            self.transform.pan_x = target_pan_x
            self.transform.pan_y = target_pan_y
            self._pending_fit = False
            self._notify_view_changed()

        cr.save()
        cr.set_source_rgba(*self._background_color)
        cr.paint()
        cr.restore()

        cr.save()
        self.transform.apply_to_cairo(cr)
        if self._image_surface is not None:
            vis_rect = self.get_visible_image_rect(width, height)
            if vis_rect is not None:
                vx, vy, vw, vh = vis_rect

                if self._show_checkerboard and self._image_has_alpha:
                    cr.save()
                    pattern = self._get_checkerboard_pattern()
                    pat_matrix = cairo.Matrix()
                    pat_matrix.scale(self.zoom, self.zoom)
                    pattern.set_matrix(pat_matrix)
                    cr.set_source(pattern)
                    cr.rectangle(vx, vy, vw, vh)
                    cr.fill()
                    cr.restore()

                cr.save()
                cr.rectangle(vx, vy, vw, vh)
                cr.clip()

                cr.set_source_surface(self._image_surface, 0, 0)
                pattern = cr.get_source()
                if pattern is not None:
                    pattern.set_filter(self.get_active_filter())
                cr.paint()
                cr.restore()

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
        is_shift = bool(state & Gdk.ModifierType.SHIFT_MASK)

        should_zoom = is_ctrl or (self._scroll_to_zoom and not is_shift)
        if should_zoom:
            if dy != 0.0:
                self._last_scroll_was_pan = False
                pivot = self._cursor_pos or (self.viewport_width / 2.0, self.viewport_height / 2.0)
                factor = 1.15 ** (-dy)
                self.zoom_by(factor, pivot=pivot)
                return True
            elif dx != 0.0:
                self._last_scroll_was_pan = True
                self.pan_by(-dx * 20.0, 0.0)
                return True
            return False
        else:
            self._last_scroll_was_pan = True
            if is_shift and dx == 0.0 and dy != 0.0:
                self.pan_by(-dy * 20.0, 0.0)
            else:
                self.pan_by(-dx * 20.0, -dy * 20.0)
            return True

    def _on_scroll_decelerate(
        self, controller: Gtk.EventControllerScroll, vel_x: float, vel_y: float
    ) -> None:
        if not self._last_scroll_was_pan:
            return
        if abs(vel_x) < 10.0 and abs(vel_y) < 10.0:
            return
        # Smooth kinetic inertia coasting upon trackpad gesture release
        distance_factor = 0.2
        target_pan_x = self.pan_x - vel_x * distance_factor
        target_pan_y = self.pan_y - vel_y * distance_factor
        self.animate_to(self.zoom, target_pan_x, target_pan_y, duration_ms=250.0)

    def _on_zoom_gesture_begin(
        self, gesture: Gtk.GestureZoom, sequence: Gdk.EventSequence | None
    ) -> None:
        self.grab_focus()
        self._cancel_animation()
        self._is_pinching = True
        self._last_gesture_scale = 1.0

    def _on_zoom_gesture_scale_changed(
        self, gesture: Gtk.GestureZoom, scale: float
    ) -> None:
        if not self._is_pinching or scale <= 0:
            return

        seq = gesture.get_last_updated_sequence()
        ok = False
        cx, cy = 0.0, 0.0
        if gesture.get_last_event(seq) is not None:
            ok, cx, cy = gesture.get_bounding_box_center()

        if not ok:
            cx, cy = self._cursor_pos or (self.viewport_width / 2.0, self.viewport_height / 2.0)

        if self._last_gesture_scale > 0:
            factor = scale / self._last_gesture_scale
            self.zoom_by(factor, pivot=(cx, cy))
        self._last_gesture_scale = scale

    def _on_zoom_gesture_end(
        self, gesture: Gtk.GestureZoom, sequence: Gdk.EventSequence | None
    ) -> None:
        self._is_pinching = False
        self._last_gesture_scale = 1.0

    def _on_zoom_gesture_cancel(
        self, gesture: Gtk.GestureZoom, sequence: Gdk.EventSequence | None
    ) -> None:
        self._is_pinching = False
        self._last_gesture_scale = 1.0

    def handle_keyboard_zoom(self, keyval: int, state: Gdk.ModifierType) -> bool:
        is_ctrl = bool(state & Gdk.ModifierType.CONTROL_MASK)
        is_alt = bool(state & Gdk.ModifierType.ALT_MASK)
        if is_alt:
            return False

        if is_ctrl:
            if keyval in (Gdk.KEY_plus, Gdk.KEY_equal, Gdk.KEY_KP_Add):
                self.zoom_in()
                return True
            elif keyval in (Gdk.KEY_minus, Gdk.KEY_KP_Subtract, Gdk.KEY_underscore):
                self.zoom_out()
                return True
            elif keyval in (Gdk.KEY_0, Gdk.KEY_KP_0, Gdk.KEY_1, Gdk.KEY_KP_1):
                self.zoom_actual_size()
                return True
            elif keyval in (Gdk.KEY_9, Gdk.KEY_KP_9):
                self.zoom_fit()
                return True
        else:
            if keyval in (Gdk.KEY_plus, Gdk.KEY_equal, Gdk.KEY_KP_Add):
                self.zoom_in()
                return True
            elif keyval in (Gdk.KEY_minus, Gdk.KEY_KP_Subtract, Gdk.KEY_underscore):
                self.zoom_out()
                return True
            elif keyval in (Gdk.KEY_1, Gdk.KEY_KP_1):
                self.zoom_actual_size()
                return True
            elif keyval in (Gdk.KEY_f, Gdk.KEY_F):
                self.zoom_fit()
                return True

        return False

    def _update_cursor(self, name: str | None = None) -> None:
        if name is not None:
            self.set_cursor_from_name(name)
            return

        if self._is_panning or self._is_space_panning:
            self.set_cursor_from_name("grabbing")
        elif self._space_pressed:
            self.set_cursor_from_name("grab")
        elif self._tool_cursor_name:
            self.set_cursor_from_name(self._tool_cursor_name)
        else:
            self.set_cursor(None)

    def _on_middle_drag_begin(
        self, gesture: Gtk.GestureDrag, start_x: float, start_y: float
    ) -> None:
        self._pending_fit = False
        self.grab_focus()
        self._cancel_animation()
        self._is_panning = True
        self._drag_start_pan = (self.transform.pan_x, self.transform.pan_y)
        self._update_cursor("grabbing")

    def _on_middle_drag_update(
        self, gesture: Gtk.GestureDrag, offset_x: float, offset_y: float
    ) -> None:
        if not self._is_panning:
            return
        self.set_pan(self._drag_start_pan[0] + offset_x, self._drag_start_pan[1] + offset_y)

    def _on_middle_drag_end(
        self, gesture: Gtk.GestureDrag, offset_x: float, offset_y: float
    ) -> None:
        if self._is_panning:
            self.set_pan(self._drag_start_pan[0] + offset_x, self._drag_start_pan[1] + offset_y)
            self._is_panning = False
        self._update_cursor()

    def _on_middle_drag_cancel(
        self, gesture: Gtk.Gesture, sequence: Gdk.EventSequence | None
    ) -> None:
        self._is_panning = False
        self._update_cursor()

    def _on_primary_drag_begin(
        self, gesture: Gtk.GestureDrag, start_x: float, start_y: float
    ) -> None:
        self.grab_focus()
        if self._space_pressed or (self._drag_to_pan and self._tool_cursor_name is None):
            self._pending_fit = False
            self._cancel_animation()
            self._is_space_panning = True
            self._drag_start_pan = (self.transform.pan_x, self.transform.pan_y)
            self._update_cursor("grabbing")
        else:
            self._is_space_panning = False

    def _on_primary_drag_update(
        self, gesture: Gtk.GestureDrag, offset_x: float, offset_y: float
    ) -> None:
        if self._is_space_panning:
            self.set_pan(self._drag_start_pan[0] + offset_x, self._drag_start_pan[1] + offset_y)

    def _on_primary_drag_end(
        self, gesture: Gtk.GestureDrag, offset_x: float, offset_y: float
    ) -> None:
        if self._is_space_panning:
            self.set_pan(self._drag_start_pan[0] + offset_x, self._drag_start_pan[1] + offset_y)
            self._is_space_panning = False
        self._update_cursor()

    def _on_primary_drag_cancel(
        self, gesture: Gtk.Gesture, sequence: Gdk.EventSequence | None
    ) -> None:
        self._is_space_panning = False
        self._update_cursor()

    def _on_focus_leave(self, controller: Gtk.EventControllerFocus) -> None:
        if not (self._is_panning or self._is_space_panning):
            self._space_pressed = False
            self._update_cursor()

    def handle_key_pressed(self, keyval: int, state: Gdk.ModifierType) -> bool:
        if keyval == Gdk.KEY_space:
            if not self._space_pressed:
                self._space_pressed = True
                if not (self._is_panning or self._is_space_panning):
                    self._update_cursor("grab")
            return True

        # Viewport navigation via arrow keys (general navigation standard)
        step = 150.0 if bool(state & Gdk.ModifierType.SHIFT_MASK) else 50.0
        if keyval in (Gdk.KEY_Left, Gdk.KEY_KP_Left):
            self.pan_by(step, 0.0)
            return True
        elif keyval in (Gdk.KEY_Right, Gdk.KEY_KP_Right):
            self.pan_by(-step, 0.0)
            return True
        elif keyval in (Gdk.KEY_Up, Gdk.KEY_KP_Up):
            self.pan_by(0.0, step)
            return True
        elif keyval in (Gdk.KEY_Down, Gdk.KEY_KP_Down):
            self.pan_by(0.0, -step)
            return True

        return self.handle_keyboard_zoom(keyval, state)

    def handle_key_released(self, keyval: int, state: Gdk.ModifierType) -> bool:
        if keyval == Gdk.KEY_space:
            self._space_pressed = False
            if not (self._is_panning or self._is_space_panning):
                self._update_cursor()
            return True
        return False

    def _on_key_pressed(
        self, controller: Gtk.EventControllerKey, keyval: int, keycode: int, state: Gdk.ModifierType
    ) -> bool:
        return self.handle_key_pressed(keyval, state)

    def _on_key_released(
        self, controller: Gtk.EventControllerKey, keyval: int, keycode: int, state: Gdk.ModifierType
    ) -> None:
        self.handle_key_released(keyval, state)

