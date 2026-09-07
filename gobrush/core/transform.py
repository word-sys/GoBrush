from __future__ import annotations
import cairo


class ViewportTransform:
    def __init__(
        self,
        min_zoom: float = 0.1,
        max_zoom: float = 32.0,
    ) -> None:
        self.zoom: float = 1.0
        self.pan_x: float = 0.0
        self.pan_y: float = 0.0
        self.min_zoom: float = min_zoom
        self.max_zoom: float = max_zoom

    def clamp_zoom(self, z: float) -> float:
        return max(self.min_zoom, min(self.max_zoom, z))

    def set_zoom(self, z: float, pivot_screen: tuple[float, float] | None = None) -> None:
        new_zoom = self.clamp_zoom(z)
        if pivot_screen is not None:
            # Keep image point under screen pivot stationary during zoom
            ratio = new_zoom / self.zoom
            px, py = pivot_screen
            self.pan_x = px - (px - self.pan_x) * ratio
            self.pan_y = py - (py - self.pan_y) * ratio
        self.zoom = new_zoom

    def zoom_by(self, factor: float, pivot_screen: tuple[float, float] | None = None) -> None:
        self.set_zoom(self.zoom * factor, pivot_screen)

    def set_pan(self, pan_x: float, pan_y: float) -> None:
        self.pan_x = pan_x
        self.pan_y = pan_y

    def pan_by(self, dx: float, dy: float) -> None:
        self.pan_x += dx
        self.pan_y += dy

    def screen_to_image(self, sx: float, sy: float) -> tuple[float, float]:
        ix = (sx - self.pan_x) / self.zoom
        iy = (sy - self.pan_y) / self.zoom
        return ix, iy

    def image_to_screen(self, ix: float, iy: float) -> tuple[float, float]:
        sx = ix * self.zoom + self.pan_x
        sy = iy * self.zoom + self.pan_y
        return sx, sy

    def screen_to_image_dist(self, d: float) -> float:
        return d / self.zoom

    def image_to_screen_dist(self, d: float) -> float:
        return d * self.zoom

    def fit_to_viewport(
        self,
        viewport_width: float,
        viewport_height: float,
        image_width: float,
        image_height: float,
        padding: float = 20.0,
        upscale: bool = False,
    ) -> None:
        if image_width <= 0 or image_height <= 0 or viewport_width <= 0 or viewport_height <= 0:
            return

        avail_w = max(1.0, viewport_width - 2 * padding)
        avail_h = max(1.0, viewport_height - 2 * padding)
        scale = min(avail_w / image_width, avail_h / image_height)
        if not upscale:
            scale = min(1.0, scale)

        self.zoom = self.clamp_zoom(scale)
        # Center image within the viewport
        self.pan_x = (viewport_width - image_width * self.zoom) / 2.0
        self.pan_y = (viewport_height - image_height * self.zoom) / 2.0

    def center_image(
        self,
        viewport_width: float,
        viewport_height: float,
        image_width: float,
        image_height: float,
    ) -> None:
        self.pan_x = (viewport_width - image_width * self.zoom) / 2.0
        self.pan_y = (viewport_height - image_height * self.zoom) / 2.0

    def reset(
        self,
        viewport_width: float = 0.0,
        viewport_height: float = 0.0,
        image_width: float = 0.0,
        image_height: float = 0.0,
    ) -> None:
        self.zoom = 1.0
        if viewport_width > 0 and viewport_height > 0 and image_width > 0 and image_height > 0:
            self.center_image(viewport_width, viewport_height, image_width, image_height)
        else:
            self.pan_x = 0.0
            self.pan_y = 0.0

    def apply_to_cairo(self, cr: cairo.Context) -> None:
        cr.translate(self.pan_x, self.pan_y)
        cr.scale(self.zoom, self.zoom)

    def get_cairo_matrix(self) -> cairo.Matrix:
        matrix = cairo.Matrix()
        matrix.translate(self.pan_x, self.pan_y)
        matrix.scale(self.zoom, self.zoom)
        return matrix
