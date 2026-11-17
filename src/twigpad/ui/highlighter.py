# SPDX-License-Identifier: GPL-3.0-or-later
"""Shows links in article text in the link color, underlined."""
from __future__ import annotations

from PyQt5.QtGui import QPalette, QSyntaxHighlighter, QTextCharFormat
from PyQt5.QtWidgets import QApplication

from .. import links, search


class LinkHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        self.fmt = QTextCharFormat()
        self.fmt.setForeground(QApplication.palette().color(QPalette.Link))
        self.fmt.setFontUnderline(True)

    def highlightBlock(self, text: str) -> None:
        for start, end, _link in links.iter_links(text):
            qs, qe = search.to_qt(text, start), search.to_qt(text, end)
            self.setFormat(qs, qe - qs, self.fmt)
