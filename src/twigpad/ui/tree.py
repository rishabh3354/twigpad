# SPDX-License-Identifier: GPL-3.0-or-later
"""The left-hand tree of notes."""
from __future__ import annotations

from typing import Dict, List, Optional

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QDrag
from PyQt5.QtWidgets import QAbstractItemView, QTreeWidget, QTreeWidgetItem

from ..model import Document, Node

DEFAULT_TITLE = "New node"


class NoteItem(QTreeWidgetItem):
    """A tree row. The article text lives on the item itself."""

    def __init__(self, title: str = DEFAULT_TITLE, body: str = ""):
        super().__init__([title])
        self.body = body
        self.cursor_pos = 0
        self.setFlags(self.flags() | Qt.ItemIsEditable)

    @property
    def title(self) -> str:
        return self.text(0)


class NoteTree(QTreeWidget):
    """Tree with node-level operations used by the window's menus.

    ``structureChanged`` fires whenever nodes are added, removed or moved.
    """

    structureChanged = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderHidden(True)
        self.setColumnCount(1)
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setEditTriggers(QAbstractItemView.EditKeyPressed)
        self.setUniformRowHeights(True)
        self.setAnimated(False)

    # ------------------------------------------------------------ conversion

    @staticmethod
    def _make_item(node: Node) -> NoteItem:
        item = NoteItem(node.title, node.text)
        for child in node.children:
            item.addChild(NoteTree._make_item(child))
        return item

    def load_document(self, doc: Document) -> None:
        self.clear()
        for top in doc.top_nodes:
            item = self._make_item(top)
            self.addTopLevelItem(item)
            item.setExpanded(True)
        if self.topLevelItemCount():
            self.setCurrentItem(self.topLevelItem(0))

    @staticmethod
    def item_to_node(item: NoteItem) -> Node:
        node = Node(item.title, item.body)
        for i in range(item.childCount()):
            node.add_child(NoteTree.item_to_node(item.child(i)))
        return node

    def insert_nodes(self, nodes: List[Node], parent: Optional[QTreeWidgetItem], index: int) -> List[NoteItem]:
        """Insert copies of ``nodes`` (with their subtrees) and select the first."""
        target = parent or self.invisibleRootItem()
        index = max(0, min(index, target.childCount()))
        items = [self._make_item(n) for n in nodes]
        for offset, item in enumerate(items):
            target.insertChild(index + offset, item)
        if parent is not None:
            parent.setExpanded(True)
        if items:
            self.setCurrentItem(items[0])
            self.scrollToItem(items[0])
        self.structureChanged.emit()
        return items

    def to_document(self) -> Document:
        doc = Document()
        for i in range(self.topLevelItemCount()):
            doc.root.add_child(self.item_to_node(self.topLevelItem(i)))
        return doc

    @staticmethod
    def all_items_under(item: QTreeWidgetItem) -> List[NoteItem]:
        """``item`` and all its descendants, in tree order."""
        out: List[NoteItem] = [item]
        for i in range(item.childCount()):
            out.extend(NoteTree.all_items_under(item.child(i)))
        return out

    def all_items(self) -> List[NoteItem]:
        out: List[NoteItem] = []
        for i in range(self.topLevelItemCount()):
            out.extend(self.all_items_under(self.topLevelItem(i)))
        return out

    # ------------------------------------------------------------ positions

    def _siblings_parent(self, item: QTreeWidgetItem):
        return item.parent() or self.invisibleRootItem()

    def index_in_parent(self, item: QTreeWidgetItem) -> int:
        return self._siblings_parent(item).indexOfChild(item)

    @staticmethod
    def is_ancestor(ancestor: QTreeWidgetItem, item: Optional[QTreeWidgetItem]) -> bool:
        while item is not None:
            if item is ancestor:
                return True
            item = item.parent()
        return False

    def _expanded_states(self, item: QTreeWidgetItem) -> Dict[int, bool]:
        states = {}

        def walk(it):
            states[id(it)] = it.isExpanded()
            for i in range(it.childCount()):
                walk(it.child(i))

        walk(item)
        return states

    def _restore_expanded(self, item: QTreeWidgetItem, states: Dict[int, bool]) -> None:
        def walk(it):
            it.setExpanded(states.get(id(it), False))
            for i in range(it.childCount()):
                walk(it.child(i))

        walk(item)

    def move_item(self, item: NoteItem, new_parent: Optional[QTreeWidgetItem], index: int) -> None:
        """Move ``item`` so it ends up at ``index`` among ``new_parent``'s children
        (``None`` = top level). ``index`` counts positions after the removal."""
        new_parent = new_parent or self.invisibleRootItem()
        if self.is_ancestor(item, new_parent if new_parent is not self.invisibleRootItem() else None):
            return
        states = self._expanded_states(item)
        old_parent = self._siblings_parent(item)
        old_parent.takeChild(old_parent.indexOfChild(item))
        index = max(0, min(index, new_parent.childCount()))
        new_parent.insertChild(index, item)
        self._restore_expanded(item, states)
        if new_parent is not self.invisibleRootItem():
            new_parent.setExpanded(True)
        self.setCurrentItem(item)
        self.scrollToItem(item)
        self.structureChanged.emit()

    # ------------------------------------------------------------ operations

    def add_sibling(self, after: bool = True, title: str = DEFAULT_TITLE) -> NoteItem:
        new = NoteItem(title)
        cur = self.currentItem()
        if cur is None:
            self.addTopLevelItem(new)
        else:
            parent = self._siblings_parent(cur)
            idx = parent.indexOfChild(cur)
            parent.insertChild(idx + 1 if after else idx, new)
        self.setCurrentItem(new)
        self.structureChanged.emit()
        return new

    def add_child(self, title: str = DEFAULT_TITLE) -> NoteItem:
        cur = self.currentItem()
        if cur is None:
            return self.add_sibling(title=title)
        new = NoteItem(title)
        cur.addChild(new)
        cur.setExpanded(True)
        self.setCurrentItem(new)
        self.structureChanged.emit()
        return new

    def remove_item(self, item: NoteItem) -> None:
        parent = self._siblings_parent(item)
        idx = parent.indexOfChild(item)
        # Pick the row that takes the focus afterwards: next sibling,
        # else previous sibling, else the parent.
        if idx + 1 < parent.childCount():
            nxt = parent.child(idx + 1)
        elif idx > 0:
            nxt = parent.child(idx - 1)
        else:
            nxt = item.parent()
        parent.takeChild(idx)
        if nxt is not None:
            self.setCurrentItem(nxt)
        self.structureChanged.emit()

    def move_up(self) -> bool:
        cur = self.currentItem()
        if cur is None or self.index_in_parent(cur) == 0:
            return False
        self.move_item(cur, cur.parent(), self.index_in_parent(cur) - 1)
        return True

    def move_down(self) -> bool:
        cur = self.currentItem()
        if cur is None:
            return False
        parent = self._siblings_parent(cur)
        idx = parent.indexOfChild(cur)
        if idx >= parent.childCount() - 1:
            return False
        self.move_item(cur, cur.parent(), idx + 1)
        return True

    def move_left(self) -> bool:
        """Promote: become the next sibling of the current parent."""
        cur = self.currentItem()
        if cur is None or cur.parent() is None:
            return False
        parent = cur.parent()
        grand = parent.parent()
        self.move_item(cur, grand, self._siblings_parent(parent).indexOfChild(parent) + 1)
        return True

    def move_right(self) -> bool:
        """Demote: become the last child of the previous sibling."""
        cur = self.currentItem()
        if cur is None:
            return False
        idx = self.index_in_parent(cur)
        if idx == 0:
            return False
        prev = self._siblings_parent(cur).child(idx - 1)
        self.move_item(cur, prev, prev.childCount())
        return True

    # ------------------------------------------------------------ drag & drop
    # Moves are done by hand (take + insert of the same item) so the article
    # text and the expanded state of the subtree travel with the node.

    def startDrag(self, supported_actions) -> None:
        item = self.currentItem()
        if item is None:
            return
        drag = QDrag(self)
        drag.setMimeData(self.mimeData([item]))
        drag.exec_(Qt.MoveAction)

    def dropEvent(self, event) -> None:
        item = self.currentItem()
        if event.source() is not self or item is None:
            event.ignore()
            return
        target = self.itemAt(event.pos())
        pos = self.dropIndicatorPosition()
        if target is not None and self.is_ancestor(item, target):
            event.ignore()
            return
        if target is None or pos == QAbstractItemView.OnViewport:
            parent, index = None, self.topLevelItemCount()
        elif pos == QAbstractItemView.OnItem:
            parent, index = target, target.childCount()
        else:
            parent = target.parent()
            index = self._siblings_parent(target).indexOfChild(target)
            if pos == QAbstractItemView.BelowItem:
                index += 1
        # Convert to an index that counts positions after the removal.
        same_parent = (parent or self.invisibleRootItem()) is self._siblings_parent(item)
        if same_parent and self.index_in_parent(item) < index:
            index -= 1
        # startDrag above never removes the source row, so accepting the
        # move here is safe: the node is moved exactly once, by move_item.
        event.setDropAction(Qt.MoveAction)
        event.accept()
        self.move_item(item, parent, index)
