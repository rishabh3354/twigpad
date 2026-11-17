# SPDX-License-Identifier: GPL-3.0-or-later
"""Entry point.

    python3 -m twigpad [file.hjt]          open the window
    python3 -m twigpad --dump file.hjt     print a file's tree and exit
"""
from __future__ import annotations

import argparse
import os
import sys

from . import APP_ID, APP_NAME, DESKTOP_ID, __version__, hjt


def dump(path: str, show_text: bool) -> int:
    try:
        doc = hjt.load(path)
    except (OSError, hjt.HjtFormatError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(f"{path}: format version {doc.version}, encoding {doc.encoding}, "
          f"{doc.node_count()} nodes")
    for node, level in doc.walk():
        lines = node.text.count("\n") + 1 if node.text else 0
        print(f"{'  ' * level}- {node.title}  ({lines} lines)")
        if show_text and node.text:
            for line in node.text.split("\n"):
                print(f"{'  ' * level}    | {line}")
    for w in doc.warnings:
        print(f"warning: {w}", file=sys.stderr)
    return 0


# Qt messages that say nothing useful to the user. "OpenType support missing"
# is printed once for every installed font that lacks shaping tables for its
# script (many Indic fonts do) whenever Qt looks for a font that has a
# character; the text still shows.
NOISE = ("OpenType support missing for",)


def qt_message(_mode, _context, message: str) -> None:
    if message.startswith(NOISE):
        return
    sys.stderr.write(message + "\n")


def run_gui(path=None, language: str = "") -> int:
    from PyQt5.QtCore import QSettings, Qt, QTimer, qInstallMessageHandler
    from PyQt5.QtWidgets import QApplication

    qInstallMessageHandler(qt_message)

    from .portable import portable_ini

    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv[:1])
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_ID)
    app.setApplicationVersion(__version__)
    app.setDesktopFileName(DESKTOP_ID)

    ini = portable_ini()
    settings = QSettings(ini, QSettings.IniFormat) if ini else QSettings(APP_ID, APP_ID)
    # The language is chosen before any window (or module with menu texts) is made.
    from . import i18n
    i18n.set_language(language or settings.value("view/language", i18n.AUTO, type=str))
    i18n.install_qt_translations(app)

    from .ui.icons import app_icon
    from .ui.mainwindow import MainWindow
    app.setWindowIcon(app_icon())
    if ini:   # portable: keep crash-recovery copies on the stick, not on this computer
        from . import recovery
        recovery.FOLDER = os.path.join(os.path.dirname(ini), f"{APP_ID}-recovery")
    win = MainWindow(settings if ini else None)
    win.show()
    if path:
        win.load_path(path)
    elif not win.check_recovery():
        win.open_startup_file()
    QTimer.singleShot(1200, win.offer_file_association)
    return app.exec_()


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog=APP_ID, description=f"{APP_NAME} tree notes editor")
    p.add_argument("file", nargs="?", help=".hjt file or backup to open")
    p.add_argument("--version", action="version", version=f"{APP_NAME} {__version__}")
    p.add_argument("--dump", metavar="FILE", help="print the tree of a .hjt file and exit")
    p.add_argument("--text", action="store_true", help="with --dump, also print article text")
    p.add_argument("--language", metavar="CODE", default="",
                   help="language of the menus for this start (en, de, fr, es, it, pt_BR, ru, zh_CN, ja)")
    args = p.parse_args(argv)
    if args.dump:
        return dump(args.dump, args.text)
    return run_gui(args.file, args.language)


if __name__ == "__main__":
    sys.exit(main())
