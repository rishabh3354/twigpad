# SPDX-License-Identifier: GPL-3.0-or-later
"""The left-hand tree of notes."""
from __future__ import annotations

from typing import Dict, List, Optional

from PyQt5.QtCore import QSize, Qt, pyqtSignal
from PyQt5.QtGui import QDrag
from PyQt5.QtWidgets import QAbstractItemView, QTreeWidget, QTreeWidgetItem

from ..model import Document, Node
from . import treestyle

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
        self.classic = False
        self.setItemDelegate(treestyle.TreeDelegate(self))
        self.set_classic(True)

    # ------------------------------------------------------------ look

    def set_classic(self, on: bool) -> None:
        """Classic look: folder icons, dotted lines, +/- boxes."""
        self.classic = on
        self.setIndentation(treestyle.INDENT if on else self.style().pixelMetric(
            self.style().PM_TreeViewIndentation, None, self))
        self.setIconSize(QSize(treestyle.ICON, treestyle.ICON))
        self.scheduleDelayedItemsLayout()
        self.viewport().update()

    def drawBranches(self, painter, rect, index) -> None:
        if self.classic:
            treestyle.draw_branches(self, painter, rect, index)
        else:
            super().drawBranches(painter, rect, index)

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

    # A tree file has exactly one top node: nothing can be added next to it,
    # and it cannot be deleted, moved or dragged.

    @staticmethod
    def is_top(item: Optional[QTreeWidgetItem]) -> bool:
        return item is not None and item.parent() is None

    def add_sibling(self, after: bool = True, title: str = DEFAULT_TITLE) -> Optional[NoteItem]:
        cur = self.currentItem()
        if self.is_top(cur):
            return None
        new = NoteItem(title)
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

    def remove_item(self, item: NoteItem) -> bool:
        if self.is_top(item) and self.topLevelItemCount() == 1:
            return False
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
        return True

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
        if cur is None or cur.parent() is None or cur.parent().parent() is None:
            return False  # children of the top node cannot become top nodes
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

    def move_next_siblings_right(self) -> int:
        """The nodes after the selected one (same level) become its last
        children. Returns how many nodes moved."""
        cur = self.currentItem()
        if cur is None or self.is_top(cur):
            return 0
        parent = self._siblings_parent(cur)
        idx = parent.indexOfChild(cur)
        moved = []
        while parent.childCount() > idx + 1:
            moved.append(parent.takeChild(idx + 1))
        if not moved:
            return 0
        states = {}
        for m in moved:
            states.update(self._expanded_states(m))
        cur.addChildren(moved)
        for m in moved:
            self._restore_expanded(m, states)
        cur.setExpanded(True)
        self.setCurrentItem(cur)
        self.structureChanged.emit()
        return len(moved)

    def move_children_left(self) -> int:
        """The children of the selected node become its siblings, placed right
        after it. Not possible on the top node. Returns how many nodes moved."""
        cur = self.currentItem()
        if cur is None or self.is_top(cur) or cur.childCount() == 0:
            return 0
        parent = self._siblings_parent(cur)
        idx = parent.indexOfChild(cur)
        states = self._expanded_states(cur)
        kids = [cur.takeChild(0) for _ in range(cur.childCount())]
        parent.insertChildren(idx + 1, kids)
        for k in kids:
            self._restore_expanded(k, states)
        self.setCurrentItem(cur)
        self.structureChanged.emit()
        return len(kids)

    @staticmethod
    def set_branch_expanded(item: QTreeWidgetItem, expanded: bool, all_levels: bool = True) -> None:
        """Expand or collapse ``item`` (and, with ``all_levels``, everything inside it)."""
        if all_levels:
            for it in NoteTree.all_items_under(item):
                it.setExpanded(expanded)
        else:
            item.setExpanded(expanded)

    def select_sibling(self, step: int) -> bool:
        """Jump to the next (+1) or previous (-1) node at the same level."""
        cur = self.currentItem()
        if cur is None:
            return False
        parent = self._siblings_parent(cur)
        idx = parent.indexOfChild(cur) + step
        if 0 <= idx < parent.childCount():
            self.setCurrentItem(parent.child(idx))
            self.scrollToItem(parent.child(idx))
            return True
        return False

    def sort_children(self, item: QTreeWidgetItem, recursive: bool = False) -> bool:
        """Sort the children of ``item`` by title (and their children too when
        ``recursive``). The selected node and expanded branches are kept."""
        current = self.currentItem()
        changed = False
        pending = [item]
        while pending:
            it = pending.pop()
            if it.childCount() > 1:
                kids = [it.takeChild(0) for _ in range(it.childCount())]
                states = {}
                for k in kids:
                    states.update(self._expanded_states(k))
                kids.sort(key=lambda k: k.title.casefold())
                it.addChildren(kids)
                for k in kids:
                    self._restore_expanded(k, states)
                changed = True
            if recursive:
                pending.extend(it.child(i) for i in range(it.childCount()))
        if current is not None:
            self.setCurrentItem(current)
        if changed:
            self.structureChanged.emit()
        return changed

    def title_path(self, item: QTreeWidgetItem) -> List[str]:
        """Titles from the top node down to ``item``."""
        titles = []
        while item is not None:
            titles.append(item.text(0))
            item = item.parent()
        return titles[::-1]

    # ------------------------------------------------------------ drag & drop
    # Moves are done by hand (take + insert of the same item) so the article
    # text and the expanded state of the subtree travel with the node.

    def startDrag(self, supported_actions) -> None:
        item = self.currentItem()
        if item is None or self.is_top(item):
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
            event.ignore()  # would create a second top node
            return
        elif pos == QAbstractItemView.OnItem:
            parent, index = target, target.childCount()
        else:
            parent = target.parent()
            if parent is None:
                event.ignore()  # next to the top node
                return
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
