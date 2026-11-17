# SPDX-License-Identifier: GPL-3.0-or-later
"""Options and conveniences: pane colours, startup and closing choices, Tab
switching, whole-article cut/copy/delete, toolbars, portable settings."""
import os
import shutil
import sys
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QSettings, Qt  # noqa: E402
from PyQt5.QtGui import QPalette  # noqa: E402
from PyQt5.QtTest import QTest  # noqa: E402
from PyQt5.QtWidgets import QAbstractItemView, QApplication  # noqa: E402

from twigpad import hjt, portable  # noqa: E402
from twigpad.ui.finddialog import SCOPE_NODE  # noqa: E402
from twigpad.ui.mainwindow import MainWindow  # noqa: E402
from tests.test_hjt import SAMPLE, windows_file  # noqa: E402

app = QApplication.instance() or QApplication([])


class OptionTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.settings_path = os.path.join(self.dir, "settings.ini")
        self.sample = os.path.join(self.dir, "notes.hjt")
        with open(self.sample, "wb") as fh:
            fh.write(windows_file(SAMPLE))
        self.win = self.make_window()
        self.assertTrue(self.win.load_path(self.sample))
        self.tree = self.win.tree

    def make_window(self):
        return MainWindow(QSettings(self.settings_path, QSettings.IniFormat))

    def tearDown(self):
        self.win.setWindowModified(False)
        self.win.close()
        self.win.deleteLater()
        app.processEvents()
        shutil.rmtree(self.dir)

    def select(self, title):
        self.tree.setCurrentItem(next(i for i in self.tree.all_items() if i.title == title))

    # ------------------------------------------------------------ colours

    def test_pane_colours_apply_and_reset(self):
        self.win.set_pane_color("tree_bg", "#112233")
        self.win.set_pane_color("article_fg", "#445566")
        self.assertEqual(self.tree.palette().color(QPalette.Base).name(), "#112233")
        self.assertEqual(self.win.editor.palette().color(QPalette.Text).name(), "#445566")
        self.assertEqual(self.win.settings.value("colors/tree_bg"), "#112233")
        self.win.set_pane_color("tree_bg", "")
        self.assertEqual(self.tree.palette().color(QPalette.Base),
                         QApplication.palette(self.tree).color(QPalette.Base))

    # ------------------------------------------------------------ find

    def test_ctrl_f_scope_follows_focus(self):
        self.win.editor.hasFocus = lambda: True
        self.win.find_here()
        self.assertEqual(self.win.find_dialog().scope_combo.currentIndex(), SCOPE_NODE)
        self.win.editor.hasFocus = lambda: False
        self.win.find_here()
        self.assertTrue(self.win.tree_search_dialog().isVisible())

    # ------------------------------------------------------------ article edits

    def test_copy_and_cut_whole_article_without_selection(self):
        ed = self.win.editor
        self.win.copy_article()
        self.assertEqual(QApplication.clipboard().text(), "Welcome text\nsecond line")
        self.assertFalse(ed.textCursor().hasSelection())
        self.win.cut_article()
        self.assertEqual(ed.toPlainText(), "")
        ed.undo()
        self.assertEqual(ed.toPlainText(), "Welcome text\nsecond line")

    def test_delete_clears_article_after_asking(self):
        ed = self.win.editor
        self.win._confirm_clear_article = lambda: False
        self.win.delete_article_text()
        self.assertEqual(ed.toPlainText(), "Welcome text\nsecond line")
        self.win._confirm_clear_article = lambda: True
        self.win.delete_article_text()
        self.assertEqual(ed.toPlainText(), "")

    def test_replace_article_from_file_is_undoable(self):
        path = os.path.join(self.dir, "new.txt")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("from a file\n")
        self.assertTrue(self.win.replace_article_from_file(path))
        self.assertEqual(self.win.editor.toPlainText(), "from a file\n")
        self.win.editor.undo()
        self.assertEqual(self.win.editor.toPlainText(), "Welcome text\nsecond line")

    # ------------------------------------------------------------ Tab switching

    def test_tab_switches_panes_when_option_is_on(self):
        calls = []
        self.win.switch_pane = lambda: calls.append(1)
        QTest.keyClick(self.win.editor, Qt.Key_Tab)
        self.assertEqual(calls, [])
        self.assertIn("\t", self.win.editor.toPlainText())
        self.win.act_tab_switch.setChecked(True)
        self.win.set_tab_switch(True)
        self.assertEqual([k.toString() for k in self.win.act_switch_pane.shortcuts()], ["F6"])
        before = self.win.editor.toPlainText()
        QTest.keyClick(self.win.editor, Qt.Key_Tab)
        self.assertEqual(calls, [1])
        self.assertEqual(self.win.editor.toPlainText(), before)
        QTest.keyClick(self.win.editor, Qt.Key_Tab, Qt.ControlModifier)
        self.assertEqual(self.win.editor.toPlainText().count("\t"), before.count("\t") + 1)
        self.win.set_tab_switch(False)
        self.assertIn("Ctrl+Tab", [k.toString() for k in self.win.act_switch_pane.shortcuts()])

    def test_shift_f10_opens_context_menu(self):
        shown = []
        self.win._tree_menu = lambda pos: shown.append("tree")
        self.win._editor_menu = lambda pos: shown.append("editor")
        QTest.keyClick(self.tree, Qt.Key_F10, Qt.ShiftModifier)
        QTest.keyClick(self.win.editor, Qt.Key_F10, Qt.ShiftModifier)
        self.assertEqual(shown, ["tree", "editor"])

    # ------------------------------------------------------------ tree

    def test_slow_click_renames(self):
        self.assertTrue(self.tree.editTriggers() & QAbstractItemView.SelectedClicked)
        self.win.set_read_only(True)
        self.assertEqual(self.tree.editTriggers(), QAbstractItemView.NoEditTriggers)
        self.win.set_read_only(False)
        self.assertTrue(self.tree.editTriggers() & QAbstractItemView.SelectedClicked)

    def test_shift_drop_on_node_makes_sibling(self):
        class FakeDrop:
            def __init__(self, src): self.src = src
            def keyboardModifiers(self): return Qt.ShiftModifier
            def source(self): return self.src
            def pos(self): return None
            def setDropAction(self, a): pass
            def accept(self): pass
            def ignore(self): self.ignored = True

        self.select("Soup")
        recipes = next(i for i in self.tree.all_items() if i.title == "Recipes")
        self.tree.itemAt = lambda pos: recipes
        self.tree.dropIndicatorPosition = lambda: QAbstractItemView.OnItem
        self.tree.dropEvent(FakeDrop(self.tree))
        titles = [(i.title, i.parent().title if i.parent() else None) for i in self.tree.all_items()]
        self.assertEqual(titles, [("My notes", None), ("Recipes", "My notes"), ("Soup", "My notes"),
                                  ("Work", "My notes")])

    def test_ctrl_down_scrolls_without_moving_selection(self):
        self.select("Work")
        for n in range(60):
            self.tree.add_sibling(title=f"Extra {n}")
        self.select("My notes")
        self.win.resize(500, 300)
        self.win.show()
        app.processEvents()
        bar = self.tree.verticalScrollBar()
        self.assertGreater(bar.maximum(), 0)
        bar.setValue(0)
        QTest.keyClick(self.tree, Qt.Key_Down, Qt.ControlModifier)
        self.assertGreater(bar.value(), 0)
        self.assertEqual(self.tree.currentItem().title, "My notes")

    # ------------------------------------------------------------ toolbars

    def test_toolbars_match_the_classic_layout(self):
        w = self.win
        expected = {
            "file-bar": [w.act_new, w.act_open, w.act_save, w.act_print, w.act_options],
            "article-edit-bar": [w.act_cut, w.act_copy, w.act_paste, w.act_delete_text],
            "tree-edit-bar": [w.act_add_child, w.act_add_before, w.act_add_after, w.act_delete, w.act_rename],
            "view-bar": [w.act_find, w.act_search_tree, w.act_view_modes["both"], w.act_view_modes["tree"],
                         w.act_view_modes["article"], w.act_word_wrap],
            "navigate-bar": [w.act_follow_link, w.act_move_up, w.act_move_down, w.act_move_left,
                             w.act_move_right, w.act_expand_branch, w.act_collapse_branch],
            "extras-bar": [w.act_undo, w.act_redo, w.act_bold, w.act_italic, w.act_focus, w.act_unfocus],
        }
        self.assertEqual(list(w.toolbars), list(expected))   # left-to-right order
        for name, acts in expected.items():
            tb = w.toolbars[name]
            self.assertTrue(tb.isMovable())
            self.assertEqual([a for a in tb.actions() if not a.isSeparator()], acts, name)
            for a in acts:
                self.assertFalse(a.icon().isNull(), a.text())
        w.show()
        app.processEvents()
        self.assertTrue(all(w.toolbars[n].isVisible() for n in list(expected)[:5]))
        self.assertFalse(w.toolbars["extras-bar"].isVisible())
        self.assertIs(w.act_options.menu(), w.options_menu)
        sub = next(a.menu() for a in w.view_menu.actions() if a.menu() and "Toolbars" in a.text().replace("&", ""))
        self.assertEqual(len([a for a in sub.actions() if not a.isSeparator() and not a.menu()]), 8)
        w._show_toolbars(False)
        self.assertFalse(any(tb.isVisible() for tb in w.toolbars.values()))

    def test_toolbar_icon_size(self):
        w = self.win
        self.assertTrue(all(tb.iconSize().width() == 24 for tb in w.toolbars.values()))   # default
        w.act_icon_sizes[16].trigger()
        self.assertTrue(all(tb.iconSize().width() == 16 for tb in w.toolbars.values()))
        self.assertEqual(w.settings.value("view/toolbar_icon_size", type=int), 16)
        w.settings.sync()
        win = self.make_window()
        try:
            self.assertTrue(win.act_icon_sizes[16].isChecked())
            self.assertEqual(win.toolbars["file-bar"].iconSize().width(), 16)
        finally:
            win.close()
            win.deleteLater()

    def test_rename_box_fits_the_title(self):
        from PyQt5.QtWidgets import QLineEdit
        for mode in ("light", "dark"):
            self.win.set_theme(mode)
            for classic in (True, False):
                self.win.set_classic_tree(classic)
                self.win.show()
                self.win.add_child_node()
                app.processEvents()
                ed = self.tree.findChild(QLineEdit, "node-title-editor")
                self.assertIsNotNone(ed)
                self.assertGreaterEqual(ed.height(), ed.sizeHint().height(), (mode, classic))
                self.tree.closePersistentEditor(self.tree.currentItem())
                self.tree.setFocus()
                app.processEvents()
        self.win.set_theme("auto")

    def test_search_tree_opens_tree_search(self):
        self.win.act_search_tree.trigger()
        self.assertTrue(self.win.tree_search_dialog().isVisible())

    # ------------------------------------------------------------ startup

    def test_legacy_open_last_setting_maps_to_startup_mode(self):
        self.win.settings.setValue("options/open_last", False)
        self.win.settings.remove("options/startup")
        self.win.settings.sync()
        win = self.make_window()
        try:
            self.assertEqual(win.startup_mode(), "new")
        finally:
            win.close()
            win.deleteLater()

    def test_startup_modes(self):
        self.win._add_recent(self.sample)
        self.assertTrue(self.win.recent_files())
        win = self.make_window()
        try:
            asked = []
            win.act_startup["ask"].setChecked(True)
            win._ask_reopen = lambda name: asked.append(name) or False
            win.open_startup_file()
            self.assertEqual(asked, ["notes.hjt"])
            self.assertIsNone(win.path)
            win.act_startup["quickstart"].setChecked(True)
            win._quick_start = lambda: self.sample
            win.open_startup_file()
            self.assertEqual(win.path, self.sample)
        finally:
            win.setWindowModified(False)
            win.close()
            win.deleteLater()

    # ------------------------------------------------------------ closing

    def test_close_saves_automatically(self):
        self.win.act_close_modes["save"].setChecked(True)
        self.win.editor.setPlainText("saved on exit")
        self.assertTrue(self.win.isWindowModified())
        self.assertTrue(self.win._ok_to_close())
        self.assertIn("saved on exit", "\n".join(n.text for n, _ in hjt.load(self.sample).walk()))

    def test_close_without_saving(self):
        self.win.act_close_modes["discard"].setChecked(True)
        self.win.editor.setPlainText("thrown away")
        self.win.maybe_save = lambda: self.fail("should not ask")
        self.assertTrue(self.win._ok_to_close())
        self.assertNotIn("thrown away", "\n".join(n.text for n, _ in hjt.load(self.sample).walk()))

    # ------------------------------------------------------------ portable

    def test_portable_settings_move_both_ways(self):
        prog_dir = os.path.join(self.dir, "usb")
        home_dir = os.path.join(self.dir, "home")
        os.makedirs(prog_dir)
        old_argv0 = sys.argv[0]
        sys.argv[0] = os.path.join(prog_dir, "twigpad")
        QSettings.setPath(QSettings.NativeFormat, QSettings.UserScope, home_dir)
        try:
            self.win.settings.setValue("colors/tree_bg", "#010203")
            self.assertTrue(self.win.set_portable(True))
            ini = os.path.join(prog_dir, portable.INI_NAME)
            self.assertEqual(os.path.abspath(self.win.settings.fileName()), ini)
            self.assertEqual(portable.portable_ini(), ini)
            self.assertTrue(self.win._using_portable())
            self.assertEqual(QSettings(ini, QSettings.IniFormat).value("colors/tree_bg"), "#010203")
            self.assertTrue(self.win.set_portable(False))
            self.assertFalse(os.path.exists(ini))
            self.assertTrue(self.win.settings.fileName().startswith(home_dir))
            self.assertEqual(self.win.settings.value("colors/tree_bg"), "#010203")
        finally:
            sys.argv[0] = old_argv0
            xdg = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
            QSettings.setPath(QSettings.NativeFormat, QSettings.UserScope, xdg)


if __name__ == "__main__":
    unittest.main()
