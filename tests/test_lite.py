# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for the format menu, CSV/HTML/tree export and import, tree moves,
view modes, read-only mode, automatic paste and portable settings."""
import os
import shutil
import stat
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QSettings  # noqa: E402
from PyQt5.QtGui import QTextCursor  # noqa: E402
from PyQt5.QtWidgets import QAbstractItemView, QApplication  # noqa: E402

from twigpad import export, hjt, importers, portable, textfmt  # noqa: E402
from twigpad.model import Node  # noqa: E402
from twigpad.ui.mainwindow import MainWindow  # noqa: E402
from tests.test_hjt import SAMPLE, windows_file  # noqa: E402

app = QApplication.instance() or QApplication([])


class TextFormatTests(unittest.TestCase):
    def test_case(self):
        self.assertEqual(textfmt.to_upper("abc Def"), "ABC DEF")
        self.assertEqual(textfmt.to_lower("ABC Def"), "abc def")

    def test_remove_leading_spaces(self):
        self.assertEqual(textfmt.remove_leading_spaces("  a\n\tb\nc  \n"), "a\nb\nc  \n")

    def test_remove_leading_spaces_and_returns(self):
        mail = ("> Hello there,\n"
                ">   this line was wrapped\n"
                "> by the mail program.\n"
                ">\n"
                "> > Second paragraph\n"
                ">  continues here.\n\n\n")
        self.assertEqual(textfmt.remove_leading_spaces_and_returns(mail),
                         "Hello there, this line was wrapped by the mail program.\n\n"
                         "Second paragraph continues here.")


class ImportExportHelperTests(unittest.TestCase):
    def test_csv_rows_become_nodes(self):
        nodes = importers.csv_to_nodes('name,phone,city\nAnn,"555, 1",Oslo\n\n,x\nBob,2,Rome\n')
        self.assertEqual([n.title for n in nodes], ["name", "Ann", "Untitled", "Bob"])
        self.assertEqual(nodes[1].text, "555, 1\nOslo")

    def test_csv_semicolon_and_tab(self):
        self.assertEqual(importers.csv_to_nodes("a;1\nb;2\n")[1].text, "2")
        self.assertEqual(importers.csv_to_nodes("a\t1\nb\t2\n")[0].text, "1")

    def test_html_page(self):
        root = Node("Top <1>", "line & text")
        root.add_child(Node("Child", "inner"))
        page = export.html_page([root], "My file")
        self.assertIn("<title>My file</title>", page)
        self.assertIn("<h1 id='n1'>Top &lt;1&gt;</h1>", page)
        self.assertIn("<pre>line &amp; text</pre>", page)
        self.assertIn("<h2 id='n2'>Child</h2>", page)
        self.assertIn("<a href='#n2'>Child</a>", page)  # table of contents

    def test_portable_ini(self):
        d = tempfile.mkdtemp()
        try:
            prog = os.path.join(d, "twigpad")
            self.assertIsNone(portable.portable_ini(prog, {}))
            open(os.path.join(d, "twigpad.ini"), "w").close()
            self.assertEqual(portable.portable_ini(prog, {}), os.path.join(d, "twigpad.ini"))
            # Inside an AppImage the program runs from a mount point; the ini
            # file sits next to the .AppImage file itself.
            self.assertEqual(portable.portable_ini("/tmp/.mount_x/usr/bin/twigpad",
                                                   {"APPIMAGE": os.path.join(d, "Twigpad.AppImage")}),
                             os.path.join(d, "twigpad.ini"))
        finally:
            shutil.rmtree(d)


class LiteWindowTests(unittest.TestCase):
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
        os.chmod(self.sample, stat.S_IRUSR | stat.S_IWUSR)
        self.win.setWindowModified(False)
        self.win.close()
        self.win.deleteLater()
        app.processEvents()
        shutil.rmtree(self.dir)

    def titles(self):
        out = []
        for i in self.tree.all_items():
            d, it = 0, i
            while it.parent() is not None:
                it, d = it.parent(), d + 1
            out.append((i.title, d))
        return out

    def find(self, title):
        return next(i for i in self.tree.all_items() if i.title == title)

    def select(self, title):
        self.tree.setCurrentItem(self.find(title))

    def write(self, name, text):
        path = os.path.join(self.dir, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path

    # ------------------------------------------------------------ format

    def test_format_whole_article_and_undo(self):
        self.win.editor.setPlainText("  hello\n  world")
        self.assertTrue(self.win.format_text(textfmt.to_upper))
        self.assertEqual(self.win.editor.toPlainText(), "  HELLO\n  WORLD")
        self.assertTrue(self.win.format_text(textfmt.remove_leading_spaces))
        self.assertEqual(self.win.editor.toPlainText(), "HELLO\nWORLD")
        self.win.editor.undo()
        self.assertEqual(self.win.editor.toPlainText(), "  HELLO\n  WORLD")
        self.assertFalse(self.win.format_text(textfmt.to_upper))  # nothing to change

    def test_format_selection_only(self):
        self.win.editor.setPlainText("one two three")
        cur = self.win.editor.textCursor()
        cur.setPosition(4)
        cur.setPosition(7, QTextCursor.KeepAnchor)
        self.win.editor.setTextCursor(cur)
        self.win.format_text(textfmt.to_upper)
        self.assertEqual(self.win.editor.toPlainText(), "one TWO three")
        self.assertEqual(self.win.editor.textCursor().selectedText(), "TWO")

    # ------------------------------------------------------------ tree moves

    def test_next_siblings_move_right_and_children_move_left(self):
        self.select("Recipes")
        self.assertEqual(self.win.move_next_siblings_right(), 1)
        self.assertEqual(self.titles(), [("My notes", 0), ("Recipes", 1), ("Soup", 2), ("Work", 2)])
        self.assertEqual(self.tree.currentItem().title, "Recipes")
        self.assertTrue(self.win.isWindowModified())
        self.assertEqual(self.win.move_children_left(), 2)
        self.assertEqual(self.titles(), [("My notes", 0), ("Recipes", 1), ("Soup", 1), ("Work", 1)])
        # The top node keeps its children: they can't become top nodes.
        self.select("My notes")
        self.assertEqual(self.win.move_children_left(), 0)
        self.assertFalse(self.win.act_children_left.isEnabled())
        self.select("Work")
        self.assertFalse(self.win.act_siblings_right.isEnabled())

    def test_expand_branch(self):
        top = self.find("My notes")
        self.select("My notes")
        self.win.expand_branch(False, True)
        self.assertFalse(top.isExpanded())
        self.win.expand_branch(True, False)
        self.assertTrue(top.isExpanded())
        self.assertFalse(self.find("Recipes").isExpanded())
        self.win.expand_branch(True, True)
        self.assertTrue(self.find("Recipes").isExpanded())

    def test_copy_and_paste_node_name(self):
        self.select("Soup")
        self.win.copy_node_name()
        self.assertEqual(QApplication.clipboard().text(), "Soup")
        QApplication.clipboard().setText("\n  Lentil   soup \nmore")
        self.assertTrue(self.win.paste_node_name())
        self.assertEqual(self.tree.currentItem().title, "Lentil soup")
        self.assertTrue(self.win.isWindowModified())

    # ------------------------------------------------------------ import / export

    def test_import_several_text_files_and_csv(self):
        a = self.write("alpha.txt", "A text")
        b = self.write("beta.txt", "B text")
        self.select("Work")
        self.assertTrue(self.win.import_text_files([a, b]))
        self.assertEqual(self.titles()[-2:], [("alpha", 2), ("beta", 2)])
        self.assertEqual(self.find("beta").body, "B text")
        csv_path = self.write("people.csv", "Ann,555\nBob,777\n")
        self.select("Work")
        self.assertTrue(self.win.import_csv_file(csv_path))
        self.assertEqual(self.find("Bob").body, "777")
        self.assertEqual(self.find("Bob").parent().title, "Work")

    def test_insert_text_file(self):
        path = self.write("part.txt", "inserted\r\nlines")
        self.win.editor.setPlainText("start ")
        self.win.editor.moveCursor(QTextCursor.End)
        self.assertTrue(self.win.insert_text_file(path))
        self.assertEqual(self.win.editor.toPlainText(), "start inserted\nlines")

    def test_export_html_and_tree_file(self):
        self.select("Recipes")
        page = os.path.join(self.dir, "out.html")
        self.assertTrue(self.win.export_file("html", "branch", page))
        with open(page, encoding="utf-8") as fh:
            html = fh.read()
        self.assertIn(">Recipes</h1>", html)
        self.assertIn(">Soup</h2>", html)
        self.assertNotIn("Work", html)
        branch = os.path.join(self.dir, "recipes.hjt")
        self.assertTrue(self.win.export_file("hjt", "branch", branch))
        doc = hjt.load(branch)
        self.assertEqual([(n.title, lvl) for n, lvl in doc.walk()], [("Recipes", 0), ("Soup", 1)])
        # Exporting must not change the open file.
        self.assertEqual(self.win.path, self.sample)

    def test_export_whole_file_as_html(self):
        page = os.path.join(self.dir, "all.html")
        self.assertTrue(self.win.export_file("html", "all", page))
        with open(page, encoding="utf-8") as fh:
            html = fh.read()
        self.assertIn("<title>notes</title>", html)
        self.assertIn("<nav>", html)
        self.assertIn(">Work</h2>", html)

    # ------------------------------------------------------------ view modes

    def test_view_modes_are_remembered(self):
        self.win.show()
        self.win.set_view_mode("tree")
        self.assertTrue(self.tree.isVisible())
        self.assertFalse(self.win.editor.isVisible())
        self.win.set_view_mode("article")
        self.assertFalse(self.tree.isVisible())
        self.assertTrue(self.win.editor.isVisible())
        self.assertTrue(self.win.act_view_modes["article"].isChecked())
        other = MainWindow(self.win.settings)
        try:
            self.assertEqual(other.view_mode, "article")
        finally:
            other.close()
            other.deleteLater()
        self.win.set_view_mode("both")

    # ------------------------------------------------------------ read only

    def test_read_only_blocks_changes(self):
        self.win.set_read_only(True)
        self.assertTrue(self.win.editor.isReadOnly())
        self.assertTrue(self.win.act_read_only.isChecked())
        self.select("Recipes")
        for act in (self.win.act_add_child, self.win.act_delete, self.win.act_move_down,
                    self.win.act_paste_child, self.win.act_save, self.win.act_upper,
                    self.win.act_replace, self.win.act_import_tree):
            self.assertFalse(act.isEnabled(), act.text())
        self.assertTrue(self.win.act_copy_node.isEnabled())
        self.assertEqual(self.tree.dragDropMode(), QAbstractItemView.NoDragDrop)
        self.assertEqual(self.win.move_children_left(), 0)
        self.assertFalse(self.win.import_text_files([self.write("x.txt", "x")]))
        self.win.set_read_only(False)
        self.assertFalse(self.win.editor.isReadOnly())
        self.assertTrue(self.win.act_add_child.isEnabled())
        self.assertEqual(self.tree.dragDropMode(), QAbstractItemView.InternalMove)

    @unittest.skipIf(hasattr(os, "geteuid") and os.geteuid() == 0, "root can write any file")
    def test_unwritable_file_opens_read_only(self):
        os.chmod(self.sample, stat.S_IRUSR)
        self.assertTrue(self.win.load_path(self.sample))
        self.assertTrue(self.win.read_only)
        self.win.new_file(confirm=False)
        self.assertFalse(self.win.read_only)

    # ------------------------------------------------------------ automatic paste

    def test_automatic_paste(self):
        self.win._clipboard_is_ours = lambda: False   # pretend another program copied
        self.win.editor.setPlainText("Collected:")
        self.win.act_auto_paste.setChecked(True)
        QApplication.clipboard().setText("first clip")
        app.processEvents()
        QApplication.clipboard().setText("second clip\r\n")
        app.processEvents()
        self.assertEqual(self.win.editor.toPlainText(), "Collected:\nfirst clip\nsecond clip\n")
        self.win.act_auto_paste.setChecked(False)
        QApplication.clipboard().setText("ignored")
        app.processEvents()
        self.assertNotIn("ignored", self.win.editor.toPlainText())

    def test_minimize_to_tray_falls_back(self):
        self.win.show()
        self.win.minimize_to_tray()   # no tray on the offscreen platform: minimizes
        app.processEvents()
        self.win.restore_from_tray()
        self.assertTrue(self.win.isVisible())


if __name__ == "__main__":
    unittest.main()
