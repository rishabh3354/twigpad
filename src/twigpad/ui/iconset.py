# SPDX-License-Identifier: GPL-3.0-or-later
"""Twigpad's own toolbar icons: rounded outline icons on a 24 x 24 grid, drawn
in the theme's text colour with one accent colour each, so they look the same
on every desktop and in light and dark themes."""
from __future__ import annotations

from typing import Dict, Optional, Tuple

from PyQt5.QtCore import QByteArray, QRectF, Qt
from PyQt5.QtGui import QIcon, QPainter, QPalette, QPixmap
from PyQt5.QtWidgets import QApplication

try:
    from PyQt5.QtSvg import QSvgRenderer
except ImportError:  # pragma: no cover - the PyQt5 build has no SVG module
    QSvgRenderer = None

SIZES = (16, 20, 24, 32, 40, 48)

# Paths use {ink} implicitly (the default stroke); accents are written as
# stroke="{blue}", "{green}", "{red}" or "{amber}".
ICONS: Dict[str, str] = {
    # ------------------------------------------------------------ file
    "new": '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/>'
           '<path d="M14 3v5h5"/>'
           '<path stroke="{green}" d="M12 11v6M9 14h6"/>',
    "open": '<path d="M3 18V6a2 2 0 0 1 2-2h4l2 2h6a2 2 0 0 1 2 2v2"/>'
            '<path stroke="{amber}" fill="{amber_soft}" d="M3.3 19.2l2.4-6.6A2 2 0 0 1 7.6 11.3H20a1 1 0 0 1 '
            '.95 1.3l-2.2 6.4a1.5 1.5 0 0 1-1.4 1H4.2a1 1 0 0 1-.9-.8z"/>',
    "save": '<path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/>'
            '<path d="M7 3v4h7"/>'
            '<path stroke="{blue}" fill="{blue_soft}" d="M7 21v-6.5a1 1 0 0 1 1-1h8a1 1 0 0 1 1 1V21"/>',
    "print": '<path d="M6 9V4a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v5"/>'
             '<path d="M6 18H4.5A1.5 1.5 0 0 1 3 16.5v-5A2.5 2.5 0 0 1 5.5 9h13a2.5 2.5 0 0 1 2.5 2.5v5'
             'a1.5 1.5 0 0 1-1.5 1.5H18"/>'
             '<path stroke="{blue}" fill="{blue_soft}" d="M7 14h10v6a1 1 0 0 1-1 1H8a1 1 0 0 1-1-1z"/>',
    "options": '<path d="M4 6h8M18 6h2M4 12h2M12 12h8M4 18h10M19.5 18h0.5"/>'
               '<g stroke="{blue}"><circle cx="15" cy="6" r="2.2"/><circle cx="9" cy="12" r="2.2"/>'
               '<circle cx="17" cy="18" r="2.2"/></g>',
    # ------------------------------------------------------------ article edit
    "cut": '<circle cx="6" cy="18" r="3"/><circle cx="18" cy="18" r="3"/>'
           '<path stroke="{blue}" d="M8.2 15.8L18.5 3.5M15.8 15.8L5.5 3.5"/>',
    "copy": '<path stroke="{blue}" d="M16 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h3"/>'
            '<rect x="8" y="8" width="13" height="13" rx="2"/>',
    "paste": '<path d="M15.5 4H17a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h1.5"/>'
             '<rect stroke="{blue}" fill="{blue_soft}" x="8.5" y="2.5" width="7" height="4" rx="1"/>'
             '<path d="M9 12h6M9 16h4"/>',
    "delete-text": '<path d="M20 5H9.5a1.5 1.5 0 0 0-1.1.5L3 12l5.4 6.5a1.5 1.5 0 0 0 1.1.5H20a1 1 0 0 0 1-1V6'
                   'a1 1 0 0 0-1-1z"/>'
                   '<path stroke="{red}" d="M17 9l-5 6M12 9l5 6"/>',
    # ------------------------------------------------------------ tree edit
    "node-child": '<rect x="3" y="3" width="10" height="6" rx="1.8"/>'
                  '<path d="M7 9v6.5a1.5 1.5 0 0 0 1.5 1.5H12"/>'
                  '<path stroke="{green}" d="M17.5 13v8M13.5 17h8"/>',
    "node-before": '<path stroke="{green}" d="M12 2.5v7M8.5 6h7"/>'
                   '<rect x="3" y="13" width="18" height="7.5" rx="2"/>',
    "node-after": '<rect x="3" y="3.5" width="18" height="7.5" rx="2"/>'
                  '<path stroke="{green}" d="M12 14.5v7M8.5 18h7"/>',
    "node-delete": '<rect x="3" y="4" width="13" height="7" rx="1.8"/>'
                   '<path d="M7 11v5.5a1.5 1.5 0 0 0 1.5 1.5H11"/>'
                   '<path stroke="{red}" d="M15 15l6 6M21 15l-6 6"/>',
    "rename": '<path d="M13 20h8"/>'
              '<path stroke="{blue}" d="M16.4 3.6a2.1 2.1 0 0 1 3 3L7.5 18.5 3 19.5l1-4.5z"/>',
    # ------------------------------------------------------------ view
    "find": '<circle cx="10.5" cy="10.5" r="6.5"/><path stroke="{blue}" d="M20.5 20.5l-5.3-5.3"/>',
    "search-tree": '<path d="M3 4.5h8M6 9.5h3M6 14.5h2M3 19.5h6"/>'
                   '<circle cx="15" cy="12" r="4.5"/><path stroke="{blue}" d="M21 18.5l-2.8-2.8"/>',
    "view-both": '<rect x="3" y="4" width="18" height="16" rx="2.2"/><path d="M10 4v16"/>'
                 '<path stroke="{blue}" d="M6 9h1.5M6 12.5h1.5M6 16h1.5"/><path d="M13 9h5M13 12.5h5M13 16h3"/>',
    "view-tree": '<rect x="3" y="4" width="18" height="16" rx="2.2"/>'
                 '<path stroke="{blue}" d="M7 9h6M10 12.5h7M10 16h5"/>',
    "view-article": '<rect x="3" y="4" width="18" height="16" rx="2.2"/>'
                    '<path d="M7 9h10M7 12.5h10M7 16h6"/>',
    "word-wrap": '<path d="M3 6h18M3 12h14.5a3.5 3.5 0 0 1 0 7H13M3 18h6"/>'
                 '<path stroke="{blue}" d="M15.5 16.5L13 19l2.5 2.5"/>',
    # ------------------------------------------------------------ navigate
    "link": '<path d="M10 13.5a4.5 4.5 0 0 0 6.8.5l3-3a4.5 4.5 0 0 0-6.4-6.4l-1.6 1.6"/>'
            '<path stroke="{blue}" d="M14 10.5a4.5 4.5 0 0 0-6.8-.5l-3 3a4.5 4.5 0 0 0 6.4 6.4l1.6-1.6"/>',
    "move-up": '<path stroke="{blue}" d="M12 19.5v-15M5.5 11L12 4.5 18.5 11"/>',
    "move-down": '<path stroke="{blue}" d="M12 4.5v15M18.5 13L12 19.5 5.5 13"/>',
    "move-left": '<path stroke="{blue}" d="M19.5 12h-15M11 18.5L4.5 12 11 5.5"/>',
    "move-right": '<path stroke="{blue}" d="M4.5 12h15M13 5.5l6.5 6.5-6.5 6.5"/>',
    "expand": '<path stroke="{blue}" d="M7 15l5 5 5-5M7 9l5-5 5 5"/>',
    "collapse": '<path stroke="{blue}" d="M7 20l5-5 5 5M7 4l5 5 5-5"/>',
    # ------------------------------------------------------------ extras
    "undo": '<path stroke="{blue}" d="M9 14L4 9l5-5"/><path d="M4 9h10.5a5.5 5.5 0 0 1 0 11H11"/>',
    "redo": '<path stroke="{blue}" d="M15 14l5-5-5-5"/><path d="M20 9H9.5a5.5 5.5 0 0 0 0 11H13"/>',
    "bold": '<path stroke-width="2.4" d="M7 4h6a4 4 0 0 1 0 8H7zM7 12h7a4 4 0 0 1 0 8H7z"/>',
    "italic": '<path d="M19 4h-8.5M13.5 20H5"/><path stroke="{blue}" d="M15 4L9 20"/>',
    "focus": '<path d="M3 8V5.5A2.5 2.5 0 0 1 5.5 3H8M16 3h2.5A2.5 2.5 0 0 1 21 5.5V8M21 16v2.5a2.5 2.5 0 0 1'
             '-2.5 2.5H16M8 21H5.5A2.5 2.5 0 0 1 3 18.5V16"/>'
             '<circle stroke="{blue}" fill="{blue_soft}" cx="12" cy="12" r="3.5"/>',
    "bug": '<path d="M8 8.5a4 4 0 0 1 8 0"/>'
           '<rect x="7" y="8.5" width="10" height="11.5" rx="5"/>'
           '<path stroke="{red}" d="M12 12v8M3.5 13H7M17 13h3.5M4.5 8.5l2.8 1.8M19.5 8.5l-2.8 1.8'
           'M4.5 19l2.9-1.8M19.5 19l-2.9-1.8M9.5 4.5L8 3M14.5 4.5L16 3"/>',
    "unfocus": '<path d="M15 3h6v6M9 21H3v-6"/><path stroke="{blue}" d="M21 3l-7 7M3 21l7-7"/>',
}

LIGHT_ACCENTS = {"blue": "#2f6fd6", "green": "#23955a", "red": "#d64235", "amber": "#d9901a"}
DARK_ACCENTS = {"blue": "#6ea4ff", "green": "#4cc985", "red": "#ff7b72", "amber": "#f0b44c"}

_cache: Dict[Tuple[str, str], QIcon] = {}


def available() -> bool:
    return QSvgRenderer is not None


def _colors() -> Dict[str, str]:
    pal = QApplication.palette()
    dark = pal.color(QPalette.Base).lightness() < 128
    colors = dict(DARK_ACCENTS if dark else LIGHT_ACCENTS)
    colors["ink"] = pal.color(QPalette.WindowText).name()
    for key in ("blue", "amber"):
        colors[f"{key}_soft"] = colors[key] + ("33" if dark else "26")   # translucent fill
    return colors


def svg(name: str, colors: Optional[Dict[str, str]] = None) -> str:
    colors = colors or _colors()
    body = ICONS[name]
    for key, value in colors.items():
        body = body.replace("{%s}" % key, value)
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
            f'stroke="{colors["ink"]}" stroke-width="1.8" stroke-linecap="round" '
            f'stroke-linejoin="round">{body}</svg>')


def _hex_alpha(markup: str) -> str:
    """Qt's SVG renderer reads #rrggbbaa wrongly: use fill-opacity instead."""
    import re
    return re.sub(r'fill="(#[0-9a-fA-F]{6})([0-9a-fA-F]{2})"',
                  lambda m: f'fill="{m.group(1)}" fill-opacity="{int(m.group(2), 16) / 255:.2f}"', markup)


def icon(name: str) -> QIcon:
    """The icon in the current theme's colours (empty if Qt has no SVG support)."""
    if QSvgRenderer is None:
        return QIcon()
    colors = _colors()
    key = (name, colors["ink"] + colors["blue"])
    cached = _cache.get(key)
    if cached is not None:
        return cached
    renderer = QSvgRenderer(QByteArray(_hex_alpha(svg(name, colors)).encode("utf-8")))
    result = QIcon()
    for size in SIZES:
        pm = QPixmap(size, size)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        renderer.render(p, QRectF(0, 0, size, size))
        p.end()
        result.addPixmap(pm)
    _cache[key] = result
    return result
