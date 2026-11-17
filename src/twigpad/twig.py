# SPDX-License-Identifier: GPL-3.0-or-later
"""Reading and writing ``.twig`` files.

A ``.twig`` file holds what the ``.hjt`` format can't: formatted text with
images, note icons and colours, and optional password protection.

Plain ``.twig`` files are UTF-8 JSON::

    {"format": "twigpad", "version": 1,
     "nodes": [{"title": "...", "text": "...", "html": "...", "icon": "star",
                "color": "#c0392b", "children": [...]}],
     "images": {"<name>": "<base64 data>"}}

``text`` is always the plain text of the note (so other tools can read it);
``html`` is present only for formatted notes. Images are referenced from the
HTML as ``twigimg:<name>``.

Password-protected files start with the line ``TWIGPAD-ENCRYPTED``, then one
line of JSON with the key-derivation settings, then the zlib-compressed JSON
above, encrypted with AES-256-GCM. The key comes from the password with
scrypt. Both header lines are authenticated, so any change to the file is
detected. A forgotten password cannot be recovered.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import zlib
from dataclasses import dataclass
from typing import Dict, List, Optional

from .hjt import write_atomic
from .model import Document, Node

FORMAT = "twigpad"
VERSION = 1
ENC_MAGIC = b"TWIGPAD-ENCRYPTED\n"
IMAGE_SCHEME = "twigimg"
IMAGE_REF = re.compile(IMAGE_SCHEME + r":([A-Za-z0-9._-]+)")
_COLOR = re.compile(r"#[0-9a-fA-F]{6}")

# scrypt settings: about 0.1 s and 32 MB per attempt on a typical computer.
SCRYPT_N, SCRYPT_R, SCRYPT_P = 2 ** 15, 8, 1

try:
    from cryptography.exceptions import InvalidTag
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
except ImportError:  # pragma: no cover - depends on the system
    AESGCM = None
    InvalidTag = Exception


class TwigFormatError(ValueError):
    """The file is not a .twig file or is damaged."""


class PasswordRequired(Exception):
    """The file is password protected; call again with the password."""


class WrongPassword(Exception):
    """The password is wrong (or the encrypted file was changed)."""


def encryption_available() -> bool:
    return AESGCM is not None


@dataclass
class KeyInfo:
    """The derived key, kept instead of the password itself."""
    salt: bytes
    key: bytes
    n: int = SCRYPT_N
    r: int = SCRYPT_R
    p: int = SCRYPT_P


def derive_key(password: str, salt: Optional[bytes] = None, n: int = SCRYPT_N,
               r: int = SCRYPT_R, p: int = SCRYPT_P) -> KeyInfo:
    salt = salt if salt is not None else os.urandom(16)
    key = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=n, r=r, p=p,
                         maxmem=256 * 1024 * 1024, dklen=32)
    return KeyInfo(salt, key, n, r, p)


def is_encrypted(data: bytes) -> bool:
    return data.startswith(ENC_MAGIC)


def looks_like_twig(data: bytes) -> bool:
    if is_encrypted(data):
        return True
    head = data[:200].lstrip(b"\xef\xbb\xbf \t\r\n")
    return head.startswith(b"{") and b'"format"' in data[:400] and FORMAT.encode() in data[:400]


# ---------------------------------------------------------------- JSON <-> nodes

def image_names(html: str) -> List[str]:
    return IMAGE_REF.findall(html)


def _node_to_dict(node: Node) -> dict:
    d = {"title": node.title, "text": node.text}
    for key in ("html", "icon", "color"):
        value = getattr(node, key)
        if value:
            d[key] = value
    if node.children:
        d["children"] = [_node_to_dict(c) for c in node.children]
    return d


def _dict_to_node(d: dict) -> Node:
    if not isinstance(d, dict):
        raise TwigFormatError("A note in the file is damaged.")
    color = str(d.get("color", ""))
    node = Node(str(d.get("title", "")) or "Untitled", str(d.get("text", "")),
                html=str(d.get("html", "")), icon=str(d.get("icon", ""))[:40],
                color=color if _COLOR.fullmatch(color) else "")
    for child in d.get("children", []) or []:
        node.add_child(_dict_to_node(child))
    return node


def to_json(doc: Document) -> bytes:
    used: Dict[str, str] = {}
    for node, _level in doc.walk():
        for name in image_names(node.html):
            if name in doc.images and name not in used:
                used[name] = base64.b64encode(doc.images[name]).decode("ascii")
    data = {"format": FORMAT, "version": VERSION,
            "nodes": [_node_to_dict(n) for n in doc.top_nodes]}
    if used:
        data["images"] = used
    return json.dumps(data, ensure_ascii=False, indent=1).encode("utf-8")


def from_json(raw: bytes) -> Document:
    try:
        data = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise TwigFormatError(f"The file is damaged: {exc}") from None
    if not isinstance(data, dict) or data.get("format") != FORMAT:
        raise TwigFormatError("This is not a Twigpad notes file.")
    doc = Document()
    if int(data.get("version", 1)) > VERSION:
        doc.warnings.append("The file was made by a newer version of Twigpad; "
                            "anything this version doesn't know about was left out.")
    for d in data.get("nodes", []) or []:
        doc.root.add_child(_dict_to_node(d))
    for name, b64 in (data.get("images") or {}).items():
        try:
            doc.images[name] = base64.b64decode(b64)
        except (ValueError, TypeError):
            doc.warnings.append(f"Image {name} is damaged and was left out.")
    doc.encoding = "utf-8"
    return doc


# ---------------------------------------------------------------- encryption

def encrypt(plain: bytes, info: KeyInfo) -> bytes:
    if AESGCM is None:
        raise OSError("Password protection needs the Python 'cryptography' package.")
    header = json.dumps({"version": VERSION, "cipher": "AES-256-GCM", "kdf": "scrypt",
                         "n": info.n, "r": info.r, "p": info.p,
                         "salt": base64.b64encode(info.salt).decode("ascii")}).encode() + b"\n"
    nonce = os.urandom(12)
    sealed = AESGCM(info.key).encrypt(nonce, zlib.compress(plain, 6), ENC_MAGIC + header)
    return ENC_MAGIC + header + nonce + sealed


def _read_header(data: bytes):
    rest = data[len(ENC_MAGIC):]
    line_end = rest.find(b"\n")
    if line_end < 0:
        raise TwigFormatError("The encrypted file is damaged.")
    header = rest[: line_end + 1]
    try:
        h = json.loads(header)
        salt = base64.b64decode(h["salt"])
        params = (int(h.get("n", SCRYPT_N)), int(h.get("r", SCRYPT_R)), int(h.get("p", SCRYPT_P)))
    except (ValueError, KeyError, TypeError):
        raise TwigFormatError("The encrypted file is damaged.") from None
    return header, salt, params, rest[line_end + 1:]


def decrypt(data: bytes, password: Optional[str] = None, info: Optional[KeyInfo] = None):
    """Returns (plain JSON bytes, KeyInfo)."""
    if AESGCM is None:
        raise OSError("Opening password-protected files needs the Python 'cryptography' package.")
    header, salt, (n, r, p), body = _read_header(data)
    if info is None or info.salt != salt:
        if password is None:
            raise PasswordRequired()
        info = derive_key(password, salt, n, r, p)
    nonce, sealed = body[:12], body[12:]
    try:
        packed = AESGCM(info.key).decrypt(nonce, sealed, ENC_MAGIC + header)
    except InvalidTag:
        raise WrongPassword() from None
    try:
        return zlib.decompress(packed), info
    except zlib.error:
        raise TwigFormatError("The encrypted file is damaged.") from None


# ---------------------------------------------------------------- files

def load_bytes(data: bytes, password: Optional[str] = None) -> Document:
    info = None
    if is_encrypted(data):
        data, info = decrypt(data, password)
    doc = from_json(data)
    doc.crypto = info
    return doc


def load(path: str, password: Optional[str] = None) -> Document:
    with open(path, "rb") as fh:
        data = fh.read()
    doc = load_bytes(data, password)
    doc.path = path
    return doc


def serialize(doc: Document) -> bytes:
    plain = to_json(doc)
    return encrypt(plain, doc.crypto) if doc.crypto is not None else plain


def save(doc: Document, path: str) -> None:
    write_atomic(path, serialize(doc))
    doc.path = path
    doc.encoding = "utf-8"
