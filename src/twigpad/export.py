# SPDX-License-Identifier: GPL-3.0-or-later
"""Turn nodes into plain text (for export and the clipboard) or HTML (for printing)."""
from __future__ import annotations

import html
from typing import List, Sequence

from .model import Node


def _numbered(nodes: Sequence[Node], prefix: str = ""):
    for i, node in enumerate(nodes, 1):
        number = f"{prefix}{i}."
        yield node, number, prefix.count(".")
        yield from _numbered(node.children, number)


def outline_text(nodes: Sequence[Node], numbered: bool = True) -> str:
    """Readable outline: a numbered, underlined heading per node, then its text."""
    parts: List[str] = []
    for node, number, depth in _numbered(nodes):
        heading = f"{number} {node.title}" if numbered else node.title
        parts.append(heading)
        parts.append(("=" if depth == 0 else "-") * len(heading))
        if node.text:
            parts.append(node.text.rstrip("\n"))
        parts.append("")
    return "\n".join(parts).rstrip("\n") + "\n"


def outline_html(nodes: Sequence[Node], doc_title: str = "") -> str:
    """HTML for printing: headings sized by depth, articles kept as typed."""
    out = ["<html><head><meta charset='utf-8'>"]
    out.append("<style>pre{white-space:pre-wrap;font-family:inherit;margin:0 0 1em 0}"
               "h1,h2,h3,h4,h5,h6{margin:0.8em 0 0.3em 0}</style></head><body>")
    if doc_title:
        out.append(f"<p><small>{html.escape(doc_title)}</small></p>")
    for node, number, depth in _numbered(nodes):
        h = min(depth + 1, 6)
        out.append(f"<h{h}>{html.escape(node.title)}</h{h}>")
        if node.text:
            out.append(f"<pre>{html.escape(node.text)}</pre>")
    out.append("</body></html>")
    return "".join(out)
