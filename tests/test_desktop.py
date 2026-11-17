# SPDX-License-Identifier: GPL-3.0-or-later
"""Opening .hjt files with Twigpad from the file manager."""
import os
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QSettings  # noqa: E402
from PyQt5.QtWidgets import QApplication  # noqa: E402

from twigpad import DESKTOP_ID, desktop  # noqa: E402
from twigpad.ui import popups  # noqa: E402
from twigpad.ui.mainwindow import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class FakeTools:
    """Stands in for xdg-mime and friends; remembers the default app."""

    def __init__(self):
        self.calls = []
        self.default = ""

    def __call__(self, args, **_kw):
        self.calls.append(args)
        out = ""
        if args[:3] == ["xdg-mime", "query", "default"]:
            out = self.default + "\n"
        elif args[:2] == ["xdg-mime", "default"]:
            self.default = args[2]
        return subprocess.CompletedProcess(args, 0, out, "")


class DesktopTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        env = {"XDG_DATA_HOME": os.path.join(self.dir, "data"),
               "XDG_CONFIG_HOME": os.path.join(self.dir, "config"),
               "XDG_DATA_DIRS": os.path.join(self.dir, "system")}
        self.env = mock.patch.dict(os.environ, env)
        self.env.start()
        os.environ.pop("FLATPAK_ID", None)
        os.environ.pop("APPIMAGE", None)
        self.tools = FakeTools()
        self.which = mock.patch.object(desktop.shutil, "which", side_effect=lambda name: "/usr/bin/" + name
                                       if name != "twigpad" else None)
        self.which.start()
        self.flatpak = mock.patch.object(desktop, "in_flatpak", return_value=False)
        self.flatpak.start()

    def tearDown(self):
        self.flatpak.stop()
        self.which.stop()
        self.env.stop()
        popups.auto_answer = None
        shutil.rmtree(self.dir)

    def test_bundled_mime_file_matches_data_folder(self):
        with open(os.path.join(ROOT, "data", "twigpad-mime.xml"), "rb") as a, \
                open(os.path.join(desktop.RESOURCES, "twigpad-mime.xml"), "rb") as b:
            self.assertEqual(a.read(), b.read())
        with open(os.path.join(ROOT, "data", DESKTOP_ID + ".desktop"), encoding="utf-8") as fh:
            shipped = fh.read()
        for line in desktop.desktop_entry("twigpad %f").splitlines():
            if not line.startswith("Exec="):
                self.assertIn(line, shipped)

    def test_make_default_for_this_user(self):
        self.assertFalse(desktop.is_default(run=self.tools))
        desktop.make_default(run=self.tools)
        self.assertTrue(desktop.is_default(run=self.tools))
        data = os.environ["XDG_DATA_HOME"]
        self.assertTrue(os.path.exists(os.path.join(data, "mime", "packages", DESKTOP_ID + ".xml")))
        entry = os.path.join(data, "applications", DESKTOP_ID + ".desktop")
        with open(entry, encoding="utf-8") as fh:
            text = fh.read()
        self.assertIn("MimeType=application/x-hjt;application/x-twigpad;", text)
        exec_line = next(line for line in text.splitlines() if line.startswith("Exec="))
        self.assertTrue(exec_line.endswith("-m twigpad %f"), exec_line)
        self.assertTrue(os.path.exists(os.path.join(data, "icons", "hicolor", "scalable", "apps",
                                                    DESKTOP_ID + ".svg")))
        commands = [c[0] for c in self.tools.calls]
        self.assertIn("update-mime-database", commands)
        self.assertIn(["xdg-mime", "default", DESKTOP_ID + ".desktop", *desktop.MIME_TYPES], self.tools.calls)

    def test_installed_package_keeps_its_own_menu_entry(self):
        system = os.path.join(os.environ["XDG_DATA_DIRS"], "applications", DESKTOP_ID + ".desktop")
        os.makedirs(os.path.dirname(system))
        open(system, "w").close()
        desktop.make_default(run=self.tools)
        self.assertFalse(os.path.exists(desktop.user_desktop_file()))
        self.assertTrue(desktop.is_default(run=self.tools))

    def test_without_xdg_mime_writes_mimeapps_list(self):
        os.makedirs(os.environ["XDG_CONFIG_HOME"])
        with open(os.path.join(os.environ["XDG_CONFIG_HOME"], "mimeapps.list"), "w") as fh:
            fh.write("[Default Applications]\ntext/plain=gedit.desktop\n\n[Added Associations]\nimage/png=eog.desktop;\n")
        self.which.stop()
        with mock.patch.object(desktop.shutil, "which", return_value=None):
            desktop.make_default(run=self.tools)
            self.assertTrue(desktop.is_default(run=self.tools))
        self.which.start()
        with open(os.path.join(os.environ["XDG_CONFIG_HOME"], "mimeapps.list")) as fh:
            text = fh.read()
        self.assertIn("text/plain=gedit.desktop", text)        # other apps are kept
        self.assertIn("image/png=eog.desktop;", text)
        self.assertIn(f"application/x-hjt={DESKTOP_ID}.desktop;", text)

    def test_appimage_and_quoting(self):
        with mock.patch.dict(os.environ, {"APPIMAGE": "/home/me/My Apps/Twigpad.AppImage"}):
            cmd = desktop.launch_command()
        self.assertEqual(desktop.shell_command(cmd), ["/home/me/My Apps/Twigpad.AppImage", "FILE"])

    def test_offer_once_and_option(self):
        win = MainWindow(QSettings(os.path.join(self.dir, "s.ini"), QSettings.IniFormat))
        asked = []
        try:
            with mock.patch.object(desktop, "is_default", return_value=False), \
                    mock.patch.object(desktop, "make_default") as make:
                popups.auto_answer = lambda d: asked.append(d.title_label.text()) or "cancel"
                win.offer_file_association()
                win.offer_file_association()
                self.assertEqual(len(asked), 1)                  # only asked once
                make.assert_not_called()
                popups.auto_answer = lambda d: asked.append(d.title_label.text()) or "ok"
                win.act_file_types.trigger()
                make.assert_called_once()
                self.assertIn("now open with", asked[-1])
        finally:
            win.setWindowModified(False)
            win.close()
            win.deleteLater()


class QtMessageTests(unittest.TestCase):
    def test_font_noise_is_dropped_other_messages_kept(self):
        import io
        from twigpad import __main__ as entry
        with mock.patch("sys.stderr", new=io.StringIO()) as err:
            entry.qt_message(None, None, 'OpenType support missing for "Saab", script 13')
            entry.qt_message(None, None, "QPixmap: something real")
        self.assertEqual(err.getvalue(), "QPixmap: something real\n")


if __name__ == "__main__":
    unittest.main()
