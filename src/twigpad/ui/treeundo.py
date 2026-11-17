# SPDX-License-Identifier: GPL-3.0-or-later
"""Undo and redo for changes to the tree: adding, deleting, moving, sorting,
pasting, importing and renaming nodes, and changing their icons.

Every change is recorded as the difference between the tree before and after
it. Undo puts back the very same node objects (with their articles, pictures,
icons and subnodes), so tabs, focus and links to them keep working.
"""
from __future__ import annotations

from typing import Dict, Iterable, List, Optional, Set, Tuple

from PyQt5.QtWidgets import QTreeWidgetItem

from ..i18n import tr

ROOT = "root"          # key for the tree's top level
LIMIT = 200            # changes kept in the history
Attrs = Tuple[str, str, str, str, str]   # title, body, html, icon, color


def attrs(item) -> Attrs:
    return (item.text(0), item.body, item.html, item.icon, item.color)


class Snapshot:
    """Which node is inside which, the text and look of every node, and which
    branches are open. Qt's tree items can't be dictionary keys, so they are
    looked up by id() and kept alive in ``items``."""

    def __init__(self, tree):
        self.items: Dict[int, QTreeWidgetItem] = {}
        self.children: Dict[object, List[QTreeWidgetItem]] = {}   # id(parent) or ROOT -> children
        self.attrs: Dict[int, Attrs] = {}
        self.expanded: Set[int] = set()
        root = tree.invisibleRootItem()
        pending = [(ROOT, root)]
        while pending:
            key, parent = pending.pop()
            kids = [parent.child(i) for i in range(parent.childCount())]
            self.children[key] = kids
            for kid in kids:
                k = id(kid)
                self.items[k] = kid
                self.attrs[k] = attrs(kid)
                if kid.isExpanded():
                    self.expanded.add(k)
                pending.append((k, kid))


def _ids(items) -> List[int]:
    return [id(i) for i in items]


class Change:
    """One step in the history: what differs between before and after."""

    def __init__(self, label: str):
        self.label = label
        # id(parent) or ROOT -> (parent, children before, children after)
        self.parents: Dict[object, Tuple[Optional[QTreeWidgetItem], List, List]] = {}
        self.attrs: Dict[int, Tuple[QTreeWidgetItem, Attrs, Attrs]] = {}
        self.expanded: Tuple[Set[int], Set[int]] = (set(), set())   # open branches among moved nodes
        self.current: Tuple[Optional[QTreeWidgetItem], Optional[QTreeWidgetItem]] = (None, None)

    def __bool__(self) -> bool:
        return bool(self.parents or self.attrs)


def _subtree(children: Dict[object, List], tops: Iterable[QTreeWidgetItem]) -> Set[int]:
    out: Set[int] = set()
    pending = list(tops)
    while pending:
        it = pending.pop()
        if id(it) in out:
            continue
        out.add(id(it))
        pending.extend(children.get(id(it), ()))
    return out


def diff(label: str, before: Snapshot, after: Snapshot, current_before=None, current_after=None) -> Change:
    change = Change(label)
    for key in set(before.children) & set(after.children):
        # A node that exists only on one side (added or deleted) travels with
        # its children: only its parent's list needs recording.
        old, new = before.children[key], after.children[key]
        if _ids(old) != _ids(new):
            parent = None if key == ROOT else (before.items.get(key) or after.items.get(key))
            change.parents[key] = (parent, old, new)
    for k in set(before.attrs) & set(after.attrs):
        if before.attrs[k] != after.attrs[k]:
            change.attrs[k] = (after.items[k], before.attrs[k], after.attrs[k])
    moved: List[QTreeWidgetItem] = []
    for parent, old, new in change.parents.values():
        moved.extend(old)
        moved.extend(new)
        if parent is not None:
            moved.append(parent)
    change.expanded = (_subtree(before.children, moved) & before.expanded,
                       _subtree(after.children, moved) & after.expanded)
    change.current = (current_before, current_after)
    return change


def apply(tree, change: Change, undo: bool) -> None:
    """Put the tree in the state before (undo) or after (redo) ``change``.
    The caller blocks the tree's signals and refreshes the window."""
    side = 1 if undo else 2
    root = tree.invisibleRootItem()
    expanded = change.expanded[0 if undo else 1]
    for parent, *_lists in change.parents.values():
        (parent or root).takeChildren()
    for parent, *lists in change.parents.values():
        kids = lists[side - 1]
        for kid in kids:   # anything moved since by a change that was not recorded
            holder = kid.parent() or (root if tree.indexOfTopLevelItem(kid) >= 0 else None)
            if holder is not None:
                holder.takeChild(holder.indexOfChild(kid))
        (parent or root).addChildren(kids)
    for item, *values in change.attrs.values():
        title, body, html, icon, color = values[side - 1]
        item.setText(0, title)
        item.body, item.html = body, html
        if (item.icon, item.color) != (icon, color):
            item.set_look(icon, color)
    # Nodes that were taken out and put back lose their open/closed state.
    pending = [p for p, *_ in change.parents.values() if p is not None]
    pending += [i for _p, *lists in change.parents.values() for i in lists[side - 1]]
    seen: Set[int] = set()
    while pending:
        item = pending.pop()
        if id(item) in seen:
            continue
        seen.add(id(item))
        item.setExpanded(id(item) in expanded)
        pending.extend(item.child(i) for i in range(item.childCount()))


class History:
    def __init__(self):
        self.changes: List[Change] = []
        self.index = 0          # changes[:index] can be undone, changes[index:] redone

    def clear(self) -> None:
        self.changes = []
        self.index = 0

    def push(self, change: Change) -> None:
        if not change:
            return
        del self.changes[self.index:]
        top = self.changes[-1] if self.changes else None
        if (top is not None and change.label == tr("Rename") and top.label == tr("Add Node")
                and top.current[1] is not None and set(change.attrs) <= {id(top.current[1])}
                and not change.parents):
            # Typing the name of a node just added: one step, not two.
            for k, (item, old, new) in change.attrs.items():
                if k in top.attrs:
                    old = top.attrs[k][1]
                top.attrs[k] = (item, old, new)
            return
        self.changes.append(change)
        if len(self.changes) > LIMIT:
            del self.changes[0]
        self.index = len(self.changes)

    def can_undo(self) -> bool:
        return self.index > 0

    def can_redo(self) -> bool:
        return self.index < len(self.changes)

    def undo_label(self) -> str:
        return self.changes[self.index - 1].label if self.can_undo() else ""

    def redo_label(self) -> str:
        return self.changes[self.index].label if self.can_redo() else ""

    def take_undo(self) -> Optional[Change]:
        if not self.can_undo():
            return None
        self.index -= 1
        return self.changes[self.index]

    def take_redo(self) -> Optional[Change]:
        if not self.can_redo():
            return None
        self.index += 1
        return self.changes[self.index - 1]
