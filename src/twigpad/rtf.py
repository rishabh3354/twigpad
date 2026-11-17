# SPDX-License-Identifier: GPL-3.0-or-later
"""Minimal RTF -> plain text converter.

``.hjt`` articles are normally plain text, but files from some editors mark
some articles as ``dt=RTF``. We keep the words and line breaks and drop the
formatting so those articles stay readable.
"""
from __future__ import annotations

import re

# Destinations whose content is not visible text.
_SKIP_DESTINATIONS = {
    "fonttbl", "colortbl", "stylesheet", "info", "pict", "object", "header",
    "footer", "headerl", "headerr", "footerl", "footerr", "listtable",
    "listoverridetable", "rsidtbl", "generator", "xmlnstbl", "themedata",
    "colorschememapping", "latentstyles", "datastore", "fldinst", "filetbl",
    "revtbl", "pgdsctbl", "nonshppict", "bkmkstart", "bkmkend",
}

_TOKEN = re.compile(
    r"\\([a-zA-Z]+)(-?\d+)? ?"      # control word with optional numeric param
    r"|\\'([0-9a-fA-F]{2})"          # hex-escaped byte
    r"|\\(.)"                        # control symbol
    r"|([{}])"                       # group delimiters
    r"|(\r\n|\r|\n)"                 # raw newlines are ignored in RTF
    r"|([^\\{}\r\n]+)",              # plain text run
    re.S,
)


def looks_like_rtf(text: str) -> bool:
    return text.lstrip().startswith("{\\rtf")


def rtf_to_text(rtf: str, codepage: str = "cp1252") -> str:
    out: list[str] = []
    # Each stack entry: (skip_group, uc_skip_count)
    stack: list[tuple[bool, int]] = []
    skip = False
    uc = 1
    pending_skip = 0          # chars to drop after a \uN escape
    hex_bytes = bytearray()   # consecutive \'hh bytes, decoded together

    def flush_hex() -> None:
        if hex_bytes:
            if not skip:
                out.append(hex_bytes.decode(codepage, errors="replace"))
            hex_bytes.clear()

    for m in _TOKEN.finditer(rtf):
        word, param, hexbyte, symbol, brace, _newline, plain = m.groups()

        if hexbyte is not None:
            if pending_skip:
                pending_skip -= 1
                continue
            hex_bytes.append(int(hexbyte, 16))
            continue
        flush_hex()

        if brace == "{":
            stack.append((skip, uc))
            continue
        if brace == "}":
            if stack:
                skip, uc = stack.pop()
            continue

        if word is not None:
            if word in _SKIP_DESTINATIONS:
                skip = True
            elif skip:
                pass
            elif word in ("par", "line", "sect"):
                out.append("\n")
            elif word == "tab":
                out.append("\t")
            elif word == "uc" and param is not None:
                uc = int(param)
            elif word == "u" and param is not None:
                code = int(param)
                if code < 0:
                    code += 65536
                out.append(chr(code))
                pending_skip = uc
            elif word in ("emdash",):
                out.append("\u2014")
            elif word in ("endash",):
                out.append("\u2013")
            elif word in ("bullet",):
                out.append("\u2022")
            elif word in ("lquote", "rquote"):
                out.append("'")
            elif word in ("ldblquote", "rdblquote"):
                out.append('"')
            continue

        if symbol is not None:
            if symbol == "*":
                skip = True  # ignorable destination
            elif skip:
                pass
            elif symbol in "\\{}":
                out.append(symbol)
            elif symbol == "~":
                out.append("\u00a0")
            elif symbol in ("\n", "\r"):
                out.append("\n")
            continue

        if plain is not None:
            if pending_skip:
                drop = min(pending_skip, len(plain))
                plain = plain[drop:]
                pending_skip -= drop
            if not skip and plain:
                out.append(plain)

    flush_hex()
    text = "".join(out)
    return text.rstrip("\n")
