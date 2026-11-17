# SPDX-License-Identifier: GPL-3.0-or-later
"""Light and dark themes, the developer links and the app id."""
import os
import shutil
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QSettings  # noqa: E402
from PyQt5.QtGui import QPalette  # noqa: E402
from PyQt5.QtWidgets import QApplication, QPushButton  # noqa: E402

from twigpad import DESKTOP_ID, developer  # noqa: E402
from twigpad.ui import theme  # noqa: E402
from twigpad.ui.mainwindow import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class ThemeTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.win = MainWindow(QSettings(os.path.join(self.dir, "s.ini"), QSettings.IniFormat))
        self.opened = []
        self.win.open_web = lambda url: self.opened.append(url) or True

    def tearDown(self):
        self.win.set_theme("auto")
        self.win.setWindowModified(False)
        self.win.close()
        self.win.deleteLater()
        app.processEvents()
        shutil.rmtree(self.dir)

    def base(self, widget=None):
        return (widget or app).palette().color(QPalette.Base)

    def test_dark_and_light(self):
        self.win.set_theme("dark")
        self.assertEqual(theme.current, "dark")
        self.assertTrue(theme.is_dark())
        self.assertEqual(self.base(self.win.editor).name(), theme.DARK["base"])
        self.assertEqual(self.win.settings.value("view/theme"), "dark")
        self.assertTrue(self.win.act_themes["dark"].isChecked())
        self.assertIn(theme.DARK["accent"], app.styleSheet())
        self.win.set_theme("light")
        self.assertFalse(theme.is_dark())
        self.assertEqual(self.base(self.win.tree).name(), theme.LIGHT["base"])

    def test_desktop_style_restores_original_look(self):
        self.win.set_theme("dark")
        self.win.set_theme("system")
        self.assertEqual(app.styleSheet(), "")
        self.assertEqual(self.base().name(), theme._original[1].color(QPalette.Base).name())

    def test_automatic_follows_desktop(self):
        old = theme.desktop_prefers_dark
        try:
            theme.desktop_prefers_dark = lambda: True
            self.assertEqual(theme.resolve("auto"), "dark")
            theme.desktop_prefers_dark = lambda: False
            self.assertEqual(theme.resolve("auto"), "light")
        finally:
            theme.desktop_prefers_dark = old

    def test_pane_colours_survive_theme_change(self):
        self.win.set_pane_color("tree_bg", "#123456")
        self.win.set_theme("dark")
        self.assertEqual(self.base(self.win.tree).name(), "#123456")
        self.assertEqual(self.base(self.win.editor).name(), theme.DARK["base"])

    def test_theme_is_remembered(self):
        self.win.set_theme("dark")
        self.win.settings.sync()
        win = MainWindow(QSettings(os.path.join(self.dir, "s.ini"), QSettings.IniFormat))
        try:
            self.assertTrue(win.act_themes["dark"].isChecked())
        finally:
            win.close()
            win.deleteLater()

    def test_help_menu_links(self):
        self.win.act_donate.trigger()
        self.win.act_developer.trigger()
        self.assertEqual(self.opened, ["https://paypal.me/TechRishabh/10",
                                       "https://warlordsoftwares.com/rishabh-bhardwaj/"])
        help_menu = next(a.menu() for a in self.win.menuBar().actions() if a.text() == "&Help")
        self.assertIn(self.win.act_more_apps, help_menu.actions())

    def test_more_apps_window(self):
        dlg = self.win._more_apps_dialog()
        buttons = [b for b in dlg.findChildren(QPushButton) if b.text() == "Learn More"]
        self.assertEqual(len(buttons), len(developer.OTHER_APPS))
        buttons[0].click()
        self.assertEqual(self.opened, [developer.OTHER_APPS[0].url])
        names = [a.name for a in developer.OTHER_APPS]
        for name in ("PDF 30-in-1 PRO", "4KTUBE PRO", "4KWALL PRO"):
            self.assertIn(name, names)
        for a in developer.OTHER_APPS:   # every app shows its own icon
            from twigpad.ui import icons
            self.assertFalse(icons.other_app_icon(a.icon).isNull(), a.name)
        dlg.deleteLater()

    def test_report_bug(self):
        help_menu = next(a.menu() for a in self.win.menuBar().actions() if a.text() == "&Help")
        self.assertIn(self.win.act_report_bug, help_menu.actions())
        self.win.act_report_bug.trigger()
        self.assertEqual(len(self.opened), 1)
        from urllib.parse import parse_qs, urlsplit
        url = urlsplit(self.opened[0])
        self.assertEqual(f"{url.scheme}://{url.netloc}{url.path}", developer.ISSUES_URL + "/new")
        query = parse_qs(url.query)
        self.assertEqual(query["labels"], ["bug"])
        body = query["body"][0]
        for text in ("What happened?", "Steps to reproduce", "- Twigpad: ", "- Qt: ", "- Python: ", "- OS: "):
            self.assertIn(text, body)
        self.assertNotIn(os.path.expanduser("~"), body)   # nothing personal

    def test_bug_icon_follows_theme(self):
        from twigpad.ui import iconset
        if not iconset.available():
            self.skipTest("no Qt SVG module")
        self.win.set_theme("light")
        light = self.win.act_report_bug.icon().pixmap(24, 24).toImage()
        self.win.set_theme("dark")
        dark = self.win.act_report_bug.icon().pixmap(24, 24).toImage()
        self.assertFalse(light.isNull())
        self.assertNotEqual(light, dark)

    def test_about_window(self):
        dlg = self.win._about_dialog()
        donate = next(b for b in dlg.findChildren(QPushButton) if "Support" in b.text())
        donate.click()
        self.assertEqual(self.opened, [developer.DONATE_URL])
        from PyQt5.QtWidgets import QLabel
        label = next(lb for lb in dlg.findChildren(QLabel) if "Report a bug" in lb.text())
        self.assertIn(developer.ISSUES_URL + "/new?labels=bug&amp;body=", label.text())
        dlg.deleteLater()

    def test_links_are_https(self):
        urls = [developer.DONATE_URL, developer.DEVELOPER_URL, developer.ALL_APPS_URL, developer.WEBSITE,
                developer.ISSUES_URL]
        urls += [a.url for a in developer.OTHER_APPS]
        for url in urls:
            self.assertTrue(url.startswith("https://"), url)

    def test_app_id(self):
        self.assertEqual(DESKTOP_ID, "com.warlordsoftwares.twigpad")
        for ext in (".desktop", ".metainfo.xml"):
            path = os.path.join(ROOT, "data", DESKTOP_ID + ext)
            with open(path, encoding="utf-8") as fh:
                self.assertIn(DESKTOP_ID, fh.read())


if __name__ == "__main__":
    unittest.main()
