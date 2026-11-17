# SPDX-License-Identifier: GPL-3.0-or-later
"""The developer, ways to support Twigpad, and other apps by the same developer."""
from __future__ import annotations

import os
import platform
from typing import Dict, List, NamedTuple
from urllib.parse import urlencode

DEVELOPER = "Rishabh Bhardwaj"
COMPANY = "Warlord Softwares"
WEBSITE = "https://warlordsoftwares.com/"
DEVELOPER_URL = "https://warlordsoftwares.com/rishabh-bhardwaj/"
DONATE_URL = "https://paypal.me/TechRishabh/10"
ALL_APPS_URL = "https://warlordsoftwares.com/apps/linux-apps/"
REPO_URL = "https://github.com/rishabh3354/twigpad"
ISSUES_URL = REPO_URL + "/issues"


def system_info(app_version: str, qt_version: str = "", pyqt_version: str = "") -> Dict[str, str]:
    """Versions that help to reproduce a bug. Nothing personal: no names, paths or files."""
    try:
        os_name = platform.freedesktop_os_release().get("PRETTY_NAME", "")
    except (AttributeError, OSError):
        os_name = ""
    info = {
        "Twigpad": app_version,
        "OS": os_name or platform.platform(terse=True),
        "Desktop": os.environ.get("XDG_CURRENT_DESKTOP", "") or "unknown",
        "Session": os.environ.get("XDG_SESSION_TYPE", "") or "unknown",
        "Python": platform.python_version(),
    }
    if qt_version:
        info["Qt"] = qt_version
    if pyqt_version:
        info["PyQt"] = pyqt_version
    return info


def bug_report_url(info: Dict[str, str]) -> str:
    """A new GitHub issue with a short form and the system details filled in."""
    details = "\n".join(f"- {key}: {value}" for key, value in info.items())
    body = ("**What happened?**\n\n\n"
            "**Steps to reproduce**\n1. \n2. \n3. \n\n"
            "**What did you expect to happen?**\n\n\n"
            "**System**\n" + details + "\n")
    return ISSUES_URL + "/new?" + urlencode({"labels": "bug", "body": body})


class App(NamedTuple):
    name: str
    summary: str
    url: str
    icon: str   # file name in resources/apps (the app's own icon)


_PAGE = "https://warlordsoftwares.com/trending-apps/"

OTHER_APPS: List[App] = [
    App("PDF 30-in-1 PRO", "Merge, split, convert, compress, sign and OCR PDF files, all offline",
        _PAGE + "pdf-30-in-1-offline-pdf-editor-and-converter/", "pdf30in1.png"),
    App("4KTUBE PRO", "Download YouTube videos, playlists and audio in up to 4K quality",
        _PAGE + "4ktube-pro-best-youtube-video-downloader-linux/", "4ktube.png"),
    App("4KWALL PRO", "Find beautiful high-resolution wallpapers and change them automatically",
        _PAGE + "4kwall-modern-wallpaper-app-with-auto-wallpaper-changer/", "4kwall.png"),
    App("FORMAT LAB PRO", "Convert and compress video and audio files in one click",
        _PAGE + "formatlab-pro-convert-or-compress-video-audio-formats-one-click/", "formatlab.png"),
    App("Torrent4K PRO", "Torrent client that lets you watch videos while they download",
        _PAGE + "torrent4k-torrent-client-and-video-player/", "torrent4k.png"),
    App("PDF2OCR PRO", "Turn scanned pages and images into text you can copy and search (free)",
        _PAGE + "pdf2go-convert-imagespdf-text-uding-ocr-technology/", "pdf2ocr.png"),
    App("JPEG2PDF PRO", "Combine a folder of pictures into one PDF (free)",
        _PAGE + "jpg2pdf-pro-convert-your-images-pdfs/", "jpeg2pdf.png"),
    App("SpeedX", "Live internet speed and system monitor for your desktop (free)",
        _PAGE + "speedx-system-monitor-app-linux/", "speedx.png"),
]
