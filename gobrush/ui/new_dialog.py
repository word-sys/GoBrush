from __future__ import annotations
import math
from typing import Any, Callable
import cairo
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gdk, GLib

from gobrush.compat.color import pick_color_dialog, rgba_from_floats, rgba_to_cairo

UNIT_PIXELS = "Pixels (px)"
UNIT_MILLIMETERS = "Millimeters (mm)"
UNIT_INCHES = "Inches (in)"
UNITS = [UNIT_PIXELS, UNIT_MILLIMETERS, UNIT_INCHES]

BG_TRANSPARENT = "Transparent (Checkerboard)"
BG_WHITE = "Solid White"
BG_BLACK = "Solid Black"
BG_CUSTOM = "Custom Color..."
BACKGROUND_OPTIONS = [BG_TRANSPARENT, BG_WHITE, BG_BLACK, BG_CUSTOM]

DPI = 96.0  # Screen reference DPI for unit conversions

# Preset templates: name -> (width_px, height_px, default_unit)
PRESET_TEMPLATES: list[tuple[str, int, int, str]] = [
    ("1920 × 1080 (16:9 Full HD)", 1920, 1080, UNIT_PIXELS),
    ("1280 × 720 (16:9 HD)", 1280, 720, UNIT_PIXELS),
    ("3840 × 2160 (16:9 4K UHD)", 3840, 2160, UNIT_PIXELS),
    ("2560 × 1440 (16:9 2K QHD)", 2560, 1440, UNIT_PIXELS),
    ("1080 × 1080 (1:1 Square)", 1080, 1080, UNIT_PIXELS),
    ("1080 × 1920 (9:16 Story / Reel)", 1080, 1920, UNIT_PIXELS),
    ("1280 × 720 (YouTube Thumbnail)", 1280, 720, UNIT_PIXELS),
    ("1500 × 500 (Twitter / X Header)", 1500, 500, UNIT_PIXELS),
    ("A4 (210 × 297 mm)", 794, 1123, UNIT_MILLIMETERS),
    ("A5 (148 × 210 mm)", 559, 794, UNIT_MILLIMETERS),
    ("US Letter (8.5 × 11 in)", 816, 1056, UNIT_INCHES),
    ("From Clipboard", 0, 0, UNIT_PIXELS),
    ("Custom", 0, 0, UNIT_PIXELS),
]


def px_to_unit(px: float, unit: str) -> float:
    if unit == UNIT_MILLIMETERS:
        return px * 25.4 / DPI
    elif unit == UNIT_INCHES:
        return px / DPI
    return px


def unit_to_px(val: float, unit: str) -> int:
    if unit == UNIT_MILLIMETERS:
        px = val * DPI / 25.4
    elif unit == UNIT_INCHES:
        px = val * DPI
    else:
        px = val
    return max(1, int(round(px)))


class NewCanvasDialog(Adw.Window):
    """Modal dialog for creating a new picture / canvas with presets, custom dimensions, and background fill."""

    def __init__(
        self,
        parent: Gtk.Window | None = None,
        on_create: Callable[[cairo.ImageSurface, bool, int, int], None] | None = None,
    ) -> None:
        super().__init__(
            title="New Canvas",
            transient_for=parent,
            modal=True,
        )
        self.set_default_size(440, 520)
        self.set_resizable(False)

        self.on_create = on_create
        self._updating_fields = False

        # State in pixels
        self._width_px = 1920
        self._height_px = 1080
        self._current_unit = UNIT_PIXELS
        self._is_landscape = True
        self._bg_choice = BG_TRANSPARENT
        self._custom_color = rgba_from_floats(1.0, 1.0, 1.0, 1.0)

        # Detect clipboard dimensions if available
        self._clipboard_w: int | None = None
        self._clipboard_h: int | None = None
        self._probe_clipboard(parent)

        self._build_ui()
        self._sync_dimension_inputs()

    def _probe_clipboard(self, parent: Gtk.Window | None) -> None:
        try:
            display = parent.get_display() if parent else Gdk.Display.get_default()
            if display:
                cb = display.get_clipboard()
                tex = cb.get_texture() if hasattr(cb, "get_texture") else None
                if tex:
                    self._clipboard_w = tex.get_width()
                    self._clipboard_h = tex.get_height()
        except Exception:
            pass

    def _build_ui(self) -> None:
        # Header Bar - unified titlebar without outer window frame
        header = Adw.HeaderBar()
        header.set_show_end_title_buttons(True)
        header.set_show_start_title_buttons(False)

        title_widget = Adw.WindowTitle(title="New Canvas")
        header.set_title_widget(title_widget)

        self.btn_cancel = Gtk.Button(label="Cancel")
        self.btn_cancel.connect("clicked", lambda _: self.destroy())
        header.pack_start(self.btn_cancel)

        self.btn_create = Gtk.Button(label="Create")
        self.btn_create.add_css_class("suggested-action")
        self.btn_create.connect("clicked", self._on_create_clicked)
        header.pack_end(self.btn_create)

        root_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        root_box.append(header)

        # Content Box
        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        content_box.set_margin_start(16)
        content_box.set_margin_end(16)
        content_box.set_margin_top(16)
        content_box.set_margin_bottom(16)

        # ---------------------------------------------------------------------
        # Section 1: Page Setup
        # ---------------------------------------------------------------------
        sec1_lbl = Gtk.Label(label="Page Setup", xalign=0.0)
        sec1_lbl.add_css_class("heading")
        content_box.append(sec1_lbl)

        sec1_list = Gtk.ListBox()
        sec1_list.add_css_class("boxed-list")
        sec1_list.set_selection_mode(Gtk.SelectionMode.NONE)

        # Template Dropdown Row
        self.row_template = Adw.ActionRow(title="Template")
        template_strings: list[str] = []
        for label, _, _, _ in PRESET_TEMPLATES:
            if label == "From Clipboard" and self._clipboard_w and self._clipboard_h:
                label_display = f"From Clipboard ({self._clipboard_w} × {self._clipboard_h} px)"
            else:
                label_display = label
            template_strings.append(label_display)

        self.combo_template = Gtk.DropDown.new_from_strings(template_strings)
        self.combo_template.set_valign(Gtk.Align.CENTER)
        self.combo_template.set_selected(0)
        self.combo_template.connect("notify::selected", self._on_template_changed)
        self.row_template.add_suffix(self.combo_template)
        sec1_list.append(self.row_template)

        # Orientation Row (Pill Switcher)
        self.row_orientation = Adw.ActionRow(title="Orientation")
        orient_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        orient_box.add_css_class("linked")

        self.btn_portrait = Gtk.ToggleButton()
        p_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        p_box.append(Gtk.Image.new_from_icon_name("document-page-setup-symbolic"))
        p_box.append(Gtk.Label(label="Portrait"))
        self.btn_portrait.set_child(p_box)
        self.btn_portrait.set_tooltip_text("Portrait orientation (taller than wide)")

        self.btn_landscape = Gtk.ToggleButton()
        l_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        l_box.append(Gtk.Image.new_from_icon_name("object-flip-horizontal-symbolic"))
        l_box.append(Gtk.Label(label="Landscape"))
        self.btn_landscape.set_child(l_box)
        self.btn_landscape.set_group(self.btn_portrait)
        self.btn_landscape.set_tooltip_text("Landscape orientation (wider than tall)")
        self.btn_landscape.set_active(True)

        self.btn_portrait.connect("toggled", self._on_orientation_toggled)
        self.btn_landscape.connect("toggled", self._on_orientation_toggled)

        orient_box.append(self.btn_portrait)
        orient_box.append(self.btn_landscape)
        self.row_orientation.add_suffix(orient_box)
        sec1_list.append(self.row_orientation)

        content_box.append(sec1_list)

        # ---------------------------------------------------------------------
        # Section 2: Dimensions
        # ---------------------------------------------------------------------
        sec2_lbl = Gtk.Label(label="Dimensions", xalign=0.0)
        sec2_lbl.add_css_class("heading")
        content_box.append(sec2_lbl)

        sec2_list = Gtk.ListBox()
        sec2_list.add_css_class("boxed-list")
        sec2_list.set_selection_mode(Gtk.SelectionMode.NONE)

        # Unit Row
        self.row_unit = Adw.ActionRow(title="Unit")
        self.combo_unit = Gtk.DropDown.new_from_strings(UNITS)
        self.combo_unit.set_valign(Gtk.Align.CENTER)
        self.combo_unit.set_selected(0)
        self.combo_unit.connect("notify::selected", self._on_unit_changed)
        self.row_unit.add_suffix(self.combo_unit)
        sec2_list.append(self.row_unit)

        # Width SpinButton Row
        self.row_width = Adw.ActionRow(title="Width")
        self.adj_width = Gtk.Adjustment(value=1920, lower=1, upper=16384, step_increment=1, page_increment=100)
        self.spin_width = Gtk.SpinButton(adjustment=self.adj_width, climb_rate=1.0, digits=0)
        self.spin_width.set_valign(Gtk.Align.CENTER)
        self.spin_width.connect("value-changed", self._on_dimension_value_changed)
        self.row_width.add_suffix(self.spin_width)
        sec2_list.append(self.row_width)

        # Height SpinButton Row
        self.row_height = Adw.ActionRow(title="Height")
        self.adj_height = Gtk.Adjustment(value=1080, lower=1, upper=16384, step_increment=1, page_increment=100)
        self.spin_height = Gtk.SpinButton(adjustment=self.adj_height, climb_rate=1.0, digits=0)
        self.spin_height.set_valign(Gtk.Align.CENTER)
        self.spin_height.connect("value-changed", self._on_dimension_value_changed)
        self.row_height.add_suffix(self.spin_height)
        sec2_list.append(self.row_height)

        content_box.append(sec2_list)

        # ---------------------------------------------------------------------
        # Section 3: Canvas Setup
        # ---------------------------------------------------------------------
        sec3_lbl = Gtk.Label(label="Canvas Setup", xalign=0.0)
        sec3_lbl.add_css_class("heading")
        content_box.append(sec3_lbl)

        sec3_list = Gtk.ListBox()
        sec3_list.add_css_class("boxed-list")
        sec3_list.set_selection_mode(Gtk.SelectionMode.NONE)

        self.row_bg = Adw.ActionRow(title="Background")
        bg_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        self.combo_bg = Gtk.DropDown.new_from_strings(BACKGROUND_OPTIONS)
        self.combo_bg.set_valign(Gtk.Align.CENTER)
        self.combo_bg.set_selected(0)
        self.combo_bg.connect("notify::selected", self._on_bg_changed)
        bg_box.append(self.combo_bg)

        self.btn_color_pick = Gtk.Button(label="Pick...")
        self.btn_color_pick.set_valign(Gtk.Align.CENTER)
        self.btn_color_pick.set_visible(False)
        self.btn_color_pick.connect("clicked", self._on_pick_color_clicked)
        bg_box.append(self.btn_color_pick)

        self.row_bg.add_suffix(bg_box)
        sec3_list.append(self.row_bg)

        content_box.append(sec3_list)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_vexpand(True)
        scrolled.set_hexpand(True)
        scrolled.set_child(content_box)
        root_box.append(scrolled)
        self.set_content(root_box)

    # -------------------------------------------------------------------------
    # Event Handlers
    # -------------------------------------------------------------------------

    def _on_template_changed(self, dropdown: Gtk.DropDown, _pspec: Any = None) -> None:
        if self._updating_fields:
            return

        idx = dropdown.get_selected()
        if idx < 0 or idx >= len(PRESET_TEMPLATES):
            return

        label, pw, ph, default_unit = PRESET_TEMPLATES[idx]
        if label == "Custom":
            return

        if label == "From Clipboard":
            if self._clipboard_w and self._clipboard_h:
                pw, ph = self._clipboard_w, self._clipboard_h
            else:
                pw, ph = 1920, 1080

        self._updating_fields = True
        try:
            self._current_unit = default_unit
            if default_unit in UNITS:
                self.combo_unit.set_selected(UNITS.index(default_unit))

            if pw >= ph:
                self._is_landscape = True
                self.btn_landscape.set_active(True)
                self._width_px = pw
                self._height_px = ph
            else:
                self._is_landscape = False
                self.btn_portrait.set_active(True)
                self._width_px = pw
                self._height_px = ph

            self._sync_dimension_inputs()
        finally:
            self._updating_fields = False

    def _on_orientation_toggled(self, btn: Gtk.ToggleButton) -> None:
        if self._updating_fields:
            return

        is_land = self.btn_landscape.get_active()
        if is_land == self._is_landscape:
            return
        self._is_landscape = is_land

        self._updating_fields = True
        try:
            # Swap width and height if needed
            w, h = self._width_px, self._height_px
            if self._is_landscape and w < h:
                self._width_px, self._height_px = h, w
            elif not self._is_landscape and w > h:
                self._width_px, self._height_px = h, w
            self._sync_dimension_inputs()
        finally:
            self._updating_fields = False

    def _on_unit_changed(self, dropdown: Gtk.DropDown, _pspec: Any = None) -> None:
        if self._updating_fields:
            return
        idx = dropdown.get_selected()
        if idx < 0 or idx >= len(UNITS):
            return
        new_unit = UNITS[idx]
        if new_unit == self._current_unit:
            return
        self._current_unit = new_unit
        self._sync_dimension_inputs()

    def _on_dimension_value_changed(self, spin: Gtk.SpinButton) -> None:
        if self._updating_fields:
            return

        # Read current spin values and convert to px
        val_w = self.spin_width.get_value()
        val_h = self.spin_height.get_value()
        self._width_px = unit_to_px(val_w, self._current_unit)
        self._height_px = unit_to_px(val_h, self._current_unit)

        # Update orientation switch state based on new dimensions
        if self._width_px >= self._height_px:
            if not self._is_landscape:
                self._is_landscape = True
                self.btn_landscape.set_active(True)
        else:
            if self._is_landscape:
                self._is_landscape = False
                self.btn_portrait.set_active(True)

        # If user altered dimensions, set Template dropdown to "Custom"
        custom_idx = len(PRESET_TEMPLATES) - 1
        if self.combo_template.get_selected() != custom_idx:
            self._updating_fields = True
            try:
                self.combo_template.set_selected(custom_idx)
            finally:
                self._updating_fields = False

    def _on_bg_changed(self, dropdown: Gtk.DropDown, _pspec: Any = None) -> None:
        idx = dropdown.get_selected()
        if idx < 0 or idx >= len(BACKGROUND_OPTIONS):
            return
        self._bg_choice = BACKGROUND_OPTIONS[idx]
        self.btn_color_pick.set_visible(self._bg_choice == BG_CUSTOM)

    def _on_pick_color_clicked(self, btn: Gtk.Button) -> None:
        def on_color_chosen(rgba: Gdk.RGBA) -> None:
            self._custom_color = rgba

        pick_color_dialog(
            parent=self,
            current=self._custom_color,
            callback=on_color_chosen,
            title="Choose Canvas Color",
        )

    # -------------------------------------------------------------------------
    # Synchronization & Creation
    # -------------------------------------------------------------------------

    def _sync_dimension_inputs(self) -> None:
        self._updating_fields = True
        try:
            val_w = px_to_unit(self._width_px, self._current_unit)
            val_h = px_to_unit(self._height_px, self._current_unit)

            if self._current_unit == UNIT_PIXELS:
                self.spin_width.set_digits(0)
                self.spin_width.set_increments(1, 100)
                self.spin_height.set_digits(0)
                self.spin_height.set_increments(1, 100)
            elif self._current_unit == UNIT_MILLIMETERS:
                self.spin_width.set_digits(1)
                self.spin_width.set_increments(1.0, 10.0)
                self.spin_height.set_digits(1)
                self.spin_height.set_increments(1.0, 10.0)
            else:  # Inches
                self.spin_width.set_digits(2)
                self.spin_width.set_increments(0.1, 1.0)
                self.spin_height.set_digits(2)
                self.spin_height.set_increments(0.1, 1.0)

            self.spin_width.set_value(val_w)
            self.spin_height.set_value(val_h)
        finally:
            self._updating_fields = False

    def _on_create_clicked(self, btn: Gtk.Button) -> None:
        # Read final width & height in px
        w_px = max(1, min(16384, self._width_px))
        h_px = max(1, min(16384, self._height_px))

        # Create Cairo surface
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, w_px, h_px)
        cr = cairo.Context(surface)

        has_alpha = False
        if self._bg_choice == BG_TRANSPARENT:
            has_alpha = True
            cr.set_operator(cairo.OPERATOR_CLEAR)
            cr.paint()
        elif self._bg_choice == BG_WHITE:
            cr.set_source_rgb(1.0, 1.0, 1.0)
            cr.paint()
        elif self._bg_choice == BG_BLACK:
            cr.set_source_rgb(0.0, 0.0, 0.0)
            cr.paint()
        elif self._bg_choice == BG_CUSTOM:
            r, g, b, a = rgba_to_cairo(self._custom_color)
            has_alpha = (a < 1.0)
            cr.set_source_rgba(r, g, b, a)
            cr.paint()

        self.destroy()

        if self.on_create:
            self.on_create(surface, has_alpha, w_px, h_px)
