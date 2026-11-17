# SPDX-License-Identifier: GPL-3.0-or-later
"""Find & Replace across all nodes (titles and/or articles)."""
from __future__ import annotations

import re
from typing import List, Optional

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QTextCursor, QTextDocument
from PyQt5.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QGridLayout, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QPushButton, QVBoxLayout,
)

from .. import search
from ..search import TEXT, TITLE, Match

SCOPE_ALL, SCOPE_SUBTREE, SCOPE_NODE = range(3)
MAX_RESULTS = 2000


class FindDialog(QDialog):
    def __init__(self, win):
        super().__init__(win)
        self.win = win
        self.setWindowTitle("Find and Replace")
        self.last_match: Optional[Match] = None
        self.scope_root = None
        self._results: List[Match] = []

        self.find_edit = QLineEdit()
        self.find_edit.setPlaceholderText("Text to find")
        self.replace_edit = QLineEdit()
        self.replace_edit.setPlaceholderText("Replace with")
        self.replace_label = QLabel("Re&place with:")
        self.replace_label.setBuddy(self.replace_edit)
        find_label = QLabel("Fi&nd what:")
        find_label.setBuddy(self.find_edit)

        self.case_box = QCheckBox("Match &case")
        self.word_box = QCheckBox("&Whole words only")
        self.regex_box = QCheckBox("Regular e&xpression")
        self.titles_box = QCheckBox("Node &titles")
        self.text_box = QCheckBox("&Articles")
        self.titles_box.setChecked(True)
        self.text_box.setChecked(True)
        self.scope_combo = QComboBox()
        self.scope_combo.addItems(["All nodes", "Selected node and its subnodes", "Selected node only"])
        self.scope_combo.currentIndexChanged.connect(self._capture_scope)

        self.btn_next = QPushButton("Find &Next")
        self.btn_prev = QPushButton("Find Pre&vious")
        self.btn_all = QPushButton("Find A&ll")
        self.btn_replace = QPushButton("&Replace")
        self.btn_replace_all = QPushButton("Replace &All")
        close = QPushButton("Close")
        self.btn_next.setDefault(True)
        self.btn_next.clicked.connect(lambda: self.find(backward=False))
        self.btn_prev.clicked.connect(lambda: self.find(backward=True))
        self.btn_all.clicked.connect(self.find_all)
        self.btn_replace.clicked.connect(self.replace_one)
        self.btn_replace_all.clicked.connect(self.replace_all)
        close.clicked.connect(self.close)

        self.status = QLabel()
        self.status.setWordWrap(True)
        self.results = QListWidget()
        self.results.setVisible(False)
        self.results.currentRowChanged.connect(self._jump_to_result)

        grid = QGridLayout()
        grid.addWidget(find_label, 0, 0)
        grid.addWidget(self.find_edit, 0, 1)
        grid.addWidget(self.replace_label, 1, 0)
        grid.addWidget(self.replace_edit, 1, 1)
        grid.addWidget(QLabel("Search in:"), 2, 0)
        look = QHBoxLayout()
        look.addWidget(self.titles_box)
        look.addWidget(self.text_box)
        look.addStretch()
        grid.addLayout(look, 2, 1)
        grid.addWidget(QLabel("Nodes:"), 3, 0)
        grid.addWidget(self.scope_combo, 3, 1)
        opts = QHBoxLayout()
        opts.addWidget(self.case_box)
        opts.addWidget(self.word_box)
        opts.addWidget(self.regex_box)
        opts.addStretch()
        grid.addLayout(opts, 4, 1)

        buttons = QVBoxLayout()
        for b in (self.btn_next, self.btn_prev, self.btn_all, self.btn_replace, self.btn_replace_all):
            buttons.addWidget(b)
        buttons.addStretch()
        buttons.addWidget(close)

        top = QHBoxLayout()
        top.addLayout(grid, 1)
        top.addLayout(buttons)
        layout = QVBoxLayout(self)
        layout.addLayout(top)
        layout.addWidget(self.status)
        layout.addWidget(self.results, 1)
        self.resize(560, 260)

    # ------------------------------------------------------------- showing

    def show_dialog(self, replace: bool = False, scope: Optional[int] = None) -> None:
        if scope is not None:
            self.scope_combo.setCurrentIndex(scope)
        for w in (self.replace_label, self.replace_edit, self.btn_replace, self.btn_replace_all):
            w.setVisible(replace)
        self.setWindowTitle("Replace" if replace else "Find")
        selected = self.win.editor.textCursor().selectedText()
        if selected and " " not in selected:
            self.find_edit.setText(selected)
        self._capture_scope()
        self.status.clear()
        self.show()
        self.raise_()
        self.activateWindow()
        self.find_edit.setFocus()
        self.find_edit.selectAll()

    def _capture_scope(self, *_args) -> None:
        self.scope_root = self.win.tree.currentItem()

    # ------------------------------------------------------------- helpers

    def _pattern(self):
        try:
            return search.compile_pattern(self.find_edit.text(), self.case_box.isChecked(),
                                          self.word_box.isChecked(), self.regex_box.isChecked())
        except ValueError as exc:
            self.status.setText(str(exc))
        except re.error as exc:
            self.status.setText(f"Invalid regular expression: {exc}")
        return None

    def _items(self) -> list:
        tree = self.win.tree
        scope = self.scope_combo.currentIndex()
        root = self.scope_root
        if scope != SCOPE_ALL and root is not None and root in tree.all_items():
            return [root] if scope == SCOPE_NODE else tree.all_items_under(root)
        return tree.all_items()

    def _fields(self):
        return self.titles_box.isChecked(), self.text_box.isChecked()

    def _anchor(self, items, backward: bool):
        tree, editor = self.win.tree, self.win.editor
        cur = tree.currentItem()
        if cur not in items:
            return (len(items), 0, 0) if backward else (-1, 0, 0)
        i = items.index(cur)
        lm = self.last_match
        if lm is not None and lm.item is cur and lm.field == TITLE:
            return (i, TITLE, lm.start if backward else lm.start + 1)
        if tree.hasFocus() and not backward:
            return (i, TITLE, 0)
        c = editor.textCursor()
        body = editor.toPlainText()
        start = search.from_qt(body, c.selectionStart())
        if backward:
            return (i, TEXT, start)
        return (i, TEXT, start + 1 if c.hasSelection() else search.from_qt(body, c.position()))

    def show_match(self, m: Match) -> None:
        win = self.win
        win.tree.setCurrentItem(m.item)
        win.tree.scrollToItem(m.item)
        cursor = win.editor.textCursor()
        if m.field == TEXT:
            body = m.item.body
            cursor.setPosition(search.to_qt(body, m.start))
            cursor.setPosition(search.to_qt(body, m.end), QTextCursor.KeepAnchor)
        else:
            cursor.setPosition(0)
        win.editor.setTextCursor(cursor)
        win.editor.ensureCursorVisible()
        self.last_match = m

    # ------------------------------------------------------------- actions

    def find(self, backward: bool = False) -> Optional[Match]:
        pattern = self._pattern()
        if pattern is None:
            return None
        titles, text = self._fields()
        self.win._commit_editor()
        items = self._items()
        m, wrapped = search.find_next(items, pattern, self._anchor(items, backward),
                                      titles, text, backward)
        if m is None:
            self.status.setText(f"\"{self.find_edit.text()}\" was not found.")
            self.last_match = None
            return None
        self.show_match(m)
        where = "title" if m.field == TITLE else "article"
        self.status.setText(f"Found in the {where} of \"{m.item.title}\"."
                            + ("  (Search wrapped around.)" if wrapped else ""))
        return m

    def find_all(self) -> int:
        pattern = self._pattern()
        if pattern is None:
            return 0
        self.win._commit_editor()
        titles, text = self._fields()
        self._results = []
        self.results.blockSignals(True)
        self.results.clear()
        for m in search.iter_matches(self._items(), pattern, titles, text):
            if len(self._results) >= MAX_RESULTS:
                break
            self._results.append(m)
            if m.field == TITLE:
                label = f"{m.item.title}   [title]"
            else:
                label = f"{m.item.title}:   {search.snippet(m.item.body, m.start, m.end)}"
            QListWidgetItem(label, self.results)
        self.results.blockSignals(False)
        n = len(self._results)
        nodes = len({id(m.item) for m in self._results})
        more = f" (showing the first {MAX_RESULTS})" if n >= MAX_RESULTS else ""
        self.status.setText(f"{n} match{'es' if n != 1 else ''} in {nodes} node{'s' if nodes != 1 else ''}{more}.")
        self.results.setVisible(n > 0)
        if n and self.height() < 420:
            self.resize(self.width(), 420)
        return n

    def _jump_to_result(self, row: int) -> None:
        if 0 <= row < len(self._results):
            m = self._results[row]
            if m.item in self.win.tree.all_items():
                self.show_match(m)

    def _current_selection_is_match(self, pattern) -> bool:
        """True if the editor/title currently shows the last match found."""
        lm = self.last_match
        if lm is None or lm.item is not self.win.tree.currentItem():
            return False
        if lm.field == TITLE:
            return pattern.fullmatch(lm.item.title[lm.start:lm.end]) is not None
        sel = self.win.editor.textCursor().selectedText()
        return bool(sel) and pattern.fullmatch(sel) is not None

    def replace_one(self) -> None:
        pattern = self._pattern()
        if pattern is None or self.win.read_only:
            return
        repl = self.replace_edit.text()
        regex = self.regex_box.isChecked()
        if self._current_selection_is_match(pattern):
            lm = self.last_match
            if lm.field == TEXT:
                cursor = self.win.editor.textCursor()
                new, _ = search.replace_in(cursor.selectedText(), pattern, repl, regex, count=1)
                cursor.insertText(new)
            else:
                title = lm.item.title
                new, _ = search.replace_in(title[lm.start:lm.end], pattern, repl, regex, count=1)
                lm.item.setText(0, title[:lm.start] + new + title[lm.end:])
                self.last_match = Match(lm.index, lm.item, TITLE, lm.start + len(new) - 1, lm.start + len(new))
        self.find(backward=False)

    def replace_all(self) -> int:
        pattern = self._pattern()
        if pattern is None or self.win.read_only:
            return 0
        win = self.win
        win._commit_editor()
        titles, text = self._fields()
        repl = self.replace_edit.text()
        regex = self.regex_box.isChecked()
        total = nodes = 0
        for item in self._items():
            changed = 0
            if titles:
                new_title, n = search.replace_in(item.title, pattern, repl, regex)
                if n:
                    item.setText(0, new_title)
                    changed += n
            if text:
                if item is win._editing_item:
                    # Through the editor, so Ctrl+Z can undo it and formatting is kept.
                    n = replace_in_document(win.editor.document(), pattern, repl, regex)
                    if n:
                        changed += n
                        win._commit_editor()
                elif item.html:
                    doc = QTextDocument()
                    doc.setHtml(item.html)
                    n = replace_in_document(doc, pattern, repl, regex)
                    if n:
                        changed += n
                        item.html = doc.toHtml()
                        item.body = doc.toPlainText()
                else:
                    new_body, n = search.replace_in(item.body, pattern, repl, regex)
                    if n:
                        changed += n
                        item.body = new_body
            if changed:
                total += changed
                nodes += 1
        if total:
            win.setWindowModified(True)
        self.last_match = None
        self.status.setText(f"Replaced {total} occurrence{'s' if total != 1 else ''} "
                            f"in {nodes} node{'s' if nodes != 1 else ''}.")
        return total

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key_F3:
            self.find(backward=bool(event.modifiers() & Qt.ShiftModifier))
            return
        super().keyPressEvent(event)


def replace_in_document(doc: QTextDocument, pattern, repl: str, regex: bool) -> int:
    """Replace every match in a text document, keeping the formatting around
    each match. One undo step."""
    text = doc.toPlainText()
    matches = [m for m in pattern.finditer(text) if m.end() > m.start()]
    if not matches:
        return 0
    cursor = QTextCursor(doc)
    cursor.beginEditBlock()
    for m in reversed(matches):
        cursor.setPosition(search.to_qt(text, m.start()))
        cursor.setPosition(search.to_qt(text, m.end()), QTextCursor.KeepAnchor)
        cursor.insertText(m.expand(repl) if regex else repl)
    cursor.endEditBlock()
    return len(matches)
