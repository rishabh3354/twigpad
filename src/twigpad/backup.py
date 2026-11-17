# SPDX-License-Identifier: GPL-3.0-or-later
"""Backup and restore, for moving to a new computer.

A backup is a .zip file holding the notes files, Twigpad's settings and a
manifest that remembers where each file was. Restoring puts every file back
in the same place under the new home folder (or in a chosen folder when that
place can't be used) and leaves files that are already there alone.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import tempfile
import zipfile

from .i18n import tr
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Optional

FORMAT = "twigpad-backup"
VERSION = 1
MANIFEST = "manifest.json"
SETTINGS = "settings.ini"
NOTES = "notes/"

# What a file in a restore plan will do.
NEW, SAME, EXISTS = "new", "same", "exists"


class BackupError(Exception):
    """Not a Twigpad backup, or a damaged one."""


@dataclass
class Entry:
    original: str     # where the file was on the old computer
    member: str       # its name inside the zip
    size: int
    sha256: str


@dataclass
class PlanItem:
    entry: Entry
    target: str       # where it goes on this computer
    status: str       # NEW, SAME (an identical file is there) or EXISTS (a different file is there)


def default_name(today: Optional[datetime.date] = None) -> str:
    return f"Twigpad-backup-{(today or datetime.date.today()).isoformat()}.zip"


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def create(zip_path: str, files: Iterable[str], settings_ini: Optional[str] = None,
           app_version: str = "", home: Optional[str] = None) -> List[Entry]:
    """Write a backup of ``files`` (and the settings file, if given)."""
    home = home or os.path.expanduser("~")
    entries: List[Entry] = []
    seen = set()
    tmp = zip_path + ".part"
    try:
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zf:
            for path in files:
                path = os.path.abspath(path)
                if path in seen or not os.path.isfile(path):
                    continue
                seen.add(path)
                member = f"{NOTES}{len(entries) + 1:03d}-{os.path.basename(path)}"
                zf.write(path, member)
                entries.append(Entry(path, member, os.path.getsize(path), _sha256_file(path)))
            if settings_ini and os.path.isfile(settings_ini):
                zf.write(settings_ini, SETTINGS)
            manifest = {
                "format": FORMAT, "version": VERSION, "app_version": app_version,
                "created": datetime.datetime.now().isoformat(timespec="seconds"),
                "home": home, "settings": bool(settings_ini and os.path.isfile(settings_ini)),
                "files": [e.__dict__ for e in entries],
            }
            zf.writestr(MANIFEST, json.dumps(manifest, indent=2))
        os.replace(tmp, zip_path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    return entries


def read_manifest(zip_path: str) -> Dict:
    try:
        with zipfile.ZipFile(zip_path) as zf:
            manifest = json.loads(zf.read(MANIFEST).decode("utf-8"))
    except (KeyError, zipfile.BadZipFile, ValueError, OSError) as exc:
        raise BackupError(tr("{name} is not a Twigpad backup ({error})").format(name=os.path.basename(zip_path), error=exc)) from exc
    if manifest.get("format") != FORMAT:
        raise BackupError(tr("{name} is not a Twigpad backup").format(name=os.path.basename(zip_path)))
    if manifest.get("version", 0) > VERSION:
        raise BackupError(tr("This backup was made by a newer Twigpad. Update Twigpad to restore it."))
    return manifest


def entries(manifest: Dict) -> List[Entry]:
    return [Entry(**{k: f[k] for k in ("original", "member", "size", "sha256")}) for f in manifest["files"]]


def map_path(original: str, old_home: str, new_home: str) -> str:
    """The same place under the new home folder (other places stay as they are)."""
    old_home = old_home.rstrip(os.sep)
    if old_home and (original == old_home or original.startswith(old_home + os.sep)):
        return new_home.rstrip(os.sep) + original[len(old_home):]
    return original


def _usable(folder: str) -> bool:
    """The folder exists and can be written to, or can be created."""
    while folder and not os.path.isdir(folder):
        parent = os.path.dirname(folder)
        if parent == folder:
            return False
        folder = parent
    return bool(folder) and os.access(folder, os.W_OK)


def plan(zip_path: str, fallback_dir: str, home: Optional[str] = None) -> List[PlanItem]:
    """Where each file of the backup goes, and whether it is already there."""
    manifest = read_manifest(zip_path)
    home = home or os.path.expanduser("~")
    out: List[PlanItem] = []
    used = set()
    for entry in entries(manifest):
        target = map_path(entry.original, manifest.get("home", ""), home)
        if not _usable(os.path.dirname(target)):
            target = os.path.join(fallback_dir, os.path.basename(entry.original))
        if target in used:   # two files with the same name in the fallback folder
            stem, ext = os.path.splitext(target)
            n = 2
            while f"{stem} ({n}){ext}" in used:
                n += 1
            target = f"{stem} ({n}){ext}"
        used.add(target)
        if os.path.exists(target):
            status = SAME if os.path.isfile(target) and _sha256_file(target) == entry.sha256 else EXISTS
        else:
            status = NEW
        out.append(PlanItem(entry, target, status))
    return out


def restore_files(zip_path: str, items: Iterable[PlanItem]) -> List[str]:
    """Write the NEW files of a plan; files already there are never touched.
    Returns error messages (empty when all went well)."""
    errors: List[str] = []
    with zipfile.ZipFile(zip_path) as zf:
        for item in items:
            if item.status != NEW or os.path.exists(item.target):
                continue
            try:
                os.makedirs(os.path.dirname(item.target), exist_ok=True)
                data = zf.read(item.entry.member)
                if hashlib.sha256(data).hexdigest() != item.entry.sha256:
                    raise BackupError(tr("the copy in the backup is damaged"))
                fd, tmp = tempfile.mkstemp(prefix=".restore-", dir=os.path.dirname(item.target))
                with os.fdopen(fd, "wb") as fh:
                    fh.write(data)
                os.replace(tmp, item.target)
            except (OSError, KeyError, BackupError) as exc:
                errors.append(f"{item.target}: {exc}")
    return errors


def extract_settings(zip_path: str, folder: str) -> Optional[str]:
    """The backup's settings file, unpacked into ``folder`` (None if it has none)."""
    with zipfile.ZipFile(zip_path) as zf:
        if SETTINGS not in zf.namelist():
            return None
        path = os.path.join(folder, SETTINGS)
        with open(path, "wb") as fh:
            fh.write(zf.read(SETTINGS))
        return path


def path_mapper(items: Iterable[PlanItem], old_home: str, new_home: str) -> Callable[[str], str]:
    """Changes old paths in settings (recent files, last folder) to where
    things are on this computer."""
    moved = {item.entry.original: item.target for item in items}

    def fix(value: str) -> str:
        return moved.get(value) or map_path(value, old_home, new_home)
    return fix
