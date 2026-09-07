from __future__ import annotations
import cairo


def create_checkerboard_pattern(
    tile_size: int = 10,
    scale_factor: int = 1,
    light_color: tuple[float, float, float, float] = (0.88, 0.88, 0.90, 1.0),
    dark_color: tuple[float, float, float, float] = (0.76, 0.76, 0.80, 1.0),
) -> cairo.SurfacePattern:
    scale = max(1, scale_factor)
    actual_tile = tile_size * scale
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, actual_tile * 2, actual_tile * 2)
    surface.set_device_scale(scale, scale)

    cr = cairo.Context(surface)

    # Light squares (top-left and bottom-right)
    cr.set_source_rgba(*light_color)
    cr.rectangle(0, 0, tile_size, tile_size)
    cr.rectangle(tile_size, tile_size, tile_size, tile_size)
    cr.fill()

    # Dark squares (top-right and bottom-left)
    cr.set_source_rgba(*dark_color)
    cr.rectangle(tile_size, 0, tile_size, tile_size)
    cr.rectangle(0, tile_size, tile_size, tile_size)
    cr.fill()

    pattern = cairo.SurfacePattern(surface)
    pattern.set_extend(cairo.EXTEND_REPEAT)
    return pattern
