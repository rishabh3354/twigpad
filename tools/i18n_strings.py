#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Find every text Twigpad shows through tr(), ntr() and N_(), and check the
translation files in src/twigpad/resources/i18n against them.

    python3 tools/i18n_strings.py              list the texts
    python3 tools/i18n_strings.py --check      what each language is missing
    python3 tools/i18n_strings.py --json       the texts as a JSON template

A translation file maps each English text to its translation. A text from
ntr() is listed under its singular form and translated as a list of plural
forms (one for Chinese and Japanese, three for Russian, two otherwise).
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import string
import sys
from typing import Dict, List, Tuple

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACKAGE = os.path.join(ROOT, "src", "twigpad")
I18N = os.path.join(PACKAGE, "resources", "i18n")
sys.path.insert(0, os.path.join(ROOT, "src"))


def _const(node) -> str | None:
    return node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None


def extract() -> Tuple[Dict[str, str], Dict[str, Tuple[str, str]], List[str]]:
    """(texts, plurals, problems): texts maps each text to where it is used;
    plurals maps a singular text to (plural text, where)."""
    texts: Dict[str, str] = {}
    plurals: Dict[str, Tuple[str, str]] = {}
    problems: List[str] = []
    for folder, _dirs, files in os.walk(PACKAGE):
        for name in sorted(files):
            if not name.endswith(".py"):
                continue
            path = os.path.join(folder, name)
            rel = os.path.relpath(path, ROOT)
            with open(path, encoding="utf-8") as fh:
                tree = ast.parse(fh.read(), path)
            for node in ast.walk(tree):
                if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
                    continue
                where = f"{rel}:{node.lineno}"
                if node.func.id in ("tr", "N_") and node.args:
                    text = _const(node.args[0])
                    if text is not None:
                        texts.setdefault(text, where)
                    elif isinstance(node.args[0], ast.JoinedStr):
                        problems.append(f"{where}: f-string in {node.func.id}(); use named fields and .format()")
                elif node.func.id == "ntr" and len(node.args) >= 2:
                    one, many = _const(node.args[0]), _const(node.args[1])
                    if one is None or many is None:
                        problems.append(f"{where}: ntr() needs two plain texts")
                    else:
                        plurals.setdefault(one, (many, where))
    return texts, plurals, problems


def fields(text: str) -> set:
    return {f for _lit, f, _spec, _conv in string.Formatter().parse(text) if f is not None}


def accel_count(text: str) -> int:
    return len(re.findall(r"&(?!&)", text.replace("&&", "")))


def check_language(code: str, table: dict, texts: dict, plurals: dict) -> List[str]:
    """Problems with one language's table: missing texts, wrong fields,
    wrong number of plural forms."""
    from twigpad.i18n import PLURAL_FORMS
    out = []
    for text in texts:
        value = table.get(text)
        if not isinstance(value, str) or not value:
            out.append(f"missing: {text!r}")
            continue
        if not fields(value) <= fields(text):
            out.append(f"unknown field in {value!r} (English {text!r})")
        if accel_count(value) > 1 or (accel_count(text) == 0 and accel_count(value) == 1):
            out.append(f"wrong & in {value!r}")
    for one, (many, _where) in plurals.items():
        value = table.get(one)
        n = PLURAL_FORMS.get(code, 2)
        if not (isinstance(value, list) and len(value) == n and all(isinstance(v, str) and v for v in value)):
            out.append(f"plural {one!r} needs a list of {n} forms")
            continue
        for form in value:
            if not fields(form) <= fields(one) | fields(many):
                out.append(f"unknown field in {form!r} (English {one!r})")
    known = set(texts) | set(plurals)
    for key in table:
        if key not in known:
            out.append(f"unused: {key!r}")
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--check", action="store_true")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()
    texts, plurals, problems = extract()
    for problem in problems:
        print("problem:", problem, file=sys.stderr)
    if args.json:
        template = {t: "" for t in texts}
        template.update({one: [one, many] for one, (many, _w) in plurals.items()})
        json.dump(template, sys.stdout, ensure_ascii=False, indent=1)
        print()
        return 1 if problems else 0
    if args.check:
        from twigpad.i18n import LANGUAGES
        bad = bool(problems)
        for code in LANGUAGES:
            if code == "en":
                continue
            try:
                with open(os.path.join(I18N, code + ".json"), encoding="utf-8") as fh:
                    table = json.load(fh)
            except OSError:
                print(f"{code}: no translation file")
                bad = True
                continue
            issues = check_language(code, table, texts, plurals)
            print(f"{code}: {'OK' if not issues else f'{len(issues)} problems'}")
            for issue in issues[:20]:
                print("   ", issue)
            bad = bad or bool(issues)
        return 1 if bad else 0
    for text, where in texts.items():
        print(f"{where}\t{text}")
    for one, (many, where) in plurals.items():
        print(f"{where}\t{one} | {many}")
    print(f"{len(texts)} texts, {len(plurals)} with plural forms", file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
