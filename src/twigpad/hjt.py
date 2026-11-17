# SPDX-License-Identifier: GPL-3.0-or-later
"""Read and write ``.hjt`` tree notes files.

File layout (version 2.x and later)::

    <Treepad version 2.7>
    dt=Text
    <node>
    Node title
    0                         <- depth, top level is 0
    article line 1
    article line 2
    <end node> 5P9i0s8y19Z

Very old files (``<hj-Treepad version 0.9>``) have no ``dt=`` lines and end
each node with a bare ``<end node>``. Windows builds write the files in the
ANSI code page (cp1252) with CRLF line endings.

The reader is lenient on purpose so damaged or truncated backups still load:
everything that could be recovered is returned and problems are listed in
``Document.warnings``.
"""
from __future__ import annotations

import codecs
import io
import os
import re
import tempfile
import zipfile
from typing import List, Optional, Tuple

from .model import Document, Node
from .rtf import looks_like_rtf, rtf_to_text

MAGIC = "5P9i0s8y19Z"
END_NODE = "<end node>"
END_NODE_MAGIC = f"{END_NODE} {MAGIC}"
DEFAULT_VERSION = "2.7"

_HEADER = re.compile(r"^<(?:hj-)?treepad\s+version\s+([0-9.]+)\s*>", re.I)
_LINE_SPLIT = re.compile(r"\r\n|\r|\n")

# File extensions offered in open dialogs (backups included).
OPEN_PATTERNS = ["*.hjt", "*.HJT", "*.bak", "*.BAK", "*.hjt~", "*.~hjt", "*.zip"]


class HjtFormatError(ValueError):
    """Raised when a file is not a tree notes (.hjt) file at all."""


# --------------------------------------------------------------------- decoding

def decode_bytes(data: bytes) -> Tuple[str, str]:
    """Decode raw file bytes, returning ``(text, encoding_used)``."""
    if data.startswith(codecs.BOM_UTF8):
        return data[len(codecs.BOM_UTF8):].decode("utf-8", errors="replace"), "utf-8-sig"
    if data.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
        return data.decode("utf-16", errors="replace"), "utf-16"
    try:
        return data.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        pass
    try:
        return data.decode("cp1252"), "cp1252"
    except UnicodeDecodeError:
        # cp1252 leaves five byte values undefined; latin-1 maps every byte.
        return data.decode("latin-1"), "latin-1"


# ---------------------------------------------------------------------- parsing

def looks_like_hjt(text: str) -> bool:
    """True if ``text`` starts with a tree-file version header."""
    return bool(_HEADER.match(text.lstrip()))


def parse(text: str) -> Document:
    """Parse ``.hjt`` text into a :class:`Document`."""
    lines = _LINE_SPLIT.split(text)
    n = len(lines)
    doc = Document()
    warnings = doc.warnings

    i = 0
    while i < n and not lines[i].strip():
        i += 1
    if i >= n:
        raise HjtFormatError("The file is empty.")

    m = _HEADER.match(lines[i].strip())
    if m:
        doc.version = m.group(1)
        i += 1
    else:
        first = lines[i].strip().lower()
        if not (first == "<node>" or first.startswith("dt=")):
            raise HjtFormatError("This is not a tree notes (.hjt) file.")
        warnings.append("File has no version header; read it as an old-format file.")

    # Files with the magic end marker must use it, so an article line that
    # happens to read "<end node>" does not cut the article short.
    strict_end = any(line.rstrip() == END_NODE_MAGIC for line in lines)

    def is_end(line: str) -> bool:
        s = line.rstrip()
        if strict_end:
            return s == END_NODE_MAGIC
        return s == END_NODE or s.startswith(END_NODE + " ")

    flat: List[Tuple[int, str, str, str]] = []
    while i < n:
        line = lines[i]
        if not line.strip():
            i += 1
            continue

        dtype = "Text"
        if line.lower().startswith("dt="):
            dtype = line[3:].strip() or "Text"
            i += 1
            if i >= n:
                break
            line = lines[i]

        if line.strip().lower() != "<node>":
            warnings.append(f"Line {i + 1}: unexpected text outside a node was skipped.")
            i += 1
            continue
        i += 1

        title = lines[i] if i < n else ""
        i += 1

        level_line = lines[i].strip() if i < n else "0"
        try:
            level = int(level_line)
            i += 1
        except ValueError:
            warnings.append(f"Line {i + 1}: node '{title}' has no valid level; placed at top level.")
            level = 0
            # Do not consume: the line belongs to the article.

        body: List[str] = []
        while i < n and not is_end(lines[i]):
            body.append(lines[i])
            i += 1
        if i >= n:
            warnings.append(f"Node '{title}' is not closed (file may be truncated); recovered its text.")
            # A truncated file usually ends with an empty line from the split.
            while body and body[-1] == "":
                body.pop()
        else:
            i += 1  # skip end marker

        article = "\n".join(body)
        if dtype.lower() == "rtf" or looks_like_rtf(article):
            article = rtf_to_text(article)
            if dtype.lower() != "text":
                warnings.append(f"Node '{title}': formatted (RTF) article converted to plain text.")
        flat.append((level, title, article, dtype))

    _build_tree(doc, flat)
    return doc


def _build_tree(doc: Document, flat: List[Tuple[int, str, str, str]]) -> None:
    stack: List[Node] = [doc.root]   # stack[d] is the parent for depth d
    for level, title, article, _dtype in flat:
        if level < 0:
            level = 0
        if level > len(stack) - 1:
            doc.warnings.append(
                f"Node '{title}' skipped levels ({level}); attached to the nearest parent.")
            level = len(stack) - 1
        parent = stack[level]
        node = parent.add_child(Node(title=title, text=article))
        del stack[level + 1:]
        stack.append(node)


# ---------------------------------------------------------------------- loading

def load_bytes(data: bytes, name: str = "") -> Document:
    if data[:4] == b"PK\x03\x04":
        return _load_zip(data, name)
    text, encoding = decode_bytes(data)
    doc = parse(text)
    doc.encoding = encoding
    return doc


def _load_zip(data: bytes, name: str) -> Document:
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        members = [m for m in zf.namelist() if not m.endswith("/")]
        ranked = sorted(members, key=lambda m: (not m.lower().endswith(".hjt"), m))
        for member in ranked:
            try:
                doc = load_bytes(zf.read(member), member)
            except HjtFormatError:
                continue
            doc.warnings.insert(0, f"Loaded '{member}' from archive '{os.path.basename(name)}'.")
            return doc
    raise HjtFormatError("The archive contains no tree notes (.hjt) file.")


def load(path: str) -> Document:
    """Load a ``.hjt`` file, a backup copy of one, or a zip containing one."""
    with open(path, "rb") as fh:
        data = fh.read()
    doc = load_bytes(data, path)
    doc.path = path
    return doc


# ---------------------------------------------------------------------- writing

def _clean_title(title: str) -> str:
    return " ".join(_LINE_SPLIT.split(title)).strip() or "Untitled"


def serialize(doc: Document) -> str:
    out: List[str] = [f"<Treepad version {DEFAULT_VERSION}>"]
    for node, level in doc.walk():
        out.append("dt=Text")
        out.append("<node>")
        out.append(_clean_title(node.title))
        out.append(str(level))
        if node.text:
            for line in _LINE_SPLIT.split(node.text):
                # Keep an article line from being read back as the end marker.
                out.append(line + " " if line.rstrip() == END_NODE_MAGIC else line)
        out.append(END_NODE_MAGIC)
    return "\r\n".join(out) + "\r\n"


def encode_text(text: str, encoding: Optional[str] = None) -> Tuple[bytes, str]:
    """Encode for saving. By default prefer cp1252 (readable by the Windows
    program), switching to UTF-8 only when the text needs it."""
    if encoding in (None, "auto", "cp1252", "latin-1"):
        try:
            return text.encode("cp1252"), "cp1252"
        except UnicodeEncodeError:
            return text.encode("utf-8"), "utf-8"
    return text.encode(encoding), encoding


def save(doc: Document, path: str, encoding: Optional[str] = None) -> None:
    """Save as .hjt. Formatting, images, icons and colours are not kept:
    the format holds plain text only."""
    data, used = encode_text(serialize(doc), encoding or doc.encoding)
    write_atomic(path, data)
    doc.path = path
    doc.encoding = used


def write_atomic(path: str, data: bytes) -> None:
    """Write atomically so a crash mid-save never destroys the previous file."""
    directory = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(prefix=".twigpad-", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        if os.path.exists(path):
            os.chmod(tmp, os.stat(path).st_mode & 0o777)
        else:
            umask = os.umask(0)
            os.umask(umask)
            os.chmod(tmp, 0o666 & ~umask)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
