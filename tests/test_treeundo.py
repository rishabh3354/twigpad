# SPDX-License-Identifier: GPL-3.0-or-later
"""Undo and redo of changes to the tree."""
import os
import shutil
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QSettings, Qt  # noqa: E402
from PyQt5.QtTest import QTest  # noqa: E402
from PyQt5.QtWidgets import QAbstractItemView, QApplication, QLineEdit  # noqa: E402

from twigpad.model import Document, Node  # noqa: E402
from twigpad.ui import popups, treeundo  # noqa: E402
from twigpad.ui.mainwindow import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])


def sample() -> Document:
    doc = Document()
    top = doc.root.add_child(Node("My notes", "top text"))
    work = top.add_child(Node("Work", "work text"))
    work.add_child(Node("Meetings", "monday"))
    work.add_child(Node("Plans", "q1"))
    top.add_child(Node("Recipes", "food"))
    top.add_child(Node("Books", "reading"))
    return doc


class TreeUndoTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.win = MainWindow(QSettings(os.path.join(self.dir, "s.ini"), QSettings.IniFormat))
        self.win._set_document(sample())
        self.tree = self.win.tree
        self.tree.expandAll()
        self.tree.setFocus()

    def tearDown(self):
        popups.auto_answer = None
        self.win.setWindowModified(False)
        self.win.close()
        self.win.deleteLater()
        app.processEvents()
        shutil.rmtree(self.dir)

    def item(self, title):
        return next(i for i in self.tree.all_items() if i.title == title)

    def select(self, title):
        self.tree.setCurrentItem(self.item(title))
        return self.item(title)

    def shape(self):
        """(title, parent title, article) for every node, in order."""
        return [(i.title, i.parent().title if i.parent() else None, i.body) for i in self.tree.all_items()]

    def test_undo_and_redo_delete_branch(self):
        before = self.shape()
        work = self.select("Work")
        self.tree.collapseItem(self.item("Meetings"))
        self.win.delete_node(confirm=False)
        self.assertNotIn("Work", [t for t, *_ in self.shape()])
        self.assertEqual(self.win.act_tree_undo.text(), "&Undo Delete “Work”")
        self.assertTrue(self.win.undo_tree())
        self.assertEqual(self.shape(), before)
        self.assertIs(self.item("Work"), work)                 # the very same node comes back
        self.assertIs(self.tree.currentItem(), work)            # ...and is selected
        self.assertTrue(work.isExpanded())
        self.assertEqual(self.win.editor.toPlainText(), "work text")
        self.assertTrue(self.win.redo_tree())
        self.assertNotIn("Work", [t for t, *_ in self.shape()])
        self.assertFalse(self.win.tree_history.can_redo())

    def test_text_typed_just_before_delete_comes_back(self):
        self.select("Recipes")
        self.win.editor.setPlainText("food, and soup")
        self.win.delete_node(confirm=False)
        self.win.undo_tree()
        self.assertEqual(self.item("Recipes").body, "food, and soup")
        self.assertEqual(self.win.editor.toPlainText(), "food, and soup")

    def test_add_and_name_is_one_step(self):
        self.select("Books")
        new = self.tree.add_sibling()
        delegate = self.tree.itemDelegate()
        editor = QLineEdit("Films")
        delegate.setModelData(editor, self.tree.model(), self.tree.indexFromItem(new))
        self.assertEqual(new.title, "Films")
        self.assertEqual(len(self.win.tree_history.changes), 1)
        self.win.undo_tree()
        self.assertNotIn("Films", [t for t, *_ in self.shape()])
        self.win.redo_tree()
        self.assertEqual(self.item("Films").parent().title, "My notes")

    def test_rename(self):
        item = self.select("Books")
        editor = QLineEdit("  Novels   and poems ")
        self.tree.itemDelegate().setModelData(editor, self.tree.model(), self.tree.indexFromItem(item))
        self.assertEqual(item.title, "Novels and poems")
        self.assertEqual(self.win.tree_history.undo_label(), "Rename")
        self.win.undo_tree()
        self.assertEqual(item.title, "Books")

    def test_moves(self):
        before = self.shape()
        self.select("Recipes")
        self.tree.move_right()        # into Work, after Plans
        self.tree.move_up()           # before Plans
        self.assertEqual(self.item("Recipes").parent().title, "Work")
        self.assertEqual([c.title for c in self.tree.all_items_under(self.item("Work"))],
                         ["Work", "Meetings", "Recipes", "Plans"])
        self.assertEqual(self.win.tree_history.undo_label(), "Move Up")
        self.win.undo_tree()
        self.win.undo_tree()
        self.assertEqual(self.shape(), before)
        self.win.redo_tree()
        self.win.redo_tree()
        self.assertEqual(self.item("Recipes").parent().title, "Work")

    def test_drag_and_drop(self):
        class FakeDrop:
            def __init__(self, src): self.src = src
            def keyboardModifiers(self): return Qt.NoModifier
            def source(self): return self.src
            def pos(self): return None
            def setDropAction(self, a): pass
            def accept(self): pass
            def ignore(self): pass

        before = self.shape()
        self.select("Books")
        work = self.item("Work")
        self.tree.itemAt = lambda pos: work
        self.tree.dropIndicatorPosition = lambda: QAbstractItemView.OnItem
        self.tree.dropEvent(FakeDrop(self.tree))
        self.assertEqual(self.item("Books").parent().title, "Work")
        self.assertEqual(self.win.tree_history.undo_label(), "Move “Books”")
        self.win.undo_tree()
        self.assertEqual(self.shape(), before)

    def test_sort_cut_paste_and_import(self):
        before = self.shape()
        self.select("My notes")
        self.win.sort_children()
        self.assertEqual([c.title for c in self.tree.all_items()[1:2]], ["Books"])
        self.select("Recipes")
        self.win.cut_node()
        self.select("Work")
        self.win.paste_node(as_child=True)
        self.assertEqual(self.item("Recipes").parent().title, "Work")
        labels = [c.label for c in self.win.tree_history.changes]
        self.assertEqual(labels, ["Sort", "Cut “Recipes”", "Paste"])
        csv = os.path.join(self.dir, "a.csv")
        with open(csv, "w") as fh:
            fh.write("Tea,green\nCoffee,black\n")
        self.win.import_csv_file(csv)
        self.assertEqual(self.win.tree_history.undo_label(), "Import")
        for _ in range(4):
            self.assertTrue(self.win.undo_tree())
        self.assertEqual(self.shape(), before)
        self.assertFalse(self.win.undo_tree())

    def test_icon_and_replace_all(self):
        self.select("Books")
        self.win.set_note_look(icon="star")
        self.assertEqual(self.win.tree_history.undo_label(), "Change Icon")
        self.win.undo_tree()
        self.assertEqual(self.item("Books").icon, "")
        dlg = self.win.find_dialog()
        dlg.find_edit.setText("text")
        dlg.replace_edit.setText("TEXT")
        self.assertGreater(dlg.replace_all(), 0)
        self.assertEqual(self.item("Work").body, "work TEXT")
        self.assertEqual(self.win.tree_history.undo_label(), "Replace All")
        self.win.undo_tree()
        self.assertEqual(self.item("Work").body, "work text")
        self.assertEqual(self.item("My notes").body, "top text")

    def test_edit_menu_follows_the_pane(self):
        self.win.show()
        self.select("Books")
        self.win.delete_node(confirm=False)
        self.tree.setFocus()
        app.processEvents()
        self.win._last_pane = "tree"
        self.win._update_undo_actions()
        self.assertEqual(self.win.act_undo.text(), "&Undo Delete “Books”")
        self.assertTrue(self.win.act_undo.isEnabled())
        self.win._last_pane = "editor"
        self.win.editor.setFocus()
        app.processEvents()
        self.win._update_undo_actions()
        self.assertIn(self.win.act_undo.text(), ("&Undo", "&Undo Typing"))
        self.win.tree.setFocus()
        app.processEvents()
        self.win._last_pane = "tree"
        self.win.act_undo.trigger()
        self.assertIn("Books", [t for t, *_ in self.shape()])

    def test_ctrl_z_in_the_tree(self):
        self.win.show()
        self.win.activateWindow()
        self.select("Books")
        self.win.delete_node(confirm=False)
        self.tree.setFocus()
        app.processEvents()
        QTest.keyClick(self.tree, Qt.Key_Z, Qt.ControlModifier)
        app.processEvents()
        if "Books" not in [t for t, *_ in self.shape()]:
            self.skipTest("this Qt platform does not deliver shortcuts offscreen")
        QTest.keyClick(self.tree, Qt.Key_Y, Qt.ControlModifier)
        self.assertNotIn("Books", [t for t, *_ in self.shape()])

    def test_tree_menu_has_undo(self):
        actions = self.win._node_menu_actions()
        self.assertIs(actions[0], self.win.act_tree_undo)
        self.assertIs(actions[1], self.win.act_tree_redo)

    def test_new_change_clears_redo_and_load_clears_history(self):
        self.select("Books")
        self.tree.move_up()
        self.win.undo_tree()
        self.assertTrue(self.win.tree_history.can_redo())
        self.tree.move_up()
        self.assertFalse(self.win.tree_history.can_redo())
        self.win.new_file(confirm=False)
        self.assertFalse(self.win.tree_history.can_undo())
        self.assertFalse(self.win.act_tree_undo.isEnabled())

    def test_read_only_blocks_undo(self):
        self.select("Books")
        self.tree.move_up()
        self.win.set_read_only(True)
        self.assertFalse(self.win.act_tree_undo.isEnabled())
        self.assertFalse(self.win.undo_tree())
        self.win.set_read_only(False)
        self.assertTrue(self.win.undo_tree())

    def test_focused_branch_and_tabs(self):
        work = self.select("Work")
        self.win.set_tab_root(work)
        self.select("Plans")
        self.tree.add_child()
        self.win.undo_tree()
        self.assertIs(self.tree.hoisted, work)
        # Delete the focused branch from outside, then undo: the tab shows the whole tree.
        self.win.set_tab_root(None)
        self.select("Work")
        self.win.open_branch_tab(work)
        self.win.tabs.setCurrentIndex(0)
        self.select("Work")
        self.win.delete_node(confirm=False)
        self.win.tabs.setCurrentIndex(1)
        self.assertIsNone(self.tree.hoisted)
        self.win.undo_tree()
        self.assertTrue(self.tree.contains(work))

    def test_history_limit(self):
        self.select("Books")
        for _ in range(treeundo.LIMIT + 20):
            self.tree.move_up() or self.tree.move_down()
        self.assertEqual(len(self.win.tree_history.changes), treeundo.LIMIT)


if __name__ == "__main__":
    unittest.main()
