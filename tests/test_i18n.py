# SPDX-License-Identifier: GPL-3.0-or-later
"""App language: the translation files, plural forms and View > Language."""
import importlib.util
import json
import os
import shutil
import tempfile
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QSettings  # noqa: E402
from PyQt5.QtWidgets import QApplication  # noqa: E402

from twigpad import i18n, spell  # noqa: E402
from twigpad.ui import popups  # noqa: E402
from twigpad.ui.mainwindow import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location("i18n_strings", os.path.join(ROOT, "tools", "i18n_strings.py"))
i18n_strings = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(i18n_strings)


class TranslationFileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.texts, cls.plurals, cls.problems = i18n_strings.extract()

    def test_texts_are_marked_cleanly(self):
        self.assertEqual(self.problems, [])
        self.assertGreater(len(self.texts), 500)
        self.assertIn("&File", self.texts)
        self.assertIn("{n} node", self.plurals)

    def test_every_language_is_complete(self):
        for code in i18n.LANGUAGES:
            if code == "en":
                continue
            with self.subTest(code=code):
                with open(i18n.translation_file(code), encoding="utf-8") as fh:
                    table = json.load(fh)
                self.assertEqual(i18n_strings.check_language(code, table, self.texts, self.plurals), [])

    def test_fields_and_accelerators_checked(self):
        texts = {"Delete {name}?": "x", "&File": "x", "Plain": "x"}
        bad = {"Delete {name}?": "Löschen {nom}?", "&File": "&Da&tei", "Plain": "&Schlicht"}
        issues = i18n_strings.check_language("de", bad, texts, {})
        self.assertEqual(len(issues), 3)


class LanguageTests(unittest.TestCase):
    def tearDown(self):
        i18n.set_language("en")

    def test_match_and_system_language(self):
        self.assertEqual(i18n.match("de_AT.UTF-8"), "de")
        self.assertEqual(i18n.match("pt_BR"), "pt_BR")
        self.assertIsNone(i18n.match("pt_PT"))
        self.assertEqual(i18n.match("zh_SG"), "zh_CN")
        self.assertIsNone(i18n.match("tr_TR"))
        with mock.patch.dict(os.environ, {"LANGUAGE": "", "LC_ALL": "", "LC_MESSAGES": "", "LANG": "fr_CA.UTF-8"}):
            self.assertEqual(i18n.system_language(), "fr")
        with mock.patch.dict(os.environ, {"LANGUAGE": "ja:en", "LC_ALL": "", "LC_MESSAGES": "", "LANG": "C"}):
            self.assertEqual(i18n.resolve(i18n.AUTO), "ja")
        with mock.patch.dict(os.environ, {"LANGUAGE": "", "LC_ALL": "C", "LC_MESSAGES": "", "LANG": ""}):
            self.assertEqual(i18n.system_language(), "en")

    def test_tr_and_fallback(self):
        self.assertEqual(i18n.set_language("de"), "de")
        self.assertEqual(i18n.tr("&File"), "&Datei")
        self.assertEqual(i18n.tr("Not a known text"), "Not a known text")
        i18n.set_language("en")
        self.assertEqual(i18n.tr("&File"), "&File")

    def test_plural_rules(self):
        cases = {"en": [(0, 1), (1, 0), (2, 1)], "fr": [(0, 0), (1, 0), (2, 1)],
                 "ru": [(1, 0), (2, 1), (5, 2), (11, 2), (21, 0), (22, 1), (112, 2)],
                 "ja": [(1, 0), (7, 0)]}
        for code, pairs in cases.items():
            for n, index in pairs:
                self.assertEqual(i18n.plural_index(code, n), index, (code, n))

    def test_ntr(self):
        self.assertEqual(i18n.ntr("{n} node", "{n} nodes", 1).format(n=1), "1 node")
        self.assertEqual(i18n.ntr("{n} node", "{n} nodes", 3).format(n=3), "3 nodes")
        i18n.set_language("ru")
        self.assertEqual(i18n.ntr("{n} node", "{n} nodes", 3).format(n=3), "3 узла")
        self.assertEqual(i18n.ntr("{n} node", "{n} nodes", 25).format(n=25), "25 узлов")
        i18n.set_language("ja")
        self.assertEqual(i18n.ntr("{n} node", "{n} nodes", 2).format(n=2), "2 個のノード")

    def test_tr_in_another_language(self):
        self.assertEqual(i18n.tr_in("fr", "&File"), "&Fichier")
        self.assertEqual(i18n.tr_in("en", "&File"), "&File")

    def test_spelling_names_in_their_own_language(self):
        self.assertEqual(spell.language_name("de_DE"), "German (Germany)")
        i18n.set_language("de")
        self.assertEqual(spell.language_name("de_DE"), "Deutsch (Deutschland)")


class LanguageMenuTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.win = MainWindow(QSettings(os.path.join(self.dir, "s.ini"), QSettings.IniFormat))
        self.asked = []
        popups.auto_answer = lambda d: self.asked.append(d.title_label.text()) or "later"

    def tearDown(self):
        popups.auto_answer = None
        i18n.set_language("en")
        self.win.setWindowModified(False)
        self.win.close()
        self.win.deleteLater()
        app.processEvents()
        shutil.rmtree(self.dir)

    def test_menu_lists_languages(self):
        view = next(a.menu() for a in self.win.menuBar().actions() if a.text() == "&View")
        menu = next(a.menu() for a in view.actions() if a.text() == "&Language")
        texts = [a.text() for a in menu.actions() if not a.isSeparator()]
        self.assertEqual(texts[0], "&Automatic (Follow the Desktop)")
        self.assertIn("Deutsch", texts)
        self.assertIn("日本語", texts)
        self.assertTrue(self.win.act_languages[i18n.AUTO].isChecked())

    def test_choosing_a_language_asks_to_restart_in_that_language(self):
        with mock.patch.object(self.win, "restart") as restart:
            self.assertEqual(self.win.set_language("de"), "later")
            restart.assert_not_called()
        self.assertEqual(self.win.settings.value("view/language"), "de")
        self.assertTrue(self.win.act_languages["de"].isChecked())
        self.assertEqual(self.asked, ["Twigpad neu starten, um die Sprache zu ändern?"])
        popups.auto_answer = lambda d: "restart"
        with mock.patch.object(self.win, "restart") as restart:
            self.win.set_language("fr")
            restart.assert_called_once()

    def test_same_language_does_not_ask(self):
        self.assertIsNone(self.win.set_language("en"))
        self.assertEqual(self.asked, [])
        self.assertIsNone(self.win.set_language("xx"))

    def test_reset_keeps_the_language(self):
        self.win.set_language("de")
        self.win.reset_settings(confirm=False)
        self.assertEqual(self.win.settings.value("view/language"), "de")


class RestartCommandTests(unittest.TestCase):
    def test_restart_command(self):
        import sys
        from twigpad import desktop
        with mock.patch.dict(os.environ, {"APPIMAGE": "/apps/Twigpad.AppImage"}):
            self.assertEqual(desktop.restart_command(), ("/apps/Twigpad.AppImage", [], {}))
        env = dict(os.environ)
        env.pop("APPIMAGE", None)
        with mock.patch.dict(os.environ, env, clear=True):
            program, args, extra = desktop.restart_command()
        self.assertEqual((program, args), (sys.executable, ["-m", "twigpad"]))
        self.assertEqual(extra.get("PYTHONPATH"), os.path.join(ROOT, "src"))   # running from the source folder


class TranslatedWindowTests(unittest.TestCase):
    def test_window_in_german_and_japanese(self):
        for code, file_menu, help_menu in (("de", "&Datei", "&Hilfe"), ("ja", "ファイル(&F)", "ヘルプ(&H)")):
            with self.subTest(code=code):
                d = tempfile.mkdtemp()
                i18n.set_language(code)
                try:
                    win = MainWindow(QSettings(os.path.join(d, "s.ini"), QSettings.IniFormat))
                    menus = [a.text() for a in win.menuBar().actions()]
                    self.assertEqual(menus[0], file_menu)
                    self.assertIn(help_menu, menus)
                    win.close()
                    win.deleteLater()
                    app.processEvents()
                finally:
                    i18n.set_language("en")
                    shutil.rmtree(d)


if __name__ == "__main__":
    unittest.main()
