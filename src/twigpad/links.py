# SPDX-License-Identifier: GPL-3.0-or-later
"""Hyperlinks inside article text (no Qt dependency).

Links follow the conventions of the .hjt format:

    [http://example.com]   [www.example.com]   [mailto:me@example.com]
    [ftp://host/path]      [file:///home/me/doc.pdf]
    [node://Root title/Child/Grandchild]       (another node in the file)

Brackets are optional when the link has no spaces; double quotes can be used
instead of brackets. A ``node://`` link is the path of node titles from the
top node down, separated by slashes.
"""
from __future__ import annotations

import re
from typing import Callable, Iterable, Optional, Sequence, Tuple, TypeVar

T = TypeVar("T")

_SCHEMES = r"(?:https?://|ftp://|file://|node://|mailto:|news:|www\.)"
LINK_RE = re.compile(
    rf"\[{_SCHEMES}[^\]\n]*\]"            # [link, spaces allowed]
    rf'|"{_SCHEMES}[^"\n]*"'              # "link, spaces allowed"
    rf"|{_SCHEMES}[^\s\[\]\"<>]+",        # bare link, no spaces
    re.IGNORECASE,
)
_STARTS_LIKE_LINK = re.compile(_SCHEMES, re.IGNORECASE)
_TRAILING_PUNCT = ".,;:!?)'"

NODE, WEB, MAIL, FILE, OTHER = "node", "web", "mail", "file", "other"


def _clean(raw: str) -> str:
    if len(raw) >= 2 and ((raw[0] == "[" and raw[-1] == "]") or (raw[0] == raw[-1] == '"')):
        return raw[1:-1].strip()
    return raw.rstrip(_TRAILING_PUNCT)


def iter_links(text: str):
    """Yield ``(start, end, link)`` for each link in ``text``."""
    for m in LINK_RE.finditer(text):
        yield m.start(), m.end(), _clean(m.group(0))


def link_at(text: str, pos: int, selection: str = "") -> Optional[str]:
    """The link under ``pos`` (a Python index into ``text``), or the selected
    text when it is a link (needed for unbracketed links with spaces)."""
    sel = _clean(selection.strip())
    if sel and _STARTS_LIKE_LINK.match(sel):
        return sel
    for start, end, link in iter_links(text):
        if start <= pos <= end:
            return link
        if start > pos:
            break
    return None


def classify(link: str) -> Tuple[str, str]:
    """Return ``(kind, target)``: the kind of link and what it points to.

    For NODE the target is the title path; for FILE a local path; for WEB a
    full URL (``www.`` gets ``http://``); otherwise the link itself."""
    low = link.lower()
    if low.startswith("node://"):
        return NODE, link[7:].strip("/")
    if low.startswith("file://"):
        path = link[7:]
        # file:///home/x and file://localhost/home/x are both absolute paths.
        if path.lower().startswith("localhost/"):
            path = path[9:]
        return FILE, path
    if low.startswith("www."):
        return WEB, "http://" + link
    if low.startswith(("http://", "https://", "ftp://")):
        return WEB, link
    if low.startswith("mailto:"):
        return MAIL, link
    return OTHER, link


def node_address(titles: Sequence[str]) -> str:
    """The ``node://`` link for a node, given titles from the top node down."""
    return "node://" + "/".join(titles)


def resolve_node(roots: Iterable[T], path: str, title_of: Callable[[T], str],
                 children_of: Callable[[T], Iterable[T]]) -> Optional[T]:
    """Find the node a ``node://`` path points to. Titles match without regard
    to case, and a title that itself contains '/' is still found."""
    segments = [s for s in path.split("/")]
    while segments and segments[-1] == "":
        segments.pop()
    if not segments:
        return None

    def walk(candidates, segs):
        for c in candidates:
            title = title_of(c).strip()
            n = title.count("/") + 1
            if len(segs) >= n and "/".join(segs[:n]).strip().casefold() == title.casefold():
                if len(segs) == n:
                    return c
                found = walk(children_of(c), segs[n:])
                if found is not None:
                    return found
        return None

    return walk(roots, segments)
