# SPDX-License-Identifier: GPL-3.0-or-later
"""Main window: note tree on the left, article editor on the right."""
from __future__ import annotations

import os
import shutil
import zipfile
from typing import List, Optional

from PyQt5.QtCore import QDateTime, QLocale, QMimeData, QSettings, Qt, QTimer
from PyQt5.QtGui import QFont, QKeySequence
from PyQt5.QtWidgets import (
    QAction, QApplication, QFileDialog, QFontDialog, QLabel, QMainWindow, QMenu,
    QMessageBox, QPlainTextEdit, QSplitter, QStyle,
)

from .. import APP_ID, APP_NAME, __version__, export, hjt
from ..model import Document, Node
from . import icons
from .finddialog import FindDialog
from .tree import NoteItem, NoteTree

FILE_FILTERS = (
    "Tree notes and backups (*.hjt *.HJT *.bak *.BAK *.hjt~ *.zip);;"
    "Tree notes (*.hjt *.HJT);;"
    "All files (*)"
)
NEW_FILE_TITLE = "Notes"
NODE_MIME = "application/x-twigpad-hjt"
MAX_RECENT = 10
AUTOSAVE_MINUTES = 5


class MainWindow(QMainWindow):
    def __init__(self, settings: Optional[QSettings] = None):
        super().__init__()
        self.settings = settings or QSettings(APP_ID, APP_ID)
        self.path: Optional[str] = None       # where Save writes; None = ask
        self.source_name = ""                 # name shown when path is None
        self.encoding = "cp1252"
        self._loading = False
        self._editing_item: Optional[NoteItem] = None
        self._editor_dirty = False
        self._backed_up_path: Optional[str] = None
        self._find_dialog: Optional[FindDialog] = None

        self.tree = NoteTree()
        self.editor = QPlainTextEdit()
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.addWidget(self.tree)
        self.splitter.addWidget(self.editor)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 3)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setSizes([260, 740])
        self.setCentralWidget(self.splitter)

        self.autosave_timer = QTimer(self)
        self.autosave_timer.setInterval(AUTOSAVE_MINUTES * 60 * 1000)
        self.autosave_timer.timeout.connect(self.autosave)

        self._create_actions()
        self._create_menus()
        self._create_toolbar()
        self._create_statusbar()

        self.tree.currentItemChanged.connect(self._on_current_changed)
        self.tree.itemChanged.connect(self._on_item_renamed)
        self.tree.structureChanged.connect(self._on_structure_changed)
        self.editor.textChanged.connect(self._on_text_changed)
        self.editor.cursorPositionChanged.connect(self._update_cursor_label)
        self.editor.undoAvailable.connect(self.act_undo.setEnabled)
        self.editor.redoAvailable.connect(self.act_redo.setEnabled)
        self.editor.copyAvailable.connect(self.act_cut.setEnabled)
        self.editor.copyAvailable.connect(self.act_copy.setEnabled)

        self._restore_settings()
        self.new_file(confirm=False)

    # ================================================================ setup

    def _action(self, text, slot, shortcut=None, icon=None, tip=None,
                context_widget=None, checkable=False) -> QAction:
        act = QAction(text, self)
        if icon is not None:
            act.setIcon(icon)
        if shortcut:
            act.setShortcut(QKeySequence(shortcut))
        if tip:
            act.setStatusTip(tip)
            act.setToolTip(tip)
        if checkable:
            act.setCheckable(True)
            act.toggled.connect(slot)
        else:
            act.triggered.connect(lambda _checked=False: slot())
        if context_widget is not None:
            # Shortcut only works while that pane has the keyboard focus, so
            # e.g. Del deletes a node in the tree but a character in the editor.
            act.setShortcutContext(Qt.WidgetShortcut)
            context_widget.addAction(act)
        return act

    def _create_actions(self) -> None:
        S = QStyle
        t, e = self.tree, self.editor

        # File
        self.act_new = self._action("&New", self.new_file, QKeySequence.New,
                                    icons.themed("document-new", S.SP_FileIcon), "Start a new file")
        self.act_open = self._action("&Open...", self.open_file, QKeySequence.Open,
                                     icons.themed("document-open", S.SP_DialogOpenButton),
                                     "Open a tree notes file or a backup")
        self.act_save = self._action("&Save", self.save, QKeySequence.Save,
                                     icons.themed("document-save", S.SP_DialogSaveButton), "Save the file")
        self.act_save_as = self._action("Save &As...", self.save_as, "Ctrl+Shift+S",
                                        tip="Save under a new name")
        self.act_import_tree = self._action(
            "Tree File or Backup (into the selected node)...", self.import_tree_file,
            tip="Add all nodes of another tree file or backup inside the selected node")
        self.act_import_text = self._action("Text File as New Node...", self.import_text_file,
                                            tip="Add a text file as a new node inside the selected node")
        self.act_export_node = self._action("Selected Node...", lambda: self.export_text("node"))
        self.act_export_branch = self._action("Selected Node and Subnodes...",
                                              lambda: self.export_text("branch"))
        self.act_export_all = self._action("Whole File...", lambda: self.export_text("all"))
        self.act_print = self._action("&Print...", lambda: self.print_nodes(True), QKeySequence.Print,
                                      icons.themed("document-print", S.SP_FileDialogDetailedView),
                                      "Print the selected node and its subnodes")
        self.act_print_node = self._action("Print Selected Node &Only...", lambda: self.print_nodes(False))
        self.act_exit = self._action("E&xit", self.close, "Ctrl+Q")

        # Edit (article text)
        self.act_undo = self._action("&Undo", e.undo, QKeySequence.Undo,
                                     icons.themed("edit-undo", S.SP_ArrowBack), context_widget=e)
        self.act_redo = self._action("&Redo", e.redo, "Ctrl+Y",
                                     icons.themed("edit-redo", S.SP_ArrowForward), context_widget=e)
        self.act_cut = self._action("Cu&t", e.cut, QKeySequence.Cut, context_widget=e)
        self.act_copy = self._action("&Copy", e.copy, QKeySequence.Copy, context_widget=e)
        self.act_paste = self._action("&Paste", e.paste, QKeySequence.Paste, context_widget=e)
        self.act_select_all = self._action("Select &All", e.selectAll, QKeySequence.SelectAll,
                                           context_widget=e)
        for a in (self.act_undo, self.act_redo, self.act_cut, self.act_copy):
            a.setEnabled(False)
        self.act_date = self._action("Insert &Date", lambda: self.insert_datetime("date"),
                                     "Ctrl+Shift+D", context_widget=e)
        self.act_time = self._action("Insert &Time", lambda: self.insert_datetime("time"),
                                     "Ctrl+Shift+T", context_widget=e)
        self.act_datetime = self._action("Insert Date &and Time", lambda: self.insert_datetime("both"),
                                         "F5", context_widget=e)

        # Search
        self.act_find = self._action("&Find...", lambda: self.show_find(False), QKeySequence.Find,
                                     icons.themed("edit-find", S.SP_FileDialogContentsView),
                                     "Search titles and articles of all nodes")
        self.act_find_next = self._action("Find &Next", lambda: self.find_again(False), "F3")
        self.act_find_prev = self._action("Find &Previous", lambda: self.find_again(True), "Shift+F3")
        self.act_replace = self._action("&Replace...", lambda: self.show_find(True), "Ctrl+H")

        # Node
        self.act_add_after = self._action("&Add Node", self.add_node_after, "Ins",
                                          icons.add_sibling(), "Add a node below the selected one",
                                          context_widget=t)
        self.act_add_before = self._action("&Insert Node Before", self.add_node_before, "Shift+Ins",
                                           tip="Add a node above the selected one", context_widget=t)
        self.act_add_child = self._action("Add &Child Node", self.add_child_node, "Ctrl+Ins",
                                          icons.add_child(), "Add a node inside the selected one",
                                          context_widget=t)
        self.act_rename = self._action("&Rename", self.rename_node, "F2",
                                       tip="Rename the selected node", context_widget=t)
        self.act_delete = self._action("&Delete Node", self.delete_node, "Del",
                                       icons.themed("edit-delete", S.SP_TrashIcon),
                                       "Delete the selected node and everything inside it",
                                       context_widget=t)
        self.act_cut_node = self._action("Cu&t Node", self.cut_node, QKeySequence.Cut,
                                         tip="Cut the selected node and its subnodes", context_widget=t)
        self.act_copy_node = self._action("C&opy Node", self.copy_node, QKeySequence.Copy,
                                          tip="Copy the selected node and its subnodes", context_widget=t)
        self.act_paste_node = self._action("&Paste Node", lambda: self.paste_node(False),
                                           QKeySequence.Paste, tip="Paste below the selected node",
                                           context_widget=t)
        self.act_paste_child = self._action("Paste as C&hild", lambda: self.paste_node(True),
                                            "Ctrl+Shift+V", tip="Paste inside the selected node",
                                            context_widget=t)
        self.act_move_up = self._action("Move &Up", self.tree.move_up, "Ctrl+Shift+Up",
                                        icons.themed("go-up", S.SP_ArrowUp), "Move node up",
                                        context_widget=t)
        self.act_move_down = self._action("Move Do&wn", self.tree.move_down, "Ctrl+Shift+Down",
                                          icons.themed("go-down", S.SP_ArrowDown), "Move node down",
                                          context_widget=t)
        self.act_move_left = self._action("Move &Left (out a level)", self.tree.move_left,
                                          "Ctrl+Shift+Left", icons.themed("go-previous", S.SP_ArrowLeft),
                                          "Move node out one level", context_widget=t)
        self.act_move_right = self._action("Move R&ight (in a level)", self.tree.move_right,
                                           "Ctrl+Shift+Right", icons.themed("go-next", S.SP_ArrowRight),
                                           "Move node in one level", context_widget=t)
        self.act_sort = self._action("&Sort Subnodes A-Z", self.sort_children,
                                     tip="Sort the nodes inside the selected node by title")

        # View
        self.act_word_wrap = self._action("&Word Wrap", self.set_word_wrap, checkable=True)
        self.act_expand_all = self._action("&Expand All", self.tree.expandAll)
        self.act_collapse_all = self._action("&Collapse All", self.tree.collapseAll)
        self.act_switch_pane = self._action("&Switch Pane", self.switch_pane, "F6",
                                            tip="Jump between the tree and the article")
        self.act_article_font = self._action("&Article Font...", lambda: self.choose_font("editor"))
        self.act_tree_font = self._action("&Tree Font...", lambda: self.choose_font("tree"))
        self.act_reset_fonts = self._action("&Reset Fonts", self.reset_fonts)

        # Options
        self.act_open_last = self._action("&Open Last File at Startup",
                                          lambda on: self.settings.setValue("options/open_last", on),
                                          checkable=True)
        self.act_backup = self._action(
            "Keep a &Backup Copy (.bak) When Saving",
            lambda on: self.settings.setValue("options/backup", on), checkable=True)
        self.act_autosave = self._action(f"&Auto-save Every {AUTOSAVE_MINUTES} Minutes",
                                         self.set_autosave, checkable=True)

        self.act_about = self._action(f"&About {APP_NAME}", self.about)

    def _create_menus(self) -> None:
        mb = self.menuBar()
        m = mb.addMenu("&File")
        m.addActions([self.act_new, self.act_open])
        self.recent_menu = m.addMenu("Open &Recent")
        self.recent_menu.aboutToShow.connect(self._fill_recent_menu)
        m.addActions([self.act_save, self.act_save_as])
        m.addSeparator()
        sub = m.addMenu("&Import")
        sub.addActions([self.act_import_tree, self.act_import_text])
        sub = m.addMenu("&Export as Text")
        sub.addActions([self.act_export_node, self.act_export_branch, self.act_export_all])
        m.addSeparator()
        m.addActions([self.act_print, self.act_print_node])
        m.addSeparator()
        m.addAction(self.act_exit)

        m = mb.addMenu("&Edit")
        m.addActions([self.act_undo, self.act_redo])
        m.addSeparator()
        m.addActions([self.act_cut, self.act_copy, self.act_paste])
        m.addSeparator()
        m.addAction(self.act_select_all)
        m.addSeparator()
        m.addActions([self.act_date, self.act_time, self.act_datetime])

        m = mb.addMenu("&Search")
        m.addActions([self.act_find, self.act_find_next, self.act_find_prev])
        m.addSeparator()
        m.addAction(self.act_replace)

        m = mb.addMenu("&Node")
        m.addActions(self._node_menu_actions())

        m = mb.addMenu("&View")
        m.addAction(self.act_word_wrap)
        m.addSeparator()
        m.addActions([self.act_expand_all, self.act_collapse_all])
        m.addSeparator()
        m.addActions([self.act_article_font, self.act_tree_font, self.act_reset_fonts])
        m.addSeparator()
        self.view_menu = m
        m.addAction(self.act_switch_pane)

        m = mb.addMenu("&Options")
        m.addActions([self.act_open_last, self.act_backup, self.act_autosave])

        m = mb.addMenu("&Help")
        m.addAction(self.act_about)

        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._tree_menu)

    def _node_menu_actions(self) -> List[QAction]:
        sep = lambda: self._separator()  # noqa: E731
        return [self.act_add_after, self.act_add_before, self.act_add_child, sep(),
                self.act_rename, self.act_delete, sep(),
                self.act_cut_node, self.act_copy_node, self.act_paste_node, self.act_paste_child, sep(),
                self.act_move_up, self.act_move_down, self.act_move_left, self.act_move_right, sep(),
                self.act_sort]

    def _separator(self) -> QAction:
        a = QAction(self)
        a.setSeparator(True)
        return a

    def _tree_menu(self, pos) -> None:
        menu = QMenu(self)
        menu.addActions(self._node_menu_actions())
        menu.exec_(self.tree.viewport().mapToGlobal(pos))

    def _create_toolbar(self) -> None:
        tb = self.addToolBar("Main toolbar")
        tb.setObjectName("main-toolbar")
        tb.setMovable(False)
        tb.addActions([self.act_new, self.act_open, self.act_save])
        tb.addSeparator()
        tb.addActions([self.act_add_after, self.act_add_child, self.act_delete])
        tb.addSeparator()
        tb.addActions([self.act_move_up, self.act_move_down, self.act_move_left, self.act_move_right])
        tb.addSeparator()
        tb.addActions([self.act_find, self.act_print])
        self.view_menu.addAction(tb.toggleViewAction())

    def _create_statusbar(self) -> None:
        sb = self.statusBar()
        self.nodes_label = QLabel()
        self.cursor_label = QLabel()
        sb.addPermanentWidget(self.nodes_label)
        sb.addPermanentWidget(self.cursor_label)
        self._update_cursor_label()

    # ============================================================ settings

    def _restore_settings(self) -> None:
        s = self.settings
        geo = s.value("window/geometry")
        if geo is not None:
            self.restoreGeometry(geo)
        else:
            self.resize(1000, 680)
        state = s.value("window/state")
        if state is not None:
            self.restoreState(state)
        split = s.value("window/splitter")
        if split is not None:
            self.splitter.restoreState(split)
        self.act_word_wrap.setChecked(s.value("editor/word_wrap", True, type=bool))
        self.set_word_wrap(self.act_word_wrap.isChecked())
        for key, widget in (("fonts/editor", self.editor), ("fonts/tree", self.tree)):
            desc = s.value(key, "", type=str)
            font = QFont()
            if desc and font.fromString(desc):
                widget.setFont(font)
        self._update_tab_width()
        self.act_open_last.setChecked(s.value("options/open_last", True, type=bool))
        self.act_backup.setChecked(s.value("options/backup", True, type=bool))
        self.act_autosave.setChecked(s.value("options/autosave", False, type=bool))
        self.set_autosave(self.act_autosave.isChecked())

    def _save_settings(self) -> None:
        s = self.settings
        s.setValue("window/geometry", self.saveGeometry())
        s.setValue("window/state", self.saveState())
        s.setValue("window/splitter", self.splitter.saveState())
        s.setValue("editor/word_wrap", self.act_word_wrap.isChecked())
        s.sync()

    def recent_files(self) -> List[str]:
        value = self.settings.value("files/recent", [])
        if isinstance(value, str):
            value = [value]
        return [p for p in (value or []) if p]

    def _add_recent(self, path: str) -> None:
        path = os.path.abspath(path)
        files = [p for p in self.recent_files() if p != path]
        self.settings.setValue("files/recent", [path] + files[: MAX_RECENT - 1])

    def _fill_recent_menu(self) -> None:
        self.recent_menu.clear()
        files = self.recent_files()
        for n, path in enumerate(files, 1):
            label = f"&{n % 10}  {os.path.basename(path)}"
            act = self.recent_menu.addAction(label)
            act.setStatusTip(path)
            act.setToolTip(path)
            act.setEnabled(os.path.exists(path))
            act.triggered.connect(lambda _c=False, p=path: self.open_file(p))
        if files:
            self.recent_menu.addSeparator()
            self.recent_menu.addAction("&Clear List", lambda: self.settings.setValue("files/recent", []))
        else:
            self.recent_menu.addAction("(no recent files)").setEnabled(False)

    def open_startup_file(self) -> None:
        """Reopen the most recent .hjt file when that option is on."""
        if not self.act_open_last.isChecked():
            return
        for path in self.recent_files()[:1]:
            if path.lower().endswith(".hjt") and os.path.exists(path):
                self.load_path(path)

    # ===================================================== editor <-> tree

    def _commit_editor(self) -> None:
        """Copy the editor's text back into the node it belongs to."""
        item = self._editing_item
        if item is None:
            return
        item.cursor_pos = self.editor.textCursor().position()
        if self._editor_dirty:
            item.body = self.editor.toPlainText()
            self._editor_dirty = False

    def _show_item(self, item: Optional[NoteItem]) -> None:
        self._loading = True
        try:
            self._editing_item = item
            self._editor_dirty = False
            if item is None:
                self.editor.clear()
                self.editor.setEnabled(False)
            else:
                self.editor.setEnabled(True)
                self.editor.setPlainText(item.body)
                cur = self.editor.textCursor()
                cur.setPosition(min(item.cursor_pos, self.editor.document().characterCount() - 1))
                self.editor.setTextCursor(cur)
                self.editor.ensureCursorVisible()
        finally:
            self._loading = False
        self._update_node_actions()

    def _on_current_changed(self, current, _previous) -> None:
        self._commit_editor()
        self._show_item(current)

    def _on_text_changed(self) -> None:
        if not self._loading:
            self._editor_dirty = True
            self.setWindowModified(True)

    def _on_item_renamed(self, item, _column) -> None:
        if self._loading:
            return
        title = " ".join(item.text(0).split())
        if not title:
            title = "Untitled"
        if title != item.text(0):
            self._loading = True
            item.setText(0, title)
            self._loading = False
        self.setWindowModified(True)

    def _on_structure_changed(self) -> None:
        self.setWindowModified(True)
        self._update_node_actions()

    def _update_node_actions(self) -> None:
        cur = self.tree.currentItem()
        has = cur is not None
        idx = self.tree.index_in_parent(cur) if has else 0
        siblings = (cur.parent() or self.tree.invisibleRootItem()).childCount() if has else 0
        for act in (self.act_add_child, self.act_rename, self.act_delete, self.act_cut_node,
                    self.act_copy_node, self.act_paste_child, self.act_export_node,
                    self.act_export_branch, self.act_print, self.act_print_node):
            act.setEnabled(has)
        self.act_move_up.setEnabled(has and idx > 0)
        self.act_move_down.setEnabled(has and idx < siblings - 1)
        self.act_move_left.setEnabled(has and cur.parent() is not None)
        self.act_move_right.setEnabled(has and idx > 0)
        self.act_sort.setEnabled(has and cur.childCount() > 1)
        n = len(self.tree.all_items())
        self.nodes_label.setText(f" {n} node{'s' if n != 1 else ''} ")

    def _update_cursor_label(self) -> None:
        c = self.editor.textCursor()
        self.cursor_label.setText(f" Ln {c.blockNumber() + 1}, Col {c.positionInBlock() + 1} ")

    # =========================================================== node ops

    def _start_rename(self, item: NoteItem) -> None:
        self.tree.scrollToItem(item)
        self.tree.editItem(item, 0)

    def add_node_after(self) -> None:
        self._start_rename(self.tree.add_sibling(after=True))

    def add_node_before(self) -> None:
        self._start_rename(self.tree.add_sibling(after=False))

    def add_child_node(self) -> None:
        self._start_rename(self.tree.add_child())

    def rename_node(self) -> None:
        item = self.tree.currentItem()
        if item is not None:
            self._start_rename(item)

    def delete_node(self, confirm: bool = True) -> None:
        item = self.tree.currentItem()
        if item is None:
            return
        if confirm:
            inner = len(NoteTree.all_items_under(item)) - 1
            extra = (f"\n\nIt contains {inner} other node{'s' if inner != 1 else ''}, "
                     "which will also be deleted.") if inner else ""
            answer = QMessageBox.question(
                self, "Delete Node", f"Delete the node \"{item.title}\"?{extra}",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if answer != QMessageBox.Yes:
                return
        self._remove(item)

    def _remove(self, item: NoteItem) -> None:
        if item is self._editing_item or NoteTree.is_ancestor(item, self._editing_item):
            self._editing_item = None
        self.tree.remove_item(item)
        if self.tree.currentItem() is None:
            self._show_item(None)

    def copy_node(self) -> bool:
        item = self.tree.currentItem()
        if item is None:
            return False
        self._commit_editor()
        node = NoteTree.item_to_node(item)
        doc = Document()
        doc.root.add_child(node)
        mime = QMimeData()
        mime.setData(NODE_MIME, hjt.serialize(doc).encode("utf-8"))
        mime.setText(export.outline_text([node], numbered=False))
        QApplication.clipboard().setMimeData(mime)
        n = node.count()
        self.statusBar().showMessage(f"Copied {n} node{'s' if n != 1 else ''}.", 4000)
        return True

    def cut_node(self) -> None:
        item = self.tree.currentItem()
        if item is not None and self.copy_node():
            self._remove(item)

    def _clipboard_nodes(self) -> List[Node]:
        mime = QApplication.clipboard().mimeData()
        if mime is None:
            return []
        if mime.hasFormat(NODE_MIME):
            try:
                return hjt.parse(bytes(mime.data(NODE_MIME)).decode("utf-8")).top_nodes
            except hjt.HjtFormatError:
                return []
        if mime.hasText():
            text = mime.text()
            if hjt.looks_like_hjt(text):
                try:
                    return hjt.parse(text).top_nodes
                except hjt.HjtFormatError:
                    pass
            if text.strip():
                # Plain text becomes a new node titled by its first line.
                title = next(line.strip() for line in text.splitlines() if line.strip())
                return [Node(title[:80], text)]
        return []

    def paste_node(self, as_child: bool = False) -> None:
        nodes = self._clipboard_nodes()
        if not nodes:
            self.statusBar().showMessage("Nothing to paste.", 3000)
            return
        cur = self.tree.currentItem()
        if cur is None:
            self.tree.insert_nodes(nodes, None, self.tree.topLevelItemCount())
        elif as_child:
            self.tree.insert_nodes(nodes, cur, cur.childCount())
        else:
            self.tree.insert_nodes(nodes, cur.parent(), self.tree.index_in_parent(cur) + 1)

    def sort_children(self) -> None:
        cur = self.tree.currentItem()
        if cur is None or cur.childCount() < 2:
            return
        states = {}
        kids = [cur.takeChild(0) for _ in range(cur.childCount())]
        for k in kids:
            states.update(self.tree._expanded_states(k))
        kids.sort(key=lambda it: it.title.casefold())
        cur.addChildren(kids)
        for k in kids:
            self.tree._restore_expanded(k, states)
        cur.setExpanded(True)
        self.tree.structureChanged.emit()

    def switch_pane(self) -> None:
        if self.tree.hasFocus() and self.editor.isEnabled():
            self.editor.setFocus()
        else:
            self.tree.setFocus()

    # ============================================================== editing

    def insert_datetime(self, which: str) -> None:
        if not self.editor.isEnabled():
            return
        now = QDateTime.currentDateTime()
        loc = QLocale()
        date = loc.toString(now.date(), QLocale.ShortFormat)
        time = loc.toString(now.time(), QLocale.ShortFormat)
        text = {"date": date, "time": time}.get(which, f"{date} {time}")
        self.editor.insertPlainText(text)

    def set_word_wrap(self, on: bool) -> None:
        self.editor.setLineWrapMode(QPlainTextEdit.WidgetWidth if on else QPlainTextEdit.NoWrap)

    def _update_tab_width(self) -> None:
        self.editor.setTabStopDistance(4 * self.editor.fontMetrics().horizontalAdvance(" "))

    def choose_font(self, which: str) -> None:
        widget = self.editor if which == "editor" else self.tree
        font, ok = QFontDialog.getFont(widget.font(), self,
                                       "Article Font" if which == "editor" else "Tree Font")
        if ok:
            widget.setFont(font)
            self.settings.setValue(f"fonts/{which}", font.toString())
            self._update_tab_width()

    def reset_fonts(self) -> None:
        for which, widget in (("editor", self.editor), ("tree", self.tree)):
            widget.setFont(QApplication.font())
            self.settings.remove(f"fonts/{which}")
        self._update_tab_width()

    # =============================================================== search

    def find_dialog(self) -> FindDialog:
        if self._find_dialog is None:
            self._find_dialog = FindDialog(self)
        return self._find_dialog

    def show_find(self, replace: bool = False) -> None:
        self.find_dialog().show_dialog(replace)

    def find_again(self, backward: bool = False) -> None:
        dlg = self.find_dialog()
        if not dlg.find_edit.text():
            self.show_find(False)
        else:
            dlg.find(backward)
            if dlg.status.text():
                self.statusBar().showMessage(dlg.status.text(), 5000)

    # =============================================================== files

    def _update_title(self) -> None:
        if self.path:
            name = os.path.basename(self.path)
        else:
            name = self.source_name or "Untitled"
        self.setWindowTitle(f"{name}[*] - {APP_NAME}")

    def _set_document(self, doc: Document) -> None:
        self._editing_item = None
        self._loading = True
        try:
            self.tree.load_document(doc)
        finally:
            self._loading = False
        self._show_item(self.tree.currentItem())
        self._backed_up_path = None
        if self._find_dialog is not None:
            self._find_dialog.last_match = None
        self.tree.setFocus()

    def maybe_save(self) -> bool:
        """Ask about unsaved changes. Returns False if the user cancelled."""
        self._commit_editor()
        if not self.isWindowModified():
            return True
        name = os.path.basename(self.path) if self.path else (self.source_name or "Untitled")
        answer = QMessageBox.warning(
            self, APP_NAME, f"Save changes to \"{name}\"?",
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel, QMessageBox.Save)
        if answer == QMessageBox.Save:
            return self.save()
        return answer == QMessageBox.Discard

    def new_file(self, confirm: bool = True) -> None:
        if confirm and not self.maybe_save():
            return
        doc = Document()
        doc.root.add_child(Node(NEW_FILE_TITLE))
        self._set_document(doc)
        self.path = None
        self.source_name = ""
        self.encoding = "cp1252"
        self.setWindowModified(False)
        self._update_title()

    def _last_dir(self) -> str:
        return self.settings.value("files/last_dir", os.path.expanduser("~"), type=str)

    def open_file(self, path: Optional[str] = None) -> bool:
        if not self.maybe_save():
            return False
        if path is None:
            path, _ = QFileDialog.getOpenFileName(self, "Open", self._last_dir(), FILE_FILTERS)
            if not path:
                return False
        return self.load_path(path)

    def _read_tree_file(self, path: str) -> Optional[Document]:
        try:
            return hjt.load(path)
        except (OSError, hjt.HjtFormatError, zipfile.BadZipFile) as exc:
            QMessageBox.warning(self, APP_NAME, f"Could not open \"{os.path.basename(path)}\".\n\n{exc}")
            return None

    def _show_repairs(self, doc: Document) -> None:
        if not doc.warnings:
            return
        box = QMessageBox(QMessageBox.Information, APP_NAME,
                          "The file was opened, but some parts needed repair.", parent=self)
        box.setInformativeText("Check the details, then save to keep the repaired copy.")
        box.setDetailedText("\n".join(doc.warnings))
        box.exec_()

    def load_path(self, path: str) -> bool:
        """Load without asking about unsaved changes (callers do that)."""
        doc = self._read_tree_file(path)
        if doc is None:
            return False
        if not doc.top_nodes:
            doc.root.add_child(Node(NEW_FILE_TITLE))
        self._set_document(doc)
        self.encoding = doc.encoding
        self.settings.setValue("files/last_dir", os.path.dirname(os.path.abspath(path)))
        self._add_recent(path)

        # Backups and archives are imported: Save asks for a new .hjt name
        # instead of overwriting the backup.
        imported = not path.lower().endswith(".hjt")
        if imported:
            self.path = None
            base = os.path.basename(path)
            for suffix in (".bak", ".BAK", "~", ".zip", ".ZIP"):
                if base.endswith(suffix):
                    base = base[: -len(suffix)]
            if not base.lower().endswith(".hjt"):
                base += ".hjt"
            self.source_name = base
            self.setWindowModified(True)
            self.statusBar().showMessage(
                f"Imported {os.path.basename(path)}. Use Save to keep it as a new file.", 10000)
        else:
            self.path = path
            self.source_name = ""
            self.setWindowModified(False)
            self.statusBar().showMessage(f"Opened {path}", 5000)
        self._update_title()
        self._show_repairs(doc)
        return True

    def import_tree_file(self, path: Optional[str] = None) -> bool:
        if path is None:
            path, _ = QFileDialog.getOpenFileName(self, "Import Tree File or Backup",
                                                  self._last_dir(), FILE_FILTERS)
            if not path:
                return False
        doc = self._read_tree_file(path)
        if doc is None:
            return False
        if not doc.top_nodes:
            self.statusBar().showMessage("That file has no nodes.", 4000)
            return False
        self._commit_editor()
        cur = self.tree.currentItem()
        if cur is None:
            self.tree.insert_nodes(doc.top_nodes, None, self.tree.topLevelItemCount())
        else:
            self.tree.insert_nodes(doc.top_nodes, cur, cur.childCount())
        n = doc.node_count()
        self.statusBar().showMessage(f"Imported {n} node{'s' if n != 1 else ''} from {os.path.basename(path)}.", 6000)
        self._show_repairs(doc)
        return True

    def import_text_file(self, path: Optional[str] = None) -> bool:
        if path is None:
            path, _ = QFileDialog.getOpenFileName(self, "Import Text File", self._last_dir(),
                                                  "Text files (*.txt *.text *.md *.log);;All files (*)")
            if not path:
                return False
        try:
            with open(path, "rb") as fh:
                text, _enc = hjt.decode_bytes(fh.read())
        except OSError as exc:
            QMessageBox.warning(self, APP_NAME, f"Could not read \"{path}\".\n\n{exc}")
            return False
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        title = os.path.splitext(os.path.basename(path))[0]
        cur = self.tree.currentItem()
        node = Node(title, text)
        if cur is None:
            self.tree.insert_nodes([node], None, self.tree.topLevelItemCount())
        else:
            self.tree.insert_nodes([node], cur, cur.childCount())
        return True

    def _nodes_for(self, scope: str) -> List[Node]:
        self._commit_editor()
        cur = self.tree.currentItem()
        if scope == "all" or cur is None:
            return self.tree.to_document().top_nodes
        node = NoteTree.item_to_node(cur)
        if scope == "node":
            node.children = []
        return [node]

    def export_text(self, scope: str, path: Optional[str] = None) -> bool:
        nodes = self._nodes_for(scope)
        if path is None:
            if scope == "all":
                base = os.path.splitext(os.path.basename(self.path or self.source_name or "Untitled"))[0]
            else:
                base = nodes[0].title
            safe = "".join(c if c not in '/\\:*?"<>|' else "_" for c in base).strip() or "export"
            path, _ = QFileDialog.getSaveFileName(self, "Export as Text",
                                                  os.path.join(self._last_dir(), safe + ".txt"),
                                                  "Text files (*.txt);;All files (*)")
            if not path:
                return False
        try:
            with open(path, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(export.outline_text(nodes))
        except OSError as exc:
            QMessageBox.critical(self, APP_NAME, f"Could not write \"{path}\".\n\n{exc}")
            return False
        self.statusBar().showMessage(f"Exported to {path}", 5000)
        return True

    def print_nodes(self, with_children: bool = True) -> None:
        from PyQt5.QtGui import QTextDocument
        from PyQt5.QtPrintSupport import QPrinter, QPrintPreviewDialog

        nodes = self._nodes_for("branch" if with_children else "node")
        document = QTextDocument()
        document.setDefaultFont(self.editor.font())
        document.setHtml(export.outline_html(nodes))
        printer = QPrinter(QPrinter.HighResolution)
        preview = QPrintPreviewDialog(printer, self)
        preview.setWindowTitle("Print Preview")
        preview.paintRequested.connect(document.print_)
        preview.resize(900, 700)
        preview.exec_()

    def save(self) -> bool:
        if not self.path:
            return self.save_as()
        return self._write(self.path)

    def save_as(self) -> bool:
        start = self.path or os.path.join(self._last_dir(), self.source_name or "Untitled.hjt")
        path, _ = QFileDialog.getSaveFileName(self, "Save As", start, "Tree notes (*.hjt)")
        if not path:
            return False
        if not os.path.splitext(path)[1]:
            path += ".hjt"
        return self._write(path)

    def _make_backup(self, path: str) -> None:
        """Once per opened file, copy the version on disk to ``<file>.bak``."""
        if not self.act_backup.isChecked() or self._backed_up_path == path or not os.path.exists(path):
            return
        try:
            shutil.copy2(path, path + ".bak")
            self._backed_up_path = path
        except OSError as exc:
            self.statusBar().showMessage(f"Could not write backup copy: {exc}", 8000)

    def _write(self, path: str, quiet: bool = False) -> bool:
        self._commit_editor()
        doc = self.tree.to_document()
        self._make_backup(path)
        try:
            hjt.save(doc, path, self.encoding)
        except OSError as exc:
            if quiet:
                self.statusBar().showMessage(f"Auto-save failed: {exc}", 10000)
            else:
                QMessageBox.critical(self, APP_NAME, f"Could not save \"{path}\".\n\n{exc}")
            return False
        self.path = path
        self.source_name = ""
        self.encoding = doc.encoding
        self.settings.setValue("files/last_dir", os.path.dirname(os.path.abspath(path)))
        self._add_recent(path)
        self.setWindowModified(False)
        self._update_title()
        when = QLocale().toString(QDateTime.currentDateTime().time(), QLocale.ShortFormat)
        self.statusBar().showMessage(f"{'Auto-saved' if quiet else 'Saved'} {path} at {when}", 5000)
        return True

    def set_autosave(self, on: bool) -> None:
        self.settings.setValue("options/autosave", on)
        if on:
            self.autosave_timer.start()
        else:
            self.autosave_timer.stop()

    def autosave(self) -> None:
        self._commit_editor()
        if self.path and self.isWindowModified():
            self._write(self.path, quiet=True)

    # ================================================================ misc

    def about(self) -> None:
        from PyQt5.QtCore import QT_VERSION_STR
        QMessageBox.about(
            self, f"About {APP_NAME}",
            f"<h3>{APP_NAME} {__version__}</h3>"
            "<p>A two-pane tree notes editor.</p>"
            "<p>Opens and saves .hjt tree notes files, including backup copies.</p>"
            f"<p><small>Qt {QT_VERSION_STR}</small></p>")

    def closeEvent(self, event) -> None:
        if self.maybe_save():
            self._save_settings()
            if self._find_dialog is not None:
                self._find_dialog.close()
            event.accept()
        else:
            event.ignore()
