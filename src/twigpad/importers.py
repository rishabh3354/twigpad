# SPDX-License-Identifier: GPL-3.0-or-later
"""Turn CSV data into nodes (no Qt dependency)."""
from __future__ import annotations

import csv
import io
from typing import List

from .model import Node


def csv_to_nodes(text: str) -> List[Node]:
    """One node per row: the first field is the node title, the remaining
    fields become the lines of its article. The delimiter (comma, semicolon
    or tab) is detected automatically."""
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    nodes = []
    for row in csv.reader(io.StringIO(text), dialect):
        if not row or not any(field.strip() for field in row):
            continue
        title = row[0].strip() or "Untitled"
        body = "\n".join(field for field in row[1:])
        nodes.append(Node(title, body.rstrip("\n")))
    return nodes
