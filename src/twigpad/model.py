# SPDX-License-Identifier: GPL-3.0-or-later
"""In-memory data model: a document is an invisible root holding a tree of nodes.

Each node has a single-line title and a plain-text article, as in the
``.hjt`` file format.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator, List, Optional, Tuple


@dataclass(eq=False)
class Node:
    title: str = "New node"
    text: str = ""
    children: List["Node"] = field(default_factory=list)
    parent: Optional["Node"] = field(default=None, repr=False)

    def add_child(self, child: "Node", index: Optional[int] = None) -> "Node":
        child.parent = self
        if index is None:
            self.children.append(child)
        else:
            self.children.insert(index, child)
        return child

    def walk(self, level: int = 0) -> Iterator[Tuple["Node", int]]:
        """Depth-first, pre-order walk of this node and its descendants."""
        yield self, level
        for child in self.children:
            yield from child.walk(level + 1)

    def count(self) -> int:
        return sum(1 for _ in self.walk())


@dataclass(eq=False)
class Document:
    root: Node = field(default_factory=lambda: Node(title=""))
    path: Optional[str] = None
    encoding: str = "cp1252"
    version: str = "2.7"
    warnings: List[str] = field(default_factory=list)

    @property
    def top_nodes(self) -> List[Node]:
        return self.root.children

    def walk(self) -> Iterator[Tuple[Node, int]]:
        """All real nodes with their level (top-level nodes are level 0)."""
        for top in self.root.children:
            yield from top.walk(0)

    def node_count(self) -> int:
        return sum(1 for _ in self.walk())

    def ensure_single_root(self, title: str) -> bool:
        """A .hjt file may have only one top node. If there are several, put
        them under a new top node called ``title``. Returns True if it did."""
        tops = self.root.children
        if len(tops) <= 1:
            return False
        new_root = Node(title)
        self.root.children = []
        self.root.add_child(new_root)
        for node in tops:
            new_root.add_child(node)
        self.warnings.append(
            f"The file had {len(tops)} top-level nodes; they were placed under a new "
            f"top node \"{title}\", because a tree file can have only one top node.")
        return True
