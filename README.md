# GoBrush

A lightweight, fast image annotation and screenshot markup utility for Linux desktops, built with Python, GTK4, Libadwaita, and Cairo.

## Features

- **Fast & Responsive**: Instant startup with hardware-accelerated Cairo rendering.
- **Fluid Navigation**:
  - Smooth mouse wheel zoom (10% to 3200%) centered on the cursor (`Ctrl + Scroll`).
  - Smooth keyboard zoom presets (100% 1:1, Fit to Window, Zoom In/Out).
  - Panning via middle mouse button or `Space + Left-click drag`.
- **Text-First & Intuitive UI**: Clear text actions in the header bar and tool panels for immediate readability.
- **Multi-Format Support**: Opens and edits PNG, JPEG, and WebP with full alpha transparency handling and checkerboard background.
- **Annotation Tools** (in active development):
  - Freehand pen and text-preserving highlighter.
  - Geometric shapes (rectangles, rounded boxes, circles, straight lines, single-headed arrows).
  - Privacy tools (mosaic pixelate, smooth blur, solid blackout/whiteout redaction).
  - Numbered step badges, reaction stamps, and non-destructive cropping.
- **Undo / Redo & Clipboard**: Full history stack and instant bidirectional clipboard support.

## Requirements

- **OS**: Linux (Ubuntu 22.04 LTS or newer / GNOME 42+)
- **Python**: 3.10 or newer
- **Libraries**: GTK 4.6+, Libadwaita 1.0+, Cairo, Pillow

### Install System Dependencies (Ubuntu / Debian)

```bash
sudo apt update
sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1 python3-pil
```

### Install Python Dependencies

```bash
pip install -e .
```

## Running GoBrush

Run directly from the source repository:

```bash
./bin/gobrush
```

or with Python:

```bash
python3 -m gobrush
```

Open an image directly from the command line:

```bash
./bin/gobrush /path/to/image.png
```

## Shortcuts

| Shortcut / Gesture | Action |
| --- | --- |
| `Ctrl + Mouse Scroll` | Zoom in / out centered on cursor |
| `Ctrl + +` / `Ctrl + =` | Zoom In |
| `Ctrl + -` | Zoom Out |
| `Ctrl + 0` | 1:1 Actual Size (100%) |
| `Ctrl + 9` | Fit Image to Window |
| `Middle Mouse Drag` | Pan viewport |
| `Space + Left Mouse Drag` | Pan viewport |
| `Two-Finger Pinch (Trackpad)` | Smooth zoom centered on pinch focus |
| `Two-Finger Scroll / Swipe (Trackpad)` | Smooth kinetic pan viewport |
| `Ctrl + O` | Open image file |
| `Ctrl + S` | Save image |
| `Ctrl + C` | Copy flattened image to clipboard |
| `Ctrl + V` | Paste image from clipboard |
| `Ctrl + Z` | Undo |
| `Ctrl + Shift + Z` / `Ctrl + Y` | Redo |

## Running Tests

The test suite runs with standard Python `unittest`:

```bash
python3 -m unittest discover tests/
```

## License

This project is licensed under the GNU General Public License v3.0. See the [LICENSE](LICENSE) file for details.
