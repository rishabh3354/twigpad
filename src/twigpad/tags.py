# SPDX-License-Identifier: GPL-3.0-or-later
"""#tags written in node titles and articles (no Qt dependency).

A tag is '#' followed by a letter, then letters, digits, '_' or '-'
(#work, #to-do, #2026 is not a tag). Tags are matched without regard to case.
The '#' must not follow a letter, digit, '#', '/' or '&', so web addresses
with '#section' and '&#38;' are not tags.
"""
from __future__ import annotations

import re
from typing import Dict, Iterable, List, Tuple

TAG_RE = re.compile(r"(?<![\w#/&])#([^\W\d_][\w-]*)")


def iter_tags(text: str):
    """Yield (start, end, tag) for every tag; the tag excludes the '#'."""
    for m in TAG_RE.finditer(text):
        tag = m.group(1).rstrip("-")
        yield m.start(), m.start() + 1 + len(tag), tag


def tags_in(text: str) -> List[str]:
    return [t for _s, _e, t in iter_tags(text)]


def collect(entries: Iterable[Tuple[object, str]]) -> Dict[str, Tuple[str, list]]:
    """Group notes by tag. ``entries`` gives (note, text). Returns
    casefolded tag -> (display name, [notes in order, each once])."""
    out: Dict[str, Tuple[str, list]] = {}
    for note, text in entries:
        for tag in tags_in(text):
            key = tag.casefold()
            _name, notes = out.setdefault(key, (tag, []))
            if not any(n is note for n in notes):
                notes.append(note)
    return out
