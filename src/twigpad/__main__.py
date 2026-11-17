# SPDX-License-Identifier: GPL-3.0-or-later
"""Entry point.

    python3 -m twigpad [file.hjt]          open the window
    python3 -m twigpad --dump file.hjt     print a file's tree and exit
"""
from __future__ import annotations

import argparse
import sys

from . import APP_ID, APP_NAME, __version__, hjt


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


def run_gui(path=None) -> int:
    from PyQt5.QtCore import Qt
    from PyQt5.QtWidgets import QApplication

    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv[:1])
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_ID)
    app.setApplicationVersion(__version__)
    app.setDesktopFileName(APP_ID)

    from .ui.icons import app_icon
    from .ui.mainwindow import MainWindow
    app.setWindowIcon(app_icon())
    win = MainWindow()
    win.show()
    if path:
        win.load_path(path)
    else:
        win.open_startup_file()
    return app.exec_()


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog=APP_ID, description=f"{APP_NAME} tree notes editor")
    p.add_argument("file", nargs="?", help=".hjt file or backup to open")
    p.add_argument("--version", action="version", version=f"{APP_NAME} {__version__}")
    p.add_argument("--dump", metavar="FILE", help="print the tree of a .hjt file and exit")
    p.add_argument("--text", action="store_true", help="with --dump, also print article text")
    args = p.parse_args(argv)
    if args.dump:
        return dump(args.dump, args.text)
    return run_gui(args.file)


if __name__ == "__main__":
    sys.exit(main())
