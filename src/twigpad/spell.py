# SPDX-License-Identifier: GPL-3.0-or-later
"""Spell checking with the system's Hunspell library and dictionaries.

Uses ctypes, so no extra Python package is needed. When Hunspell or a
dictionary is missing, ``available_languages()`` is empty and spell checking
is simply switched off.
"""
from __future__ import annotations

import ctypes
import ctypes.util
import glob
import os
import re
import tempfile
import urllib.request
from typing import Callable, Dict, List, NamedTuple, Optional

from .i18n import tr

USER_DICT_DIR = os.path.join(os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share"),
                             "hunspell")
DICT_DIRS = [
    USER_DICT_DIR,
    os.path.expanduser("~/.local/share/hunspell"),
    "/usr/share/hunspell",
    "/usr/share/myspell/dicts",
    "/usr/share/myspell",
    "/usr/local/share/hunspell",
    "/app/share/hunspell",          # Flatpak
]
_LIB_NAMES = ["libhunspell-1.7.so.0", "libhunspell-1.6.so.0", "libhunspell.so",
              "libhunspell-1.7.dylib", "libhunspell-1.7-0.dll"]

# A word: letters, optionally joined by an apostrophe (don't, l'eau).
WORD_RE = re.compile(r"[^\W\d_]+(?:['’][^\W\d_]+)*")

_lib = None
_lib_tried = False


def _load_lib():
    global _lib, _lib_tried
    if _lib_tried:
        return _lib
    _lib_tried = True
    names = list(_LIB_NAMES)
    found = ctypes.util.find_library("hunspell-1.7") or ctypes.util.find_library("hunspell")
    if found:
        names.insert(0, found)
    for name in names:
        try:
            lib = ctypes.CDLL(name)
        except OSError:
            continue
        lib.Hunspell_create.restype = ctypes.c_void_p
        lib.Hunspell_create.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
        lib.Hunspell_destroy.argtypes = [ctypes.c_void_p]
        lib.Hunspell_spell.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        lib.Hunspell_spell.restype = ctypes.c_int
        lib.Hunspell_get_dic_encoding.argtypes = [ctypes.c_void_p]
        lib.Hunspell_get_dic_encoding.restype = ctypes.c_char_p
        lib.Hunspell_suggest.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.POINTER(ctypes.c_char_p)),
                                         ctypes.c_char_p]
        lib.Hunspell_suggest.restype = ctypes.c_int
        lib.Hunspell_free_list.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.POINTER(ctypes.c_char_p)),
                                           ctypes.c_int]
        lib.Hunspell_add.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        lib.Hunspell_add.restype = ctypes.c_int
        _lib = lib
        break
    return _lib


def available_languages() -> Dict[str, str]:
    """Language code (e.g. 'en_US') -> path of its .dic file."""
    if _load_lib() is None:
        return {}
    out: Dict[str, str] = {}
    for folder in DICT_DIRS:
        for dic in sorted(glob.glob(os.path.join(folder, "*.dic"))):
            code = os.path.splitext(os.path.basename(dic))[0]
            if code.startswith("hyph_") or code in out:
                continue
            if os.path.exists(os.path.splitext(dic)[0] + ".aff"):
                out[code] = dic
    return out


class Language(NamedTuple):
    code: str      # the dictionary's file name, e.g. en_GB
    name: str
    source: str    # folder in the dictionary collection


# Dictionaries Twigpad can download: the Hunspell dictionaries of the
# LibreOffice and Mozilla projects, as collected (in UTF-8) at
# https://github.com/wooorm/dictionaries. Each has its own free licence.
DOWNLOAD_BASE = "https://raw.githubusercontent.com/wooorm/dictionaries/main/dictionaries/"
DOWNLOADS: List[Language] = [Language(*row) for row in (
    ("en_US", "English (United States)", "en"),
    ("en_GB", "English (United Kingdom)", "en-GB"),
    ("en_AU", "English (Australia)", "en-AU"),
    ("en_CA", "English (Canada)", "en-CA"),
    ("en_ZA", "English (South Africa)", "en-ZA"),
    ("de_DE", "German (Germany)", "de"),
    ("de_AT", "German (Austria)", "de-AT"),
    ("de_CH", "German (Switzerland)", "de-CH"),
    ("fr_FR", "French", "fr"),
    ("es_ES", "Spanish", "es"),
    ("es_MX", "Spanish (Mexico)", "es-MX"),
    ("es_AR", "Spanish (Argentina)", "es-AR"),
    ("it_IT", "Italian", "it"),
    ("pt_BR", "Portuguese (Brazil)", "pt"),
    ("pt_PT", "Portuguese (Portugal)", "pt-PT"),
    ("nl_NL", "Dutch", "nl"),
    ("ru_RU", "Russian", "ru"),
    ("uk_UA", "Ukrainian", "uk"),
    ("pl_PL", "Polish", "pl"),
    ("cs_CZ", "Czech", "cs"),
    ("sk_SK", "Slovak", "sk"),
    ("sv_SE", "Swedish", "sv"),
    ("da_DK", "Danish", "da"),
    ("nb_NO", "Norwegian (Bokmål)", "nb"),
    ("nn_NO", "Norwegian (Nynorsk)", "nn"),
    ("is_IS", "Icelandic", "is"),
    ("el_GR", "Greek", "el"),
    ("tr_TR", "Turkish", "tr"),
    ("ro_RO", "Romanian", "ro"),
    ("hu_HU", "Hungarian", "hu"),
    ("bg_BG", "Bulgarian", "bg"),
    ("hr_HR", "Croatian", "hr"),
    ("sr_RS", "Serbian (Cyrillic)", "sr"),
    ("sl_SI", "Slovenian", "sl"),
    ("lt_LT", "Lithuanian", "lt"),
    ("lv_LV", "Latvian", "lv"),
    ("et_EE", "Estonian", "et"),
    ("ca_ES", "Catalan", "ca"),
    ("gl_ES", "Galician", "gl"),
    ("eu_ES", "Basque", "eu"),
    ("ga_IE", "Irish", "ga"),
    ("cy_GB", "Welsh", "cy"),
    ("he_IL", "Hebrew", "he"),
    ("fa_IR", "Persian", "fa"),
    ("ko_KR", "Korean", "ko"),
    ("vi_VN", "Vietnamese", "vi"),
    ("ka_GE", "Georgian", "ka"),
    ("hy_AM", "Armenian", "hy"),
    ("mk_MK", "Macedonian", "mk"),
    ("eo", "Esperanto", "eo"),
    ("la", "Latin", "la"),
)]
_NAMES = {lang.code: lang.name for lang in DOWNLOADS}


def _native_name(code: str) -> Optional[str]:
    """'Deutsch (Österreich)' for de_AT: how the language calls itself."""
    try:
        from PyQt5.QtCore import QLocale
    except ImportError:
        return None
    loc = QLocale(code)
    if loc.language() == QLocale.C or not loc.nativeLanguageName():
        return None
    lang = loc.nativeLanguageName()
    lang = lang[:1].upper() + lang[1:]
    if "_" in code and loc.nativeCountryName():
        return f"{lang} ({loc.nativeCountryName()})"
    return lang


def language_name(code: str) -> str:
    """'English (United Kingdom)' for en_GB; other codes as they are. When
    Twigpad is not in English, each language's own name ('Deutsch (Österreich)')."""
    from . import i18n
    if i18n.current != "en":
        native = _native_name(code)
        if native:
            return native
    name = _NAMES.get(code)
    if name:
        return name
    base = _NAMES.get(code.split("_")[0] + "_" + code.split("_")[0].upper())
    return f"{base.split(' (')[0]} ({code})" if base else code


def library_available() -> bool:
    return _load_lib() is not None


def user_installed(code: str) -> bool:
    return os.path.exists(os.path.join(USER_DICT_DIR, code + ".dic"))


def install_dictionary(lang: Language, progress: Optional[Callable[[int, int], None]] = None,
                       opener=None, timeout: float = 60) -> str:
    """Download a dictionary into the user's Hunspell folder. Returns the .dic path."""
    opener = opener or urllib.request.urlopen
    os.makedirs(USER_DICT_DIR, exist_ok=True)
    parts = {}
    for n, ext in enumerate(("aff", "dic")):
        url = f"{DOWNLOAD_BASE}{lang.source}/index.{ext}"
        req = urllib.request.Request(url, headers={"User-Agent": "Twigpad"})
        with opener(req, timeout=timeout) as resp:
            total = int(resp.headers.get("Content-Length") or 0) if getattr(resp, "headers", None) else 0
            chunks, done = [], 0
            while True:
                chunk = resp.read(1 << 16)
                if not chunk:
                    break
                chunks.append(chunk)
                done += len(chunk)
                if progress:
                    progress(n, int(100 * done / total) if total else -1)
        parts[ext] = b"".join(chunks)
    first = parts["dic"].split(b"\n", 1)[0].strip()
    if not parts["aff"] or not first.isdigit():
        raise OSError(tr("The downloaded dictionary for {name} is not valid").format(name=language_name(lang.code)))
    targets = {}
    for ext, data in parts.items():
        fd, tmp = tempfile.mkstemp(prefix=f".{lang.code}-", dir=USER_DICT_DIR)
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        targets[ext] = tmp
    for ext, tmp in targets.items():   # .aff first, then .dic: a .dic means "ready"
        os.replace(tmp, os.path.join(USER_DICT_DIR, f"{lang.code}.{ext}"))
    _drop_speller(os.path.join(USER_DICT_DIR, lang.code + ".dic"))
    return os.path.join(USER_DICT_DIR, lang.code + ".dic")


def remove_dictionary(code: str) -> bool:
    """Remove a dictionary the user downloaded (system ones are left alone)."""
    removed = False
    for ext in ("dic", "aff"):
        path = os.path.join(USER_DICT_DIR, f"{code}.{ext}")
        if os.path.exists(path):
            os.remove(path)
            removed = True
    _drop_speller(os.path.join(USER_DICT_DIR, code + ".dic"))
    return removed


def best_language(preferred: str, languages: Dict[str, str]) -> Optional[str]:
    """The dictionary to use for a locale like 'en_GB': exact match, then the
    same language, then English, then anything."""
    if not languages:
        return None
    if preferred in languages:
        return preferred
    base = preferred.split("_")[0]
    for prefix in (base + "_", "en_US", "en_"):
        for code in sorted(languages):
            if code == prefix or code.startswith(prefix) or code == base:
                return code
    return sorted(languages)[0]


class Speller:
    """One loaded dictionary plus the user's own words."""

    def __init__(self, dic_path: str):
        lib = _load_lib()
        if lib is None:
            raise OSError(tr("The Hunspell library is not installed"))
        aff = os.path.splitext(dic_path)[0] + ".aff"
        self._lib = lib
        self._h = lib.Hunspell_create(aff.encode(), dic_path.encode())
        if not self._h:
            raise OSError(tr("Could not load the dictionary {path}").format(path=dic_path))
        enc = (lib.Hunspell_get_dic_encoding(self._h) or b"UTF-8").decode("ascii", "replace")
        self.encoding = {"ISO8859-1": "latin-1", "ISO8859-15": "iso8859-15"}.get(enc, enc)
        self.language = os.path.splitext(os.path.basename(dic_path))[0]
        self._cache: Dict[str, bool] = {}

    def __del__(self):
        h = getattr(self, "_h", None)
        if h:
            self._lib.Hunspell_destroy(h)
            self._h = None

    def _enc(self, word: str) -> Optional[bytes]:
        try:
            return word.replace("’", "'").encode(self.encoding)
        except (UnicodeEncodeError, LookupError):
            return None

    def check(self, word: str) -> bool:
        ok = self._cache.get(word)
        if ok is None:
            raw = self._enc(word)
            ok = raw is None or bool(self._lib.Hunspell_spell(self._h, raw))
            self._cache[word] = ok
        return ok

    def suggest(self, word: str, limit: int = 8) -> List[str]:
        raw = self._enc(word)
        if raw is None:
            return []
        lst = ctypes.POINTER(ctypes.c_char_p)()
        n = self._lib.Hunspell_suggest(self._h, ctypes.byref(lst), raw)
        try:
            out = [lst[i].decode(self.encoding, "replace") for i in range(n)]
        finally:
            if n:
                self._lib.Hunspell_free_list(self._h, ctypes.byref(lst), n)
        return out[:limit]

    def add(self, word: str) -> None:
        raw = self._enc(word)
        if raw is not None:
            self._lib.Hunspell_add(self._h, raw)
        self._cache[word] = True


_spellers: Dict[str, Speller] = {}


def get_speller(dic_path: str) -> Speller:
    """A shared Speller per dictionary: loading one takes a moment."""
    sp = _spellers.get(dic_path)
    if sp is None:
        sp = _spellers[dic_path] = Speller(dic_path)
    return sp


def _drop_speller(dic_path: str) -> None:
    _spellers.pop(dic_path, None)


def misspelled(text: str, speller: Speller, skip=()):
    """Yield (start, end) of misspelled words in ``text``. ``skip`` is a list of
    (start, end) ranges to leave alone, such as links."""
    for m in WORD_RE.finditer(text):
        word = m.group()
        if len(word) < 2 or word.isupper():
            continue   # single letters and acronyms
        if any(s <= m.start() < e for s, e in skip):
            continue
        if not speller.check(word):
            yield m.start(), m.end()
