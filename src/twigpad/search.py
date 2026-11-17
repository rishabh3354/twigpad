# SPDX-License-Identifier: GPL-3.0-or-later
"""Search across node titles and articles (no Qt dependency).

Items are any objects with ``title`` and ``body`` string attributes. Match
positions are Python string indices; use :func:`to_qt` / :func:`from_qt` to
convert to and from Qt text positions (which count UTF-16 units).
"""
from __future__ import annotations

import re

from .i18n import tr
from dataclasses import dataclass
from typing import Iterator, Optional, Sequence, Tuple

TITLE, TEXT = 0, 1


@dataclass
class Match:
    index: int       # position of the item in the searched list
    item: object
    field: int       # TITLE or TEXT
    start: int
    end: int

    @property
    def key(self) -> Tuple[int, int, int]:
        return (self.index, self.field, self.start)


def compile_pattern(query: str, match_case: bool = False, whole_word: bool = False,
                    regex: bool = False) -> "re.Pattern[str]":
    """Raises ``ValueError`` for an empty query and ``re.error`` for a bad regex."""
    if not query:
        raise ValueError(tr("Nothing to search for."))
    body = query if regex else re.escape(query)
    if whole_word:
        body = rf"(?<!\w)(?:{body})(?!\w)"
    flags = re.MULTILINE | (0 if match_case else re.IGNORECASE)
    return re.compile(body, flags)


def iter_matches(items: Sequence, pattern, titles: bool = True, text: bool = True) -> Iterator[Match]:
    for i, item in enumerate(items):
        if titles:
            for m in pattern.finditer(item.title):
                if m.end() > m.start():
                    yield Match(i, item, TITLE, m.start(), m.end())
        if text:
            for m in pattern.finditer(item.body):
                if m.end() > m.start():
                    yield Match(i, item, TEXT, m.start(), m.end())


def find_next(items: Sequence, pattern, anchor: Tuple[int, int, int], titles: bool = True,
              text: bool = True, backward: bool = False) -> Tuple[Optional[Match], bool]:
    """Find the match after ``anchor`` (or before it when ``backward``).

    Forward returns the first match whose key is >= anchor; backward returns
    the last match whose key is < anchor. Wraps around the list; the second
    value tells whether it wrapped.
    """
    matches = list(iter_matches(items, pattern, titles, text))
    if not matches:
        return None, False
    if backward:
        before = [m for m in matches if m.key < anchor]
        return (before[-1], False) if before else (matches[-1], True)
    for m in matches:
        if m.key >= anchor:
            return m, False
    return matches[0], True


def replace_in(s: str, pattern, replacement: str, regex: bool = False, count: int = 0) -> Tuple[str, int]:
    """Replace matches; ``replacement`` may use \\1 etc. only when ``regex``."""
    if regex:
        return pattern.subn(replacement, s, count=count)
    return pattern.subn(lambda _m: replacement, s, count=count)


def snippet(s: str, start: int, end: int, width: int = 70) -> str:
    """One-line context around a match."""
    line_start = s.rfind("\n", 0, start) + 1
    line_end = s.find("\n", end)
    if line_end == -1:
        line_end = len(s)
    left = max(line_start, start - width // 2)
    right = min(line_end, max(end, left + width))
    text = s[left:right].replace("\t", " ").strip()
    if left > line_start:
        text = "…" + text
    if right < line_end:
        text += "…"
    return text


def to_qt(s: str, index: int) -> int:
    """Python string index -> Qt (UTF-16) position."""
    return len(s[:index].encode("utf-16-le")) // 2


def from_qt(s: str, pos: int) -> int:
    """Qt (UTF-16) position -> Python string index."""
    if s.isascii():
        return min(pos, len(s))
    units = 0
    for i, ch in enumerate(s):
        if units >= pos:
            return i
        units += 2 if ord(ch) > 0xFFFF else 1
    return len(s)

