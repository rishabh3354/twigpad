# SPDX-License-Identifier: GPL-3.0-or-later
"""File > Backup & Restore: put your notes files and settings in one .zip,
and bring them back on another computer."""
from __future__ import annotations

import os
import shutil
import tempfile
from typing import List, Optional

from PyQt5.QtCore import QSettings, Qt
from PyQt5.QtWidgets import (
    QAbstractItemView, QCheckBox, QDialog, QDialogButtonBox, QFileDialog, QHeaderView, QLabel,
    QListWidget, QListWidgetItem, QTreeWidget, QTreeWidgetItem, QVBoxLayout,
)

from .. import APP_NAME, __version__, backup
from . import popups

SETTINGS_TEXT = "Settings (theme, fonts, toolbars, spelling words, recent files)"
STATUS_TEXT = {backup.NEW: "Will be restored",
               backup.SAME: "Already there, skipped",
               backup.EXISTS: "A different file is already there, skipped"}


def restore_folder() -> str:
    """Where files go whose old folder can't be used on this computer."""
    docs = os.path.expanduser("~/Documents")
    return os.path.join(docs if os.path.isdir(docs) else os.path.expanduser("~"), f"{APP_NAME} Restored")


def _home_short(path: str) -> str:
    home = os.path.expanduser("~")
    if path == home:
        return "~"
    return "~" + path[len(home):] if path.startswith(home + os.sep) else path


class BackupDialog(QDialog):
    """Choose what goes into the backup."""

    def __init__(self, window, files: List[str]):
        super().__init__(window)
        self.setWindowTitle("Back Up Notes and Settings")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 14)
        lay.setSpacing(10)
        head = QLabel("<b>Make a backup to move to a new computer.</b><br>"
                      "Everything goes into one .zip file. Copy it to the new computer and use "
                      "<i>File → Backup &amp; Restore → Restore from Backup</i> there.")
        head.setWordWrap(True)
        lay.addWidget(head)
        lay.addWidget(QLabel("Notes files:"))
        self.list = QListWidget()
        self.list.setObjectName("backup-files")
        for path in files:
            row = QListWidgetItem(f"{os.path.basename(path)}    —    {_home_short(os.path.dirname(path))}")
            row.setData(Qt.UserRole, path)
            row.setToolTip(path)
            row.setFlags(row.flags() | Qt.ItemIsUserCheckable)
            row.setCheckState(Qt.Checked)
            self.list.addItem(row)
        if not files:
            row = QListWidgetItem("(no notes files saved yet)")
            row.setFlags(Qt.NoItemFlags)
            self.list.addItem(row)
        self.list.setMinimumHeight(150)
        lay.addWidget(self.list)
        self.settings_box = QCheckBox(SETTINGS_TEXT)
        self.settings_box.setChecked(True)
        lay.addWidget(self.settings_box)
        hint = QLabel("Password-protected files stay protected in the backup.")
        hint.setObjectName("hint")
        lay.addWidget(hint)
        buttons = QDialogButtonBox(QDialogButtonBox.Cancel)
        self.ok = buttons.addButton("Back Up...", QDialogButtonBox.AcceptRole)
        self.ok.setObjectName("accent")
        self.ok.setDefault(True)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)
        self.setMinimumWidth(600)

    def chosen_files(self) -> List[str]:
        out = []
        for i in range(self.list.count()):
            row = self.list.item(i)
            if row.data(Qt.UserRole) and row.checkState() == Qt.Checked:
                out.append(row.data(Qt.UserRole))
        return out


class RestoreDialog(QDialog):
    """What a backup holds, where each file goes, and what is already there."""

    def __init__(self, window, zip_path: str, plan: List[backup.PlanItem], has_settings: bool):
        super().__init__(window)
        self.setWindowTitle("Restore from Backup")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(20, 18, 20, 14)
        lay.setSpacing(10)
        new = sum(1 for item in plan if item.status == backup.NEW)
        head = QLabel(f"<b>{os.path.basename(zip_path)}</b><br>"
                      f"{new} of {len(plan)} notes file{'s' if len(plan) != 1 else ''} will be restored. "
                      "Files that are already on this computer are left as they are.")
        head.setWordWrap(True)
        lay.addWidget(head)
        self.table = QTreeWidget()
        self.table.setObjectName("restore-files")
        self.table.setHeaderLabels(["File", "Restore to", "Status"])
        self.table.setRootIsDecorated(False)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        for item in plan:
            row = QTreeWidgetItem([os.path.basename(item.entry.original),
                                   _home_short(os.path.dirname(item.target)), STATUS_TEXT[item.status]])
            row.setToolTip(1, item.target)
            row.setToolTip(0, item.entry.original)
            if item.status != backup.NEW:
                for col in range(3):
                    row.setForeground(col, self.palette().placeholderText())
            self.table.addTopLevelItem(row)
        header = self.table.header()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.setMinimumHeight(160)
        lay.addWidget(self.table)
        self.settings_box = QCheckBox(SETTINGS_TEXT)
        self.settings_box.setChecked(has_settings)
        self.settings_box.setEnabled(has_settings)
        lay.addWidget(self.settings_box)
        buttons = QDialogButtonBox(QDialogButtonBox.Cancel)
        self.ok = buttons.addButton("Restore", QDialogButtonBox.AcceptRole)
        self.ok.setObjectName("accent")
        self.ok.setDefault(True)
        self.ok.setEnabled(bool(new) or has_settings)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        lay.addWidget(buttons)
        self.setMinimumSize(640, 340)


def backup_candidates(window) -> List[str]:
    """The open file and the recent files that still exist, newest first."""
    out: List[str] = []
    for path in ([window.path] if window.path else []) + window.recent_files():
        path = os.path.abspath(path)
        if os.path.isfile(path) and path not in out:
            out.append(path)
    return out


def make_backup(window, zip_path: str, files: List[str], with_settings: bool) -> List[backup.Entry]:
    tmp = tempfile.mkdtemp(prefix="twigpad-backup-")
    try:
        ini = None
        if with_settings:
            window._save_settings()
            ini = os.path.join(tmp, backup.SETTINGS)
            copy = QSettings(ini, QSettings.IniFormat)
            for key in window.settings.allKeys():
                copy.setValue(key, window.settings.value(key))
            copy.sync()
        return backup.create(zip_path, files, ini, __version__)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def run_backup(window, zip_path: Optional[str] = None) -> bool:
    if window.isWindowModified() and window.path:
        answer = popups.show(
            window, popups.QUESTION, "Save before backing up?",
            "The open file has changes that are not saved yet. Save them so the backup has them.",
            (("skip", "Back Up Without Them", popups.NORMAL), ("cancel", "Cancel", popups.CANCEL),
             ("save", "Save", popups.PRIMARY)), "save")
        if answer == "cancel" or answer is None or (answer == "save" and not window.save()):
            return False
    dlg = BackupDialog(window, backup_candidates(window))
    if zip_path is None:
        if dlg.exec_() != QDialog.Accepted:
            return False
        start = os.path.join(os.path.expanduser("~"), backup.default_name())
        zip_path, _ = QFileDialog.getSaveFileName(window, "Save Backup As", start, "Backup (*.zip)")
        if not zip_path:
            return False
        if not zip_path.lower().endswith(".zip"):
            zip_path += ".zip"
    files, with_settings = dlg.chosen_files(), dlg.settings_box.isChecked()
    try:
        saved = make_backup(window, zip_path, files, with_settings)
    except OSError as exc:
        popups.error(window, "Could not make the backup", f"\"{zip_path}\" could not be written.",
                     details=str(exc))
        return False
    what = f"{len(saved)} notes file{'s' if len(saved) != 1 else ''}" + (" and your settings" if with_settings else "")
    popups.success(window, "Backup saved",
                   f"{what} are in \"{zip_path}\". Copy this file to your new computer and restore it "
                   f"there with File → Backup & Restore → Restore from Backup.")
    window.statusBar().showMessage(f"Backup saved to {zip_path}", 8000)
    return True


def apply_settings(window, ini: str, fix_path) -> None:
    """Copy the backup's settings in, with old paths changed to this computer's."""
    src = QSettings(ini, QSettings.IniFormat)
    for key in src.allKeys():
        value = src.value(key)
        if isinstance(value, str) and os.sep in value:
            value = fix_path(value)
        elif isinstance(value, list):
            value = [fix_path(v) if isinstance(v, str) and os.sep in v else v for v in value]
        window.settings.setValue(key, value)
    window.settings.sync()
    window.reload_settings()


def run_restore(window, zip_path: Optional[str] = None, confirm: bool = True) -> Optional[List[backup.PlanItem]]:
    if zip_path is None:
        zip_path, _ = QFileDialog.getOpenFileName(window, "Restore from Backup", os.path.expanduser("~"),
                                                  "Twigpad backup (*.zip)")
        if not zip_path:
            return None
    try:
        manifest = backup.read_manifest(zip_path)
        plan = backup.plan(zip_path, restore_folder())
    except backup.BackupError as exc:
        popups.error(window, "This is not a Twigpad backup", str(exc))
        return None
    has_settings = bool(manifest.get("settings"))
    with_settings = has_settings
    if confirm:
        dlg = RestoreDialog(window, zip_path, plan, has_settings)
        if dlg.exec_() != QDialog.Accepted:
            return None
        with_settings = has_settings and dlg.settings_box.isChecked()
    errors = backup.restore_files(zip_path, plan)
    if with_settings:
        tmp = tempfile.mkdtemp(prefix="twigpad-restore-")
        try:
            ini = backup.extract_settings(zip_path, tmp)
            if ini:
                apply_settings(window, ini, backup.path_mapper(plan, manifest.get("home", ""),
                                                               os.path.expanduser("~")))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    restored = [item for item in plan if item.status == backup.NEW and os.path.exists(item.target)]
    skipped = len(plan) - len(restored) - len(errors)
    lines = [f"{len(restored)} notes file{'s' if len(restored) != 1 else ''} restored."]
    if skipped:
        lines.append(f"{skipped} {'were' if skipped != 1 else 'was'} already on this computer and left as "
                     f"{'they were' if skipped != 1 else 'it was'}.")
    if with_settings:
        lines.append("Your settings were restored.")
    if errors:
        popups.warning(window, "Some files could not be restored", " ".join(lines), details="\n".join(errors))
    else:
        popups.success(window, "Restore finished", " ".join(lines))
    return plan
