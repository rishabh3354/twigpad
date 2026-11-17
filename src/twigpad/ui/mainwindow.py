# SPDX-License-Identifier: GPL-3.0-or-later
"""Main window: note tree on the left, article editor on the right."""
from __future__ import annotations

import os
import shutil
import zipfile
from typing import List, Optional

from PyQt5.QtCore import (
    QDateTime, QEvent, QFileSystemWatcher, QLocale, QMimeData, QSettings, Qt, QTimer, QUrl,
)
from PyQt5.QtGui import (
    QColor, QDesktopServices, QPalette, QFont, QIcon, QImage, QKeySequence, QPixmap, QTextBlockFormat,
    QTextCharFormat, QTextCursor, QTextDocument, QTextLength, QTextListFormat, QTextTableFormat,
)
from PyQt5.QtWidgets import (
    QAbstractItemView, QAction, QActionGroup, QApplication, QColorDialog, QDialog,
    QDialogButtonBox, QFileDialog, QFontDialog, QFormLayout, QInputDialog, QLabel, QLineEdit,
    QMainWindow, QMenu, QMessageBox, QSplitter, QStyle, QSystemTrayIcon, QTabBar, QTextEdit,
    QVBoxLayout, QWidget,
)

from .. import (
    APP_ID, APP_NAME, __version__, export, hjt, importers, links, portable, search, spell, tags,
    textfmt, twig,
)
from ..model import Document, Node
from . import icons, treestyle
from .editor import ArticleEdit, heading_format
from .finddialog import FindDialog
from .highlighter import ArticleHighlighter
from .panels import BacklinksPanel, TagsPanel
from .tree import NoteItem, NoteTree

FILE_FILTERS = (
    "Notes files and backups (*.twig *.hjt *.HJT *.bak *.BAK *.hjt~ *.zip);;"
    "Twigpad notes (*.twig);;"
    "Tree notes (*.hjt *.HJT);;"
    "All files (*)"
)
TWIG_FILTER = "Twigpad notes (*.twig)"
HJT_FILTER = "Tree notes (*.hjt)"
OWN_EXTS = (".hjt", ".twig")
IMAGE_FILTERS = "Images (*.png *.jpg *.jpeg *.gif *.bmp *.webp);;All files (*)"
TEXT_FILTERS = "Text files (*.txt *.text *.md *.log);;All files (*)"
VIEW_MODES = ("both", "tree", "article")
STARTUP_MODES = {"reopen": "&Reopen the Last File", "ask": "&Ask Whether to Reopen the Last File",
                 "quickstart": "Show the &Quick Start Window", "new": "Start With a &New File"}
CLOSE_MODES = {"ask": "&Ask Whether to Save", "save": "&Save Automatically",
               "discard": "&Don't Save (not recommended)"}
COLOR_KEYS = ("tree_bg", "tree_fg", "article_bg", "article_fg")
NEW_FILE_TITLE = "Notes"
NODE_MIME = "application/x-twigpad-notes"
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
        self._views: List[dict] = []          # one per tab: {"root": item|None, "current": item|None}
        self._disk_stamp = None               # (mtime, size) of the open file as we last saw it
        self._checking_disk = False
        self.speller: Optional[spell.Speller] = None
        self.crypto: Optional[twig.KeyInfo] = None   # set when the file is password protected
        self._plain_ok_path: Optional[str] = None    # .hjt the user chose to save without formatting

        self.tree = NoteTree()
        self.tabs = QTabBar()
        self.tabs.setDocumentMode(True)
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.setExpanding(False)
        self.tabs.setElideMode(Qt.ElideRight)
        self.tabs.setVisible(False)
        self.tabs.currentChanged.connect(self._on_tab_changed)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.tabMoved.connect(self._on_tab_moved)
        self.tree_pane = QWidget()
        lay = QVBoxLayout(self.tree_pane)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)
        lay.addWidget(self.tabs)
        lay.addWidget(self.tree)

        self.editor = ArticleEdit()
        self.editor.needRich.connect(self.make_rich)
        self.link_highlighter = ArticleHighlighter(self.editor.document())
        self.editor.viewport().installEventFilter(self)  # Ctrl+click follows links
        self.editor.installEventFilter(self)             # Tab switches panes (option)
        self.editor.setContextMenuPolicy(Qt.CustomContextMenu)
        self.editor.customContextMenuRequested.connect(self._editor_menu)
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.addWidget(self.tree_pane)
        self.splitter.addWidget(self.editor)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 3)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setSizes([260, 740])
        self.setCentralWidget(self.splitter)

        self.autosave_timer = QTimer(self)
        self.autosave_timer.setInterval(AUTOSAVE_MINUTES * 60 * 1000)
        self.autosave_timer.timeout.connect(self.autosave)
        self.info_timer = QTimer(self)        # backlinks, tags and word count, after a pause
        self.info_timer.setSingleShot(True)
        self.info_timer.setInterval(250)
        self.info_timer.timeout.connect(self.refresh_info)
        self.watcher = QFileSystemWatcher(self)
        self.disk_timer = QTimer(self)
        self.disk_timer.setSingleShot(True)
        self.disk_timer.setInterval(400)
        self.disk_timer.timeout.connect(self.check_disk)
        self.watcher.fileChanged.connect(self._on_file_changed)

        self.backlinks_panel = BacklinksPanel(self)
        self.tags_panel = TagsPanel(self)
        for panel in (self.backlinks_panel, self.tags_panel):
            self.addDockWidget(Qt.RightDockWidgetArea, panel)
            panel.noteActivated.connect(self.go_to_note)
            panel.visibilityChanged.connect(self._on_panel_visibility)
            panel.hide()

        self._create_actions()
        self._create_menus()
        self._create_toolbar()
        self._create_statusbar()

        self.tree.currentItemChanged.connect(self._on_current_changed)
        self.tree.itemChanged.connect(self._on_item_renamed)
        self.tree.structureChanged.connect(self._on_structure_changed)
        self.editor.textChanged.connect(self._on_text_changed)
        self.editor.cursorPositionChanged.connect(self._update_cursor_label)
        self.editor.selectionChanged.connect(self._update_word_label)
        self.editor.undoAvailable.connect(lambda on: self.act_undo.setEnabled(on and not self.read_only))
        self.editor.redoAvailable.connect(lambda on: self.act_redo.setEnabled(on and not self.read_only))
        QApplication.clipboard().dataChanged.connect(self._on_clipboard_changed)

        self._restore_settings()
        self._load_speller()
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
        self.act_replace_article = self._action(
            "Text File into Article (Replace Its Text)...", self.replace_article_from_file,
            tip="Replace the text of the selected node with a text file")
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
        self.act_set_password = self._action("Set &Password...", self.set_password,
                                             tip="Encrypt the file with a password (saved as .twig)")
        self.act_remove_password = self._action("Remo&ve Password", self.remove_password,
                                                tip="Save the file without a password from now on")
        self.act_tray = self._action("&Minimize to Tray", self.minimize_to_tray, "Ctrl+M",
                                     tip="Hide the window; click the tray icon to bring it back")
        self.act_exit = self._action("E&xit", self.close, "Ctrl+Q")

        # Edit (article text)
        self.act_undo = self._action("&Undo", e.undo, QKeySequence.Undo,
                                     icons.themed("edit-undo", S.SP_ArrowBack), context_widget=e)
        self.act_redo = self._action("&Redo", e.redo, "Ctrl+Y",
                                     icons.themed("edit-redo", S.SP_ArrowForward), context_widget=e)
        self.act_cut = self._action("Cu&t", self.cut_article, QKeySequence.Cut, context_widget=e,
                                    tip="Cut the selected text, or the whole article when nothing is selected")
        self.act_copy = self._action("&Copy", self.copy_article, QKeySequence.Copy, context_widget=e,
                                     tip="Copy the selected text, or the whole article when nothing is selected")
        self.act_delete_text = self._action("De&lete", self.delete_article_text,
                                            tip="Delete the selected text, or the whole article (asks first)")
        self.act_goto_start = self._action("Go to &Start", lambda: self._goto(QTextCursor.Start))
        self.act_goto_end = self._action("Go to &End", lambda: self._goto(QTextCursor.End))
        self.act_paste = self._action("&Paste", e.paste, QKeySequence.Paste, context_widget=e)
        self.act_select_all = self._action("Select &All", e.selectAll, QKeySequence.SelectAll,
                                           context_widget=e)
        for a in (self.act_undo, self.act_redo):
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
        self.act_word_count = self._action("&Word Count...", self.show_word_count,
                                           tip="Count words in the selection, article, branch and file")

        # Format: formatted text (turns a plain note into a formatted one)
        def rich(text, slot, key=None, tip=None, checkable=False):
            return self._action(text, slot, key, tip=tip, context_widget=e if key else None,
                                checkable=checkable)
        self.act_bold = rich("&Bold", lambda: self.toggle_char("bold"), "Ctrl+B")
        self.act_italic = rich("&Italic", lambda: self.toggle_char("italic"), "Ctrl+I")
        self.act_underline = rich("U&nderline", lambda: self.toggle_char("underline"), "Ctrl+U")
        self.act_strike = rich("Stri&kethrough", lambda: self.toggle_char("strike"))
        self.act_text_color = rich("Text &Colour...", lambda: self.choose_color(False))
        self.act_highlight = rich("&Highlight Colour...", lambda: self.choose_color(True))
        self.act_char_font = rich("&Font...", self.choose_char_font)
        self.act_bigger = rich("Larger Text", lambda: self.change_size(2), "Ctrl+Shift+.")
        self.act_smaller = rich("Smaller Text", lambda: self.change_size(-2), "Ctrl+Shift+,")
        self.act_styles = {}
        for level, label in ((0, "Normal Text"), (1, "Heading 1"), (2, "Heading 2"), (3, "Heading 3")):
            self.act_styles[level] = rich(label, lambda lv=level: self.set_heading(lv),
                                          f"Ctrl+{level}")
        self.act_bullets = rich("&Bulleted List", lambda: self.toggle_list(QTextListFormat.ListDisc))
        self.act_numbers = rich("&Numbered List", lambda: self.toggle_list(QTextListFormat.ListDecimal))
        self.act_align = {}
        for name, flag, label in (("left", Qt.AlignLeft, "Align &Left"), ("center", Qt.AlignHCenter, "&Centre"),
                                  ("right", Qt.AlignRight, "Align &Right")):
            self.act_align[name] = rich(label, lambda f=flag: self.set_alignment(f))
        self.act_image = rich("&Picture...", self.insert_image_file,
                              tip="Insert a picture into the article")
        self.act_table = rich("&Table...", self.insert_table, tip="Insert a table")
        self.act_row = rich("Insert &Row Below", lambda: self.table_edit("row"))
        self.act_col = rich("Insert &Column Right", lambda: self.table_edit("col"))
        self.act_del_row = rich("&Delete Row", lambda: self.table_edit("del-row"))
        self.act_del_col = rich("D&elete Column", lambda: self.table_edit("del-col"))
        self.act_hr = rich("&Horizontal Line", self.insert_rule)
        self.act_clear_fmt = rich("Clear Formatting", self.clear_formatting,
                                  tip="Remove the formatting of the selected text")
        self.act_plain = rich("Convert Note to &Plain Text...", self.make_plain,
                              tip="Remove all formatting and pictures from this note")
        self.rich_actions = [self.act_bold, self.act_italic, self.act_underline, self.act_strike,
                             self.act_text_color, self.act_highlight, self.act_char_font, self.act_bigger,
                             self.act_smaller, *self.act_styles.values(), self.act_bullets,
                             self.act_numbers, *self.act_align.values(), self.act_image, self.act_table,
                             self.act_row, self.act_col, self.act_del_row, self.act_del_col, self.act_hr,
                             self.act_clear_fmt, self.act_plain]

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
        self.act_find = self._action("&Find...", self.find_here, ["Ctrl+F", "Shift+F12"],
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
        self.icon_group = QActionGroup(self)
        self.act_icons = {}
        for kind, (label, _color) in treestyle.NOTE_ICONS.items():
            act = QAction(treestyle.note_icon(kind), label, self, checkable=True)
            act.triggered.connect(lambda _c=False, k=kind: self.set_note_look(icon=k))
            self.icon_group.addAction(act)
            self.act_icons[kind] = act
        self.act_colors = {}
        self.color_group = QActionGroup(self)
        for label, value in [("Default", "")] + list(treestyle.NOTE_COLORS.items()):
            pm = QPixmap(14, 14)
            pm.fill(QColor(value) if value else Qt.transparent)
            act = QAction(QIcon(pm), label, self, checkable=True)
            act.triggered.connect(lambda _c=False, v=value: self.set_note_look(color=v))
            self.color_group.addAction(act)
            self.act_colors[value] = act
        self.act_color_custom = self._action("Other Colour...", self.choose_note_color)
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
        self.act_focus = self._action("&Focus on Branch", self.focus_branch, "Ctrl+]",
                                      tip="Show only the selected node and the nodes inside it")
        self.act_focus_out = self._action("Focus &Out One Level", self.focus_out, "Ctrl+[",
                                          tip="Show the branch one level up")
        self.act_unfocus = self._action("Show &Whole Tree", lambda: self.set_tab_root(None),
                                        tip="Show the whole tree again in this tab")
        self.act_new_tab = self._action("Open Branch in New &Tab", self.open_branch_tab, "Ctrl+T",
                                        tip="Open the selected branch in a tab of its own")
        self.act_close_tab = self._action("Close Ta&b", lambda: self.close_tab(self.tabs.currentIndex()),
                                          "Ctrl+W")
        self.act_next_tab = self._action("Next Tab", lambda: self._step_tab(1), "Ctrl+PgDown")
        self.act_prev_tab = self._action("Previous Tab", lambda: self._step_tab(-1), "Ctrl+PgUp")
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
        self.act_pane_colors = self._action("Colo&urs...", self.choose_pane_colors,
                                            tip="Background and text colours of the tree and the article")

        # Options
        self.startup_group = QActionGroup(self)
        self.act_startup = {}
        for mode, label in STARTUP_MODES.items():
            act = QAction(label, self, checkable=True)
            act.triggered.connect(lambda _c=False, m=mode: self.settings.setValue("options/startup", m))
            self.startup_group.addAction(act)
            self.act_startup[mode] = act
        self.act_open_last = self.act_startup["reopen"]
        self.close_group = QActionGroup(self)
        self.act_close_modes = {}
        for mode, label in CLOSE_MODES.items():
            act = QAction(label, self, checkable=True)
            act.triggered.connect(lambda _c=False, m=mode: self.settings.setValue("options/on_close", m))
            self.close_group.addAction(act)
            self.act_close_modes[mode] = act
        self.act_tab_switch = self._action("Use &Tab to Switch Between Tree and Article",
                                           self.set_tab_switch, checkable=True,
                                           tip="Tab switches panes; Ctrl+Tab then types a tab in the article")
        self.act_tray_minimize = self._action(
            "&Minimize to Tray Instead of the Taskbar",
            lambda on: self.settings.setValue("options/tray_on_minimize", on), checkable=True)
        self.act_portable = self._action(
            "Keep Settings &Next to the Program", self.set_portable, checkable=True,
            tip=f"Store settings in {portable.INI_NAME} beside the program, for use from a USB stick")
        self.act_backup = self._action(
            "Keep a &Backup Copy (.bak) When Saving",
            lambda on: self.settings.setValue("options/backup", on), checkable=True)
        self.act_autosave = self._action(f"&Auto-save Every {AUTOSAVE_MINUTES} Minutes",
                                         self.set_autosave, checkable=True)
        self.act_auto_paste = self._action(
            "Automatic &Paste", self.set_auto_paste, checkable=True,
            tip="Text copied in other programs is added to the current article")
        self.act_spell = self._action("Check &Spelling", self.set_spell_check, checkable=True,
                                      tip="Underline misspelled words in articles")
        self.spell_group = QActionGroup(self)
        self.act_spell_langs = {}
        for code in sorted(spell.available_languages()):
            act = QAction(code, self, checkable=True)
            act.triggered.connect(lambda _c=False, c=code: self.set_spell_language(c))
            self.spell_group.addAction(act)
            self.act_spell_langs[code] = act
        if not self.act_spell_langs:
            self.act_spell.setEnabled(False)
            self.act_spell.setStatusTip("Spell checking needs Hunspell and a dictionary "
                                        "(for example the hunspell-en-us package)")

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
        sub.addSeparator()
        sub.addAction(self.act_replace_article)
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
        m.addActions([self.act_set_password, self.act_remove_password])
        m.addSeparator()
        m.addActions([self.act_tray, self.act_exit])

        m = mb.addMenu("&Edit")
        m.addActions([self.act_undo, self.act_redo])
        m.addSeparator()
        m.addActions([self.act_cut, self.act_copy, self.act_paste, self.act_delete_text])
        m.addSeparator()
        m.addAction(self.act_select_all)
        m.addSeparator()
        m.addActions([self.act_date, self.act_time, self.act_datetime])
        m.addSeparator()
        m.addAction(self.act_word_count)
        m.addSeparator()
        m.addAction(self.act_follow_link)
        sub = m.addMenu("&Insert")
        sub.addActions([self.act_link_file, self.act_link_folder])
        sub.addSeparator()
        sub.addAction(self.act_insert_file)

        m = mb.addMenu("F&ormat")
        m.addActions([self.act_bold, self.act_italic, self.act_underline, self.act_strike])
        m.addSeparator()
        m.addActions([self.act_text_color, self.act_highlight, self.act_char_font,
                      self.act_bigger, self.act_smaller])
        sub = m.addMenu("Paragraph &Style")
        sub.addActions(list(self.act_styles.values()))
        sub = m.addMenu("&Alignment")
        sub.addActions(list(self.act_align.values()))
        m.addActions([self.act_bullets, self.act_numbers])
        m.addSeparator()
        sub = m.addMenu("&Insert")
        sub.addActions([self.act_image, self.act_table, self.act_hr])
        sub = m.addMenu("Ta&ble")
        sub.addActions([self.act_row, self.act_col, self.act_del_row, self.act_del_col])
        self.table_menu = sub
        m.addSeparator()
        m.addActions([self.act_clear_fmt, self.act_plain])
        m.addSeparator()
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
        m.addActions([self.act_focus, self.act_focus_out, self.act_unfocus])
        m.addSeparator()
        m.addActions([self.act_new_tab, self.act_close_tab, self.act_next_tab, self.act_prev_tab])
        m.addSeparator()
        m.addActions([self.act_expand_one, self.act_expand_branch, self.act_collapse_branch])
        m.addActions([self.act_expand_all, self.act_collapse_all])
        m.addSeparator()
        panels = m.addMenu("&Panels")
        for panel, key in ((self.backlinks_panel, "Ctrl+Shift+B"), (self.tags_panel, "Ctrl+Shift+G")):
            act = panel.toggleViewAction()
            act.setShortcut(QKeySequence(key))
            panels.addAction(act)
        m.addSeparator()
        m.addActions([self.act_article_font, self.act_tree_font, self.act_reset_fonts, self.act_pane_colors])
        m.addSeparator()
        self.view_menu = m
        m.addAction(self.act_switch_pane)

        m = mb.addMenu("&Options")
        sub = m.addMenu("At &Startup")
        sub.addActions(list(self.act_startup.values()))
        sub = m.addMenu("When &Closing With Unsaved Changes")
        sub.addActions(list(self.act_close_modes.values()))
        m.addSeparator()
        m.addActions([self.act_backup, self.act_autosave])
        m.addSeparator()
        m.addActions([self.act_tab_switch, self.act_tray_minimize, self.act_portable])
        m.addSeparator()
        m.addAction(self.act_auto_paste)
        m.addSeparator()
        m.addAction(self.act_spell)
        langs = m.addMenu("Spelling &Language")
        langs.addActions(list(self.act_spell_langs.values()))
        langs.setEnabled(bool(self.act_spell_langs))

        m = mb.addMenu("&Help")
        m.addAction(self.act_about)

        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._tree_menu)
        self.tree.installEventFilter(self)

    def _node_menu_actions(self) -> List[QAction]:
        sep = lambda: self._separator()  # noqa: E731
        if not hasattr(self, "_look_menu"):
            self._look_menu = QMenu("Icon and &Colour", self)
            self._look_menu.addActions(list(self.act_icons.values()))
            self._look_menu.addSeparator()
            self._look_menu.addActions(list(self.act_colors.values()))
            self._look_menu.addAction(self.act_color_custom)
            self._look_menu.aboutToShow.connect(self._sync_look_menu)
        return [self.act_add_child, self.act_add_after, self.act_add_before, sep(),
                self.act_rename, self.act_delete, sep(),
                self.act_cut_node, self.act_copy_node, self.act_paste_child, self.act_paste_node, sep(),
                self.act_copy_name, self.act_paste_name, self.act_copy_link,
                self._look_menu.menuAction(), sep(),
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
        """Five toolbars; show or hide them in View > Toolbars and drag them
        by their handle to move them."""
        S = QStyle
        self.act_cut.setIcon(icons.themed_drawn("edit-cut", icons.cut))
        self.act_copy.setIcon(icons.themed_drawn("edit-copy", icons.copy))
        self.act_paste.setIcon(icons.themed_drawn("edit-paste", icons.paste))
        self.act_follow_link.setIcon(icons.themed("go-jump", S.SP_CommandLink))
        self.act_bold.setIcon(icons.themed_drawn("format-text-bold", icons.bold))
        self.act_italic.setIcon(icons.themed_drawn("format-text-italic", icons.italic))
        self.act_prev_sibling.setIcon(icons.themed("go-top", S.SP_ArrowUp))
        self.act_next_sibling.setIcon(icons.themed("go-bottom", S.SP_ArrowDown))
        self.act_focus.setIcon(icons.themed("zoom-in", S.SP_FileDialogContentsView))
        self.act_unfocus.setIcon(icons.themed("zoom-original", S.SP_FileDialogListView))
        self.act_word_wrap.setIcon(icons.themed("format-justify-fill", S.SP_FileDialogDetailedView))
        bars = [
            ("file-toolbar", "File", [self.act_new, self.act_open, self.act_save, None, self.act_print]),
            ("tree-toolbar", "Tree Edit", [self.act_add_after, self.act_add_child, self.act_delete, None,
                                           self.act_move_up, self.act_move_down, self.act_move_left,
                                           self.act_move_right]),
            ("article-toolbar", "Article Edit", [self.act_undo, self.act_redo, None, self.act_cut,
                                                 self.act_copy, self.act_paste, None, self.act_bold,
                                                 self.act_italic]),
            ("view-toolbar", "View", [self.act_focus, self.act_unfocus, self.act_word_wrap]),
            ("navigate-toolbar", "Navigate", [self.act_find, self.act_prev_sibling, self.act_next_sibling,
                                              self.act_follow_link]),
        ]
        self.toolbars = {}
        sub = self.view_menu.addMenu("Tool&bars")
        for name, title, acts in bars:
            tb = self.addToolBar(title)
            tb.setObjectName(name)
            tb.setMovable(True)
            for a in acts:
                if a is None:
                    tb.addSeparator()
                else:
                    tb.addAction(a)
            self.toolbars[name] = tb
            sub.addAction(tb.toggleViewAction())
        for name in ("view-toolbar", "article-toolbar"):
            self.toolbars[name].hide()   # off until turned on in View > Toolbars

    def _create_statusbar(self) -> None:
        sb = self.statusBar()
        self.nodes_label = QLabel()
        self.cursor_label = QLabel()
        self.read_only_label = QLabel(" Read only ")
        self.read_only_label.setVisible(False)
        self.words_label = QLabel()
        self.crypto_label = QLabel(" Password protected ")
        self.crypto_label.setVisible(False)
        sb.addPermanentWidget(self.crypto_label)
        sb.addPermanentWidget(self.read_only_label)
        sb.addPermanentWidget(self.words_label)
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
        startup = s.value("options/startup", "", type=str)
        if startup not in STARTUP_MODES:   # older setting: a plain on/off
            startup = "reopen" if s.value("options/open_last", True, type=bool) else "new"
        self.act_startup[startup].setChecked(True)
        on_close = s.value("options/on_close", "ask", type=str)
        self.act_close_modes[on_close if on_close in CLOSE_MODES else "ask"].setChecked(True)
        self.act_tab_switch.setChecked(s.value("options/tab_switch", False, type=bool))
        self.set_tab_switch(self.act_tab_switch.isChecked())
        self.act_tray_minimize.setChecked(s.value("options/tray_on_minimize", False, type=bool))
        self.act_portable.blockSignals(True)
        self.act_portable.setChecked(self._using_portable())
        self.act_portable.blockSignals(False)
        self.apply_pane_colors()
        self.act_backup.setChecked(s.value("options/backup", True, type=bool))
        self.act_autosave.setChecked(s.value("options/autosave", False, type=bool))
        self.set_autosave(self.act_autosave.isChecked())
        langs = spell.available_languages()
        lang = s.value("spell/language", "", type=str)
        if lang not in langs:
            lang = spell.best_language(QLocale().name(), langs) or ""
        if lang:
            self.act_spell_langs[lang].setChecked(True)
        self._spell_language = lang
        self.act_spell.setChecked(bool(lang) and s.value("spell/on", True, type=bool))

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

    def startup_mode(self) -> str:
        return next((m for m, a in self.act_startup.items() if a.isChecked()), "reopen")

    def open_startup_file(self) -> None:
        """What happens when the program starts without a file to open."""
        mode = self.startup_mode()
        last = next((p for p in self.recent_files()[:1]
                     if p.lower().endswith(OWN_EXTS) and os.path.exists(p)), None)
        if mode == "reopen" and last:
            self.load_path(last)
        elif mode == "ask" and last and self._ask_reopen(os.path.basename(last)):
            self.load_path(last)
        elif mode == "quickstart":
            choice = self._quick_start()
            if choice == "open":
                self.open_file()
            elif choice and choice != "new":
                self.load_path(choice)

    def _ask_reopen(self, name: str) -> bool:
        return QMessageBox.question(self, APP_NAME, f"Open the last file, \"{name}\"?",
                                    QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes) == QMessageBox.Yes

    def _quick_start(self) -> Optional[str]:
        """The Quick Start window: 'new', 'open', a file path, or None."""
        from PyQt5.QtWidgets import QCheckBox, QListWidget
        dlg = QDialog(self)
        dlg.setWindowTitle(f"{APP_NAME} - Quick Start")
        lay = QVBoxLayout(dlg)
        lay.addWidget(QLabel("Open a recent file (double-click), or start something new:"))
        recent = QListWidget()
        for path in self.recent_files():
            if os.path.exists(path):
                recent.addItem(path)
        lay.addWidget(recent)
        result = {"choice": None}

        def done(choice):
            result["choice"] = choice
            dlg.accept()
        recent.itemActivated.connect(lambda it: done(it.text()))
        row = QDialogButtonBox()
        for label, choice in (("&New File", "new"), ("&Open...", "open")):
            row.addButton(label, QDialogButtonBox.ActionRole).clicked.connect(
                lambda _c=False, c=choice: done(c))
        open_btn = row.addButton("Open &Selected", QDialogButtonBox.AcceptRole)
        open_btn.clicked.connect(lambda: recent.currentItem() and done(recent.currentItem().text()))
        row.addButton(QDialogButtonBox.Close).clicked.connect(dlg.reject)
        lay.addWidget(row)
        again = QCheckBox("Show this window at startup")
        again.setChecked(True)
        lay.addWidget(again)
        if recent.count():
            recent.setCurrentRow(0)
        dlg.resize(520, 320)
        dlg.exec_()
        if not again.isChecked():
            self.act_startup["reopen"].setChecked(True)
            self.settings.setValue("options/startup", "reopen")
        return result["choice"]

    # ===================================================== editor <-> tree

    def _commit_editor(self) -> None:
        """Copy the editor's text back into the node it belongs to."""
        item = self._editing_item
        if item is None:
            return
        item.cursor_pos = self.editor.textCursor().position()
        if self._editor_dirty:
            item.body = self.editor.toPlainText()
            item.html = self.editor.toHtml() if self.editor.rich else ""
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
                self.editor.set_rich(bool(item.html))
                if item.html:
                    self.editor.setHtml(item.html)
                else:
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
        if current is not None and not self.tree.in_view(current):
            # Search, links and backlinks can lead outside the focused branch.
            self.set_tab_root(None)
        if 0 <= self.tabs.currentIndex() < len(self._views):
            self._views[self.tabs.currentIndex()]["current"] = current
        self._show_item(current)
        self.info_timer.start()

    def _on_text_changed(self) -> None:
        if not self._loading:
            self._editor_dirty = True
            self.setWindowModified(True)
        self.info_timer.start()

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
        self._update_tab_titles()
        self.info_timer.start()

    def _on_structure_changed(self) -> None:
        self.setWindowModified(True)
        self._update_tab_titles()
        self._update_node_actions()
        self.info_timer.start()

    def _update_node_actions(self) -> None:
        cur = self.tree.currentItem()
        has = cur is not None
        idx = self.tree.index_in_parent(cur) if has else 0
        siblings = (cur.parent() or self.tree.invisibleRootItem()).childCount() if has else 0
        top = self.tree.is_view_top(cur)
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
        self.act_move_left.setEnabled(has and rw and not top and not self.tree.is_view_top(cur.parent()))
        self.act_move_right.setEnabled(has and rw and idx > 0)
        self.act_siblings_right.setEnabled(has and rw and not top and idx < siblings - 1)
        self.act_children_left.setEnabled(has and rw and not top and cur.childCount() > 0)
        self.act_prev_sibling.setEnabled(has and idx > 0)
        self.act_next_sibling.setEnabled(has and idx < siblings - 1)
        self.act_sort.setEnabled(has and rw and cur.childCount() > 1)
        self.act_sort_all.setEnabled(rw)
        self._look_menu.setEnabled(has and rw)
        self.act_remove_password.setEnabled(rw and self.crypto is not None)
        self.act_set_password.setEnabled(rw and twig.encryption_available())
        self.act_focus.setEnabled(has and not NoteTree.is_top(cur) and cur is not self.tree.hoisted)
        self.act_focus_out.setEnabled(self.tree.hoisted is not None)
        self.act_unfocus.setEnabled(self.tree.hoisted is not None)
        self.act_new_tab.setEnabled(has)
        self.act_close_tab.setEnabled(self.tabs.count() > 1)
        n = len(self.tree.all_items())
        self.nodes_label.setText(f" {n} node{'s' if n != 1 else ''} ")

    def _update_cursor_label(self) -> None:
        c = self.editor.textCursor()
        self.cursor_label.setText(f" Ln {c.blockNumber() + 1}, Col {c.positionInBlock() + 1} ")

    # =========================================================== node ops

    def _start_rename(self, item: NoteItem) -> None:
        self.tree.scrollToItem(item)
        self.tree.editItem(item, 0)

    def _top_word(self) -> str:
        return "focused" if self.tree.hoisted is not None else "top"

    def add_node_after(self) -> None:
        self._add_sibling(after=True)

    def add_node_before(self) -> None:
        self._add_sibling(after=False)

    def _add_sibling(self, after: bool) -> None:
        item = self.tree.add_sibling(after=after)
        if item is None:
            self.statusBar().showMessage(
                f"The {self._top_word()} node can't have nodes next to it. Use Ins to add a child node.", 5000)
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
        if self.tree.is_view_top(item):
            self.statusBar().showMessage(f"The {self._top_word()} node can't be deleted.", 4000)
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
        doc.images = self.editor.images
        mime = QMimeData()
        mime.setData(NODE_MIME, twig.to_json(doc))
        mime.setText(export.outline_text([node], numbered=False))
        QApplication.clipboard().setMimeData(mime)
        n = node.count()
        self.statusBar().showMessage(f"Copied {n} node{'s' if n != 1 else ''}.", 4000)
        return True

    def cut_node(self) -> None:
        item = self.tree.currentItem()
        if self.tree.is_view_top(item):
            self.statusBar().showMessage(f"The {self._top_word()} node can't be cut; use Copy instead.", 4000)
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
                doc = twig.from_json(bytes(mime.data(NODE_MIME)))
            except twig.TwigFormatError:
                return []
            for name, data in doc.images.items():
                self.editor.images.setdefault(name, data)
            return doc.top_nodes
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
        elif as_child or self.tree.is_view_top(cur):
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
        if self.tree.is_view_top(self.tree.currentItem()):
            self.statusBar().showMessage(f"The nodes inside the {self._top_word()} node can't move out of it.", 4000)
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
        self.tree.setEditTriggers(QAbstractItemView.NoEditTriggers if on else NoteTree.EDIT_TRIGGERS)
        for act in (self.act_save, self.act_paste, self.act_date, self.act_time, self.act_datetime,
                    self.act_link_file, self.act_link_folder, self.act_insert_file, self.act_replace,
                    self.act_upper, self.act_lower, self.act_strip, self.act_strip_returns,
                    self.act_import_tree, self.act_import_text, self.act_import_csv,
                    self.act_set_password, self.act_remove_password, self.act_color_custom,
                    *self.rich_actions, *self.act_icons.values(), *self.act_colors.values()):
            act.setEnabled(not on)
        doc = self.editor.document()
        self.act_undo.setEnabled(not on and doc.isUndoAvailable())
        self.act_redo.setEnabled(not on and doc.isRedoAvailable())
        self.act_cut.setEnabled(not on)
        self.act_delete_text.setEnabled(not on)
        self.act_replace_article.setEnabled(not on)
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

    # ====================================================== focus and tabs
    # Each tab is a view of the same tree, optionally focused on one branch.

    def _on_tab_moved(self, old: int, new: int) -> None:
        self._views.insert(new, self._views.pop(old))

    def _on_panel_visibility(self, visible: bool) -> None:
        if visible:
            self.info_timer.start()

    def _on_file_changed(self, _path: str) -> None:
        # Let the other program finish writing before looking.
        self.disk_timer.start()

    def _reset_tabs(self) -> None:
        self.tabs.blockSignals(True)
        while self.tabs.count():
            self.tabs.removeTab(0)
        self._views = [{"root": None, "current": self.tree.currentItem()}]
        self.tabs.addTab("")
        self.tabs.setCurrentIndex(0)
        self.tabs.blockSignals(False)
        self.tree.hoist(None)
        self._update_tab_titles()

    def _tab_title(self, view: dict) -> str:
        root = view["root"]
        if root is not None:
            return root.title
        top = self.tree.topLevelItem(0)
        return top.title if top is not None else "Notes"

    def _update_tab_titles(self) -> None:
        for i, view in enumerate(self._views):
            if view["root"] is not None and not self.tree.contains(view["root"]):
                view["root"] = None
            self.tabs.setTabText(i, self._tab_title(view))
            self.tabs.setTabToolTip(i, " / ".join(self.tree.title_path(view["root"]))
                                    if view["root"] is not None else "Whole tree")
        self.tabs.setVisible(self.tabs.count() > 1)
        if self.tree.hoisted is None and self._views and \
                self._views[self.tabs.currentIndex()]["root"] is None:
            return
        cur = self._views[self.tabs.currentIndex()]["root"] if self._views else None
        if cur is not self.tree.hoisted:
            self.tree.hoist(cur)

    def _on_tab_changed(self, index: int) -> None:
        if not (0 <= index < len(self._views)):
            return
        view = self._views[index]
        current = view["current"]   # read first: focusing may move the selection
        if view["root"] is not None and not self.tree.contains(view["root"]):
            view["root"] = None
        self.tree.hoist(view["root"])
        if current is not None and self.tree.contains(current) and self.tree.in_view(current):
            self.tree.setCurrentItem(current)
        elif view["root"] is not None:
            self.tree.setCurrentItem(view["root"])
        self.tree.scrollToItem(self.tree.currentItem())
        self._update_node_actions()

    def set_tab_root(self, item: Optional[NoteItem]) -> None:
        """Focus the current tab on ``item``'s branch (None = whole tree)."""
        if item is not None and item.parent() is None:
            item = None
        index = self.tabs.currentIndex()
        if 0 <= index < len(self._views):
            self._views[index]["root"] = item
        self.tree.hoist(item)
        self._update_tab_titles()
        self._update_node_actions()

    def focus_branch(self) -> None:
        item = self.tree.currentItem()
        if item is not None:
            self.set_tab_root(item)
            self.tree.setFocus()

    def focus_out(self) -> None:
        root = self.tree.hoisted
        if root is not None:
            self.set_tab_root(root.parent())
            self.tree.setCurrentItem(root)
            self.tree.scrollToItem(root)

    def open_branch_tab(self, item: Optional[NoteItem] = None) -> None:
        item = item or self.tree.currentItem()
        if item is None:
            return
        root = None if item.parent() is None else item
        self._views.append({"root": root, "current": item})
        index = self.tabs.addTab(self._tab_title(self._views[-1]))
        self._update_tab_titles()
        self.tabs.setCurrentIndex(index)

    def close_tab(self, index: int) -> None:
        if self.tabs.count() <= 1 or not (0 <= index < len(self._views)):
            return
        self._views.pop(index)
        self.tabs.removeTab(index)   # emits currentChanged for the new tab
        self._update_tab_titles()
        self._update_node_actions()

    def _step_tab(self, step: int) -> None:
        if self.tabs.count() > 1:
            self.tabs.setCurrentIndex((self.tabs.currentIndex() + step) % self.tabs.count())

    def go_to_note(self, item) -> None:
        if self.tree.contains(item):
            self.tree.setCurrentItem(item)
            self.tree.scrollToItem(item)

    # ============================================ backlinks, tags, word count

    def _body(self, item) -> str:
        """An article's text, including unsaved typing in the editor."""
        if item is self._editing_item and self._editor_dirty:
            return self.editor.toPlainText()
        return item.body

    def _describe(self, item):
        return item.title, " / ".join(self.tree.title_path(item))

    def backlinks(self, target) -> List[NoteItem]:
        """Notes whose article has a [node://...] link that leads to ``target``."""
        roots = [self.tree.topLevelItem(i) for i in range(self.tree.topLevelItemCount())]
        title_of = lambda it: it.text(0)  # noqa: E731
        children_of = lambda it: [it.child(i) for i in range(it.childCount())]  # noqa: E731
        out = []
        for item in self.tree.all_items():
            body = self._body(item)
            if "node:" not in body.lower():
                continue
            for _s, _e, link in links.iter_links(body):
                kind, path = links.classify(link)
                if kind == links.NODE and links.resolve_node(roots, path, title_of, children_of) is target:
                    if item is not target:
                        out.append(item)
                    break
        return out

    def refresh_info(self) -> None:
        self._update_word_label()
        if self.backlinks_panel.isVisibleTo(self):
            cur = self.tree.currentItem()
            notes = self.backlinks(cur) if cur is not None else []
            self.backlinks_panel.show_links(cur.title if cur is not None else "",
                                            [(n, *self._describe(n)) for n in notes])
        if self.tags_panel.isVisibleTo(self):
            groups = tags.collect((it, it.title + "\n" + self._body(it)) for it in self.tree.all_items())
            self.tags_panel.set_tags(groups, self._describe)

    @staticmethod
    def count_words(text: str) -> int:
        return len(text.split())

    def _update_word_label(self) -> None:
        if not self.editor.isEnabled():
            self.words_label.setText("")
            return
        total = self.count_words(self.editor.toPlainText())
        cursor = self.editor.textCursor()
        if cursor.hasSelection():
            n = self.count_words(cursor.selectedText().replace(" ", "\n"))
            self.words_label.setText(f" {n} of {total} words ")
        else:
            self.words_label.setText(f" {total} word{'s' if total != 1 else ''} ")

    def word_counts(self) -> List[tuple]:
        """Rows of (what, words, characters, nodes) for the Word Count window."""
        rows = []
        cursor = self.editor.textCursor()
        if cursor.hasSelection():
            sel = cursor.selectedText().replace(" ", "\n")
            rows.append(("Selection", self.count_words(sel), len(sel), None))
        cur = self.tree.currentItem()
        if cur is not None:
            body = self._body(cur)
            rows.append(("This note", self.count_words(body), len(body), 1))
            items = NoteTree.all_items_under(cur)
            texts = [it.title + "\n" + self._body(it) for it in items]
            rows.append(("This note and its subnotes", sum(self.count_words(t) for t in texts),
                         sum(len(self._body(it)) for it in items), len(items)))
        items = self.tree.all_items()
        rows.append(("Whole file", sum(self.count_words(it.title + "\n" + self._body(it)) for it in items),
                     sum(len(self._body(it)) for it in items), len(items)))
        return rows

    def show_word_count(self) -> None:
        loc = QLocale()
        cells = "".join(
            f"<tr><td>{what}</td><td align='right'>{loc.toString(w)}</td>"
            f"<td align='right'>{loc.toString(c)}</td>"
            f"<td align='right'>{'' if n is None else loc.toString(n)}</td></tr>"
            for what, w, c, n in self.word_counts())
        QMessageBox.information(
            self, "Word Count",
            "<table cellspacing='0' cellpadding='4'>"
            "<tr><th></th><th align='right'>Words</th><th align='right'>Characters</th>"
            f"<th align='right'>Notes</th></tr>{cells}</table>"
            "<p><small>Totals for several notes include the note titles.</small></p>")

    # ===================================================== changed on disk

    @staticmethod
    def _stamp(path: Optional[str]):
        try:
            st = os.stat(path)
        except (OSError, TypeError):
            return None
        return st.st_mtime_ns, st.st_size

    def _watch(self, path: Optional[str]) -> None:
        if self.watcher.files():
            self.watcher.removePaths(self.watcher.files())
        self._disk_stamp = self._stamp(path) if path else None
        if path and os.path.exists(path):
            self.watcher.addPath(path)

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        if event.type() == QEvent.ActivationChange and self.isActiveWindow():
            self.disk_timer.start()
        elif (event.type() == QEvent.WindowStateChange and self.isMinimized()
              and self.act_tray_minimize.isChecked() and QSystemTrayIcon.isSystemTrayAvailable()):
            QTimer.singleShot(0, self.minimize_to_tray)

    def check_disk(self) -> None:
        """Ask what to do when another program changed or removed the open file."""
        path = self.path
        if not path or self._checking_disk or self._disk_stamp is None:
            return
        now = self._stamp(path)
        if now == self._disk_stamp:
            if path not in self.watcher.files():   # replaced by a rename: watch the new file
                self.watcher.addPath(path)
            return
        self._checking_disk = True
        try:
            name = os.path.basename(path)
            if now is None:
                self._disk_stamp = None
                self.setWindowModified(True)
                self.statusBar().showMessage(
                    f"\"{name}\" was deleted or moved by another program. Save writes it again.", 15000)
                return
            if self._ask_reload(name, self.isWindowModified()):
                self.load_path(path)
            else:
                self._disk_stamp = now   # keep this version; Save overwrites the other one
                self.setWindowModified(True)
                if path not in self.watcher.files():
                    self.watcher.addPath(path)
        finally:
            self._checking_disk = False

    def _ask_reload(self, name: str, modified: bool) -> bool:
        extra = "\n\nYour unsaved changes here will be lost." if modified else ""
        answer = QMessageBox.question(
            self, APP_NAME,
            f"\"{name}\" was changed by another program.\n\nReload it?{extra}",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No if modified else QMessageBox.Yes)
        return answer == QMessageBox.Yes

    def _confirm_overwrite(self, name: str) -> bool:
        answer = QMessageBox.warning(
            self, APP_NAME,
            f"\"{name}\" was changed by another program after you opened it.\n\n"
            "Save anyway and replace those changes?",
            QMessageBox.Save | QMessageBox.Cancel, QMessageBox.Cancel)
        return answer == QMessageBox.Save

    # ======================================================= spell checking

    def set_spell_check(self, on: bool) -> None:
        self.settings.setValue("spell/on", on)
        self._load_speller()

    def set_spell_language(self, code: str) -> None:
        self._spell_language = code
        self.settings.setValue("spell/language", code)
        self._load_speller()

    def _load_speller(self) -> None:
        self.speller = None
        lang = getattr(self, "_spell_language", "")
        if self.act_spell.isChecked() and lang:
            path = spell.available_languages().get(lang)
            try:
                self.speller = spell.get_speller(path) if path else None
            except OSError as exc:
                self.statusBar().showMessage(str(exc), 8000)
            if self.speller is not None:
                words = self.settings.value("spell/words", [])
                for word in ([words] if isinstance(words, str) else (words or [])):
                    self.speller.add(word)
        self.link_highlighter.set_speller(self.speller)

    def add_to_dictionary(self, word: str) -> None:
        words = self.settings.value("spell/words", [])
        words = [words] if isinstance(words, str) else list(words or [])
        if word not in words:
            words.append(word)
            self.settings.setValue("spell/words", sorted(words, key=str.casefold))
        if self.speller is not None:
            self.speller.add(word)
            self.link_highlighter.rehighlight()

    def _word_at(self, cursor):
        """(word, start, end) under ``cursor`` in Qt positions, or None."""
        block = cursor.block()
        text = block.text()
        pos = search.from_qt(text, cursor.positionInBlock())
        for m in spell.WORD_RE.finditer(text):
            if m.start() <= pos <= m.end():
                base = block.position()
                return m.group(), base + search.to_qt(text, m.start()), base + search.to_qt(text, m.end())
        return None

    def _editor_menu(self, pos) -> None:
        menu = self.editor.createStandardContextMenu(pos)
        first = menu.actions()[0] if menu.actions() else None
        cursor = self.editor.cursorForPosition(pos)
        extra = []
        link = self.link_at_cursor(cursor)
        if link:
            act = QAction("Open Link", menu)
            act.triggered.connect(lambda _c=False, ln=link: self.follow_link(ln))
            extra.append(act)
        found = self._word_at(cursor) if self.speller is not None and not self.read_only else None
        if found and not self.speller.check(found[0]) and not found[0].isupper():
            word, start, end = found
            suggestions = self.speller.suggest(word)
            for s in suggestions:
                act = QAction(s, menu)
                font = act.font()
                font.setBold(True)
                act.setFont(font)
                act.triggered.connect(lambda _c=False, s=s, a=start, b=end: self._replace_word(a, b, s))
                extra.append(act)
            if not suggestions:
                none = QAction("(no suggestions)", menu)
                none.setEnabled(False)
                extra.append(none)
            add = QAction(f"Add “{word}” to Dictionary", menu)
            add.triggered.connect(lambda _c=False, w=word: self.add_to_dictionary(w))
            extra.append(add)
        if extra:
            menu.insertActions(first, extra)
            menu.insertSeparator(first)
        menu.addSeparator()
        menu.addActions([self.act_find, self.act_find_next])
        nav = menu.addMenu("&Navigate")
        nav.addActions([self.act_goto_start, self.act_goto_end, self.act_follow_link])
        menu.exec_(self.editor.viewport().mapToGlobal(pos))
        menu.deleteLater()

    def _replace_word(self, start: int, end: int, text: str) -> None:
        cursor = self.editor.textCursor()
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.KeepAnchor)
        cursor.insertText(text)
        self.editor.setTextCursor(cursor)

    # ======================================================= formatted text
    # A note becomes "formatted" the first time a formatting command is used
    # (or a picture is pasted). Formatted notes are kept in .twig files.

    def make_rich(self) -> None:
        if self.editor.rich or not self.editor.isEnabled():
            return
        self.editor.set_rich(True)
        self._editor_dirty = True
        self.setWindowModified(True)
        if self.path and self.path.lower().endswith(".hjt") and self._plain_ok_path != self.path:
            self.statusBar().showMessage(
                "This note now has formatting, which is kept in .twig files. Save will ask.", 8000)

    def _rich_ready(self) -> bool:
        if not self.editor.isEnabled() or not self._writable():
            return False
        self.make_rich()
        return True

    def _merge(self, fmt: QTextCharFormat) -> None:
        self.editor.mergeCurrentCharFormat(fmt)
        self.editor.setFocus()

    def toggle_char(self, what: str) -> None:
        if not self._rich_ready():
            return
        cur = self.editor.currentCharFormat()
        fmt = QTextCharFormat()
        if what == "bold":
            fmt.setFontWeight(QFont.Normal if cur.fontWeight() > QFont.Normal else QFont.Bold)
        elif what == "italic":
            fmt.setFontItalic(not cur.fontItalic())
        elif what == "underline":
            fmt.setFontUnderline(not cur.fontUnderline())
        elif what == "strike":
            fmt.setFontStrikeOut(not cur.fontStrikeOut())
        self._merge(fmt)

    def _pick_color(self, initial: QColor, title: str = "Colour") -> QColor:
        return QColorDialog.getColor(initial, self, title)

    def choose_color(self, background: bool) -> None:
        if not self._rich_ready():
            return
        cur = self.editor.currentCharFormat()
        initial = cur.background().color() if background else cur.foreground().color()
        color = self._pick_color(initial, "Highlight Colour" if background else "Text Colour")
        if color.isValid():
            fmt = QTextCharFormat()
            if background:
                fmt.setBackground(color)
            else:
                fmt.setForeground(color)
            self._merge(fmt)

    def choose_char_font(self) -> None:
        if not self._rich_ready():
            return
        font, ok = QFontDialog.getFont(self.editor.currentFont(), self, "Font")
        if ok:
            fmt = QTextCharFormat()
            fmt.setFont(font)
            self._merge(fmt)

    def _base_size(self) -> float:
        size = self.editor.font().pointSizeF()
        return size if size > 0 else 10.0

    def change_size(self, delta: float) -> None:
        if not self._rich_ready():
            return
        size = self.editor.currentCharFormat().fontPointSize() or self._base_size()
        fmt = QTextCharFormat()
        fmt.setFontPointSize(max(6.0, size + delta))
        self._merge(fmt)

    def set_heading(self, level: int) -> None:
        """0 = normal text, 1-3 = headings, for the paragraphs of the selection."""
        if not self._rich_ready():
            return
        cursor = self.editor.textCursor()
        start, end = cursor.selectionStart(), cursor.selectionEnd()
        cursor.beginEditBlock()
        block_fmt = QTextBlockFormat()
        block_fmt.setHeadingLevel(level)
        cursor.mergeBlockFormat(block_fmt)
        cursor.setPosition(self.editor.document().findBlock(start).position())
        last = self.editor.document().findBlock(end)
        cursor.setPosition(last.position() + last.length() - 1, QTextCursor.KeepAnchor)
        fmt = heading_format(level, self._base_size())
        cursor.mergeCharFormat(fmt)
        cursor.endEditBlock()
        if not self.editor.textCursor().hasSelection():
            self.editor.mergeCurrentCharFormat(fmt)   # also for what is typed next
        self.editor.setFocus()

    def toggle_list(self, style) -> None:
        if not self._rich_ready():
            return
        cursor = self.editor.textCursor()
        current = cursor.currentList()
        cursor.beginEditBlock()
        if current is not None and current.format().style() == style:
            doc = self.editor.document()
            block = doc.findBlock(cursor.selectionStart())
            last = doc.findBlock(cursor.selectionEnd())
            while block.isValid():
                if block.textList() is not None:
                    block.textList().remove(block)
                    fmt = block.blockFormat()
                    fmt.setIndent(0)
                    QTextCursor(block).setBlockFormat(fmt)
                if block == last:
                    break
                block = block.next()
        elif current is not None:
            fmt = current.format()
            fmt.setStyle(style)
            current.setFormat(fmt)
        else:
            cursor.createList(style)
        cursor.endEditBlock()
        self.editor.setFocus()

    def set_alignment(self, flag) -> None:
        if self._rich_ready():
            self.editor.setAlignment(flag)

    def insert_image_file(self, path: Optional[str] = None) -> bool:
        if not self.editor.isEnabled() or not self._writable():
            return False
        if path is None:
            path, _ = QFileDialog.getOpenFileName(self, "Insert Picture", self._last_dir(), IMAGE_FILTERS)
            if not path:
                return False
        try:
            with open(path, "rb") as fh:
                data = fh.read()
        except OSError as exc:
            QMessageBox.warning(self, APP_NAME, f"Could not read \"{path}\".\n\n{exc}")
            return False
        self.make_rich()
        if not self.editor.insert_image(data):
            QMessageBox.warning(self, APP_NAME, f"\"{os.path.basename(path)}\" is not a picture Twigpad can show.")
            return False
        self.editor.setFocus()
        return True

    def _ask_table_size(self):
        from PyQt5.QtWidgets import QSpinBox
        dlg = QDialog(self)
        dlg.setWindowTitle("Insert Table")
        rows, cols = QSpinBox(), QSpinBox()
        for box, value in ((rows, 3), (cols, 3)):
            box.setRange(1, 50)
            box.setValue(value)
        form = QFormLayout(dlg)
        form.addRow("&Rows:", rows)
        form.addRow("&Columns:", cols)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        form.addRow(buttons)
        return (rows.value(), cols.value()) if dlg.exec_() == QDialog.Accepted else None

    def insert_table(self, rows: Optional[int] = None, cols: Optional[int] = None) -> bool:
        if not self._rich_ready():
            return False
        if rows is None or cols is None:
            size = self._ask_table_size()
            if size is None:
                return False
            rows, cols = size
        fmt = QTextTableFormat()
        fmt.setBorder(1)
        fmt.setBorderBrush(QColor("#9a9a9a"))
        fmt.setCellPadding(4)
        fmt.setCellSpacing(0)
        if hasattr(fmt, "setBorderCollapse"):
            fmt.setBorderCollapse(True)
        fmt.setWidth(QTextLength(QTextLength.PercentageLength, 100))
        cursor = self.editor.textCursor()
        cursor.insertTable(rows, cols, fmt)   # leaves the cursor in the first cell
        self.editor.setTextCursor(cursor)
        self.editor.setFocus()
        return True

    def table_edit(self, op: str) -> bool:
        if not self._rich_ready():
            return False
        cursor = self.editor.textCursor()
        table = cursor.currentTable()
        if table is None:
            self.statusBar().showMessage("Put the cursor in a table first.", 4000)
            return False
        cell = table.cellAt(cursor)
        row, col = cell.row(), cell.column()
        if op == "row":
            table.insertRows(row + 1, 1)
        elif op == "col":
            table.insertColumns(col + 1, 1)
        elif op == "del-row":
            if table.rows() == 1:
                table.removeColumns(0, table.columns())   # last row: remove the table
            else:
                table.removeRows(row, 1)
        elif op == "del-col":
            if table.columns() == 1:
                table.removeRows(0, table.rows())
            else:
                table.removeColumns(col, 1)
        return True

    def insert_rule(self) -> None:
        if self._rich_ready():
            cursor = self.editor.textCursor()
            cursor.insertHtml("<hr>")
            cursor.insertBlock()

    def _fragments(self, start: int, end: int):
        """(start, end, char format) of each run of equally formatted text."""
        out = []
        block = self.editor.document().findBlock(start)
        while block.isValid() and block.position() <= end:
            it = block.begin()
            while not it.atEnd():
                frag = it.fragment()
                if frag.isValid():
                    s = max(frag.position(), start)
                    e = min(frag.position() + frag.length(), end)
                    if s < e:
                        out.append((s, e, frag.charFormat()))
                it += 1
            block = block.next()
        return out

    def clear_formatting(self) -> None:
        if not self.editor.isEnabled() or not self._writable() or not self.editor.rich:
            return
        cursor = self.editor.textCursor()
        if not cursor.hasSelection():
            self.statusBar().showMessage("Select the text to clear first.", 4000)
            return
        edit = QTextCursor(self.editor.document())
        edit.beginEditBlock()
        for s, e, fmt in self._fragments(cursor.selectionStart(), cursor.selectionEnd()):
            if fmt.isImageFormat():
                continue
            edit.setPosition(s)
            edit.setPosition(e, QTextCursor.KeepAnchor)
            edit.setCharFormat(QTextCharFormat())
        edit.endEditBlock()

    def _confirm_make_plain(self, pictures: bool) -> bool:
        extra = " and pictures" if pictures else ""
        return QMessageBox.question(
            self, "Convert to Plain Text",
            f"Remove all formatting{extra} from this note?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes

    def make_plain(self, confirm: bool = True) -> bool:
        if not self.editor.rich or not self.editor.isEnabled() or not self._writable():
            return False
        text = self.editor.toPlainText()
        if confirm and not self._confirm_make_plain("￼" in text):
            return False
        self.editor.set_rich(False)
        self.editor.setPlainText(text.replace("￼", ""))
        self._editor_dirty = True
        self.setWindowModified(True)
        return True

    def _format_rich(self, func) -> Optional[bool]:
        """Format-menu clean-ups that keep the formatting of a formatted note.
        Returns None when ``func`` has to work on plain text instead."""
        cursor = self.editor.textCursor()
        if cursor.hasSelection():
            start, end = cursor.selectionStart(), cursor.selectionEnd()
        else:
            start, end = 0, self.editor.document().characterCount() - 1
        edit = QTextCursor(self.editor.document())
        changed = False
        if func in (textfmt.to_upper, textfmt.to_lower):
            edit.beginEditBlock()
            for s, e, fmt in reversed(self._fragments(start, end)):
                if fmt.isImageFormat():
                    continue
                edit.setPosition(s)
                edit.setPosition(e, QTextCursor.KeepAnchor)
                old = edit.selectedText()
                new = func(old)
                if new != old:
                    edit.insertText(new, fmt)
                    changed = True
            edit.endEditBlock()
            return changed
        if func is textfmt.remove_leading_spaces:
            doc = self.editor.document()
            blocks = []
            block = doc.findBlock(start)
            while block.isValid() and block.position() <= end:
                blocks.append(block)
                block = block.next()
            edit.beginEditBlock()
            for block in reversed(blocks):
                text = block.text()
                n = len(text) - len(text.lstrip(" \t"))
                if n:
                    edit.setPosition(block.position())
                    edit.setPosition(block.position() + search.to_qt(text, n), QTextCursor.KeepAnchor)
                    edit.removeSelectedText()
                    changed = True
            edit.endEditBlock()
            return changed
        return None

    # ===================================================== icons and colours

    def set_note_look(self, icon: Optional[str] = None, color: Optional[str] = None) -> bool:
        item = self.tree.currentItem()
        if item is None or not self._writable():
            return False
        item.set_look(icon, color)
        self.tree.viewport().update()
        return True

    def choose_note_color(self) -> None:
        item = self.tree.currentItem()
        if item is None:
            return
        color = self._pick_color(QColor(item.color or "#1f5fbf"), "Note Colour")
        if color.isValid():
            self.set_note_look(color=color.name())

    def _sync_look_menu(self) -> None:
        item = self.tree.currentItem()
        if item is None:
            return
        act = self.act_icons.get(item.icon)
        if act is not None:
            act.setChecked(True)
        act = self.act_colors.get(item.color)
        if act is not None:
            act.setChecked(True)
        else:
            for a in self.act_colors.values():
                a.setChecked(False)
        for kind, a in self.act_icons.items():
            a.setIcon(treestyle.note_icon(kind, item.color))

    # ============================================================ password

    def _ask_new_password(self) -> Optional[str]:
        dlg = QDialog(self)
        dlg.setWindowTitle("Set Password")
        first, second = QLineEdit(), QLineEdit()
        for box in (first, second):
            box.setEchoMode(QLineEdit.Password)
        note = QLabel("The file will be encrypted and saved as a Twigpad notes file (.twig).\n"
                      "If you forget the password, the notes can't be recovered.")
        note.setWordWrap(True)
        error = QLabel()
        error.setStyleSheet("color: #c0392b")
        form = QFormLayout(dlg)
        form.addRow(note)
        form.addRow("&Password:", first)
        form.addRow("&Repeat:", second)
        form.addRow(error)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        form.addRow(buttons)
        buttons.rejected.connect(dlg.reject)

        def check():
            if not first.text():
                error.setText("Type a password.")
            elif first.text() != second.text():
                error.setText("The two passwords are different.")
            else:
                dlg.accept()
        buttons.accepted.connect(check)
        return first.text() if dlg.exec_() == QDialog.Accepted else None

    def _drop_plain_backup(self) -> None:
        """Delete the .bak this session made of the file before it had a password."""
        if self.path and self._backed_up_path == self.path:
            try:
                with open(self.path + ".bak", "rb") as fh:
                    plain = not twig.is_encrypted(fh.read(len(twig.ENC_MAGIC)))
                if plain:
                    os.remove(self.path + ".bak")
            except OSError:
                pass
            self._backed_up_path = None

    def set_password(self, password: Optional[str] = None) -> bool:
        if not twig.encryption_available():
            QMessageBox.warning(self, APP_NAME, "Password protection needs the Python "
                                "'cryptography' package (python3-cryptography).")
            return False
        if not self._writable():
            return False
        if password is None:
            password = self._ask_new_password()
            if password is None:
                return False
        self.crypto = twig.derive_key(password)
        self._drop_plain_backup()
        self.setWindowModified(True)
        self._update_crypto_label()
        self._update_node_actions()
        self.statusBar().showMessage("Password set. The file is encrypted from the next save.", 8000)
        return True

    def remove_password(self) -> None:
        if self.crypto is None or not self._writable():
            return
        self.crypto = None
        self.setWindowModified(True)
        self._update_crypto_label()
        self._update_node_actions()
        self.statusBar().showMessage("Password removed. The next save is not encrypted.", 8000)

    def _update_crypto_label(self) -> None:
        self.crypto_label.setVisible(self.crypto is not None)

    # ======================================================= article edits

    def _goto(self, where) -> None:
        self.editor.moveCursor(where)
        self.editor.setFocus()

    def copy_article(self) -> None:
        """Copy the selection, or the whole article when nothing is selected."""
        if self.editor.textCursor().hasSelection():
            self.editor.copy()
            return
        keep = self.editor.textCursor()
        self.editor.selectAll()
        self.editor.copy()
        self.editor.setTextCursor(keep)
        self.statusBar().showMessage("Copied the whole article.", 3000)

    def cut_article(self) -> None:
        """Cut the selection, or the whole article when nothing is selected."""
        if not self.editor.isEnabled() or not self._writable():
            return
        if not self.editor.textCursor().hasSelection():
            self.editor.selectAll()
        self.editor.cut()

    def _confirm_clear_article(self) -> bool:
        return QMessageBox.question(self, "Delete", "Delete the whole text of this article?",
                                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No) == QMessageBox.Yes

    def delete_article_text(self) -> None:
        if not self.editor.isEnabled() or not self._writable():
            return
        cursor = self.editor.textCursor()
        if cursor.hasSelection():
            cursor.removeSelectedText()
        elif self.editor.document().characterCount() > 1 and self._confirm_clear_article():
            cursor.select(QTextCursor.Document)
            cursor.removeSelectedText()

    def replace_article_from_file(self, path: Optional[str] = None) -> bool:
        """Replace the article's text with a text file (Ctrl+Z brings it back)."""
        if not self.editor.isEnabled() or not self._writable():
            return False
        if path is None:
            path, _ = QFileDialog.getOpenFileName(self, "Text File into Article", self._last_dir(), TEXT_FILTERS)
            if not path:
                return False
        text = self._read_text(path)
        if text is None:
            return False
        cursor = self.editor.textCursor()
        cursor.select(QTextCursor.Document)
        cursor.insertText(text)
        self.editor.moveCursor(QTextCursor.Start)
        return True

    def show_context_menu(self, widget) -> None:
        """Shift+F10: the right-click menu of the tree or the article."""
        if widget is self.tree:
            item = self.tree.currentItem()
            rect = self.tree.visualItemRect(item) if item is not None else self.tree.viewport().rect()
            self._tree_menu(rect.center())
        else:
            self._editor_menu(self.editor.cursorRect().center())

    # ======================================================= options

    def set_tab_switch(self, on: bool) -> None:
        """Tab switches panes; Ctrl+Tab then types a tab character in the article."""
        self.settings.setValue("options/tab_switch", on)
        self.act_switch_pane.setShortcuts([QKeySequence("F6")] if on else
                                          [QKeySequence("F6"), QKeySequence("Ctrl+Tab")])

    def pane_colors(self) -> dict:
        return {k: self.settings.value(f"colors/{k}", "", type=str) for k in COLOR_KEYS}

    def apply_pane_colors(self) -> None:
        colors = self.pane_colors()
        for widget, bg, fg in ((self.tree, "tree_bg", "tree_fg"), (self.editor, "article_bg", "article_fg")):
            pal = QApplication.palette(widget)
            for role, key in ((pal.Base, bg), (pal.Text, fg)):
                if colors[key] and QColor(colors[key]).isValid():
                    pal.setColor(role, QColor(colors[key]))
            widget.setPalette(pal)
            widget.viewport().update()

    def set_pane_color(self, key: str, color: str) -> None:
        if color:
            self.settings.setValue(f"colors/{key}", color)
        else:
            self.settings.remove(f"colors/{key}")
        self.apply_pane_colors()

    def choose_pane_colors(self) -> None:
        from PyQt5.QtWidgets import QPushButton
        dlg = QDialog(self)
        dlg.setWindowTitle("Colours")
        form = QFormLayout(dlg)
        labels = {"tree_bg": "Tree &background:", "tree_fg": "Tree &text:",
                  "article_bg": "&Article background:", "article_fg": "Article te&xt:"}

        def button_for(key):
            btn = QPushButton()

            def refresh():
                value = self.pane_colors()[key]
                btn.setText(value or "Default")
                pm = QPixmap(14, 14)
                pm.fill(QColor(value) if value else Qt.transparent)
                btn.setIcon(QIcon(pm))

            def pick():
                current = QColor(self.pane_colors()[key] or (
                    self.tree if key.startswith("tree") else self.editor).palette().color(
                    QPalette.Base if key.endswith("bg") else QPalette.Text))
                color = self._pick_color(current, labels[key].replace("&", "").rstrip(":"))
                if color.isValid():
                    self.set_pane_color(key, color.name())
                    refresh()
            btn.clicked.connect(pick)
            refresh()
            return btn, refresh

        refreshers = []
        for key in COLOR_KEYS:
            btn, refresh = button_for(key)
            refreshers.append(refresh)
            form.addRow(labels[key], btn)
        buttons = QDialogButtonBox(QDialogButtonBox.Close | QDialogButtonBox.RestoreDefaults)
        buttons.rejected.connect(dlg.reject)

        def reset():
            for key in COLOR_KEYS:
                self.set_pane_color(key, "")
            for r in refreshers:
                r()
        buttons.button(QDialogButtonBox.RestoreDefaults).clicked.connect(reset)
        form.addRow(buttons)
        dlg.exec_()

    def _using_portable(self) -> bool:
        ini = portable.portable_ini()
        return bool(ini) and os.path.abspath(self.settings.fileName()) == os.path.abspath(ini)

    def set_portable(self, on: bool) -> bool:
        """Move the settings between the home folder and a file next to the program."""
        target = os.path.join(portable.program_dir(), portable.INI_NAME)
        old = self.settings
        if on:
            try:
                open(target, "a").close()
            except OSError as exc:
                self.act_portable.blockSignals(True)
                self.act_portable.setChecked(False)
                self.act_portable.blockSignals(False)
                QMessageBox.warning(self, APP_NAME, f"Can't write settings next to the program.\n\n{exc}")
                return False
            new = QSettings(target, QSettings.IniFormat)
        else:
            new = QSettings(APP_ID, APP_ID)
        self._save_settings()
        for key in old.allKeys():
            new.setValue(key, old.value(key))
        new.sync()
        self.settings = new
        if not on and os.path.exists(target):
            try:
                os.remove(target)
            except OSError:
                pass
        where = target if on else "your home folder"
        self.statusBar().showMessage(f"Settings are now kept in {where}.", 8000)
        return True

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
        if event.type() == QEvent.KeyPress and obj in (self.editor, self.tree):
            key, mods = event.key(), event.modifiers()
            if key == Qt.Key_F10 and mods == Qt.ShiftModifier:
                self.show_context_menu(obj)
                return True
            if self.act_tab_switch.isChecked():
                if key == Qt.Key_Tab and mods == Qt.NoModifier:
                    self.switch_pane()
                    return True
                if key == Qt.Key_Tab and mods == Qt.ControlModifier and obj is self.editor:
                    if not self.read_only:
                        self.editor.insertPlainText("\t")
                    return True
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
        self.editor.setLineWrapMode(QTextEdit.WidgetWidth if on else QTextEdit.NoWrap)

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

    def show_find(self, replace: bool = False, scope: Optional[int] = None) -> None:
        self.find_dialog().show_dialog(replace, scope)

    def find_here(self) -> None:
        """Ctrl+F in the article searches this article; in the tree, the whole tree."""
        from .finddialog import SCOPE_ALL, SCOPE_NODE
        self.show_find(False, SCOPE_NODE if self.editor.hasFocus() else SCOPE_ALL)

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
        self.editor.images.clear()
        self.editor.images.update(doc.images)
        self.editor.document().clear()   # forget cached pictures of the previous file
        self.crypto = doc.crypto
        self._plain_ok_path = None
        self._update_crypto_label()
        self._loading = True
        try:
            self.tree.load_document(doc)
        finally:
            self._loading = False
        self._reset_tabs()
        self._show_item(self.tree.currentItem())
        self.info_timer.start()
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
        self._watch(None)
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
        name = os.path.basename(path)
        try:
            with open(path, "rb") as fh:
                data = fh.read()
            if not twig.looks_like_twig(data):
                doc = hjt.load_bytes(data, path)
            else:
                password, retry = None, False
                while True:
                    try:
                        doc = twig.load_bytes(data, password)
                        break
                    except (twig.PasswordRequired, twig.WrongPassword) as exc:
                        retry = isinstance(exc, twig.WrongPassword)
                        password = self._ask_password(name, retry)
                        if password is None:
                            return None
            doc.path = path
            return doc
        except (OSError, hjt.HjtFormatError, twig.TwigFormatError, zipfile.BadZipFile) as exc:
            QMessageBox.warning(self, APP_NAME, f"Could not open \"{name}\".\n\n{exc}")
            return None

    def _ask_password(self, name: str, retry: bool) -> Optional[str]:
        """Ask for the password of a protected file (None = cancelled)."""
        text = (f"Wrong password for \"{name}\". Try again:" if retry
                else f"\"{name}\" is password protected.\n\nPassword:")
        password, ok = QInputDialog.getText(self, "Password", text, QLineEdit.Password)
        return password if ok else None

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
        # .twig files are UTF-8; a later Save As .hjt picks the Windows encoding again.
        self.encoding = "cp1252" if path.lower().endswith(".twig") else doc.encoding
        self.settings.setValue("files/last_dir", os.path.dirname(os.path.abspath(path)))
        self._add_recent(path)

        # Backups and archives are imported: Save asks for a new .hjt name
        # instead of overwriting the backup.
        imported = not path.lower().endswith(OWN_EXTS)
        locked = False
        if imported:
            self._watch(None)
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
            self._watch(path)
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
        for name, data in doc.images.items():
            self.editor.images.setdefault(name, data)
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
        if self.editor.rich:
            done = self._format_rich(func)
            if done is not None:
                return done
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
        "twig": ("Export as Twigpad File", ".twig", "Twigpad notes (*.twig)"),
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
        if kind in ("hjt", "twig") and self.path and os.path.abspath(path) == os.path.abspath(self.path):
            QMessageBox.warning(self, APP_NAME, "Choose a different name: that is the file you have open.")
            return False
        try:
            if kind in ("hjt", "twig"):
                doc = Document()
                if len(nodes) == 1:
                    doc.root.add_child(nodes[0])
                else:
                    wrapper = doc.root.add_child(Node(NEW_FILE_TITLE))
                    for n in nodes:
                        wrapper.add_child(n)
                if kind == "twig":
                    doc.images = dict(self.editor.images)
                    doc.crypto = self.crypto     # a protected file's branch stays protected
                    twig.save(doc, path)
                else:
                    for node, _level in doc.walk():
                        node.text = node.text.replace("\ufffc", "")
                    hjt.save(doc, path, self.encoding)
            else:
                if kind == "html":
                    title = os.path.splitext(os.path.basename(self.path or self.source_name or ""))[0]
                    content = export.html_page(nodes, title if scope == "all" else "", self.editor.images)
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
        for name, data in self.editor.images.items():
            image = QImage()
            if image.loadFromData(data):
                document.addResource(QTextDocument.ImageResource, QUrl(f"{twig.IMAGE_SCHEME}:{name}"), image)
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

    def _current_document(self) -> Document:
        """The open file as a Document, with images and password settings."""
        self._commit_editor()
        doc = self.tree.to_document()
        doc.images = dict(self.editor.images)
        doc.crypto = self.crypto
        return doc

    def save_as(self, twig_format: Optional[bool] = None) -> bool:
        """Ask for a name and save. A file that uses formatting, pictures,
        icons, colours or a password is offered as .twig first."""
        if twig_format is None:
            twig_format = self._current_document().needs_twig()
        ext = ".twig" if twig_format else ".hjt"
        start = self.path or os.path.join(self._last_dir(), self.source_name or "Untitled.hjt")
        start = os.path.splitext(start)[0] + ext
        filters = f"{TWIG_FILTER};;{HJT_FILTER}" if twig_format else f"{HJT_FILTER};;{TWIG_FILTER}"
        path, chosen = QFileDialog.getSaveFileName(self, "Save As", start, filters)
        if not path:
            return False
        if not os.path.splitext(path)[1]:
            path += ".twig" if chosen == TWIG_FILTER else ".hjt"
        return self._write(path)

    def _ask_save_format(self, name: str, reasons: List[str]) -> Optional[str]:
        """'twig', 'hjt' (drop what .hjt can't hold) or None (cancel)."""
        box = QMessageBox(QMessageBox.Question, APP_NAME,
                          f"\"{name}\" uses {', '.join(reasons)}, which a .hjt file can't store.",
                          parent=self)
        box.setInformativeText("Save it as a Twigpad notes file (.twig) to keep everything, or as "
                               ".hjt with plain text only.")
        twig_btn = box.addButton("Save as .twig...", QMessageBox.AcceptRole)
        hjt_btn = box.addButton("Save as Plain .hjt", QMessageBox.DestructiveRole)
        box.addButton(QMessageBox.Cancel)
        box.setDefaultButton(twig_btn)
        box.exec_()
        clicked = box.clickedButton()
        return "twig" if clicked is twig_btn else "hjt" if clicked is hjt_btn else None

    @staticmethod
    def _twig_reasons(doc: Document) -> List[str]:
        nodes = [n for n, _ in doc.walk()]
        reasons = []
        if any(n.html for n in nodes):
            reasons.append("formatted text")
        if any(n.icon or n.color for n in nodes):
            reasons.append("note icons or colours")
        if doc.crypto is not None:
            reasons.append("a password")
        return reasons

    def _make_backup(self, path: str) -> None:
        """Once per opened file, copy the version on disk to ``<file>.bak``."""
        if not self.act_backup.isChecked() or self._backed_up_path == path or not os.path.exists(path):
            return
        if self.crypto is not None:
            try:
                with open(path, "rb") as fh:
                    protected = twig.is_encrypted(fh.read(len(twig.ENC_MAGIC)))
            except OSError:
                protected = False
            if not protected:
                # Never keep an unencrypted copy of a file that now has a password.
                self._backed_up_path = path
                bak = path + ".bak"
                if os.path.exists(bak):
                    self.statusBar().showMessage(
                        f"Note: the older backup copy {os.path.basename(bak)} is not password "
                        "protected. Delete it if it should stay private.", 20000)
                return
        try:
            shutil.copy2(path, path + ".bak")
            self._backed_up_path = path
        except OSError as exc:
            self.statusBar().showMessage(f"Could not write backup copy: {exc}", 8000)

    def _write(self, path: str, quiet: bool = False) -> bool:
        self._commit_editor()
        if (self.path and path == self.path and self._disk_stamp is not None
                and self._stamp(path) not in (None, self._disk_stamp)):
            if quiet or not self._confirm_overwrite(os.path.basename(path)):
                if quiet:
                    self.statusBar().showMessage(
                        "Auto-save skipped: the file was changed by another program.", 10000)
                return False
        doc = self._current_document()
        as_twig = path.lower().endswith(".twig")
        if not as_twig and doc.needs_twig() and self._plain_ok_path != path:
            if quiet:
                self.statusBar().showMessage(
                    "Auto-save skipped: choose how to save the formatting first (File > Save).", 10000)
                return False
            choice = self._ask_save_format(os.path.basename(path), self._twig_reasons(doc))
            if choice is None:
                return False
            if choice == "twig":
                return self.save_as(twig_format=True)
            self._plain_ok_path = path
        if not as_twig:
            for node, _level in doc.walk():
                node.text = node.text.replace("\ufffc", "")   # picture placeholders
        self._make_backup(path)
        try:
            if as_twig:
                twig.save(doc, path)
            else:
                hjt.save(doc, path, self.encoding)
        except (OSError, ValueError) as exc:
            if quiet:
                self.statusBar().showMessage(f"Auto-save failed: {exc}", 10000)
            else:
                QMessageBox.critical(self, APP_NAME, f"Could not save \"{path}\".\n\n{exc}")
            return False
        self.path = path
        self.source_name = ""
        if not as_twig:
            self.encoding = doc.encoding
        self._watch(path)
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

    def _ok_to_close(self) -> bool:
        mode = next((m for m, a in self.act_close_modes.items() if a.isChecked()), "ask")
        if mode == "ask":
            return self.maybe_save()
        self._commit_editor()
        if mode == "save" and self.isWindowModified():
            return self.save()
        return True

    def closeEvent(self, event) -> None:
        if self._ok_to_close():
            self._watch(None)
            self.disk_timer.stop()
            self.info_timer.stop()
            self._save_settings()
            if self._find_dialog is not None:
                self._find_dialog.close()
            event.accept()
        else:
            event.ignore()
