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
from typing import Dict, List, Optional

DICT_DIRS = [
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
            raise OSError("The Hunspell library is not installed")
        aff = os.path.splitext(dic_path)[0] + ".aff"
        self._lib = lib
        self._h = lib.Hunspell_create(aff.encode(), dic_path.encode())
        if not self._h:
            raise OSError(f"Could not load the dictionary {dic_path}")
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
