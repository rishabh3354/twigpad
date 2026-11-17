# SPDX-License-Identifier: GPL-3.0-or-later
"""Format-menu text clean-ups (no Qt dependency)."""
from __future__ import annotations

import re

_QUOTE_PREFIX = re.compile(r"^[ \t]*(?:>[ \t]*)*")


def to_upper(text: str) -> str:
    return text.upper()


def to_lower(text: str) -> str:
    return text.lower()


def remove_leading_spaces(text: str) -> str:
    """Strip spaces and tabs at the start of every line."""
    return "\n".join(line.lstrip(" \t") for line in text.split("\n"))


def remove_leading_spaces_and_returns(text: str) -> str:
    """Clean up quoted or hard-wrapped text such as pasted email.

    Removes leading spaces, tabs and '>' quote markers from every line, then
    joins the lines of each paragraph into one line. Blank lines still
    separate paragraphs.
    """
    paragraphs, current = [], []
    for line in text.split("\n"):
        cleaned = _QUOTE_PREFIX.sub("", line).rstrip()
        if cleaned:
            current.append(cleaned)
        else:
            if current:
                paragraphs.append(" ".join(current))
                current = []
            paragraphs.append("")
    if current:
        paragraphs.append(" ".join(current))
    # Collapse runs of blank lines into one paragraph break.
    out = []
    for p in paragraphs:
        if p == "" and (not out or out[-1] == ""):
            continue
        out.append(p)
    while out and out[-1] == "":
        out.pop()
    return "\n\n".join(p for p in out if p)
