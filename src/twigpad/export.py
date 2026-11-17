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


_PAGE_CSS = """
body{font-family:system-ui,-apple-system,"Segoe UI",sans-serif;max-width:52em;margin:2em auto;padding:0 1em;line-height:1.5;color:#222}
nav{border:1px solid #ddd;padding:.6em 1.2em;margin-bottom:2em;background:#fafafa}
nav ul{list-style:none;padding-left:1.1em;margin:.2em 0}
nav>ul{padding-left:0}
a{color:#0645ad}
pre{white-space:pre-wrap;font-family:inherit;margin:.3em 0 1.2em 0}
h1,h2,h3,h4,h5,h6{margin:1.2em 0 .3em 0}
""".strip()


def html_page(nodes: Sequence[Node], doc_title: str = "") -> str:
    """A standalone web page: a linked table of contents, then every node as
    a heading (sized by depth) followed by its article."""
    title = doc_title or (nodes[0].title if nodes else "Notes")
    numbered = list(_numbered(nodes))
    ids = {id(node): f"n{i}" for i, (node, _, _) in enumerate(numbered, 1)}

    def toc(level_nodes) -> str:
        items = "".join(
            f"<li><a href='#{ids[id(n)]}'>{html.escape(n.title)}</a>"
            f"{toc(n.children) if n.children else ''}</li>"
            for n in level_nodes)
        return f"<ul>{items}</ul>"

    out = ["<!DOCTYPE html>\n<html><head><meta charset='utf-8'>",
           "<meta name='viewport' content='width=device-width, initial-scale=1'>",
           f"<title>{html.escape(title)}</title>",
           f"<style>{_PAGE_CSS}</style></head><body>\n"]
    if len(numbered) > 1:
        out.append(f"<nav>{toc(nodes)}</nav>\n")
    for node, number, depth in numbered:
        h = min(depth + 1, 6)
        out.append(f"<h{h} id='{ids[id(node)]}'>{html.escape(node.title)}</h{h}>\n")
        if node.text:
            out.append(f"<pre>{html.escape(node.text.rstrip())}</pre>\n")
    out.append("</body></html>\n")
    return "".join(out)
