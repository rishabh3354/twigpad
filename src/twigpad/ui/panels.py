# SPDX-License-Identifier: GPL-3.0-or-later
"""Side panels: Backlinks (which notes link to the selected one) and Tags
(every #tag in the file and the notes that use it)."""
from __future__ import annotations

from typing import List, Sequence, Tuple

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QDockWidget, QLabel, QListWidget, QListWidgetItem, QSplitter, QVBoxLayout, QWidget,
)

NOTE_ROLE = Qt.UserRole


class _NoteList(QListWidget):
    """A list of notes; activating a row emits the note."""

    noteActivated = pyqtSignal(object)

    def __init__(self):
        super().__init__()
        self.itemActivated.connect(self._emit)
        self.itemClicked.connect(self._emit)

    def _emit(self, row: QListWidgetItem) -> None:
        note = row.data(NOTE_ROLE)
        if note is not None:
            self.noteActivated.emit(note)

    def set_notes(self, notes: Sequence[Tuple[object, str, str]]) -> None:
        """``notes``: (note, label, tooltip)."""
        self.clear()
        for note, label, tip in notes:
            row = QListWidgetItem(label)
            row.setToolTip(tip)
            row.setData(NOTE_ROLE, note)
            self.addItem(row)


class BacklinksPanel(QDockWidget):
    noteActivated = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__("Backlinks", parent)
        self.setObjectName("backlinks-panel")
        self.list = _NoteList()
        self.list.noteActivated.connect(self.noteActivated)
        self.label = QLabel()
        self.label.setWordWrap(True)
        self.label.setContentsMargins(4, 2, 4, 2)
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(2)
        lay.addWidget(self.label)
        lay.addWidget(self.list)
        self.setWidget(box)

    def show_links(self, title: str, notes: Sequence[Tuple[object, str, str]]) -> None:
        self.list.set_notes(notes)
        if not title:
            self.label.setText("")
        elif notes:
            n = len(notes)
            self.label.setText(f"{n} note{'s link' if n != 1 else ' links'} to “{title}”:")
        else:
            self.label.setText(f"No notes link to “{title}”.")


class TagsPanel(QDockWidget):
    noteActivated = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__("Tags", parent)
        self.setObjectName("tags-panel")
        self.tag_list = QListWidget()
        self.tag_list.currentItemChanged.connect(self._show_tag)
        self.notes = _NoteList()
        self.notes.noteActivated.connect(self.noteActivated)
        self.empty = QLabel("Type #tag in any note, for example #todo or #work-project.")
        self.empty.setWordWrap(True)
        self.empty.setContentsMargins(4, 2, 4, 2)
        split = QSplitter(Qt.Vertical)
        split.addWidget(self.tag_list)
        split.addWidget(self.notes)
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self.empty)
        lay.addWidget(split)
        self.setWidget(box)
        self._groups: dict = {}
        self._describe = lambda note: (str(note), "")

    def set_tags(self, groups: dict, describe) -> None:
        """``groups``: key -> (name, [notes]); ``describe(note)`` -> (label, tooltip)."""
        current = self.tag_list.currentItem()
        keep = current.data(NOTE_ROLE) if current is not None else None
        self._groups, self._describe = groups, describe
        self.tag_list.blockSignals(True)
        self.tag_list.clear()
        select = None
        for key in sorted(groups):
            name, notes = groups[key]
            row = QListWidgetItem(f"#{name}  ({len(notes)})")
            row.setData(NOTE_ROLE, key)
            self.tag_list.addItem(row)
            if key == keep:
                select = row
        self.tag_list.blockSignals(False)
        self.empty.setVisible(not groups)
        if select is not None:
            self.tag_list.setCurrentItem(select)
        else:
            self.notes.clear()
        self._show_tag(self.tag_list.currentItem())

    def tag_names(self) -> List[str]:
        return [self._groups[k][0] for k in sorted(self._groups)]

    def select_tag(self, tag: str) -> bool:
        for i in range(self.tag_list.count()):
            if self.tag_list.item(i).data(NOTE_ROLE) == tag.casefold():
                self.tag_list.setCurrentRow(i)
                return True
        return False

    def _show_tag(self, row, _previous=None) -> None:
        if row is None:
            self.notes.clear()
            return
        _name, notes = self._groups.get(row.data(NOTE_ROLE), ("", []))
        self.notes.set_notes([(n, *self._describe(n)) for n in notes])
