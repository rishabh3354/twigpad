# SPDX-License-Identifier: GPL-3.0-or-later
"""Crash recovery: while a file has unsaved changes, Twigpad keeps a recovery
copy of it every half a minute. Saving, or closing the window normally,
deletes the copy. A copy that is still there at the next start belongs to a
Twigpad that crashed (or a computer that lost power) and is offered back.

Each copy is a folder holding the notes as a .twig file (encrypted with the
file's own key when the file has a password) and a small meta.json.
"""
from __future__ import annotations

import datetime
import itertools
import json
import os
import shutil
from dataclasses import dataclass
from typing import Callable, List, Optional

from . import APP_ID
from .hjt import write_atomic

INTERVAL_MS = 30_000
FOLDER: Optional[str] = None      # tests point this at a temporary folder
META = "meta.json"
_counter = itertools.count(1)


def folder() -> str:
    if FOLDER:
        return FOLDER
    base = os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state")
    return os.path.join(base, APP_ID, "recovery")


def new_id() -> str:
    """One per window: the process id and a counter."""
    return f"{os.getpid()}-{next(_counter)}"


def _safe(name: str) -> str:
    name = "".join(c if c.isalnum() or c in " ._-()" else "_" for c in name).strip() or "Untitled"
    return os.path.splitext(name)[0][:80] + ".twig"


@dataclass
class Entry:
    id: str
    data_path: str     # the recovered notes (.twig)
    original: str      # the file it belongs to ("" = never saved)
    name: str          # what the window called it
    saved: str         # ISO time of the copy
    pid: int

    def when(self) -> datetime.datetime:
        try:
            return datetime.datetime.fromisoformat(self.saved)
        except ValueError:
            return datetime.datetime.fromtimestamp(0)


def write(rec_id: str, data: bytes, original: Optional[str], name: str) -> str:
    """Write (or replace) the recovery copy of one window."""
    target = os.path.join(folder(), rec_id)
    os.makedirs(target, mode=0o700, exist_ok=True)
    data_name = _safe(name)
    for old in os.listdir(target):   # the file may have been renamed by Save As
        if old.endswith(".twig") and old != data_name:
            os.remove(os.path.join(target, old))
    write_atomic(os.path.join(target, data_name), data)
    meta = {"original": original or "", "name": name, "file": data_name, "pid": os.getpid(),
            "saved": datetime.datetime.now().isoformat(timespec="seconds")}
    write_atomic(os.path.join(target, META), json.dumps(meta, indent=1).encode("utf-8"))
    return os.path.join(target, data_name)


def remove(rec_id: str) -> None:
    shutil.rmtree(os.path.join(folder(), rec_id), ignore_errors=True)


def is_running(pid: int) -> bool:
    """Is that Twigpad still open (so its copy is not from a crash)?"""
    if pid == os.getpid():
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as fh:
            return APP_ID.encode() in fh.read().lower()
    except OSError:
        return True   # no /proc: assume it is ours


def pending(running: Callable[[int], bool] = is_running) -> List[Entry]:
    """Recovery copies left behind by Twigpads that are no longer running,
    newest first."""
    out: List[Entry] = []
    base = folder()
    if not os.path.isdir(base):
        return out
    for rec_id in os.listdir(base):
        target = os.path.join(base, rec_id)
        try:
            with open(os.path.join(target, META), encoding="utf-8") as fh:
                meta = json.load(fh)
            data_path = os.path.join(target, meta["file"])
            entry = Entry(rec_id, data_path, meta.get("original", ""), meta.get("name", "Untitled"),
                          meta.get("saved", ""), int(meta.get("pid", 0)))
        except (OSError, ValueError, KeyError, TypeError):
            continue   # half-written: skip it
        if not os.path.isfile(data_path) or running(entry.pid):
            continue
        out.append(entry)
    out.sort(key=lambda e: e.when(), reverse=True)
    return out
