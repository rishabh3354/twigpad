# SPDX-License-Identifier: GPL-3.0-or-later
"""Article highlighting: links (link color, underlined), #tags, and
misspelled words (red wavy underline) when spell checking is on."""
from __future__ import annotations

from typing import Optional

from PyQt5.QtGui import QColor, QPalette, QSyntaxHighlighter, QTextCharFormat
from PyQt5.QtWidgets import QApplication

from .. import links, search, spell, tags


class ArticleHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        self.fmt = QTextCharFormat()
        self.fmt.setForeground(QApplication.palette().color(QPalette.Link))
        self.fmt.setFontUnderline(True)
        self.tag_fmt = QTextCharFormat()
        self.tag_fmt.setForeground(QColor("#2a8a63"))
        self.spell_fmt = QTextCharFormat()
        self.spell_fmt.setUnderlineStyle(QTextCharFormat.SpellCheckUnderline)
        self.spell_fmt.setUnderlineColor(QColor("#d02020"))
        self.speller: Optional[spell.Speller] = None

    def set_speller(self, speller: Optional[spell.Speller]) -> None:
        self.speller = speller
        self.rehighlight()

    def _set(self, text: str, start: int, end: int, fmt) -> None:
        qs = search.to_qt(text, start)
        self.setFormat(qs, search.to_qt(text, end) - qs, fmt)

    def highlightBlock(self, text: str) -> None:
        skip = []
        for start, end, _link in links.iter_links(text):
            self._set(text, start, end, self.fmt)
            skip.append((start, end))
        for start, end, _tag in tags.iter_tags(text):
            self._set(text, start, end, self.tag_fmt)
            skip.append((start, end))
        if self.speller is not None:
            for start, end in spell.misspelled(text, self.speller, skip):
                self._set(text, start, end, self.spell_fmt)


LinkHighlighter = ArticleHighlighter
