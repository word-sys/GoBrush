from __future__ import annotations
import io
import uuid
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from PIL import Image
import cairo
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Gdk, Gio

from gobrush.app import GoBrushApp
from gobrush.ui.window import MainWindow


def _create_test_app() -> GoBrushApp:
    return GoBrushApp(application_id=f"io.github.word_sys.GoBrush.t{uuid.uuid4().hex[:8]}")


class TestCliAndOpen(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        Gtk.init()

    def setUp(self) -> None:
        self.tmp_image = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        im = Image.new("RGB", (64, 48), (200, 50, 100))
        im.save(self.tmp_image.name, format="PNG")
        self.image_path = self.tmp_image.name

    def tearDown(self) -> None:
        Path(self.image_path).unlink(missing_ok=True)

    def test_cli_version_flag(self) -> None:
        app = _create_test_app()
        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            exit_code = app.run(["gobrush", "--version"])
            self.assertEqual(exit_code, 0)
            self.assertIn("GoBrush", fake_out.getvalue())

    def test_cli_positional_file_argument(self) -> None:
        app = _create_test_app()
        app.register(None)
        img_path = self.image_path

        class MockCommandLine:
            def get_options_dict(self):
                return type("MockDict", (), {"contains": lambda self, k: False})()

            def get_arguments(self):
                return ["gobrush", img_path]

            def create_file_for_arg(self, arg):
                return Gio.File.new_for_path(arg)

        app.do_command_line(MockCommandLine())
        win = app.props.active_window
        self.assertIsNotNone(win)
        self.assertFalse(win.is_empty())
        self.assertEqual(win.current_file_path, str(Path(self.image_path).resolve()))
        self.assertTrue(win.canvas.has_image)
        self.assertEqual(win.canvas.image_width, 64)
        self.assertEqual(win.canvas.image_height, 48)

    def test_cli_nonexistent_file_handling(self) -> None:
        app = _create_test_app()
        app.register(None)

        class MockCommandLine:
            def get_options_dict(self):
                return type("MockDict", (), {"contains": lambda self, k: False})()

            def get_arguments(self):
                return ["gobrush", "/path/to/missing_image_12345.png"]

            def create_file_for_arg(self, arg):
                return Gio.File.new_for_path(arg)

        app.do_command_line(MockCommandLine())
        win = app.props.active_window
        self.assertIsNotNone(win)
        self.assertTrue(win.is_empty())
        self.assertIsNone(win.current_file_path)

    def test_app_do_open(self) -> None:
        app = _create_test_app()
        app.register(None)

        gfile = Gio.File.new_for_path(self.image_path)
        app.do_open([gfile], "")
        win = app.props.active_window
        self.assertIsNotNone(win)
        self.assertFalse(win.is_empty())
        self.assertEqual(win.canvas.image_width, 64)

    def test_headerbar_open_button_triggers_dialog(self) -> None:
        win = MainWindow()
        with patch("gobrush.ui.window.open_file_dialog") as mock_dialog:
            win.btn_open.emit("clicked")
            mock_dialog.assert_called_once()
            args, _ = mock_dialog.call_args
            self.assertEqual(args[0], win)

    def test_ctrl_o_triggers_open_dialog(self) -> None:
        win = MainWindow()
        with patch("gobrush.ui.window.open_file_dialog") as mock_dialog:
            res = win._on_key_pressed(
                win._key_controller,
                Gdk.KEY_o,
                0,
                Gdk.ModifierType.CONTROL_MASK,
            )
            self.assertTrue(res)
            mock_dialog.assert_called_once()

    def test_on_file_selected_loads_image(self) -> None:
        win = MainWindow()
        self.assertTrue(win.is_empty())
        win._on_file_selected(self.image_path)
        self.assertFalse(win.is_empty())
        self.assertEqual(win.canvas.image_width, 64)
        self.assertEqual(win.canvas.image_height, 48)

    def test_opened_file_centers_in_middle_of_window(self) -> None:
        win = MainWindow()
        win.open_file(self.image_path)
        self.assertTrue(win.canvas._pending_fit)

        # Draw at 800x600
        target = cairo.ImageSurface(cairo.FORMAT_ARGB32, 800, 600)
        cr = cairo.Context(target)
        win.canvas._on_draw(win.canvas, cr, 800, 600)

        self.assertFalse(win.canvas._pending_fit)
        # 64x48 image in 800x600 viewport -> zoom 1.0, pan_x = (800-64)/2 = 368, pan_y = (600-48)/2 = 276
        self.assertAlmostEqual(win.canvas.zoom, 1.0)
        self.assertAlmostEqual(win.canvas.pan_x, 368.0)
        self.assertAlmostEqual(win.canvas.pan_y, 276.0)


if __name__ == "__main__":
    unittest.main()
