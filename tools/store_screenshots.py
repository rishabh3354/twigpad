#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Make the app-store screenshots from a sample notebook.

    python3 tools/store_screenshots.py [OUT_DIR]

Writes 01-...png to 05-...png (default: docs/screenshots/store). Each picture
is the real main window at twice the normal size, with a plain title bar,
rounded corners and a soft shadow on a clear background.

The windows are drawn on Qt's VNC platform, which gives a large virtual
screen (the offscreen platform's tiny screen cuts menus short). Its VNC
server listens on a local port only while the script runs.
"""
from __future__ import annotations

import os
import sys
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "vnc:size=3200x2400:mmsize=847x635:port=59321")
os.environ.setdefault("QT_SCALE_FACTOR", "2")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from PyQt5.QtCore import QBuffer, QByteArray, QIODevice, QPointF, QRectF, QSettings, Qt  # noqa: E402
from PyQt5.QtGui import (  # noqa: E402
    QColor, QFont, QImage, QLinearGradient, QPainter, QPainterPath, QPen, QPixmap, QPolygonF,
    QRadialGradient, QTextDocument,
)
from PyQt5.QtWidgets import QApplication  # noqa: E402

QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
app = QApplication(sys.argv[:1])
app.setApplicationName("Twigpad")
app.setFont(QFont("Noto Sans", 10))

from twigpad import i18n  # noqa: E402

i18n.set_language("en")

from twigpad import twig  # noqa: E402
from twigpad.model import Document, Node  # noqa: E402
from twigpad.ui import theme  # noqa: E402
from twigpad.ui.icons import app_icon  # noqa: E402
from twigpad.ui.mainwindow import MainWindow  # noqa: E402

WIDTH, HEIGHT = 1200, 740      # the window, in logical pixels
TITLE_H = 38                   # the drawn title bar
MARGIN = 36                    # room for the shadow
RADIUS = 10


# ================================================================ the notebook

LAUNCH = """
<h1>Spring product launch</h1>
<p>Launch day: <b>Tuesday 14 April</b> &nbsp;·&nbsp; Owner: Priya &nbsp;·&nbsp;
Status: <span style="color:#1e8449; font-weight:600;">On track</span></p>
<h2>Goals</h2>
<ul>
<li>Reach <b>10,000</b> sign-ups in the first month</li>
<li>Be in three app stores on launch day</li>
<li>Publish the user guide in <i>eight languages</i></li>
</ul>
<h2>Milestones</h2>
<table width="97%" cellspacing="0" cellpadding="6" style="border-collapse:collapse; border:1px solid #c9ced6;">
<tr style="background-color:#e8eef8;"><th align="left">Milestone</th><th align="left">Owner</th>
<th align="left">Due</th><th align="left">Status</th></tr>
<tr><td>Feature freeze</td><td>Tom</td><td>16 Mar</td><td><span style="color:#1e8449;">✔ Done</span></td></tr>
<tr><td>Beta for testers</td><td>Lena</td><td>23 Mar</td><td><span style="color:#1e8449;">✔ Done</span></td></tr>
<tr><td>Store pages and screenshots</td><td>Priya</td><td>2 Apr</td><td><span style="color:#d35400;">In progress</span></td></tr>
<tr><td>Press kit</td><td>Sam</td><td>7 Apr</td><td>Not started</td></tr>
</table>
<h2>Notes</h2>
<p>Keep the press kit short: <span style="background-color:#fff1a8;">one page, five screenshots and a quote.</span></p>
"""

TRIP = """
<h1>Dolomites, June 2026</h1>
<p><img src="twigimg:dolomites.png" width="430" height="230"></p>
<p>Five days walking from hut to hut in the Puez–Odle park. Book the huts by <b>15 March</b>.</p>
<h3>Route</h3>
<ol>
<li>Ortisei → Rifugio Firenze &nbsp;(4 h 30)</li>
<li>Rifugio Firenze → Puez hut &nbsp;(5 h)</li>
<li>Puez hut → Rifugio Genova &nbsp;(4 h)</li>
<li>Rifugio Genova → Malga Zannes &nbsp;(3 h)</li>
</ol>
<p><i>Bring cash: most huts do not take cards.</i></p>
"""

PASTA = """
<h1>Lemon garlic pasta</h1>
<p><b>Serves 4</b> &nbsp;·&nbsp; 25 minutes &nbsp;·&nbsp; from Grandma's notebook</p>
<h2>Ingredients</h2>
<ul>
<li>400 g spaghetti</li>
<li>4 cloves garlic, thinly sliced</li>
<li>2 unwaxed lemons, zest and juice</li>
<li>60 g parmesan, finely grated</li>
<li>A handful of parsley</li>
</ul>
<h2>Method</h2>
<ol>
<li>Cook the pasta in well-salted water; keep a cup of the water.</li>
<li>Warm the garlic gently in olive oil until golden.</li>
<li>Toss everything together, loosening with the pasta water.</li>
</ol>
"""

WEEKLY = """Weekly sync, 10 Nov 2026
Attendees: Priya, Tom, Lena   #meeting

Decisions
- Ship the importer fixes on Friday   #release
- Move the design review to Thursday 14:00

Action items
[x] Priya: book the meeting room
[ ] Tom: write the release notes   #release
[ ] Lena: test older files and backups   #testing

Related
Launch plan: [node://My notebook/Projects/Spring product launch]
Next sync: [node://My notebook/Work/Meeting notes/Planning, 17 Nov]
Release checklist: www.example.com/release
"""

PLANNING = """Planning, 17 Nov 2026   #meeting

Follow-up from [node://My notebook/Work/Meeting notes/Weekly sync, 10 Nov]

- Freeze features for the spring launch   #release
- Lena to share the test report   #testing
"""

JOURNAL = """Wednesday 12 November

Long walk by the river before work. Started the store pages for the launch
and wrote up yesterday's [node://My notebook/Work/Meeting notes/Weekly sync, 10 Nov].

Ideas for the weekend #idea
- Repot the lemon tree
- Try the pasta recipe again, with less garlic
"""

# (title, text, html, icon, colour, children)
TREE = ("My notebook", "Everything I want to keep, in one file.", "", "", "", [
    ("Projects", "", "", "", "", [
        ("Spring product launch", "", LAUNCH, "star", "", [
            ("Launch checklist", "[x] Store pages\n[ ] Press kit #release\n[ ] Announcement post", "", "check", "", []),
            ("Press kit", "One page, five screenshots and a quote.", "", "page", "", []),
            ("Budget", "Ads: 2,000\nPrinting: 350\nTotal: 2,350", "", "page", "", []),
        ]),
        ("Website redesign", "New home page and a shorter sign-up form. #idea", "", "flag", "", []),
        ("Ideas backlog", "- Dark theme for the docs #idea\n- Keyboard cheat sheet #idea", "", "idea", "", []),
    ]),
    ("Work", "", "", "", "", [
        ("Meeting notes", "", "", "", "", [
            ("Weekly sync, 10 Nov", WEEKLY, "", "", "", []),
            ("Planning, 17 Nov", PLANNING, "", "", "", []),
        ]),
        ("Team contacts", "Priya: design\nTom: development\nLena: testing\nSam: marketing", "", "bookmark", "", []),
        ("Onboarding guide", "Start here: accounts, tools and who to ask. #work", "", "info", "", []),
    ]),
    ("Home", "", "", "", "", [
        ("Garden plan", "Tomatoes, beans and herbs along the south fence. #home", "", "check", "", []),
        ("Kitchen renovation", "Get three quotes before January. #home", "", "warning", "", []),
        ("Bills and insurance", "Renew the home insurance in December. #home", "", "", "", []),
    ]),
    ("Recipes", "", "", "", "", [
        ("Lemon garlic pasta", "", PASTA, "heart", "", []),
        ("Banana bread", "3 ripe bananas, 250 g flour, 100 g butter, 2 eggs.", "", "", "", []),
        ("Weeknight curry", "Chickpeas, spinach, coconut milk, 20 minutes.", "", "", "", []),
    ]),
    ("Travel", "", "", "", "", [
        ("Dolomites, June 2026", "", TRIP, "", "#1f5fbf", []),
        ("Packing list", "[ ] Boots\n[ ] Rain jacket\n[ ] Hut sleeping bag liner", "", "check", "", []),
    ]),
    ("Reading list", "The Overstory\nPiranesi\nA Psalm for the Wild-Built", "", "bookmark", "", []),
    ("Journal", "", "", "", "", [
        ("November 2026", JOURNAL, "", "", "", []),
        ("October 2026", "Autumn colours in the park. #home", "", "", "", []),
    ]),
])


def plain(html: str) -> str:
    doc = QTextDocument()
    doc.setHtml(html)
    return doc.toPlainText()


def build_node(spec) -> Node:
    title, text, html, icon, color, children = spec
    node = Node(title, text or (plain(html) if html else ""), html=html.strip(), icon=icon, color=color)
    for child in children:
        node.add_child(build_node(child))
    return node


def mountains_png(w: int = 860, h: int = 460) -> bytes:
    """A small landscape picture for the travel note."""
    img = QImage(w, h, QImage.Format_ARGB32)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    sky = QLinearGradient(0, 0, 0, h)
    sky.setColorAt(0, QColor("#3b5ba5"))
    sky.setColorAt(0.55, QColor("#e7a17a"))
    sky.setColorAt(1, QColor("#f6d6a8"))
    p.fillRect(0, 0, w, h, sky)
    sun = QRadialGradient(QPointF(w * 0.7, h * 0.45), h * 0.35)
    sun.setColorAt(0, QColor(255, 244, 214, 255))
    sun.setColorAt(0.25, QColor(255, 226, 170, 200))
    sun.setColorAt(1, QColor(255, 226, 170, 0))
    p.fillRect(0, 0, w, h, sun)

    def ridge(points, color):
        poly = QPolygonF([QPointF(x * w, y * h) for x, y in points] + [QPointF(w, h), QPointF(0, h)])
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(color))
        p.drawPolygon(poly)

    ridge([(0, .62), (.12, .40), (.2, .5), (.33, .22), (.42, .38), (.5, .3), (.62, .52), (.75, .35),
           (.86, .47), (1, .33)], "#8a6f9e")
    ridge([(0, .74), (.1, .58), (.22, .68), (.35, .5), (.47, .66), (.6, .55), (.72, .7), (.85, .57),
           (1, .66)], "#5a4f7c")
    ridge([(0, .86), (.15, .76), (.3, .84), (.45, .74), (.62, .85), (.8, .76), (1, .82)], "#2f3556")
    p.setBrush(QColor(255, 255, 255, 220))      # snow on the high peak
    p.drawPolygon(QPolygonF([QPointF(.33 * w, .22 * h), QPointF(.36 * w, .29 * h), QPointF(.345 * w, .28 * h),
                             QPointF(.33 * w, .31 * h), QPointF(.315 * w, .28 * h), QPointF(.30 * w, .28 * h)]))
    p.end()
    data = QByteArray()
    buf = QBuffer(data)
    buf.open(QIODevice.WriteOnly)
    img.save(buf, "PNG")
    return bytes(data)


def make_notebook(folder: str) -> str:
    doc = Document()
    doc.root.add_child(build_node(TREE))
    doc.images["dolomites.png"] = mountains_png()
    path = os.path.join(folder, "My notebook.twig")
    twig.save(doc, path)
    return path


# ================================================================ window frame

def frame_colors(dark: bool):
    if dark:
        return QColor("#1f2227"), QColor("#e6e8eb"), QColor("#33373e")
    return QColor("#e4e7eb"), QColor("#1d2127"), QColor("#d2d6dc")


def framed(body: QPixmap, title: str, dark: bool, overlays=()) -> QImage:
    """``body`` inside a title bar with rounded corners and a shadow.
    ``overlays``: (pixmap, x, y) drawn on top, in body coordinates (menus, dialogs)."""
    dpr = body.devicePixelRatio()
    w, h = int(body.width() / dpr), int(body.height() / dpr)
    cw, ch = w + 2 * MARGIN, h + TITLE_H + 2 * MARGIN
    out = QImage(int(cw * dpr), int(ch * dpr), QImage.Format_ARGB32_Premultiplied)
    out.setDevicePixelRatio(dpr)
    out.fill(Qt.transparent)
    window = QRectF(MARGIN, MARGIN, w, h + TITLE_H)

    p = QPainter(out)
    p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
    draw_shadow(p, window, cw, ch, strength=110 if dark else 70)

    clip = QPainterPath()
    clip.addRoundedRect(window, RADIUS, RADIUS)
    p.save()
    p.setClipPath(clip)
    bar, ink, line = frame_colors(dark)
    p.fillRect(QRectF(window.x(), window.y(), w, TITLE_H), bar)
    p.drawPixmap(QPointF(window.x(), window.y() + TITLE_H), body)
    p.setPen(QPen(line, 1))
    p.drawLine(QPointF(window.x(), window.y() + TITLE_H - 0.5), QPointF(window.right(), window.y() + TITLE_H - 0.5))
    p.restore()

    icon = app_icon().pixmap(20, 20)
    p.drawPixmap(QPointF(window.x() + 12, window.y() + (TITLE_H - 20) / 2), icon)
    f = QFont(app.font())
    f.setWeight(QFont.DemiBold)
    p.setFont(f)
    p.setPen(ink)
    p.drawText(QRectF(window.x(), window.y(), w, TITLE_H), Qt.AlignCenter, title)
    draw_buttons(p, QRectF(window.right() - 104, window.y(), 96, TITLE_H), ink, dark)

    for pix, x, y in overlays:
        pw, ph = pix.width() / pix.devicePixelRatio(), pix.height() / pix.devicePixelRatio()
        rect = QRectF(window.x() + x, window.y() + TITLE_H + y, pw, ph)
        draw_shadow(p, rect, cw, ch, strength=80 if dark else 55, spread=10)
        p.drawPixmap(rect.topLeft(), pix)

    p.setBrush(Qt.NoBrush)                      # a fine outline, as window managers draw
    p.setPen(QPen(QColor(255, 255, 255, 28) if dark else QColor(0, 0, 0, 40), 1))
    p.drawRoundedRect(window.adjusted(0.5, 0.5, -0.5, -0.5), RADIUS, RADIUS)
    p.end()
    return out


def draw_shadow(p: QPainter, rect: QRectF, cw: float, ch: float, strength: int, spread: int = 18) -> None:
    """A soft shadow: a rounded rectangle drawn small and scaled up smoothly."""
    k = 6
    small = QImage(int(cw / k) + 1, int(ch / k) + 1, QImage.Format_ARGB32_Premultiplied)
    small.fill(Qt.transparent)
    sp = QPainter(small)
    sp.setRenderHint(QPainter.Antialiasing)
    sp.setPen(Qt.NoPen)
    sp.setBrush(QColor(0, 0, 0, strength))
    r = rect.adjusted(-spread / 4, -spread / 8, spread / 4, spread / 2)
    sp.drawRoundedRect(QRectF(r.x() / k, r.y() / k, r.width() / k, r.height() / k), 3, 3)
    sp.end()
    for _ in range(2):   # two smooth scalings blur the edge
        small = small.scaled(small.width() // 2 or 1, small.height() // 2 or 1,
                             Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
    p.drawImage(QRectF(0, 0, cw, ch), small)


def draw_buttons(p: QPainter, area: QRectF, ink: QColor, dark: bool) -> None:
    """Minimise, maximise and close, as round flat buttons."""
    size, gap = 24, 8
    x = area.right() - 3 * size - 2 * gap
    cy = area.center().y()
    pen = QPen(ink, 1.4)
    pen.setCapStyle(Qt.RoundCap)
    for i, kind in enumerate(("min", "max", "close")):
        c = QPointF(x + i * (size + gap) + size / 2, cy)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 22) if dark else QColor(0, 0, 0, 18))
        p.drawEllipse(c, size / 2, size / 2)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        if kind == "min":
            p.drawLine(QPointF(c.x() - 4, c.y() + 3), QPointF(c.x() + 4, c.y() + 3))
        elif kind == "max":
            p.drawRect(QRectF(c.x() - 4, c.y() - 4, 8, 8))
        else:
            p.drawLine(QPointF(c.x() - 4, c.y() - 4), QPointF(c.x() + 4, c.y() + 4))
            p.drawLine(QPointF(c.x() + 4, c.y() - 4), QPointF(c.x() - 4, c.y() + 4))


# ================================================================ the scenes

def settle(times: int = 6) -> None:
    for _ in range(times):
        app.processEvents()


def find_item(win: MainWindow, title: str):
    return next(i for i in win.tree.all_items() if i.title == title)


def select(win: MainWindow, title: str):
    item = find_item(win, title)
    parent = item.parent()
    while parent is not None:
        win.tree.expandItem(parent)
        parent = parent.parent()
    win.tree.setCurrentItem(item)
    win.tree.scrollToItem(item)
    settle()
    return item


def expand(win: MainWindow, *titles: str) -> None:
    for title in titles:
        win.tree.expandItem(find_item(win, title))


def collapse_all(win: MainWindow) -> None:
    win.tree.collapseAll()
    win.tree.expandItem(win.tree.topLevelItem(0))


def new_window(notebook: str, dark: bool, settings_dir: str) -> MainWindow:
    win = MainWindow(QSettings(os.path.join(settings_dir, f"s{len(os.listdir(settings_dir))}.ini"),
                               QSettings.IniFormat))
    win.set_theme("dark" if dark else "light")
    win.resize(WIDTH, HEIGHT)
    win.show()
    win.act_spell.setChecked(False)    # no red lines under names
    win.load_path(notebook)
    win.statusBar().showMessage(i18n.tr("Opened {path}").format(path=os.path.basename(notebook)))
    settle()
    return win


def set_tree_width(win: MainWindow, px: int) -> None:
    win.splitter.setSizes([px, win.splitter.width() - px])
    settle()


def at(win: MainWindow, widget) -> tuple:
    """Where a pop-up or dialog is, relative to the main window's inside."""
    p = win.mapFromGlobal(widget.mapToGlobal(widget.rect().topLeft()))
    return p.x(), p.y()


def shoot(win: MainWindow, out: str, name: str, dark: bool, overlays=()) -> str:
    settle()
    win.editor.verticalScrollBar().setValue(0)
    settle()
    title = win.windowTitle().replace("[*]", "")
    image = framed(win.grab(), title, dark, overlays)
    path = os.path.join(out, name)
    image.save(path)
    print(path, f"{image.width()}x{image.height()}")
    return path


def close(win: MainWindow) -> None:
    win.setWindowModified(False)
    win.close()
    win.deleteLater()
    settle()


def scene_formatted(notebook, out, tmp):
    win = new_window(notebook, False, tmp)
    collapse_all(win)
    expand(win, "Projects", "Work", "Meeting notes")
    select(win, "Spring product launch")
    expand(win, "Spring product launch")
    set_tree_width(win, 300)
    shoot(win, out, "01-notes-in-a-tree.png", False)
    close(win)


def scene_dark_picture(notebook, out, tmp):
    win = new_window(notebook, True, tmp)
    collapse_all(win)
    win.open_branch_tab(find_item(win, "Travel"))
    win.open_branch_tab(find_item(win, "Recipes"))
    win.tabs.setCurrentIndex(0)
    settle()
    expand(win, "Projects", "Travel", "Journal")
    select(win, "Dolomites, June 2026")
    set_tree_width(win, 380)
    shoot(win, out, "02-dark-theme-pictures-tabs.png", True)
    close(win)


def scene_search(notebook, out, tmp):
    win = new_window(notebook, False, tmp)
    collapse_all(win)
    expand(win, "Projects", "Work", "Meeting notes")
    select(win, "Weekly sync, 10 Nov")
    set_tree_width(win, 300)
    dlg = win.tree_search_dialog()
    dlg.text_edit.setText("launch")
    dlg.show()
    dlg.resize(640, 400)
    settle()
    dlg.run_search()
    dlg.results.setCurrentItem(dlg.results.topLevelItem(1))
    settle()
    body = dlg.grab()
    dark = False
    chrome = framed_dialog(body, dlg.windowTitle(), dark)
    x = WIDTH - chrome.width() / chrome.devicePixelRatio() - 40
    shoot(win, out, "03-search-every-note.png", dark, [(chrome, x, 120)])
    dlg.close()
    close(win)


def framed_dialog(body: QPixmap, title: str, dark: bool) -> QPixmap:
    """A dialog with a small title bar and rounded corners (no shadow: the
    main picture draws it)."""
    dpr = body.devicePixelRatio()
    w, h = body.width() / dpr, body.height() / dpr
    bar_h = 34
    pix = QPixmap(int(w * dpr), int((h + bar_h) * dpr))
    pix.setDevicePixelRatio(dpr)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
    clip = QPainterPath()
    clip.addRoundedRect(QRectF(0, 0, w, h + bar_h), 8, 8)
    p.setClipPath(clip)
    bar, ink, line = frame_colors(dark)
    p.fillRect(QRectF(0, 0, w, bar_h), bar)
    p.drawPixmap(QPointF(0, bar_h), body)
    p.setPen(QPen(line, 1))
    p.drawLine(QPointF(0, bar_h - 0.5), QPointF(w, bar_h - 0.5))
    f = QFont(app.font())
    f.setWeight(QFont.DemiBold)
    p.setFont(f)
    p.setPen(ink)
    p.drawText(QRectF(0, 0, w, bar_h), Qt.AlignCenter, title)
    p.setClipping(False)
    p.setPen(QPen(QColor(0, 0, 0, 45), 1))
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(QRectF(0.5, 0.5, w - 1, h + bar_h - 1), 8, 8)
    p.end()
    return pix


def scene_tags_links(notebook, out, tmp):
    win = new_window(notebook, False, tmp)
    collapse_all(win)
    expand(win, "Work", "Meeting notes", "Projects")
    win.tags_panel.show()
    win.backlinks_panel.show()
    settle()
    select(win, "Weekly sync, 10 Nov")
    win.refresh_info()
    settle()
    tags = win.tags_panel.tag_list
    for row in range(tags.count()):
        if tags.item(row).text().lower().startswith("#release") or tags.item(row).text().lower().startswith("release"):
            tags.setCurrentRow(row)
            break
    win.resizeDocks([win.tags_panel], [260], Qt.Horizontal)
    set_tree_width(win, 290)
    settle()
    shoot(win, out, "04-tags-and-links.png", False)
    close(win)


def scene_format_menu(notebook, out, tmp):
    win = new_window(notebook, True, tmp)
    collapse_all(win)
    expand(win, "Projects", "Recipes")
    select(win, "Lemon garlic pasta")
    set_tree_width(win, 300)
    win.editor.setFocus()
    settle()
    bar = win.menuBar()
    action = next(a for a in bar.actions() if a.text() == i18n.tr("F&ormat"))
    menu = action.menu()
    bar.setActiveAction(action)          # opens the menu and highlights its title
    settle()
    hover = next(a for a in menu.actions() if a.text() == i18n.tr("Paragraph &Style"))
    menu.setActiveAction(hover)
    sub = hover.menu()
    sub.popup(menu.mapToGlobal(menu.actionGeometry(hover).topRight()))
    settle()
    sub.setActiveAction(sub.actions()[2])   # Heading 2
    settle()
    # the menu bar title stays highlighted only while the menu is open
    body = win.grab()
    overlays = [(menu.grab(), *at(win, menu)), (sub.grab(), *at(win, sub))]
    sub.hide()
    menu.hide()
    image = framed(body, win.windowTitle().replace("[*]", ""), True, overlays)
    path = os.path.join(out, "05-rich-text-formatting.png")
    image.save(path)
    print(path, f"{image.width()}x{image.height()}")
    close(win)


def main() -> int:
    out = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "docs", "screenshots", "store"))
    os.makedirs(out, exist_ok=True)
    tmp = tempfile.mkdtemp()
    notebook = make_notebook(tmp)
    settings_dir = os.path.join(tmp, "settings")
    os.makedirs(settings_dir)
    for scene in (scene_formatted, scene_dark_picture, scene_search, scene_tags_links, scene_format_menu):
        scene(notebook, out, settings_dir)
    theme.apply("light")
    return 0


if __name__ == "__main__":
    sys.exit(main())
