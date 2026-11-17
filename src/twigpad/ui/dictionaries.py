# SPDX-License-Identifier: GPL-3.0-or-later
"""Options > Spelling Language > Download Languages: install spell-checking
dictionaries for popular languages with one click."""
from __future__ import annotations

from typing import Optional

from PyQt5.QtCore import QThread, Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QAbstractItemView, QDialog, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QProgressBar,
    QPushButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout,
)

from .. import spell
from . import popups

INSTALLED, NOT_INSTALLED = "Installed", "Not installed"


class DownloadThread(QThread):
    progress = pyqtSignal(int)        # 0-100, or -1 when the size is unknown
    finished_ok = pyqtSignal(str)     # the .dic path
    failed = pyqtSignal(str)

    def __init__(self, lang: spell.Language, parent=None):
        super().__init__(parent)
        self.lang = lang

    def run(self) -> None:
        try:
            path = spell.install_dictionary(
                self.lang, lambda part, pct: self.progress.emit(-1 if pct < 0 else part * 50 + pct // 2))
        except Exception as exc:   # network errors come in many types
            self.failed.emit(str(exc))
        else:
            self.finished_ok.emit(path)


class DictionaryDialog(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.win = window
        self.thread: Optional[DownloadThread] = None
        self.setWindowTitle("Spelling Languages")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 14)
        lay.setSpacing(10)
        head = QLabel("<b>Download a dictionary to check spelling in another language.</b><br>"
                      "Dictionaries are free and come from the LibreOffice and Mozilla projects.")
        head.setWordWrap(True)
        lay.addWidget(head)
        if not spell.library_available():
            warn = QLabel("Spell checking also needs the Hunspell library. Install the "
                          "<b>hunspell</b> package (for example <i>sudo apt install libhunspell-1.7-0</i>), "
                          "then restart Twigpad.")
            warn.setWordWrap(True)
            warn.setObjectName("hint")
            lay.addWidget(warn)
        self.filter = QLineEdit()
        self.filter.setPlaceholderText("Search languages")
        self.filter.setClearButtonEnabled(True)
        self.filter.textChanged.connect(self._apply_filter)
        lay.addWidget(self.filter)
        self.table = QTreeWidget()
        self.table.setObjectName("languages")
        self.table.setHeaderLabels(["Language", "Code", "Status"])
        self.table.setRootIsDecorated(False)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.itemSelectionChanged.connect(self._update_buttons)
        self.table.itemDoubleClicked.connect(lambda *_: self.download())
        header = self.table.header()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.setMinimumHeight(200)
        lay.addWidget(self.table)
        self.status = QLabel("")
        self.status.setObjectName("hint")
        self.bar = QProgressBar()
        self.bar.setVisible(False)
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(6)
        lay.addWidget(self.bar)
        lay.addWidget(self.status)
        row = QHBoxLayout()
        self.remove_btn = QPushButton("Remove")
        self.remove_btn.clicked.connect(self.remove)
        row.addWidget(self.remove_btn)
        row.addStretch(1)
        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.reject)
        self.download_btn = QPushButton("Download")
        self.download_btn.setObjectName("accent")
        self.download_btn.setDefault(True)
        self.download_btn.clicked.connect(self.download)
        row.addWidget(self.close_btn)
        row.addWidget(self.download_btn)
        lay.addLayout(row)
        self.setMinimumWidth(520)
        self.resize(540, 560)
        self.fill()

    def fill(self) -> None:
        installed = spell.available_languages()
        current = self.selected()
        self.table.clear()
        known = {lang.code for lang in spell.DOWNLOADS}
        rows = [(lang.name, lang.code, lang) for lang in spell.DOWNLOADS]
        rows += [(spell.language_name(code), code, None) for code in installed if code not in known]
        for name, code, lang in sorted(rows, key=lambda r: (r[1] not in installed, r[0].casefold())):
            row = QTreeWidgetItem([name, code, INSTALLED if code in installed else NOT_INSTALLED])
            row.setData(0, Qt.UserRole, code)
            row.setData(1, Qt.UserRole, lang)
            if code == self.win.settings.value("spell/language", "", type=str):
                row.setText(2, INSTALLED + " (in use)")
            self.table.addTopLevelItem(row)
            if current and code == current:
                self.table.setCurrentItem(row)
        self._apply_filter(self.filter.text())
        self._update_buttons()

    def selected(self) -> Optional[str]:
        row = self.table.currentItem()
        return row.data(0, Qt.UserRole) if row else None

    def select(self, code: str) -> None:
        for i in range(self.table.topLevelItemCount()):
            row = self.table.topLevelItem(i)
            if row.data(0, Qt.UserRole) == code:
                self.table.setCurrentItem(row)
                return

    def _apply_filter(self, text: str) -> None:
        text = text.strip().casefold()
        for i in range(self.table.topLevelItemCount()):
            row = self.table.topLevelItem(i)
            row.setHidden(bool(text) and text not in (row.text(0) + " " + row.text(1)).casefold())

    def _update_buttons(self) -> None:
        row = self.table.currentItem()
        busy = self.thread is not None
        code = row.data(0, Qt.UserRole) if row else None
        installed = bool(row) and row.text(2).startswith(INSTALLED)
        self.download_btn.setText("Use" if installed else "Download")
        self.download_btn.setEnabled(bool(row) and not busy and (installed or row.data(1, Qt.UserRole) is not None))
        self.remove_btn.setEnabled(bool(code) and not busy and spell.user_installed(code))
        self.table.setEnabled(not busy)

    def download(self) -> None:
        row = self.table.currentItem()
        if row is None or self.thread is not None:
            return
        code = row.data(0, Qt.UserRole)
        if row.text(2).startswith(INSTALLED):
            self._use(code)
            return
        lang = row.data(1, Qt.UserRole)
        self.thread = DownloadThread(lang, self)
        self.thread.progress.connect(self._progress)
        self.thread.finished_ok.connect(self._done)
        self.thread.failed.connect(self._failed)
        self.bar.setVisible(True)
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        self.status.setText(f"Downloading {lang.name}...")
        self._update_buttons()
        self.thread.start()

    def _progress(self, pct: int) -> None:
        if pct < 0:
            self.bar.setRange(0, 0)
        else:
            self.bar.setRange(0, 100)
            self.bar.setValue(pct)

    def _finish_thread(self) -> None:
        if self.thread is not None:
            self.thread.wait()
            self.thread.deleteLater()
        self.thread = None
        self.bar.setVisible(False)

    def _done(self, path: str) -> None:
        lang = self.thread.lang
        self._finish_thread()
        self.status.setText(f"{lang.name} is installed and in use.")
        self._use(lang.code)

    def _failed(self, message: str) -> None:
        lang = self.thread.lang
        self._finish_thread()
        self.status.setText("")
        self._update_buttons()
        popups.error(self, f"Could not download {lang.name}",
                     "Check your internet connection and try again.", details=message)

    def _use(self, code: str) -> None:
        self.win.refresh_spell_languages(select=code)
        self.fill()
        self.select(code)
        if not self.status.text():
            self.status.setText(f"{spell.language_name(code)} is now used for spell checking.")

    def remove(self) -> None:
        code = self.selected()
        if not code or not spell.user_installed(code):
            return
        if not popups.confirm(self, f"Remove {spell.language_name(code)}?",
                              "The dictionary will be deleted. You can download it again at any time.",
                              ok="Remove", danger=True, default_ok=False):
            return
        spell.remove_dictionary(code)
        self.win.refresh_spell_languages()
        self.status.setText(f"{spell.language_name(code)} was removed.")
        self.fill()

    def reject(self) -> None:
        if self.thread is not None:
            self.thread.wait(30000)
            self._finish_thread()
        super().reject()
