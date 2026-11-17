# SPDX-License-Identifier: GPL-3.0-or-later
"""Portable mode: keep the settings next to the program instead of in the
home folder, for running from a USB stick.

Create an empty ``twigpad.ini`` beside the AppImage (or beside the program
file) and Twigpad stores its settings there.
"""
from __future__ import annotations

import os
import sys
from typing import Mapping, Optional

from . import APP_ID

INI_NAME = f"{APP_ID}.ini"


def portable_ini(argv0: Optional[str] = None, environ: Optional[Mapping[str, str]] = None) -> Optional[str]:
    """Path of the portable settings file, or None when it does not exist."""
    environ = os.environ if environ is None else environ
    argv0 = sys.argv[0] if argv0 is None else argv0
    folders = []
    appimage = environ.get("APPIMAGE")
    if appimage:
        folders.append(os.path.dirname(os.path.abspath(appimage)))
    if argv0:
        folders.append(os.path.dirname(os.path.abspath(argv0)))
    for folder in folders:
        path = os.path.join(folder, INI_NAME)
        if os.path.isfile(path):
            return path
    return None
