# SPDX-License-Identifier: GPL-3.0-or-later
"""Help menu extras, the message windows and Reset All Settings."""
import os
import shutil
import tempfile
import unittest
from urllib.parse import parse_qs, urlsplit

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QSettings  # noqa: E402
from PyQt5.QtWidgets import QApplication, QDialog  # noqa: E402

from twigpad import developer  # noqa: E402
from twigpad.ui import fonts, popups, shortcuts  # noqa: E402
from twigpad.ui.mainwindow import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])


class HelpTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.win = MainWindow(QSettings(os.path.join(self.dir, "s.ini"), QSettings.IniFormat))
        self.opened = []
        self.win.open_web = lambda url: self.opened.append(url) or True
        self.titles = []

    def tearDown(self):
        popups.auto_answer = None
        self.win.set_theme("auto")
        self.win.setWindowModified(False)
        self.win.close()
        self.win.deleteLater()
        app.processEvents()
        shutil.rmtree(self.dir)

    def help_menu(self):
        return next(a.menu() for a in self.win.menuBar().actions() if a.text() == "&Help")

    def test_request_feature(self):
        actions = self.help_menu().actions()
        self.assertEqual(actions.index(self.win.act_request_feature),
                         actions.index(self.win.act_report_bug) + 1)      # right below Report a Bug
        self.win.act_request_feature.trigger()
        url = urlsplit(self.opened[0])
        self.assertEqual(f"{url.scheme}://{url.netloc}{url.path}", developer.ISSUES_URL + "/new")
        query = parse_qs(url.query)
        self.assertEqual(query["labels"], ["enhancement"])
        self.assertIn("What would you like Twigpad to do?", query["body"][0])

    def test_keyboard_shortcuts_window(self):
        self.assertIn(self.win.act_shortcuts, self.help_menu().actions())
        self.assertEqual(self.win.act_shortcuts.shortcut().toString(), "F1")
        groups = dict(shortcuts.collect(self.win))
        self.assertIn(("Save", "Ctrl+S"), groups["File"])
        self.assertTrue(any(what == "Rename" and key == "F2" for what, key in groups["Node"]))
        self.assertIn(("Make the text larger or smaller", "Ctrl+Mouse Wheel"), groups["Tree, Article and Mouse"])
        dlg = self.win.shortcuts_dialog()
        everything = dlg.apply_filter("")
        self.assertGreater(everything, 40)
        self.assertGreaterEqual(dlg.apply_filter("ctrl+s"), 1)
        self.assertEqual(dlg.apply_filter("no such command"), 0)
        self.assertTrue(dlg.empty.isVisibleTo(dlg))
        dlg.deleteLater()

    def test_message_window_buttons(self):
        dlg = popups.MessageDialog(None, popups.WARNING, "Save changes?", "Text",
                                   (("discard", "Don't Save", popups.NORMAL), ("cancel", "Cancel", popups.CANCEL),
                                    ("save", "Save", popups.PRIMARY)), "save")
        self.assertEqual(dlg.buttons["save"].objectName(), "accent")
        self.assertTrue(dlg.buttons["save"].isDefault())
        dlg.buttons["discard"].click()
        self.assertEqual(dlg.choice, "discard")
        dlg = popups.MessageDialog(None, popups.QUESTION, "Delete?", "", (("cancel", "Cancel", popups.CANCEL),
                                                                          ("ok", "Delete", popups.DANGER)))
        self.assertEqual(dlg.buttons["ok"].objectName(), "danger")
        dlg.reject()                       # Escape or the close button
        self.assertEqual(dlg.choice, "cancel")
        for kind in (popups.INFO, popups.QUESTION, popups.WARNING, popups.ERROR, popups.SUCCESS):
            self.assertFalse(popups.badge(kind).isNull())

    def test_no_plain_message_boxes_left(self):
        src = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src", "twigpad")
        for folder, _dirs, files in os.walk(src):
            for name in files:
                if name.endswith(".py"):
                    with open(os.path.join(folder, name), encoding="utf-8") as fh:
                        text = fh.read()
                    self.assertNotIn("QMessageBox", text, name)
                    self.assertNotIn("QInputDialog", text, name)

    def test_unsaved_changes_question(self):
        self.win.setWindowModified(True)
        popups.auto_answer = lambda d: self.titles.append(d.title_label.text()) or "cancel"
        self.assertFalse(self.win.maybe_save())
        popups.auto_answer = lambda d: "discard"
        self.assertTrue(self.win.maybe_save())
        self.assertTrue(self.titles[0].startswith("Save changes to"))

    def test_password_question(self):
        popups.auto_answer = lambda d: (d.input.setText("s3cret"), "ok")[1]
        self.assertEqual(self.win._ask_password("a.twig", False), "s3cret")
        popups.auto_answer = lambda d: "cancel"
        self.assertIsNone(self.win._ask_password("a.twig", True))

    def test_reset_all_settings(self):
        s = self.win.settings
        self.win.set_theme("dark")
        self.win.set_toolbar_icon_size(32)
        self.win.zoom_text("tree", 4)
        s.setValue("fonts/editor", "DejaVu Serif,20,-1,5,50,0,0,0,0,0")
        s.setValue("files/recent", [os.path.join(self.dir, "a.hjt")])
        s.setValue("spell/words", ["Twigpad"])
        self.win.toolbars["file-bar"].hide()
        popups.auto_answer = lambda d: "cancel"
        self.assertFalse(self.win.reset_settings())
        self.assertEqual(s.value("view/theme"), "dark")
        popups.auto_answer = lambda d: "ok"
        self.assertTrue(self.win.reset_settings())
        self.assertIsNone(s.value("view/theme"))
        self.assertTrue(self.win.act_themes["auto"].isChecked())
        self.assertEqual(self.win.toolbars["file-bar"].iconSize().width(), 24)
        self.assertTrue(self.win.toolbars["file-bar"].isVisibleTo(self.win))
        self.assertFalse(self.win.toolbars["extras-bar"].isVisibleTo(self.win))
        self.assertEqual(self.win.tree.font().pointSizeF(), fonts.default_font("tree").pointSizeF())
        self.assertEqual(self.win.editor.font().pointSizeF(), fonts.default_font("editor").pointSizeF())
        self.assertIn("Twigpad", s.value("spell/words"))      # kept
        self.assertEqual(self.win.recent_files(), [os.path.join(self.dir, "a.hjt")])
        options = next(a.menu() for a in self.win.menuBar().actions() if a.text() == "&Options")
        self.assertIn(self.win.act_reset_settings, options.actions())


class FontsDialogTests(unittest.TestCase):
    def test_dialog_is_a_dialog(self):
        win = MainWindow(QSettings(os.path.join(tempfile.mkdtemp(), "s.ini"), QSettings.IniFormat))
        try:
            self.assertIsInstance(win.fonts_dialog(), QDialog)
            view = next(a.menu() for a in win.menuBar().actions() if a.text() == "&View")
            self.assertIn(win.act_fonts, view.actions())
        finally:
            win.close()
            win.deleteLater()


if __name__ == "__main__":
    unittest.main()
