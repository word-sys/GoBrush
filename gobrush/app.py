from __future__ import annotations
import sys
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio, GLib

from gobrush import __version__, __app_id__


class GoBrushApp(Adw.Application):
    def __init__(self) -> None:
        super().__init__(
            application_id=__app_id__,
            flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE,
        )
        self.add_main_option(
            "version",
            ord("v"),
            GLib.OptionFlags.NONE,
            GLib.OptionArg.NONE,
            "Show version",
            None,
        )

    def do_command_line(self, command_line: Gio.ApplicationCommandLine) -> int:
        options = command_line.get_options_dict()
        if options.contains("version"):
            print(f"GoBrush {__version__}")
            return 0
        self.activate()
        return 0

    def do_activate(self) -> None:
        win = self.props.active_window
        if not win:
            win = Adw.ApplicationWindow(application=self, title="GoBrush")
            win.set_default_size(800, 600)
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            header = Adw.HeaderBar()
            box.append(header)
            status = Adw.StatusPage(
                title="GoBrush",
                description="Modern Lightweight Quick Annotator",
                icon_name="applications-graphics-symbolic",
            )
            box.append(status)
            win.set_content(box)
        win.present()
