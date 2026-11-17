# SPDX-License-Identifier: GPL-3.0-or-later
"""The article editor. Plain notes are edited as plain text; formatted notes
(.twig files only) as rich text with images kept in a shared image store."""
from __future__ import annotations

import hashlib
from typing import Dict, Optional

from PyQt5.QtCore import QBuffer, QByteArray, QIODevice, Qt, QUrl, pyqtSignal
from PyQt5.QtGui import QFont, QImage, QTextBlockFormat, QTextCharFormat, QTextDocument, QTextImageFormat
from PyQt5.QtWidgets import QTextEdit

from ..twig import IMAGE_SCHEME

MAX_IMAGE_WIDTH = 640   # wider pictures are shown smaller (the file keeps the original)


def image_ext(data: bytes) -> str:
    if data.startswith(b"\x89PNG"):
        return "png"
    if data.startswith(b"\xff\xd8"):
        return "jpg"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    if data[:2] == b"BM":
        return "bmp"
    return "png"


HEADING_EXTRA = {0: 0, 1: 8, 2: 5, 3: 2}   # points added to the normal size


def heading_format(level: int, base_size: float) -> QTextCharFormat:
    fmt = QTextCharFormat()
    fmt.setFontPointSize(base_size + HEADING_EXTRA[level])
    fmt.setFontWeight(QFont.Bold if level else QFont.Normal)
    return fmt


def image_to_png(image: QImage) -> bytes:
    buf = QBuffer()
    buf.open(QIODevice.WriteOnly)
    image.save(buf, "PNG")
    return bytes(buf.data())


class ArticleEdit(QTextEdit):
    """``rich`` decides whether pasted formatting is kept. ``needRich`` asks
    the window to turn the note into a formatted note (an image was pasted
    into a plain note)."""

    needRich = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.images: Dict[str, bytes] = {}
        self.rich = False
        self.setAcceptRichText(False)

    def set_rich(self, on: bool) -> None:
        self.rich = on
        self.setAcceptRichText(on)

    # ------------------------------------------------------------ images

    def loadResource(self, kind: int, url: QUrl):
        if url.scheme() == IMAGE_SCHEME:
            data = self.images.get(url.path())
            image = QImage()
            if data:
                image.loadFromData(QByteArray(data))
            return image
        return super().loadResource(kind, url)

    def add_image(self, data: bytes) -> str:
        """Put image file data in the store; returns its name."""
        name = f"{hashlib.sha1(data).hexdigest()[:16]}.{image_ext(data)}"
        self.images.setdefault(name, data)
        return name

    def insert_image(self, data: bytes) -> bool:
        image = QImage()
        if not image.loadFromData(QByteArray(data)):
            return False
        if not self.rich:
            self.needRich.emit()
        name = self.add_image(data)
        url = QUrl(f"{IMAGE_SCHEME}:{name}")
        self.document().addResource(QTextDocument.ImageResource, url, image)
        fmt = QTextImageFormat()
        fmt.setName(url.toString())
        if image.width() > MAX_IMAGE_WIDTH:
            fmt.setWidth(MAX_IMAGE_WIDTH)
            fmt.setHeight(image.height() * MAX_IMAGE_WIDTH / image.width())
        cursor = self.textCursor()
        cursor.insertImage(fmt)
        self.setTextCursor(cursor)
        return True

    def image_at_cursor(self) -> Optional[str]:
        fmt = self.textCursor().charFormat()
        if fmt.isImageFormat():
            return fmt.toImageFormat().name()
        return None

    def keyPressEvent(self, event) -> None:
        cursor = self.textCursor()
        heading = (self.rich and event.key() in (Qt.Key_Return, Qt.Key_Enter)
                   and cursor.blockFormat().headingLevel() > 0 and cursor.atBlockEnd())
        super().keyPressEvent(event)
        if heading:
            # Like a word processor: the paragraph after a heading is normal text.
            cursor = self.textCursor()
            block_fmt = QTextBlockFormat()
            block_fmt.setHeadingLevel(0)
            cursor.mergeBlockFormat(block_fmt)
            size = self.font().pointSizeF()
            fmt = heading_format(0, size if size > 0 else 10.0)
            cursor.setBlockCharFormat(fmt)
            self.setCurrentCharFormat(fmt)

    # ------------------------------------------------------------ paste

    def canInsertFromMimeData(self, source) -> bool:
        return source.hasImage() or super().canInsertFromMimeData(source)

    def insertFromMimeData(self, source) -> None:
        # A picture on its own (a screenshot, an image copied in a viewer).
        # Spreadsheets also offer a picture next to their text: keep the text.
        if source.hasImage() and not source.hasText():
            image = source.imageData()
            if isinstance(image, QImage) and not image.isNull():
                self.insert_image(image_to_png(image))
                return
        super().insertFromMimeData(source)
