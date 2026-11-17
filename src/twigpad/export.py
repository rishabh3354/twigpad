# SPDX-License-Identifier: GPL-3.0-or-later
"""Turn nodes into plain text (for export and the clipboard) or HTML (for printing)."""
from __future__ import annotations

import base64
import html
import re
from typing import Dict, List, Optional, Sequence

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
        text = node.text.replace("\ufffc", "")   # picture placeholders
        if text.strip():
            parts.append(text.rstrip("\n"))
        parts.append("")
    return "\n".join(parts).rstrip("\n") + "\n"


_BODY = re.compile(r"<body[^>]*>(.*)</body>", re.S | re.I)
_IMG_SRC = re.compile(r"""(src=["'])twigimg:([A-Za-z0-9._-]+)(["'])""")
# Formatted notes come from the editor, but a file could be made by hand:
# exported pages must not run scripts from it.
_UNSAFE = re.compile(r"<(script|iframe|object|embed|style)\b.*?(</\1\s*>|$)|\son\w+\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)",
                     re.S | re.I)
_MIME = {"png": "image/png", "jpg": "image/jpeg", "gif": "image/gif", "webp": "image/webp", "bmp": "image/bmp"}


def rich_fragment(note_html: str, images: Optional[Dict[str, bytes]] = None) -> str:
    """The body of a formatted note, with its pictures embedded as data: URLs
    when ``images`` is given (for web pages), else left as twigimg: links."""
    m = _BODY.search(note_html)
    body = _UNSAFE.sub("", m.group(1) if m else note_html)
    if images is None:
        return body

    def embed(mm):
        data = images.get(mm.group(2))
        if data is None:
            return mm.group(0)
        mime = _MIME.get(mm.group(2).rsplit(".", 1)[-1].lower(), "image/png")
        return f"{mm.group(1)}data:{mime};base64,{base64.b64encode(data).decode('ascii')}{mm.group(3)}"
    return _IMG_SRC.sub(embed, body)


def _article(node: Node, images: Optional[Dict[str, bytes]]) -> str:
    if node.html:
        return f"<div class='note'>{rich_fragment(node.html, images)}</div>"
    if node.text:
        return f"<pre>{html.escape(node.text.rstrip())}</pre>"
    return ""


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
        out.append(_article(node, None))   # printing loads twigimg: pictures itself
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
.note{margin:.3em 0 1.2em 0}
.note img{max-width:100%;height:auto}
.note table{border-collapse:collapse}
.note td,.note th{border:1px solid #999;padding:4px}
""".strip()


def html_page(nodes: Sequence[Node], doc_title: str = "", images: Optional[Dict[str, bytes]] = None) -> str:
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
        style = f" style='color:{node.color}'" if re.fullmatch(r"#[0-9a-fA-F]{6}", node.color) else ""
        out.append(f"<h{h} id='{ids[id(node)]}'{style}>{html.escape(node.title)}</h{h}>\n")
        article = _article(node, images or {})
        if article:
            out.append(article + "\n")
    out.append("</body></html>\n")
    return "".join(out)
