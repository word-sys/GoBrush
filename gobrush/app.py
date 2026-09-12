from __future__ import annotations
import sys
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio, GLib

from gobrush import __version__, __app_id__
from gobrush.ui.window import MainWindow


class GoBrushApp(Adw.Application):
    def __init__(self, application_id: str | None = None, **kwargs) -> None:
        super().__init__(
            application_id=application_id or __app_id__,
            flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE | Gio.ApplicationFlags.HANDLES_OPEN,
            **kwargs,
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
        win = self.props.active_window

        args = command_line.get_arguments()
        file_to_open: str | None = None
        for arg in args[1:]:
            if not arg.startswith("-"):
                gfile = command_line.create_file_for_arg(arg)
                path = gfile.get_path()
                if path:
                    file_to_open = path
                    break

        if file_to_open and isinstance(win, MainWindow):
            win.open_file(file_to_open)

        return 0

    def do_open(self, files: list[Gio.File], hint: str) -> None:
        self.activate()
        win = self.props.active_window
        if files and isinstance(win, MainWindow):
            path = files[0].get_path()
            if path:
                win.open_file(path)

    def do_activate(self) -> None:
        win = self.props.active_window
        if not win:
            win = MainWindow(application=self)
        win.present()
