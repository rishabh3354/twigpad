# SPDX-License-Identifier: GPL-3.0-or-later
"""Make the desktop open .hjt and .twig files with Twigpad.

Installed packages (deb, rpm, Flatpak, AppImage tools) register the file types
themselves. When Twigpad was installed with pip or runs from its source
folder, Options > Open .hjt Files with Twigpad does it for the current user:
it adds the file types and a menu entry under ~/.local/share and makes
Twigpad the default app for them, just like "Open With > Always" in a file
manager. Nothing outside the user's home folder is changed.
"""
from __future__ import annotations

import configparser
import os
import shlex
import shutil
import subprocess
import sys
from typing import Callable, Dict, List, Optional, Tuple

from . import APP_ID, APP_NAME, DESKTOP_ID
from .i18n import tr

MIME_TYPES = ("application/x-hjt", "application/x-twigpad")
RESOURCES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources")
Runner = Callable[..., "subprocess.CompletedProcess"]


def data_home() -> str:
    return os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")


def config_home() -> str:
    return os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")


def in_flatpak() -> bool:
    return bool(os.environ.get("FLATPAK_ID")) or os.path.exists("/.flatpak-info")


def in_snap() -> bool:
    """A snap cannot register file types: snapd adds its menu entry, and
    file managers offer Twigpad under Open With."""
    return bool(os.environ.get("SNAP_NAME"))


def _quote(arg: str) -> str:
    """Quote an Exec argument the way desktop entries want it."""
    if arg and all(c.isalnum() or c in "/._-+=:," for c in arg):
        return arg
    return '"' + arg.replace("\\", "\\\\").replace('"', '\\"').replace("`", "\\`").replace("$", "\\$") + '"'


def launch_command() -> str:
    """How the file manager should start this Twigpad."""
    appimage = os.environ.get("APPIMAGE")
    if appimage:
        return f"{_quote(appimage)} %f"
    if shutil.which(APP_ID):
        return f"{APP_ID} %f"
    package_parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cmd = f"{_quote(sys.executable)} -m {APP_ID} %f"
    if os.path.basename(package_parent) not in ("site-packages", "dist-packages"):
        cmd = f"env PYTHONPATH={_quote(package_parent)} {cmd}"   # running from the source folder
    return cmd


def restart_command() -> Tuple[str, List[str], Dict[str, str]]:
    """How to start this Twigpad again: program, arguments and extra
    environment variables."""
    appimage = os.environ.get("APPIMAGE")
    if appimage:
        return appimage, [], {}
    package_parent = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env = {}
    if os.path.basename(package_parent) not in ("site-packages", "dist-packages"):
        env["PYTHONPATH"] = package_parent
    return sys.executable, ["-m", APP_ID], env


def desktop_entry(exec_cmd: str) -> str:
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name={APP_NAME}\n"
        "GenericName=Tree Notes\n"
        "Comment=Organize notes, ideas and knowledge in a tree\n"
        f"Exec={exec_cmd}\n"
        f"Icon={DESKTOP_ID}\n"
        "Terminal=false\n"
        "StartupNotify=true\n"
        "Categories=Office;\n"
        "Keywords=notes;notebook;outliner;outline;tree;hierarchical;organizer;knowledge base;PIM;hjt;\n"
        f"MimeType={';'.join(MIME_TYPES)};\n"
    )


def _data_dirs() -> List[str]:
    dirs = os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share"
    return [d for d in dirs.split(":") if d]


def system_desktop_file() -> Optional[str]:
    """The menu entry a package installed, if there is one."""
    for folder in _data_dirs():
        path = os.path.join(folder, "applications", DESKTOP_ID + ".desktop")
        if os.path.isfile(path):
            return path
    return None


def user_desktop_file() -> str:
    return os.path.join(data_home(), "applications", DESKTOP_ID + ".desktop")


def _run(run: Runner, *args: str) -> Optional[str]:
    """Run a desktop tool; its output, or None when it is missing or fails."""
    if shutil.which(args[0]) is None:
        return None
    try:
        result = run(list(args), capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout if result.returncode == 0 else None


def current_default(mime: str = MIME_TYPES[0], run: Runner = subprocess.run) -> str:
    out = _run(run, "xdg-mime", "query", "default", mime)
    if out is not None:
        return out.strip()
    return _mimeapps_default(mime) or ""


def is_default(run: Runner = subprocess.run) -> bool:
    return current_default(run=run) == DESKTOP_ID + ".desktop"


def _mimeapps_path() -> str:
    return os.path.join(config_home(), "mimeapps.list")


def _read_mimeapps() -> configparser.ConfigParser:
    cp = configparser.ConfigParser(interpolation=None, strict=False, delimiters=("=",))
    cp.optionxform = str   # keep the case of MIME types
    try:
        cp.read(_mimeapps_path(), encoding="utf-8")
    except configparser.Error:
        pass
    return cp


def _mimeapps_default(mime: str) -> Optional[str]:
    cp = _read_mimeapps()
    if cp.has_option("Default Applications", mime):
        return cp.get("Default Applications", mime).split(";")[0].strip()
    return None


def _write_mimeapps_defaults() -> None:
    """Without xdg-mime: write the defaults into ~/.config/mimeapps.list."""
    cp = _read_mimeapps()
    if not cp.has_section("Default Applications"):
        cp.add_section("Default Applications")
    for mime in MIME_TYPES:
        cp.set("Default Applications", mime, DESKTOP_ID + ".desktop;")
    os.makedirs(config_home(), exist_ok=True)
    with open(_mimeapps_path(), "w", encoding="utf-8") as fh:
        cp.write(fh, space_around_delimiters=False)


def _write(path: str, data: bytes) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".part"
    with open(tmp, "wb") as fh:
        fh.write(data)
    os.replace(tmp, path)


def make_default(run: Runner = subprocess.run) -> None:
    """Register the file types and make Twigpad open them. Raises OSError."""
    if in_flatpak():
        raise OSError(tr("In the Flatpak version, use your file manager: right-click a .hjt file, "
                         "choose Open With, then {app} and Always.").format(app=APP_NAME))
    with open(os.path.join(RESOURCES, "twigpad-mime.xml"), "rb") as fh:
        _write(os.path.join(data_home(), "mime", "packages", DESKTOP_ID + ".xml"), fh.read())
    _run(run, "update-mime-database", os.path.join(data_home(), "mime"))
    if system_desktop_file() is None:
        _write(user_desktop_file(), desktop_entry(launch_command()).encode("utf-8"))
        with open(os.path.join(RESOURCES, f"{APP_ID}.svg"), "rb") as fh:
            _write(os.path.join(data_home(), "icons", "hicolor", "scalable", "apps", DESKTOP_ID + ".svg"),
                   fh.read())
        _run(run, "update-desktop-database", os.path.join(data_home(), "applications"))
    if _run(run, "xdg-mime", "default", DESKTOP_ID + ".desktop", *MIME_TYPES) is None:
        _write_mimeapps_defaults()


def shell_command(cmd: str) -> List[str]:   # used by the tests
    return shlex.split(cmd.replace("%f", "FILE"))
