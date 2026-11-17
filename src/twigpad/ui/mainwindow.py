# SPDX-License-Identifier: GPL-3.0-or-later
"""Main window: note tree on the left, article editor on the right."""
from __future__ import annotations

import os
import shutil
import zipfile
from typing import List, Optional

from PyQt5.QtCore import QDateTime, QEvent, QLocale, QMimeData, QSettings, Qt, QTimer, QUrl
from PyQt5.QtGui import QDesktopServices, QFont, QKeySequence, QTextCursor
from PyQt5.QtWidgets import (
    QAbstractItemView, QAction, QActionGroup, QApplication, QFileDialog, QFontDialog, QLabel,
    QMainWindow, QMenu, QMessageBox, QPlainTextEdit, QSplitter, QStyle, QSystemTrayIcon,
)

from .. import APP_ID, APP_NAME, __version__, export, hjt, importers, links, search, textfmt
from ..model import Document, Node
from . import icons
from .finddialog import FindDialog
from .highlighter import LinkHighlighter
from .tree import NoteItem, NoteTree

FILE_FILTERS = (
    "Tree notes and backups (*.hjt *.HJT *.bak *.BAK *.hjt~ *.zip);;"
    "Tree notes (*.hjt *.HJT);;"
    "All files (*)"
)
TEXT_FILTERS = "Text files (*.txt *.text *.md *.log);;All files (*)"
VIEW_MODES = ("both", "tree", "article")
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
        self.read_only = False
        self.view_mode = "both"
        self._tray: Optional[QSystemTrayIcon] = None
        self._last_auto_paste = ""

        self.tree = NoteTree()
        self.editor = QPlainTextEdit()
        self.link_highlighter = LinkHighlighter(self.editor.document())
        self.editor.viewport().installEventFilter(self)  # Ctrl+click follows links
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
        self.editor.undoAvailable.connect(lambda on: self.act_undo.setEnabled(on and not self.read_only))
        self.editor.redoAvailable.connect(lambda on: self.act_redo.setEnabled(on and not self.read_only))
        self.editor.copyAvailable.connect(lambda on: self.act_cut.setEnabled(on and not self.read_only))
        self.editor.copyAvailable.connect(self.act_copy.setEnabled)
        QApplication.clipboard().dataChanged.connect(self._on_clipboard_changed)

        self._restore_settings()
        self.new_file(confirm=False)

    # ================================================================ setup

    def _action(self, text, slot, shortcut=None, icon=None, tip=None,
                context_widget=None, checkable=False) -> QAction:
        act = QAction(text, self)
        if icon is not None:
            act.setIcon(icon)
        if isinstance(shortcut, (list, tuple)):
            act.setShortcuts([QKeySequence(k) for k in shortcut])
        elif shortcut:
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
        self.act_save_as = self._action("Save &As...", self.save_as, "Ctrl+Alt+S",
                                        tip="Save under a new name")
        self.act_import_tree = self._action(
            "Tree File or Backup (into the selected node)...", self.import_tree_file,
            tip="Add all nodes of another tree file or backup inside the selected node")
        self.act_import_text = self._action("Text Files as New Nodes...", self.import_text_files,
                                            tip="Add one or more text files as new nodes inside the selected node")
        self.act_import_csv = self._action("CSV File (one node per row)...", self.import_csv_file,
                                           tip="Add a node for every row of a CSV file inside the selected node")
        self.act_export_node = self._action("Selected Node...", lambda: self.export_file("text", "node"))
        self.act_export_branch = self._action("Selected Node and Subnodes...",
                                              lambda: self.export_file("text", "branch"))
        self.act_export_all = self._action("Whole File...", lambda: self.export_file("text", "all"))
        self.act_html_node = self._action("Selected Node...", lambda: self.export_file("html", "node"))
        self.act_html_branch = self._action("Selected Node and Subnodes...",
                                            lambda: self.export_file("html", "branch"))
        self.act_html_all = self._action("Whole File...", lambda: self.export_file("html", "all"))
        self.act_export_tree = self._action(
            "Selected Node and Subnodes as Tree File (.hjt)...", lambda: self.export_file("hjt", "branch"),
            tip="Save the selected branch as a separate tree notes file")
        self.act_print = self._action("&Print...", lambda: self.print_nodes("branch"), QKeySequence.Print,
                                      icons.themed("document-print", S.SP_FileDialogDetailedView),
                                      "Print the selected node and its subnodes")
        self.act_print_node = self._action("Print Selected Node &Only...", lambda: self.print_nodes("node"))
        self.act_print_all = self._action("Print &Whole File...", lambda: self.print_nodes("all"))
        self.act_read_only = self._action("Read &Only", self.set_read_only, checkable=True,
                                          tip="Protect the open file from changes")
        self.act_tray = self._action("&Minimize to Tray", self.minimize_to_tray, "Ctrl+M",
                                     tip="Hide the window; click the tray icon to bring it back")
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
        self.act_follow_link = self._action("&Follow Link", self.follow_link, "Ctrl+H",
                                            tip="Open the link at the cursor (Ctrl+click also works)",
                                            context_widget=e)
        self.act_link_file = self._action("Link to &File...", lambda: self.insert_file_link(False),
                                          tip="Insert a link to a file")
        self.act_link_folder = self._action("Link to F&older...", lambda: self.insert_file_link(True),
                                            tip="Insert a link to a folder")
        self.act_insert_file = self._action("Text from F&ile...", self.insert_text_file,
                                            tip="Insert the contents of a text file at the cursor")

        # Format (article text: the selection, or the whole article)
        self.act_upper = self._action("&UPPERCASE", lambda: self.format_text(textfmt.to_upper),
                                      tip="Change the selection (or the whole article) to capitals")
        self.act_lower = self._action("&lowercase", lambda: self.format_text(textfmt.to_lower),
                                      tip="Change the selection (or the whole article) to small letters")
        self.act_strip = self._action("Remove Leading &Spaces",
                                      lambda: self.format_text(textfmt.remove_leading_spaces),
                                      tip="Remove spaces and tabs at the start of each line")
        self.act_strip_returns = self._action(
            "Remove Leading Spaces and &Returns",
            lambda: self.format_text(textfmt.remove_leading_spaces_and_returns),
            tip="Remove quote marks and indentation and join wrapped lines into paragraphs "
                "(for pasted email)")

        # Search
        self.act_find = self._action("&Find...", lambda: self.show_find(False), ["Ctrl+F", "Shift+F12"],
                                     icons.themed("edit-find", S.SP_FileDialogContentsView),
                                     "Search titles and articles of all nodes")
        self.act_find_next = self._action("Find &Next", lambda: self.find_again(False), "F3")
        self.act_find_prev = self._action("Find &Previous", lambda: self.find_again(True), "Shift+F3")
        self.act_replace = self._action("&Replace...", lambda: self.show_find(True), "Ctrl+R")

        # Node (keys work while the tree has the focus)
        self.act_add_child = self._action("Add &Child Node", self.add_child_node, "Ins",
                                          icons.add_child(), "Add a node inside the selected one",
                                          context_widget=t)
        self.act_add_after = self._action("&Add Node Below", self.add_node_after, ["Shift+Ins", "Return"],
                                          icons.add_sibling(), "Add a node below the selected one",
                                          context_widget=t)
        self.act_add_before = self._action("Add Node A&bove", self.add_node_before, "Ctrl+Shift+Ins",
                                           tip="Add a node above the selected one", context_widget=t)
        self.act_rename = self._action("&Rename", self.rename_node, "F2",
                                       tip="Rename the selected node", context_widget=t)
        self.act_delete = self._action("&Delete Node", self.delete_node, "Del",
                                       icons.themed("edit-delete", S.SP_TrashIcon),
                                       "Delete the selected node and everything inside it",
                                       context_widget=t)
        # Explicit keys: on Linux the standard Copy/Paste also include
        # Ctrl+Ins / Shift+Ins, which add nodes here.
        self.act_cut_node = self._action("Cu&t Node", self.cut_node, "Ctrl+X",
                                         tip="Cut the selected node and its subnodes", context_widget=t)
        self.act_copy_node = self._action("C&opy Node", self.copy_node, "Ctrl+C",
                                          tip="Copy the selected node and its subnodes", context_widget=t)
        self.act_paste_child = self._action("&Paste Node (as Child)", lambda: self.paste_node(True),
                                            "Ctrl+V", tip="Paste inside the selected node",
                                            context_widget=t)
        self.act_paste_node = self._action("Paste Node &Below", lambda: self.paste_node(False),
                                           "Ctrl+Shift+V", tip="Paste below the selected node",
                                           context_widget=t)
        self.act_copy_link = self._action("Copy Node &Link Address", self.copy_node_link, "Ctrl+Shift+H",
                                          tip="Copy a node:// link to paste into another article",
                                          context_widget=t)
        self.act_move_up = self._action("Move &Up", self.tree.move_up, "Shift+Up",
                                        icons.themed("go-up", S.SP_ArrowUp), "Move node up",
                                        context_widget=t)
        self.act_move_down = self._action("Move Do&wn", self.tree.move_down, "Shift+Down",
                                          icons.themed("go-down", S.SP_ArrowDown), "Move node down",
                                          context_widget=t)
        self.act_move_left = self._action("Move &Left (out a level)", self.tree.move_left,
                                          "Shift+Left", icons.themed("go-previous", S.SP_ArrowLeft),
                                          "Move node out one level", context_widget=t)
        self.act_move_right = self._action("Move R&ight (in a level)", self.tree.move_right,
                                           "Shift+Right", icons.themed("go-next", S.SP_ArrowRight),
                                           "Move node in one level", context_widget=t)
        self.act_next_sibling = self._action("&Next Sibling", lambda: self.tree.select_sibling(1),
                                             "Alt+Down", context_widget=t)
        self.act_prev_sibling = self._action("Pre&vious Sibling", lambda: self.tree.select_sibling(-1),
                                             "Alt+Up", context_widget=t)
        self.act_sort = self._action("&Sort Subnodes (One Level)", self.sort_children, "Ctrl+Shift+S",
                                     tip="Sort the nodes inside the selected node by title",
                                     context_widget=t)
        self.act_sort_all = self._action("Sort &Whole Tree (All Levels)", self.sort_whole_tree)
        self.act_siblings_right = self._action(
            "Next Siblings Move Right", self.move_next_siblings_right,
            tip="The nodes below the selected one (same level) move inside it")
        self.act_children_left = self._action(
            "All Children Move Left", self.move_children_left,
            tip="The nodes inside the selected one move out, to just below it")
        self.act_copy_name = self._action("Copy Node &Name", self.copy_node_name,
                                          tip="Copy the title of the selected node")
        self.act_paste_name = self._action("Paste Node Na&me", self.paste_node_name,
                                           tip="Rename the selected node to the text on the clipboard")

        # View
        self.act_word_wrap = self._action("&Word Wrap", self.set_word_wrap, checkable=True)
        self.act_classic_tree = self._action("C&lassic Tree Look", self.set_classic_tree, checkable=True,
                                             tip="Folder icons, dotted lines and +/- boxes in the tree")
        self.view_group = QActionGroup(self)
        self.act_view_modes = {}
        for mode, label in (("both", "Tree &and Article"), ("tree", "Tree O&nly"),
                            ("article", "Article Onl&y")):
            act = QAction(label, self, checkable=True)
            act.triggered.connect(lambda _c=False, m=mode: self.set_view_mode(m))
            self.view_group.addAction(act)
            self.act_view_modes[mode] = act
        self.act_expand_all = self._action("&Expand All", self.tree.expandAll)
        self.act_collapse_all = self._action("&Collapse All", self.tree.collapseAll)
        self.act_expand_one = self._action("Expand Selected Node (One Level)",
                                           lambda: self.expand_branch(True, False))
        self.act_expand_branch = self._action("Expand Selected Node (All Levels)",
                                              lambda: self.expand_branch(True, True))
        self.act_collapse_branch = self._action("Collapse Selected Node",
                                                lambda: self.expand_branch(False, True))
        self.act_switch_pane = self._action("&Switch Pane", self.switch_pane, ["F6", "Ctrl+Tab"],
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
        self.act_auto_paste = self._action(
            "Automatic &Paste", self.set_auto_paste, checkable=True,
            tip="Text copied in other programs is added to the current article")

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
        sub.addActions([self.act_import_tree, self.act_import_text, self.act_import_csv])
        sub = m.addMenu("&Export")
        text = sub.addMenu("As &Text")
        text.addActions([self.act_export_node, self.act_export_branch, self.act_export_all])
        page = sub.addMenu("As &HTML Web Page")
        page.addActions([self.act_html_node, self.act_html_branch, self.act_html_all])
        sub.addAction(self.act_export_tree)
        m.addSeparator()
        m.addActions([self.act_print, self.act_print_node, self.act_print_all])
        m.addSeparator()
        m.addAction(self.act_read_only)
        m.addSeparator()
        m.addActions([self.act_tray, self.act_exit])

        m = mb.addMenu("&Edit")
        m.addActions([self.act_undo, self.act_redo])
        m.addSeparator()
        m.addActions([self.act_cut, self.act_copy, self.act_paste])
        m.addSeparator()
        m.addAction(self.act_select_all)
        m.addSeparator()
        m.addActions([self.act_date, self.act_time, self.act_datetime])
        m.addSeparator()
        m.addAction(self.act_follow_link)
        sub = m.addMenu("&Insert")
        sub.addActions([self.act_link_file, self.act_link_folder])
        sub.addSeparator()
        sub.addAction(self.act_insert_file)

        m = mb.addMenu("F&ormat")
        m.addActions([self.act_upper, self.act_lower])
        m.addSeparator()
        m.addActions([self.act_strip, self.act_strip_returns])

        m = mb.addMenu("&Search")
        m.addActions([self.act_find, self.act_find_next, self.act_find_prev])
        m.addSeparator()
        m.addAction(self.act_replace)

        m = mb.addMenu("&Node")
        m.addActions(self._node_menu_actions())

        m = mb.addMenu("&View")
        m.addActions(list(self.act_view_modes.values()))
        m.addSeparator()
        m.addActions([self.act_word_wrap, self.act_classic_tree])
        m.addSeparator()
        m.addActions([self.act_expand_one, self.act_expand_branch, self.act_collapse_branch])
        m.addActions([self.act_expand_all, self.act_collapse_all])
        m.addSeparator()
        m.addActions([self.act_article_font, self.act_tree_font, self.act_reset_fonts])
        m.addSeparator()
        self.view_menu = m
        m.addAction(self.act_switch_pane)

        m = mb.addMenu("&Options")
        m.addActions([self.act_open_last, self.act_backup, self.act_autosave])
        m.addSeparator()
        m.addAction(self.act_auto_paste)

        m = mb.addMenu("&Help")
        m.addAction(self.act_about)

        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._tree_menu)

    def _node_menu_actions(self) -> List[QAction]:
        sep = lambda: self._separator()  # noqa: E731
        return [self.act_add_child, self.act_add_after, self.act_add_before, sep(),
                self.act_rename, self.act_delete, sep(),
                self.act_cut_node, self.act_copy_node, self.act_paste_child, self.act_paste_node, sep(),
                self.act_copy_name, self.act_paste_name, self.act_copy_link, sep(),
                self.act_move_up, self.act_move_down, self.act_move_left, self.act_move_right,
                self.act_siblings_right, self.act_children_left, sep(),
                self.act_prev_sibling, self.act_next_sibling, sep(),
                self.act_sort, self.act_sort_all]

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
        self.read_only_label = QLabel(" Read only ")
        self.read_only_label.setVisible(False)
        sb.addPermanentWidget(self.read_only_label)
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
        self.act_classic_tree.setChecked(s.value("tree/classic", True, type=bool))
        self.tree.set_classic(self.act_classic_tree.isChecked())
        mode = s.value("view/mode", "both", type=str)
        self.set_view_mode(mode if mode in VIEW_MODES else "both")
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
        top = NoteTree.is_top(cur)
        rw = not self.read_only
        for act in (self.act_copy_node, self.act_copy_link, self.act_copy_name,
                    self.act_export_node, self.act_export_branch, self.act_html_node,
                    self.act_html_branch, self.act_export_tree, self.act_print, self.act_print_node,
                    self.act_expand_one, self.act_expand_branch, self.act_collapse_branch):
            act.setEnabled(has)
        for act in (self.act_add_child, self.act_rename, self.act_paste_child, self.act_paste_name):
            act.setEnabled(has and rw)
        # The single top node cannot get siblings, be removed or be moved.
        for act in (self.act_add_after, self.act_add_before, self.act_delete, self.act_cut_node,
                    self.act_paste_node):
            act.setEnabled(has and rw and not top)
        self.act_move_up.setEnabled(has and rw and idx > 0)
        self.act_move_down.setEnabled(has and rw and idx < siblings - 1)
        self.act_move_left.setEnabled(has and rw and not top and not NoteTree.is_top(cur.parent()))
        self.act_move_right.setEnabled(has and rw and idx > 0)
        self.act_siblings_right.setEnabled(has and rw and not top and idx < siblings - 1)
        self.act_children_left.setEnabled(has and rw and not top and cur.childCount() > 0)
        self.act_prev_sibling.setEnabled(has and idx > 0)
        self.act_next_sibling.setEnabled(has and idx < siblings - 1)
        self.act_sort.setEnabled(has and rw and cur.childCount() > 1)
        self.act_sort_all.setEnabled(rw)
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
        self._add_sibling(after=True)

    def add_node_before(self) -> None:
        self._add_sibling(after=False)

    def _add_sibling(self, after: bool) -> None:
        item = self.tree.add_sibling(after=after)
        if item is None:
            self.statusBar().showMessage(
                "The top node can't have nodes next to it. Use Ins to add a child node.", 5000)
        else:
            self._start_rename(item)

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
        if NoteTree.is_top(item):
            self.statusBar().showMessage("The top node can't be deleted.", 4000)
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
        if NoteTree.is_top(item):
            self.statusBar().showMessage("The top node can't be cut; use Copy instead.", 4000)
            return
        if item is not None and self.copy_node():
            self._remove(item)

    def copy_node_link(self) -> None:
        item = self.tree.currentItem()
        if item is None:
            return
        address = links.node_address(self.tree.title_path(item))
        QApplication.clipboard().setText(f"[{address}]")
        self.statusBar().showMessage(f"Copied link: [{address}]", 5000)

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
        if not self._writable():
            return
        nodes = self._clipboard_nodes()
        if not nodes:
            self.statusBar().showMessage("Nothing to paste.", 3000)
            return
        self._insert_under_current(nodes, as_child)

    def _insert_under_current(self, nodes: List[Node], as_child: bool = True) -> None:
        """Insert inside the selected node, or below it. Never creates a
        second top node: next to the top node means inside it."""
        cur = self.tree.currentItem() or self.tree.topLevelItem(0)
        if cur is None:  # empty tree: the first node becomes the top node
            if len(nodes) > 1:
                wrapper = Node("Notes")
                for n in nodes:
                    wrapper.add_child(n)
                nodes = [wrapper]
            self.tree.insert_nodes(nodes, None, 0)
        elif as_child or NoteTree.is_top(cur):
            self.tree.insert_nodes(nodes, cur, cur.childCount())
        else:
            self.tree.insert_nodes(nodes, cur.parent(), self.tree.index_in_parent(cur) + 1)

    def sort_children(self) -> None:
        cur = self.tree.currentItem()
        if cur is not None and self.tree.sort_children(cur):
            cur.setExpanded(True)

    def sort_whole_tree(self) -> None:
        if not self._writable():
            return
        for i in range(self.tree.topLevelItemCount()):
            self.tree.sort_children(self.tree.topLevelItem(i), recursive=True)

    def move_next_siblings_right(self) -> int:
        if not self._writable():
            return 0
        n = self.tree.move_next_siblings_right()
        if n:
            self.statusBar().showMessage(f"Moved {n} node{'s' if n != 1 else ''} inside the selected node.", 4000)
        return n

    def move_children_left(self) -> int:
        if not self._writable():
            return 0
        if NoteTree.is_top(self.tree.currentItem()):
            self.statusBar().showMessage("The nodes inside the top node can't move out of it.", 4000)
            return 0
        n = self.tree.move_children_left()
        if n:
            self.statusBar().showMessage(f"Moved {n} node{'s' if n != 1 else ''} out one level.", 4000)
        return n

    def copy_node_name(self) -> None:
        item = self.tree.currentItem()
        if item is not None:
            QApplication.clipboard().setText(item.title)
            self.statusBar().showMessage(f"Copied node name: {item.title}", 4000)

    def paste_node_name(self) -> bool:
        item = self.tree.currentItem()
        if item is None or not self._writable():
            return False
        text = QApplication.clipboard().text()
        title = next((" ".join(line.split()) for line in text.splitlines() if line.strip()), "")
        if not title:
            self.statusBar().showMessage("There is no text on the clipboard.", 3000)
            return False
        item.setText(0, title[:200])
        return True

    def expand_branch(self, expanded: bool, all_levels: bool) -> None:
        item = self.tree.currentItem()
        if item is not None:
            NoteTree.set_branch_expanded(item, expanded, all_levels)
            self.tree.scrollToItem(item)

    def switch_pane(self) -> None:
        if self.view_mode != "both":
            return
        if self.tree.hasFocus() and self.editor.isEnabled():
            self.editor.setFocus()
        else:
            self.tree.setFocus()

    # ====================================================== view & modes

    def set_view_mode(self, mode: str) -> None:
        """'both' panes, the 'tree' only, or the 'article' only."""
        self.view_mode = mode
        self.act_view_modes[mode].setChecked(True)
        self.tree.setVisible(mode != "article")
        self.editor.setVisible(mode != "tree")
        if mode == "article":
            self.editor.setFocus()
        elif mode == "tree":
            self.tree.setFocus()
        self.settings.setValue("view/mode", mode)

    def _writable(self) -> bool:
        if self.read_only:
            self.statusBar().showMessage("The file is read only (File > Read Only).", 4000)
            return False
        return True

    def set_read_only(self, on: bool) -> None:
        """Protect the open file: nothing can be changed until it is turned off."""
        self.read_only = on
        if self.act_read_only.isChecked() != on:
            self.act_read_only.blockSignals(True)
            self.act_read_only.setChecked(on)
            self.act_read_only.blockSignals(False)
        self.editor.setReadOnly(on)
        self.tree.setDragDropMode(QAbstractItemView.NoDragDrop if on else QAbstractItemView.InternalMove)
        self.tree.setEditTriggers(QAbstractItemView.NoEditTriggers if on else QAbstractItemView.EditKeyPressed)
        for act in (self.act_save, self.act_paste, self.act_date, self.act_time, self.act_datetime,
                    self.act_link_file, self.act_link_folder, self.act_insert_file, self.act_replace,
                    self.act_upper, self.act_lower, self.act_strip, self.act_strip_returns,
                    self.act_import_tree, self.act_import_text, self.act_import_csv):
            act.setEnabled(not on)
        doc = self.editor.document()
        self.act_undo.setEnabled(not on and doc.isUndoAvailable())
        self.act_redo.setEnabled(not on and doc.isRedoAvailable())
        self.act_cut.setEnabled(not on and self.editor.textCursor().hasSelection())
        self.read_only_label.setVisible(on)
        if self._find_dialog is not None and on and self._find_dialog.btn_replace.isVisible():
            self._find_dialog.show_dialog(False)
        self._update_node_actions()

    def minimize_to_tray(self) -> None:
        """Hide the window to the system tray (or just minimize when there is no tray)."""
        if not QSystemTrayIcon.isSystemTrayAvailable():
            self.showMinimized()
            return
        if self._tray is None:
            self._tray = QSystemTrayIcon(icons.app_icon(), self)
            self._tray.setToolTip(APP_NAME)
            menu = QMenu(self)
            menu.addAction(f"&Show {APP_NAME}", self.restore_from_tray)
            menu.addSeparator()
            menu.addAction("E&xit", lambda: (self.restore_from_tray(), self.close()))
            self._tray.setContextMenu(menu)
            self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()
        self.hide()

    def _on_tray_activated(self, reason) -> None:
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.restore_from_tray()

    def restore_from_tray(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()
        if self._tray is not None:
            self._tray.hide()

    # ===================================================== automatic paste

    def set_auto_paste(self, on: bool) -> None:
        # Start from what is on the clipboard now, so only new copies are added.
        self._last_auto_paste = QApplication.clipboard().text() if on else ""
        if on:
            self.statusBar().showMessage(
                "Automatic Paste is on: text you copy in other programs is added to this article.", 6000)

    def _clipboard_is_ours(self) -> bool:
        return QApplication.clipboard().ownsClipboard()

    def _on_clipboard_changed(self) -> None:
        if not self.act_auto_paste.isChecked() or self.read_only or not self.editor.isEnabled():
            return
        if self._clipboard_is_ours():
            return  # copied inside Twigpad
        text = QApplication.clipboard().text()
        if not text or text == self._last_auto_paste:
            return
        self._last_auto_paste = text
        self.auto_paste(text)

    def auto_paste(self, text: str) -> None:
        """Add ``text`` at the end of the current article, on its own lines."""
        cursor = QTextCursor(self.editor.document())
        cursor.movePosition(QTextCursor.End)
        existing = self.editor.toPlainText()
        prefix = "" if not existing or existing.endswith("\n") else "\n"
        cursor.insertText(prefix + text.replace("\r\n", "\n").rstrip("\n") + "\n")
        self.editor.setTextCursor(cursor)
        self.editor.ensureCursorVisible()

    # ================================================================ links

    def link_at_cursor(self, cursor=None) -> Optional[str]:
        cursor = cursor or self.editor.textCursor()
        block = cursor.block().text()
        pos = search.from_qt(block, cursor.positionInBlock())
        selection = cursor.selectedText() if cursor.hasSelection() else ""
        return links.link_at(block, pos, selection)

    def follow_link(self, link: Optional[str] = None) -> bool:
        link = link or self.link_at_cursor()
        if not link:
            self.statusBar().showMessage("There is no link at the cursor.", 4000)
            return False
        kind, target = links.classify(link)
        if kind == links.NODE:
            item = links.resolve_node(
                [self.tree.topLevelItem(i) for i in range(self.tree.topLevelItemCount())],
                target, lambda it: it.text(0),
                lambda it: [it.child(i) for i in range(it.childCount())])
            if item is None:
                self.statusBar().showMessage(f"No node found for [{link}].", 6000)
                return False
            self.tree.setCurrentItem(item)
            self.tree.scrollToItem(item)
            self.tree.setFocus()
            return True
        if kind == links.FILE:
            path = os.path.expanduser(target)
            if not os.path.isabs(path):
                # Relative links are relative to the folder of the open file.
                base = os.path.dirname(os.path.abspath(self.path)) if self.path else os.getcwd()
                path = os.path.join(base, path)
            if not os.path.exists(path):
                self.statusBar().showMessage(f"File not found: {path}", 6000)
                return False
            return self._open_url(QUrl.fromLocalFile(path))
        return self._open_url(QUrl(target, QUrl.TolerantMode))

    def _open_url(self, url: QUrl) -> bool:
        """Hand a link to the desktop (browser, mail program, file manager)."""
        ok = QDesktopServices.openUrl(url)
        if not ok:
            self.statusBar().showMessage(f"Could not open {url.toString()}", 6000)
        return ok

    def insert_file_link(self, folder: bool = False) -> None:
        if not self.editor.isEnabled() or not self._writable():
            return
        if folder:
            path = QFileDialog.getExistingDirectory(self, "Link to Folder", self._last_dir())
        else:
            path, _ = QFileDialog.getOpenFileName(self, "Link to File", self._last_dir())
        if path:
            self.editor.insertPlainText(f"[file://{path}]")
            self.editor.setFocus()

    def eventFilter(self, obj, event) -> bool:
        if (obj is self.editor.viewport() and event.type() == QEvent.MouseButtonRelease
                and event.button() == Qt.LeftButton and event.modifiers() & Qt.ControlModifier):
            link = self.link_at_cursor(self.editor.cursorForPosition(event.pos()))
            if link:
                self.follow_link(link)
                return True
        return super().eventFilter(obj, event)

    # ============================================================== editing

    def insert_datetime(self, which: str) -> None:
        if not self.editor.isEnabled() or not self._writable():
            return
        now = QDateTime.currentDateTime()
        loc = QLocale()
        date = loc.toString(now.date(), QLocale.ShortFormat)
        time = loc.toString(now.time(), QLocale.ShortFormat)
        text = {"date": date, "time": time}.get(which, f"{date} {time}")
        self.editor.insertPlainText(text)

    def set_classic_tree(self, on: bool) -> None:
        self.tree.set_classic(on)
        self.settings.setValue("tree/classic", on)

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
        self.set_read_only(False)
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
        wrapped = doc.ensure_single_root(
            os.path.splitext(os.path.basename(path))[0].split(".")[0] or NEW_FILE_TITLE)
        self._set_document(doc)
        self.encoding = doc.encoding
        self.settings.setValue("files/last_dir", os.path.dirname(os.path.abspath(path)))
        self._add_recent(path)

        # Backups and archives are imported: Save asks for a new .hjt name
        # instead of overwriting the backup.
        imported = not path.lower().endswith(".hjt")
        locked = False
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
            self.setWindowModified(wrapped)
            locked = not os.access(path, os.W_OK)
            self.statusBar().showMessage(
                f"Opened {path}" + (" (read only: the file can't be changed)" if locked else ""), 5000)
        self.set_read_only(locked)
        self._update_title()
        self._show_repairs(doc)
        return True

    def import_tree_file(self, path: Optional[str] = None) -> bool:
        if not self._writable():
            return False
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
        self._insert_under_current(doc.top_nodes)
        n = doc.node_count()
        self.statusBar().showMessage(f"Imported {n} node{'s' if n != 1 else ''} from {os.path.basename(path)}.", 6000)
        self._show_repairs(doc)
        return True

    def _read_text(self, path: str) -> Optional[str]:
        try:
            with open(path, "rb") as fh:
                text, _enc = hjt.decode_bytes(fh.read())
        except OSError as exc:
            QMessageBox.warning(self, APP_NAME, f"Could not read \"{path}\".\n\n{exc}")
            return None
        return text.replace("\r\n", "\n").replace("\r", "\n")

    def import_text_file(self, path: Optional[str] = None) -> bool:
        return self.import_text_files([path] if path else None)

    def import_text_files(self, paths: Optional[List[str]] = None) -> bool:
        """Add each text file as a new node inside the selected node."""
        if not self._writable():
            return False
        if paths is None:
            paths, _ = QFileDialog.getOpenFileNames(self, "Import Text Files", self._last_dir(), TEXT_FILTERS)
            if not paths:
                return False
        nodes = []
        for path in paths:
            text = self._read_text(path)
            if text is not None:
                nodes.append(Node(os.path.splitext(os.path.basename(path))[0], text))
        if not nodes:
            return False
        self._commit_editor()
        self._insert_under_current(nodes)
        n = len(nodes)
        self.statusBar().showMessage(f"Imported {n} text file{'s' if n != 1 else ''}.", 5000)
        return True

    def import_csv_file(self, path: Optional[str] = None) -> bool:
        """Add a node for every row of a CSV file inside the selected node."""
        if not self._writable():
            return False
        if path is None:
            path, _ = QFileDialog.getOpenFileName(self, "Import CSV File", self._last_dir(),
                                                  "CSV files (*.csv *.CSV *.tsv *.txt);;All files (*)")
            if not path:
                return False
        text = self._read_text(path)
        if text is None:
            return False
        nodes = importers.csv_to_nodes(text)
        if not nodes:
            self.statusBar().showMessage("That file has no rows.", 4000)
            return False
        self._commit_editor()
        self._insert_under_current(nodes)
        n = len(nodes)
        self.statusBar().showMessage(f"Imported {n} row{'s' if n != 1 else ''} from {os.path.basename(path)}.", 5000)
        return True

    def insert_text_file(self, path: Optional[str] = None) -> bool:
        """Insert the contents of a text file at the cursor."""
        if not self.editor.isEnabled() or not self._writable():
            return False
        if path is None:
            path, _ = QFileDialog.getOpenFileName(self, "Insert Text from File", self._last_dir(), TEXT_FILTERS)
            if not path:
                return False
        text = self._read_text(path)
        if text is None:
            return False
        self.editor.insertPlainText(text)
        self.editor.setFocus()
        return True

    def format_text(self, func) -> bool:
        """Apply a Format-menu change to the selection, or to the whole article
        when nothing is selected. One Ctrl+Z undoes it."""
        if not self.editor.isEnabled() or not self._writable():
            return False
        cursor = self.editor.textCursor()
        whole = not cursor.hasSelection()
        if whole:
            old = self.editor.toPlainText()
            pos = cursor.position()
            cursor.select(QTextCursor.Document)
        else:
            old = cursor.selectedText().replace(" ", "\n")
            start = cursor.selectionStart()
        new = func(old)
        if new == old:
            return False
        cursor.beginEditBlock()
        cursor.insertText(new)
        cursor.endEditBlock()
        if whole:
            cursor.setPosition(min(pos, self.editor.document().characterCount() - 1))
        else:
            cursor.setPosition(start)
            cursor.setPosition(start + search.to_qt(new, len(new)), QTextCursor.KeepAnchor)
        self.editor.setTextCursor(cursor)
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

    _EXPORT_KINDS = {
        "text": ("Export as Text", ".txt", "Text files (*.txt);;All files (*)"),
        "html": ("Export as HTML", ".html", "Web pages (*.html *.htm);;All files (*)"),
        "hjt": ("Export as Tree File", ".hjt", "Tree notes (*.hjt)"),
    }

    def export_text(self, scope: str, path: Optional[str] = None) -> bool:
        return self.export_file("text", scope, path)

    def export_file(self, kind: str, scope: str, path: Optional[str] = None) -> bool:
        """Export the selected node ('node'), its branch ('branch') or the whole
        file ('all') as plain text, an HTML page or a separate .hjt file."""
        nodes = self._nodes_for(scope)
        caption, ext, filters = self._EXPORT_KINDS[kind]
        if path is None:
            if scope == "all":
                base = os.path.splitext(os.path.basename(self.path or self.source_name or "Untitled"))[0]
            else:
                base = nodes[0].title
            safe = "".join(c if c not in '/\\:*?"<>|' else "_" for c in base).strip() or "export"
            path, _ = QFileDialog.getSaveFileName(self, caption, os.path.join(self._last_dir(), safe + ext),
                                                  filters)
            if not path:
                return False
            if not os.path.splitext(path)[1]:
                path += ext
        if kind == "hjt" and self.path and os.path.abspath(path) == os.path.abspath(self.path):
            QMessageBox.warning(self, APP_NAME, "Choose a different name: that is the file you have open.")
            return False
        try:
            if kind == "hjt":
                doc = Document()
                if len(nodes) == 1:
                    doc.root.add_child(nodes[0])
                else:
                    wrapper = doc.root.add_child(Node(NEW_FILE_TITLE))
                    for n in nodes:
                        wrapper.add_child(n)
                hjt.save(doc, path, self.encoding)
            else:
                if kind == "html":
                    title = os.path.splitext(os.path.basename(self.path or self.source_name or ""))[0]
                    content = export.html_page(nodes, title if scope == "all" else "")
                else:
                    content = export.outline_text(nodes)
                with open(path, "w", encoding="utf-8", newline="\n") as fh:
                    fh.write(content)
        except OSError as exc:
            QMessageBox.critical(self, APP_NAME, f"Could not write \"{path}\".\n\n{exc}")
            return False
        self.statusBar().showMessage(f"Exported to {path}", 5000)
        return True

    def print_nodes(self, scope: str = "branch") -> None:
        """Print preview of the selected node ('node'), its branch ('branch')
        or the whole file ('all')."""
        from PyQt5.QtGui import QTextDocument
        from PyQt5.QtPrintSupport import QPrinter, QPrintPreviewDialog

        nodes = self._nodes_for(scope)
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
        if self.read_only:
            return self.save_as()
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
        if self.path and self.isWindowModified() and not self.read_only:
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
