# SPDX-License-Identifier: GPL-3.0-or-later
"""The language of Twigpad's menus and windows.

Every text the user sees goes through ``tr("English text")``. Translations
are JSON files in resources/i18n, one per language, mapping the English text
to the translated one; a missing entry falls back to English. Texts with
values in them use named fields: ``tr("Delete {name}?").format(name=...)``.

The language is chosen before the windows are built (at start), so changing
it in View > Language asks to restart Twigpad.
"""
from __future__ import annotations

import json
import os
from typing import Dict, List, Optional

RESOURCES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "resources", "i18n")
AUTO = "auto"

# Shown in each language's own name, so people can find theirs.
LANGUAGES: Dict[str, str] = {
    "en": "English",
    "de": "Deutsch",
    "fr": "Français",
    "es": "Español",
    "it": "Italiano",
    "pt_BR": "Português (Brasil)",
    "ru": "Русский",
    "zh_CN": "简体中文",
    "ja": "日本語",
}

current = "en"
_table: Dict[str, str] = {}
_plurals: Dict[str, List[str]] = {}
_qt_translators: List[object] = []


def tr(text: str) -> str:
    """The text in the chosen language (English when not translated)."""
    return _table.get(text, text)


def N_(text: str) -> str:
    """Marks a text for translation where it is defined (a table of menu
    names, say) without translating it yet; tr() it where it is shown."""
    return text


def plural_index(code: str, n: int) -> int:
    """Which plural form a number takes in a language (CLDR rules for
    cardinal numbers, simplified to whole numbers)."""
    n = abs(int(n))
    if code in ("zh_CN", "ja"):
        return 0
    if code in ("fr", "pt_BR"):
        return 0 if n <= 1 else 1
    if code == "ru":
        if n % 10 == 1 and n % 100 != 11:
            return 0
        if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
            return 1
        return 2
    return 0 if n == 1 else 1


PLURAL_FORMS = {"zh_CN": 1, "ja": 1, "ru": 3}


def ntr(one: str, many: str, n: int) -> str:
    """A text that depends on a number: ``ntr("{n} node", "{n} nodes", n)``.
    The translation file holds a list of forms under the singular text."""
    forms = _plurals.get(one)
    if forms:
        return forms[min(plural_index(current, n), len(forms) - 1)]
    return one if n == 1 else many


def _env_languages() -> List[str]:
    out: List[str] = []
    for var in ("LANGUAGE", "LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(var, "")
        if value:
            out.extend(part for part in value.split(":") if part)
            if var != "LANGUAGE":
                break
    return out


def match(name: str) -> Optional[str]:
    """'de_AT.UTF-8' -> 'de', 'pt_BR' -> 'pt_BR', 'pt_PT' -> None."""
    name = name.split(".")[0].split("@")[0].replace("-", "_")
    if name in LANGUAGES:
        return name
    base = name.split("_")[0]
    if base in LANGUAGES:
        return base
    if base == "zh" and name in ("zh", "zh_SG", "zh_Hans"):
        return "zh_CN"
    return None


def system_language() -> str:
    for name in _env_languages():
        if name in ("C", "POSIX"):
            continue
        code = match(name)
        if code:
            return code
    return "en"


def resolve(choice: str) -> str:
    if choice in LANGUAGES:
        return choice
    return system_language()


def translation_file(code: str) -> str:
    return os.path.join(RESOURCES, f"{code}.json")


def load_table(code: str) -> Dict[str, str]:
    if code == "en":
        return {}
    try:
        with open(translation_file(code), encoding="utf-8") as fh:
            table = json.load(fh)
    except (OSError, ValueError):
        return {}
    return table if isinstance(table, dict) else {}


def set_language(choice: str) -> str:
    """Use a language ('auto' follows the desktop). Returns the code in use."""
    global current, _table, _plurals
    current = resolve(choice)
    table = load_table(current)
    _table = {k: v for k, v in table.items() if isinstance(v, str) and v}
    _plurals = {k: v for k, v in table.items()
                if isinstance(v, list) and v and all(isinstance(f, str) and f for f in v)}
    return current


def tr_in(code: str, text: str) -> str:
    """A text in another language than the one in use (for the question
    asked right after choosing a new language)."""
    if code == current:
        return tr(text)
    value = load_table(code).get(text)
    return value if isinstance(value, str) and value else text


def install_qt_translations(app) -> None:
    """Qt's own texts (file dialogs, standard buttons) in the same language."""
    from PyQt5.QtCore import QLibraryInfo, QLocale, QTranslator
    for old in _qt_translators:
        app.removeTranslator(old)
    _qt_translators.clear()
    if current == "en":
        return
    folder = QLibraryInfo.location(QLibraryInfo.TranslationsPath)
    for name in ("qtbase", "qt"):
        translator = QTranslator(app)
        if translator.load(QLocale(current), name, "_", folder):
            app.installTranslator(translator)
            _qt_translators.append(translator)
            break
