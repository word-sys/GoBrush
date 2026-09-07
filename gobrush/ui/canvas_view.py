from __future__ import annotations
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from gobrush.ui.canvas import Canvas
from gobrush.ui.status_bar import CanvasStatusBar


class CanvasView(Gtk.Overlay):
    def __init__(self, canvas: Canvas | None = None) -> None:
        super().__init__()
        self.set_hexpand(True)
        self.set_vexpand(True)

        self.canvas = canvas or Canvas()
        self.set_child(self.canvas)

        self.status_bar = CanvasStatusBar()
        self.add_overlay(self.status_bar)

        # Track cursor movement for pixel coordinates readout
        self._motion_ctrl = Gtk.EventControllerMotion()
        self._motion_ctrl.connect("motion", self._on_pointer_motion)
        self._motion_ctrl.connect("leave", self._on_pointer_leave)
        self.canvas.add_controller(self._motion_ctrl)

        # Subscribe to canvas viewport updates
        self.canvas.add_view_changed_callback(self._on_view_changed)
        self._sync_status()

    def _on_pointer_motion(
        self, controller: Gtk.EventControllerMotion, x: float, y: float
    ) -> None:
        if not self.canvas.has_image:
            self.status_bar.set_cursor_position(None, None)
            return

        ix, iy = self.canvas.screen_to_image(x, y)
        if 0 <= ix < self.canvas.image_width and 0 <= iy < self.canvas.image_height:
            self.status_bar.set_cursor_position(int(ix), int(iy))
        else:
            self.status_bar.set_cursor_position(None, None)

    def _on_pointer_leave(self, controller: Gtk.EventControllerMotion) -> None:
        self.status_bar.set_cursor_position(None, None)

    def _on_view_changed(self) -> None:
        self._sync_status()

    def _sync_status(self) -> None:
        self.status_bar.set_zoom(self.canvas.zoom)
        self.status_bar.set_dimensions(self.canvas.image_width, self.canvas.image_height)
