# SPDX-License-Identifier: GPL-3.0-or-later
"""Window tests. They run without a display (Qt 'offscreen' platform)."""
import gc
import os
import shutil
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QSettings, Qt  # noqa: E402
from PyQt5.QtTest import QTest  # noqa: E402
from PyQt5.QtWidgets import QAbstractItemView, QApplication  # noqa: E402

from twigpad import hjt  # noqa: E402
from twigpad.ui.mainwindow import MainWindow  # noqa: E402
from tests.test_hjt import SAMPLE, windows_file  # noqa: E402

app = QApplication.instance() or QApplication([])


class WindowTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        settings = QSettings(os.path.join(self.dir, "settings.ini"), QSettings.IniFormat)
        self.win = MainWindow(settings)
        self.sample = os.path.join(self.dir, "notes.hjt")
        with open(self.sample, "wb") as fh:
            fh.write(windows_file(SAMPLE))
        self.assertTrue(self.win.load_path(self.sample))
        self.tree = self.win.tree

    def tearDown(self):
        self.win.setWindowModified(False)
        self.win.close()
        self.win.deleteLater()
        app.processEvents()
        shutil.rmtree(self.dir)

    def titles(self):
        return [(i.title, self._depth(i)) for i in self.tree.all_items()]

    @staticmethod
    def _depth(item):
        d = 0
        while item.parent() is not None:
            item, d = item.parent(), d + 1
        return d

    def find(self, title):
        return next(i for i in self.tree.all_items() if i.title == title)

    def select(self, title):
        self.tree.setCurrentItem(self.find(title))

    # ---------------------------------------------------------------- tests

    def test_open_shows_tree_and_article(self):
        self.assertEqual(self.titles(), [("My notes", 0), ("Recipes", 1), ("Soup", 2), ("Work", 1)])
        self.assertEqual(self.win.editor.toPlainText(), "Welcome text\nsecond line")
        self.assertFalse(self.win.isWindowModified())
        self.assertIn("notes.hjt", self.win.windowTitle())
        self.select("Recipes")
        self.assertEqual(self.win.editor.toPlainText(), "Café crème — 2€")

    def test_edit_is_kept_when_switching_nodes(self):
        self.select("Work")
        self.win.editor.setPlainText("changed text")
        self.assertTrue(self.win.isWindowModified())
        self.select("Soup")
        self.assertEqual(self.win.editor.toPlainText(), "")
        self.select("Work")
        self.assertEqual(self.win.editor.toPlainText(), "changed text")

    def test_add_rename_delete(self):
        self.select("Recipes")
        child = self.tree.add_child("Bread")
        self.assertEqual(self.titles()[2:4], [("Soup", 2), ("Bread", 2)])
        self.win.editor.setPlainText("flour, water")
        self.tree.add_sibling(after=False, title="Cake")
        self.assertEqual([t for t, _ in self.titles()][2:5], ["Soup", "Cake", "Bread"])
        child.setText(0, "  ")  # blank rename is refused
        self.assertEqual(child.title, "Untitled")
        self.select("Recipes")
        self.win.delete_node(confirm=False)
        self.assertEqual(self.titles(), [("My notes", 0), ("Work", 1)])
        self.assertEqual(self.tree.currentItem().title, "Work")

    def test_moves_keep_text_and_children(self):
        self.select("Work")
        self.assertTrue(self.tree.move_up())
        self.assertEqual(self.titles(), [("My notes", 0), ("Work", 1), ("Recipes", 1), ("Soup", 2)])
        self.assertFalse(self.tree.move_left())  # would become a second top node
        self.select("Soup")
        self.assertTrue(self.tree.move_left())
        self.assertEqual(self.titles(), [("My notes", 0), ("Work", 1), ("Recipes", 1), ("Soup", 1)])
        self.assertTrue(self.tree.move_right())
        self.assertEqual(self.titles(), [("My notes", 0), ("Work", 1), ("Recipes", 1), ("Soup", 2)])
        self.select("Work")
        self.assertTrue(self.tree.move_down())
        self.assertEqual(self.titles(), [("My notes", 0), ("Recipes", 1), ("Soup", 2), ("Work", 1)])
        self.select("Recipes")
        self.assertTrue(self.tree.move_down())
        self.assertEqual(self.titles(), [("My notes", 0), ("Work", 1), ("Recipes", 1), ("Soup", 2)])
        self.assertFalse(self.tree.move_down())
        gc.collect()
        self.assertEqual(self.find("Recipes").body, "Café crème — 2€")
        self.assertEqual(self.find("Work").body, "Line before\n\nLine after blank")

    def test_drop_moves_node_onto_another(self):
        class FakeDrop:
            def __init__(self, src): self.src = src
            def source(self): return self.src
            def pos(self): return None
            def setDropAction(self, a): pass
            def accept(self): pass
            def ignore(self): self.ignored = True

        self.select("Recipes")
        work = self.find("Work")
        self.tree.itemAt = lambda pos: work
        self.tree.dropIndicatorPosition = lambda: QAbstractItemView.OnItem
        self.tree.dropEvent(FakeDrop(self.tree))
        self.assertEqual(self.titles(), [("My notes", 0), ("Work", 1), ("Recipes", 2), ("Soup", 3)])
        # Dropping a node into its own child is refused.
        soup = self.find("Soup")
        self.select("Recipes")
        self.tree.itemAt = lambda pos: soup
        ev = FakeDrop(self.tree)
        self.tree.dropEvent(ev)
        self.assertTrue(ev.ignored)

    def test_save_round_trip(self):
        self.select("Soup")
        self.win.editor.setPlainText("hot\nsoup")
        self.tree.add_sibling(title="Salad")
        out = os.path.join(self.dir, "saved.hjt")
        self.assertTrue(self.win._write(out))
        self.assertFalse(self.win.isWindowModified())
        doc = hjt.load(out)
        self.assertEqual([(n.title, l) for n, l in doc.walk()],
                         [("My notes", 0), ("Recipes", 1), ("Soup", 2), ("Salad", 2), ("Work", 1)])
        self.assertEqual(doc.top_nodes[0].children[0].children[0].text, "hot\nsoup")
        self.assertEqual(doc.encoding, "cp1252")

    def test_backup_is_imported_not_overwritten(self):
        bak = os.path.join(self.dir, "notes.hjt.bak")
        shutil.copy(self.sample, bak)
        self.assertTrue(self.win.load_path(bak))
        self.assertIsNone(self.win.path)
        self.assertIn("notes.hjt", self.win.windowTitle())
        self.assertNotIn(".bak", self.win.windowTitle())
        self.assertTrue(self.win.isWindowModified())

    def test_delete_key_depends_on_focus(self):
        self.win.show()
        self.win.activateWindow()
        QTest.qWaitForWindowActive(self.win)
        self.select("Work")
        self.win.editor.setFocus()
        cur = self.win.editor.textCursor()
        cur.setPosition(0)
        self.win.editor.setTextCursor(cur)
        QTest.keyClick(self.win.editor, Qt.Key_Delete)
        self.assertEqual(self.win.editor.toPlainText(), "ine before\n\nLine after blank")
        self.assertEqual(len(self.tree.all_items()), 4)

        self.select("Soup")
        self.tree.setFocus()
        QTest.keyClick(self.tree, Qt.Key_Insert)
        app.processEvents()
        self.assertEqual(len(self.tree.all_items()), 5)
        self.assertEqual(self.tree.currentItem().title, "New node")

    # ------------------------------------------------ classic key layout

    def _key(self, key, mods=Qt.NoModifier, widget=None):
        widget = widget or self.tree
        widget.setFocus()
        QTest.keyClick(widget, key, mods)
        app.processEvents()
        # Adding a node opens the title editor; close it so the tree has the keys again.
        editor = QApplication.focusWidget()
        if editor is not None and editor not in (self.tree, self.win.editor):
            QTest.keyClick(editor, Qt.Key_Escape)
            app.processEvents()

    def test_classic_tree_keys(self):
        self.win.show()
        self.win.activateWindow()
        QTest.qWaitForWindowActive(self.win)
        self.select("Soup")
        self._key(Qt.Key_Insert)                                  # Ins: child
        self.assertEqual(self.titles()[3], ("New node", 3))
        self.select("Soup")
        self._key(Qt.Key_Insert, Qt.ShiftModifier)               # Shift+Ins: below
        self.assertEqual(self.titles()[4], ("New node", 2))
        self.select("Recipes")
        self._key(Qt.Key_Insert, Qt.ControlModifier | Qt.ShiftModifier)   # above
        self.assertEqual(self.titles()[1], ("New node", 1))
        self.select("Recipes")
        self._key(Qt.Key_Return)                                  # Enter: below
        n = len(self.tree.all_items())
        self.assertEqual(n, 8)

        self.select("Work")
        self._key(Qt.Key_Up, Qt.ShiftModifier)                    # Shift+Up: move
        self.assertEqual(self.tree.index_in_parent(self.find("Work")), 2)
        self._key(Qt.Key_Up, Qt.AltModifier)                      # Alt+Up: previous sibling
        self.assertEqual(self.tree.currentItem().title, "Recipes")

        # The top node: no siblings, no delete, no move.
        self.select("My notes")
        self._key(Qt.Key_Insert, Qt.ShiftModifier)
        self._key(Qt.Key_Return)
        self._key(Qt.Key_Delete)
        self._key(Qt.Key_X, Qt.ControlModifier)
        self.assertEqual(len(self.tree.all_items()), n)
        self.assertEqual(self.tree.topLevelItemCount(), 1)

        self._key(Qt.Key_Tab, Qt.ControlModifier)                 # Ctrl+Tab: switch pane
        self.assertTrue(self.win.editor.hasFocus())

    def test_paste_and_sort_keep_single_top(self):
        self.select("Recipes")
        self.win.copy_node()
        self.select("My notes")
        self.win.paste_node(as_child=False)   # next to the top node means inside it
        self.assertEqual(self.tree.topLevelItemCount(), 1)
        self.assertEqual(self.titles()[-2:], [("Recipes", 1), ("Soup", 2)])
        self.tree.add_child("Apple")
        self.select("My notes")
        self.win.sort_whole_tree()
        self.assertEqual([t for t, d in self.titles() if d == 1], ["Recipes", "Recipes", "Work"])
        self.assertEqual(self.find("Soup").title, "Soup")

    def test_file_with_several_top_nodes_is_wrapped(self):
        path = os.path.join(self.dir, "multi.hjt")
        with open(path, "w", encoding="cp1252", newline="\r\n") as fh:
            fh.write(f"<Treepad version 2.7>\ndt=Text\n<node>\nA\n0\n<end node> {hjt.MAGIC}\n"
                     f"dt=Text\n<node>\nB\n0\n<end node> {hjt.MAGIC}\n")
        shown = []
        self.win._show_repairs = lambda doc: shown.extend(doc.warnings)
        self.assertTrue(self.win.load_path(path))
        self.assertEqual(self.titles(), [("multi", 0), ("A", 1), ("B", 1)])
        self.assertTrue(any("only one top node" in w for w in shown))
        self.assertTrue(self.win.isWindowModified())

    # -------------------------------------------------------------- links

    def test_links(self):
        opened = []
        self.win._open_url = lambda url: opened.append(url.toString()) or True
        self.select("Soup")
        self.win.copy_node_link()
        self.assertEqual(QApplication.clipboard().text(), "[node://My notes/Recipes/Soup]")

        self.select("Work")
        self.win.editor.setPlainText("see [node://my notes/recipes/soup] and [www.example.com] and "
                                     "[file://missing.txt]")
        cur = self.win.editor.textCursor()
        cur.setPosition(10)
        self.win.editor.setTextCursor(cur)
        self.assertTrue(self.win.follow_link())
        self.assertEqual(self.tree.currentItem().title, "Soup")

        self.select("Work")
        self.assertEqual(self.win.editor.toPlainText()[:4], "see ")  # edit was kept
        cur = self.win.editor.textCursor()
        cur.setPosition(45)
        self.win.editor.setTextCursor(cur)
        self.assertTrue(self.win.follow_link())
        self.assertEqual(opened, ["http://www.example.com"])
        self.assertFalse(self.win.follow_link("file://missing.txt"))
        target = os.path.join(self.dir, "here.txt")
        open(target, "w").close()
        self.assertTrue(self.win.follow_link(f"file://{target}"))
        self.assertTrue(opened[-1].endswith("/here.txt"))
        self.assertFalse(self.win.follow_link("node://My notes/Nowhere"))

        # Ctrl+H in the article follows the link under the cursor.
        self.win.show()
        self.win.activateWindow()
        QTest.qWaitForWindowActive(self.win)
        self.select("Work")
        cur = self.win.editor.textCursor()
        cur.setPosition(12)
        self.win.editor.setTextCursor(cur)
        self._key(Qt.Key_H, Qt.ControlModifier, widget=self.win.editor)
        self.assertEqual(self.tree.currentItem().title, "Soup")


    # ------------------------------------------------------ step 3 features

    def test_find_next_previous_and_all(self):
        dlg = self.win.find_dialog()
        dlg.show_dialog()
        dlg.find_edit.setText("line")
        dlg.find()
        self.assertEqual(self.tree.currentItem().title, "My notes")
        self.assertEqual(self.win.editor.textCursor().selectedText(), "line")
        dlg.find()
        self.assertEqual(self.tree.currentItem().title, "Work")
        self.assertEqual(self.win.editor.textCursor().selectedText(), "Line")
        self.assertEqual(self.win.editor.textCursor().selectionStart(), 0)
        dlg.find()
        self.assertEqual(self.win.editor.textCursor().selectionStart(), 13)
        dlg.find(backward=True)
        self.assertEqual(self.win.editor.textCursor().selectionStart(), 0)
        self.assertEqual(dlg.find_all(), 3)
        self.assertIn("3 matches in 2 nodes", dlg.status.text())
        dlg.case_box.setChecked(True)
        self.assertEqual(dlg.find_all(), 1)
        dlg.find_edit.setText("recipes")
        dlg.case_box.setChecked(False)
        dlg.find()
        self.assertEqual(self.tree.currentItem().title, "Recipes")
        self.assertIn("title", dlg.status.text())

    def test_find_in_selected_branch_only(self):
        self.select("Recipes")
        dlg = self.win.find_dialog()
        dlg.show_dialog()
        dlg.scope_combo.setCurrentIndex(1)
        dlg.find_edit.setText("line")
        self.assertEqual(dlg.find_all(), 0)
        dlg.find_edit.setText("crème")
        self.assertEqual(dlg.find_all(), 1)

    def test_replace_one_and_all(self):
        dlg = self.win.find_dialog()
        dlg.show_dialog(replace=True)
        dlg.find_edit.setText("crème")
        dlg.replace_edit.setText("cream")
        dlg.find()
        dlg.replace_one()
        self.assertEqual(self.find("Recipes").body, "Café crème — 2€".replace("crème", "cream"))
        dlg.find_edit.setText("line")
        dlg.replace_edit.setText("row")
        self.assertEqual(dlg.replace_all(), 3)
        self.win._commit_editor()
        self.assertEqual(self.find("Work").body, "row before\n\nrow after blank")
        self.assertEqual(self.find("My notes").body, "Welcome text\nsecond row")
        self.assertTrue(self.win.isWindowModified())

    def test_copy_cut_paste_nodes(self):
        self.select("Recipes")
        self.win.copy_node()
        self.select("Work")
        self.win.paste_node()
        self.assertEqual(self.titles(), [("My notes", 0), ("Recipes", 1), ("Soup", 2), ("Work", 1),
                                         ("Recipes", 1), ("Soup", 2)])
        self.assertEqual(self.tree.currentItem().body, "Café crème — 2€")
        self.select("Work")
        self.win.cut_node()
        self.assertEqual([t for t, _ in self.titles()].count("Work"), 0)
        self.select("Soup")
        self.win.paste_node(as_child=True)
        self.assertEqual(self.titles()[3], ("Work", 3))
        QApplication.clipboard().setText("Shopping\nmilk\neggs")
        self.win.paste_node()
        self.assertEqual(self.tree.currentItem().title, "Shopping")
        self.assertEqual(self.tree.currentItem().body, "Shopping\nmilk\neggs")

    def test_import_export(self):
        other = os.path.join(self.dir, "old.hjt.bak")
        shutil.copy(self.sample, other)
        self.select("Work")
        self.assertTrue(self.win.import_tree_file(other))
        self.assertEqual(self.titles()[4:], [("My notes", 2), ("Recipes", 3), ("Soup", 4), ("Work", 3)])
        txt = os.path.join(self.dir, "todo.txt")
        with open(txt, "wb") as fh:
            fh.write("buy bread\r\ncall Zoë\r\n".encode("cp1252"))
        self.select("Soup")
        self.assertTrue(self.win.import_text_file(txt))
        self.assertEqual(self.tree.currentItem().title, "todo")
        self.assertEqual(self.tree.currentItem().body, "buy bread\ncall Zoë\n")
        out = os.path.join(self.dir, "out.txt")
        self.select("Recipes")
        self.assertTrue(self.win.export_text("branch", out))
        with open(out, encoding="utf-8") as fh:
            content = fh.read()
        self.assertTrue(content.startswith("1. Recipes\n"))
        self.assertIn("1.1. Soup", content)
        self.assertIn("1.1.1. todo", content)

    def test_backup_once_per_session_and_recent(self):
        with open(self.sample, "rb") as fh:
            original = fh.read()
        self.win.editor.setPlainText("edit 1")
        self.assertTrue(self.win.save())
        self.win.editor.setPlainText("edit 2")
        self.assertTrue(self.win.save())
        with open(self.sample + ".bak", "rb") as fh:
            self.assertEqual(fh.read(), original)
        self.assertEqual(hjt.load(self.sample).top_nodes[0].text, "edit 2")
        self.assertEqual(self.win.recent_files()[0], os.path.abspath(self.sample))

    def test_autosave(self):
        self.win.editor.setPlainText("typed")
        self.win.autosave()
        self.assertFalse(self.win.isWindowModified())
        self.assertEqual(hjt.load(self.sample).top_nodes[0].text, "typed")

    def test_insert_date_and_sort(self):
        from PyQt5.QtCore import QDate
        self.win.editor.setPlainText("")
        self.win.insert_datetime("date")
        year = str(QDate.currentDate().year())
        self.assertTrue(year in self.win.editor.toPlainText() or year[2:] in self.win.editor.toPlainText())
        self.select("My notes")
        self.tree.add_child("Apples")
        self.select("My notes")
        self.win.sort_children()
        self.assertEqual([t for t, d in self.titles() if d == 1], ["Apples", "Recipes", "Work"])
        self.assertEqual(self.find("Recipes").childCount(), 1)


if __name__ == "__main__":
    unittest.main()
