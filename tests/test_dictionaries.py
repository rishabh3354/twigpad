# SPDX-License-Identifier: GPL-3.0-or-later
"""Downloading spell-checking dictionaries."""
import io
import os
import shutil
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QSettings  # noqa: E402
from PyQt5.QtWidgets import QApplication  # noqa: E402

from twigpad import spell  # noqa: E402
from twigpad.ui import popups  # noqa: E402
from twigpad.ui.dictionaries import DictionaryDialog  # noqa: E402
from twigpad.ui.mainwindow import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])
AFF = b"SET UTF-8\nTRY esiarntolcdugmphbyfvkwz\n"
DIC = b"3\nhello\nworld\nTwigpad\n"


class FakeResponse(io.BytesIO):
    def __init__(self, data):
        super().__init__(data)
        self.headers = {"Content-Length": str(len(data))}


def fake_opener(files):
    def opener(req, timeout=None):
        ext = req.full_url.rsplit(".", 1)[1]
        return FakeResponse(files[ext])
    return opener


class DictionaryTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.saved = (spell.USER_DICT_DIR, list(spell.DICT_DIRS), spell.install_dictionary)
        spell.USER_DICT_DIR = os.path.join(self.dir, "hunspell")
        spell.DICT_DIRS[:] = [spell.USER_DICT_DIR]
        self.lang = next(lang for lang in spell.DOWNLOADS if lang.code == "en_GB")

    def tearDown(self):
        spell.USER_DICT_DIR, spell.DICT_DIRS[:], spell.install_dictionary = self.saved
        popups.auto_answer = None
        shutil.rmtree(self.dir)

    def test_list_has_popular_languages(self):
        names = {lang.name for lang in spell.DOWNLOADS}
        for name in ("English (United Kingdom)", "German (Germany)", "French", "Spanish", "Italian",
                     "Portuguese (Brazil)", "Russian", "Dutch", "Polish"):
            self.assertIn(name, names)
        self.assertEqual(len({lang.code for lang in spell.DOWNLOADS}), len(spell.DOWNLOADS))
        self.assertTrue(all(spell.DOWNLOAD_BASE.startswith("https://") for _ in [0]))
        self.assertEqual(spell.language_name("en_GB"), "English (United Kingdom)")
        self.assertEqual(spell.language_name("de_LU"), "German (de_LU)")

    def test_install_and_remove(self):
        seen = []
        path = spell.install_dictionary(self.lang, lambda part, pct: seen.append((part, pct)),
                                        opener=fake_opener({"aff": AFF, "dic": DIC}))
        self.assertEqual(path, os.path.join(spell.USER_DICT_DIR, "en_GB.dic"))
        self.assertTrue(os.path.exists(path[:-4] + ".aff"))
        self.assertEqual(seen[-1], (1, 100))
        self.assertTrue(spell.user_installed("en_GB"))
        self.assertTrue(spell.remove_dictionary("en_GB"))
        self.assertFalse(os.path.exists(path))

    def test_bad_download_leaves_nothing(self):
        with self.assertRaises(OSError):
            spell.install_dictionary(self.lang, opener=fake_opener({"aff": AFF, "dic": b"<html>404</html>"}))
        self.assertEqual(os.listdir(spell.USER_DICT_DIR), [])

    @unittest.skipUnless(spell.library_available(), "the Hunspell library is not installed")
    def test_download_from_window(self):
        win = MainWindow(QSettings(os.path.join(self.dir, "s.ini"), QSettings.IniFormat))
        try:
            real = self.saved[2]
            spell.install_dictionary = lambda lang, progress=None: real(
                lang, progress, opener=fake_opener({"aff": AFF, "dic": DIC}))
            dlg = DictionaryDialog(win)
            dlg.select("en_GB")
            self.assertEqual(dlg.download_btn.text(), "Download")
            dlg.download()
            dlg.thread.wait(5000)
            for _ in range(20):
                app.processEvents()
            self.assertIsNone(dlg.thread)
            self.assertIn("en_GB", win.act_spell_langs)
            self.assertEqual(win.act_spell_langs["en_GB"].text(), "English (United Kingdom)")
            self.assertTrue(win.act_spell_langs["en_GB"].isChecked())
            self.assertTrue(win.act_spell.isChecked())
            self.assertTrue(win.speller.check("Twigpad"))
            self.assertFalse(win.speller.check("Twigpadd"))
            self.assertEqual(win.settings.value("spell/language"), "en_GB")
            self.assertIn("Download Languages", win.spell_lang_menu.actions()[-1].text())
            popups.auto_answer = lambda d: "ok"      # confirm Remove
            dlg.select("en_GB")
            dlg.remove()
            self.assertNotIn("en_GB", win.act_spell_langs)
            self.assertFalse(win.act_spell.isEnabled())
            dlg.deleteLater()
        finally:
            win.setWindowModified(False)
            win.close()
            win.deleteLater()


if __name__ == "__main__":
    unittest.main()
