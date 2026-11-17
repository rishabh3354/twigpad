# SPDX-License-Identifier: GPL-3.0-or-later
"""Text sizes of the tree and article, tree icon size, toolbar icons and labels."""
import os
import shutil
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QPoint, QPointF, QSettings, Qt  # noqa: E402
from PyQt5.QtGui import QFont, QWheelEvent  # noqa: E402
from PyQt5.QtWidgets import QApplication  # noqa: E402

from twigpad.ui import fonts  # noqa: E402
from twigpad.ui.mainwindow import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])


class SizeTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "s.ini")
        self.win = MainWindow(QSettings(self.path, QSettings.IniFormat))

    def tearDown(self):
        self.win.setWindowModified(False)
        self.win.close()
        self.win.deleteLater()
        app.processEvents()
        shutil.rmtree(self.dir)

    def reopen(self):
        self.win.settings.sync()
        win = MainWindow(QSettings(self.path, QSettings.IniFormat))
        self.addCleanup(win.deleteLater)
        self.addCleanup(win.close)
        return win

    def size(self, widget):
        return widget.font().pointSizeF()

    def test_article_text_size(self):
        ed = self.win.editor
        base = self.size(ed)
        self.win.zoom_text("editor", 1)
        self.win.zoom_text("editor", 1)
        self.assertEqual(self.size(ed), base + 2)
        self.win.zoom_text("editor", -1)
        self.assertEqual(self.size(ed), base + 1)
        self.assertEqual(self.size(self.reopen().editor), base + 1)
        self.win.zoom_text("editor", 0)
        self.assertEqual(self.size(ed), base)

    def test_shortcuts_follow_focus(self):
        tree_base, ed_base = self.size(self.win.tree), self.size(self.win.editor)
        self.win.tree.hasFocus = lambda: True
        self.win.act_zoom_in.trigger()
        self.assertEqual(self.size(self.win.tree), tree_base + 1)
        self.assertEqual(self.size(self.win.editor), ed_base)
        self.win.tree.hasFocus = lambda: False
        self.win.act_zoom_out.trigger()
        self.assertEqual(self.size(self.win.editor), ed_base - 1)
        self.assertEqual([k.toString() for k in self.win.act_zoom_in.shortcuts()], ["Ctrl+=", "Ctrl++"])

    def test_ctrl_wheel_resizes_the_pane_under_the_mouse(self):
        base = self.size(self.win.tree)
        vp = self.win.tree.viewport()
        ev = QWheelEvent(QPointF(5, 5), QPointF(5, 5), QPoint(0, 0), QPoint(0, 120), Qt.NoButton,
                         Qt.ControlModifier, Qt.NoScrollPhase, False)
        self.assertTrue(self.win.eventFilter(vp, ev))
        self.assertEqual(self.size(self.win.tree), base + 1)

    def test_zoom_has_limits(self):
        base = self.size(self.win.editor)
        for _ in range(50):
            self.win.zoom_text("editor", -1)
        self.assertGreaterEqual(self.size(self.win.editor), 5)
        self.assertEqual(self.size(self.win.editor), max(5.0, base - 6))

    def test_font_choice_and_reset(self):
        self.win.zoom_text("tree", 3)
        font = QFont("Serif")
        font.setPointSize(13)
        self.win.settings.setValue("fonts/tree", font.toString())
        self.win.settings.remove("view/tree_zoom")
        self.win.apply_text_sizes()
        self.assertEqual(self.size(self.win.tree), 13)
        self.win.zoom_text("tree", 2)
        self.assertEqual(self.size(self.win.tree), 15)
        self.win.reset_fonts()
        self.assertEqual(self.size(self.win.tree), fonts.default_font("tree").pointSizeF())

    def test_default_fonts_are_a_little_larger(self):
        desk = fonts.desktop_font().pointSizeF()
        self.assertGreaterEqual(self.size(self.win.tree), max(11, desk + 1))
        self.assertGreaterEqual(self.size(self.win.editor), max(12, desk + 2))
        self.assertEqual(self.win.tree.font().family(), fonts.default_family())

    def test_tree_icons_follow_tree_zoom(self):
        tree = self.win.tree
        self.assertEqual(tree.iconSize().width(), 16)
        for _ in range(6):
            self.win.zoom_text("tree", 1)
        bigger = tree.iconSize().width()
        self.assertGreater(bigger, 20)
        self.assertGreaterEqual(tree.indentation(), bigger + 3)
        self.win.zoom_text("tree", 0)
        self.assertEqual(tree.iconSize().width(), 16)
        self.win.zoom_text("tree", -6)
        self.assertLess(tree.iconSize().width(), 16)
        self.assertEqual(self.win.settings.value("view/tree_icon_size", 16, type=int), 16)

    def test_fonts_window(self):
        dlg = self.win.fonts_dialog("tree")
        dlg.size["tree"].setValue(18)
        self.assertEqual(self.size(self.win.tree), 18)      # shows at once
        self.assertGreater(self.win.tree.iconSize().width(), 16)
        dlg.size["app"].setValue(14)
        self.assertEqual(QApplication.font().pointSize(), 14)
        dlg.reject()                                        # Cancel: old fonts back
        self.assertEqual(self.size(self.win.tree), fonts.default_font("tree").pointSizeF())
        self.assertEqual(QApplication.font().pointSizeF(), fonts.default_font("app").pointSizeF())
        dlg = self.win.fonts_dialog("editor")
        dlg.family["editor"].setCurrentFont(QFont("DejaVu Serif"))
        dlg.size["editor"].setValue(15)
        dlg.accept()
        self.assertEqual(self.size(self.win.editor), 15)
        self.assertEqual(self.reopen().editor.font().pointSizeF(), 15)
        dlg = self.win.fonts_dialog()
        dlg.restore_defaults()
        dlg.accept()
        self.assertEqual(self.size(self.win.editor), fonts.default_font("editor").pointSizeF())

    def test_tree_icon_size(self):
        tree = self.win.tree
        self.assertEqual(tree.iconSize().width(), 16)
        self.win.act_tree_icon_sizes[24].trigger()
        self.assertEqual(tree.iconSize().width(), 24)
        self.assertGreaterEqual(tree.indentation(), 27)
        item = tree.topLevelItem(0)
        self.assertGreaterEqual(tree.visualItemRect(item).height(), 26)
        self.assertEqual(self.reopen().tree.iconSize().width(), 24)
        self.win.set_classic_tree(False)
        self.assertEqual(tree.iconSize().width(), 24)

    def test_toolbar_sizes_and_labels(self):
        w = self.win
        w.act_icon_sizes[32].trigger()
        self.assertTrue(all(tb.iconSize().width() == 32 for tb in w.toolbars.values()))
        self.assertTrue(all(tb.toolButtonStyle() == Qt.ToolButtonIconOnly for tb in w.toolbars.values()))
        w.act_toolbar_labels["under"].trigger()
        self.assertTrue(all(tb.toolButtonStyle() == Qt.ToolButtonTextUnderIcon for tb in w.toolbars.values()))
        self.assertEqual(w.act_add_child.iconText(), "Child")
        self.assertEqual(w.act_add_child.toolTip(), "Add a node inside the selected one")   # unchanged
        self.assertEqual(w.act_search_tree.iconText(), "Search")
        self.assertNotEqual(w.act_search_tree.toolTip(), "Search")
        w.resize(900, 500)
        w.show()
        w.arrange_toolbars()
        app.processEvents()
        for tb in w.toolbars.values():   # wrapped onto rows: nothing hidden in an overflow menu
            if tb.isVisible():
                self.assertLessEqual(tb.sizeHint().width(), tb.width() + 1, tb.windowTitle())
        rows = {tb.y() for tb in w.toolbars.values() if tb.isVisible()}
        self.assertGreater(len(rows), 1)
        win = self.reopen()
        self.assertTrue(win.act_toolbar_labels["under"].isChecked())
        self.assertEqual(win.toolbars["file-bar"].iconSize().width(), 32)


if __name__ == "__main__":
    unittest.main()
