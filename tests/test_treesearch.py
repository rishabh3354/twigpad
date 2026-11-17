# SPDX-License-Identifier: GPL-3.0-or-later
"""The Tree Search window."""
import os
import shutil
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QSettings, Qt  # noqa: E402
from PyQt5.QtTest import QTest  # noqa: E402
from PyQt5.QtWidgets import QApplication  # noqa: E402

from twigpad.ui.mainwindow import MainWindow  # noqa: E402
from twigpad.ui.treesearch import ARTICLE, BOTH, NODE, node_path, search_items  # noqa: E402
from tests.test_hjt import SAMPLE, windows_file  # noqa: E402

app = QApplication.instance() or QApplication([])


class TreeSearchTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.settings_path = os.path.join(self.dir, "s.ini")
        self.win = MainWindow(QSettings(self.settings_path, QSettings.IniFormat))
        self.sample = os.path.join(self.dir, "notes.hjt")
        with open(self.sample, "wb") as fh:
            fh.write(windows_file(SAMPLE))
        self.assertTrue(self.win.load_path(self.sample))
        self.tree = self.win.tree
        self.find("Soup").body = "Soup is hot. More soup please."
        self.dlg = self.win.tree_search_dialog()

    def tearDown(self):
        self.dlg.close()
        self.win.setWindowModified(False)
        self.win.close()
        self.win.deleteLater()
        app.processEvents()
        shutil.rmtree(self.dir)

    def find(self, title):
        return next(i for i in self.tree.all_items() if i.title == title)

    def search(self, text):
        self.dlg.show_dialog()
        self.dlg.text_edit.setText(text)
        return self.dlg.run_search()

    def rows(self):
        r = self.dlg.results
        return [[r.topLevelItem(i).text(c) for c in range(4)] for i in range(r.topLevelItemCount())]

    # ------------------------------------------------------------ searching

    def test_locations_and_paths(self):
        hits = search_items(self.tree.all_items(), "SOUP")
        self.assertEqual([(h.item.title, h.location, h.path) for h in hits],
                         [("Soup", BOTH, "My notes/Recipes/Soup")])
        hits = search_items(self.tree.all_items(), "line")
        self.assertEqual([(h.item.title, h.location) for h in hits], [("My notes", ARTICLE), ("Work", ARTICLE)])
        hits = search_items(self.tree.all_items(), "work")
        self.assertEqual([(h.item.title, h.location) for h in hits], [("Work", NODE)])
        self.assertEqual(node_path(self.find("Work")), "My notes/Work")

    def test_results_table(self):
        self.assertEqual(self.search("e"), 4)
        self.assertEqual(self.rows()[0], ["1", "My notes", BOTH, "My notes"])
        self.assertEqual([r[0] for r in self.rows()], ["1", "2", "3", "4"])
        self.assertIn("4 items found", self.dlg.count_label.text())
        self.assertEqual(self.dlg.results.headerItem().text(0), "Nr.")

    def test_nodes_and_articles_switches(self):
        self.dlg.nodes_box.setChecked(False)
        self.assertEqual(self.search("work"), 0)
        self.assertIn("0 items found", self.dlg.count_label.text())
        self.dlg.nodes_box.setChecked(True)
        self.dlg.articles_box.setChecked(False)
        self.assertEqual(self.search("line"), 0)
        self.dlg.nodes_box.setChecked(False)
        self.assertFalse(self.dlg.find_btn.isEnabled())

    def test_maximum_rows(self):
        self.dlg.max_spin.setValue(2)
        self.assertEqual(self.search("e"), 4)
        self.assertEqual(len(self.rows()), 2)
        self.assertIn("showing the first 2", self.dlg.count_label.text())

    def test_subtree(self):
        self.tree.setCurrentItem(self.find("Recipes"))
        self.dlg.show_dialog()
        self.dlg.subtree_radio.setChecked(True)
        self.dlg.text_edit.setText("e")
        self.dlg.run_search()
        self.assertEqual([r[1] for r in self.rows()], ["Recipes", "Soup"])

    # ------------------------------------------------------------ results

    def test_double_click_selects_node_and_hides(self):
        self.search("hot")
        self.dlg.results.itemDoubleClicked.emit(self.dlg.results.topLevelItem(0), 0)
        self.assertIs(self.tree.currentItem(), self.find("Soup"))
        self.assertEqual(self.win.editor.textCursor().selectedText(), "hot")
        self.assertFalse(self.dlg.isVisible())

    def test_enter_keeps_window_when_hide_is_off(self):
        self.dlg.hide_box.setChecked(False)
        self.search("work")
        self.dlg.results.setFocus()
        self.dlg.results.hasFocus = lambda: True
        QTest.keyClick(self.dlg, Qt.Key_Return)
        self.assertIs(self.tree.currentItem(), self.find("Work"))
        self.assertTrue(self.dlg.isVisible())

    def test_search_article_steps_through_matches(self):
        self.search("soup")
        self.assertTrue(self.dlg.search_article_btn.isEnabled())
        cursor_pos = []
        for _ in range(3):
            self.dlg.search_article_btn.click()
            c = self.win.editor.textCursor()
            self.assertEqual(c.selectedText().lower(), "soup")
            cursor_pos.append(c.selectionStart())
        self.assertEqual(cursor_pos, [0, 18, 0])   # wraps around
        self.search("work")
        self.assertFalse(self.dlg.search_article_btn.isEnabled())   # title only

    def test_deleted_node_and_new_file(self):
        self.search("hot")
        soup = self.find("Soup")
        soup.parent().removeChild(soup)
        self.assertFalse(self.dlg.open_selected())
        self.win.load_path(self.sample)
        self.assertEqual(self.rows(), [])

    def test_options_are_remembered(self):
        self.dlg.hide_box.setChecked(False)
        self.dlg.max_spin.setValue(50)
        self.search("e")
        self.dlg.close()
        win = MainWindow(QSettings(self.settings_path, QSettings.IniFormat))
        try:
            dlg = win.tree_search_dialog()
            self.assertFalse(dlg.hide_box.isChecked())
            self.assertEqual(dlg.max_spin.value(), 50)
        finally:
            win.close()
            win.deleteLater()


if __name__ == "__main__":
    unittest.main()
