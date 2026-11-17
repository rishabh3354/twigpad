# SPDX-License-Identifier: GPL-3.0-or-later
import re
import unittest

from twigpad import export, search
from twigpad.model import Node
from twigpad.search import TEXT, TITLE


class Item:
    def __init__(self, title, body):
        self.title, self.body = title, body


ITEMS = [Item("Apple pie", "Bake the apple.\nPineapple is different."),
         Item("Notes", "nothing here"),
         Item("Snapple", "APPLE juice")]


class SearchTests(unittest.TestCase):
    def test_case_and_whole_word(self):
        p = search.compile_pattern("apple")
        self.assertEqual(len(list(search.iter_matches(ITEMS, p))), 5)
        p = search.compile_pattern("apple", whole_word=True)
        hits = [(m.index, m.field) for m in search.iter_matches(ITEMS, p)]
        self.assertEqual(hits, [(0, TITLE), (0, TEXT), (2, TEXT)])
        p = search.compile_pattern("apple", match_case=True, whole_word=True)
        self.assertEqual([(m.index, m.field) for m in search.iter_matches(ITEMS, p)], [(0, TEXT)])

    def test_titles_or_text_only(self):
        p = search.compile_pattern("apple")
        self.assertEqual(len(list(search.iter_matches(ITEMS, p, titles=True, text=False))), 2)
        self.assertEqual(len(list(search.iter_matches(ITEMS, p, titles=False, text=True))), 3)

    def test_find_next_and_previous_wrap(self):
        p = search.compile_pattern("apple")
        m, wrapped = search.find_next(ITEMS, p, (0, TEXT, 1))
        self.assertEqual((m.index, m.field, m.start, wrapped), (0, TEXT, 9, False))
        m, wrapped = search.find_next(ITEMS, p, (2, TEXT, 1))
        self.assertEqual((m.index, m.field, wrapped), (0, TITLE, True))
        m, wrapped = search.find_next(ITEMS, p, (0, TITLE, 0), backward=True)
        self.assertEqual((m.index, m.field, wrapped), (2, TEXT, True))
        self.assertEqual(search.find_next(ITEMS, search.compile_pattern("zzz"), (0, 0, 0)), (None, False))

    def test_bad_queries(self):
        with self.assertRaises(ValueError):
            search.compile_pattern("")
        with self.assertRaises(re.error):
            search.compile_pattern("(", regex=True)
        self.assertEqual(search.compile_pattern("a.c").search("abc"), None)  # literal by default

    def test_replace(self):
        p = search.compile_pattern("apple")
        self.assertEqual(search.replace_in("apple Apple", p, r"\1"), (r"\1 \1", 2))
        p = search.compile_pattern(r"(\w+)@", regex=True)
        self.assertEqual(search.replace_in("joe@x", p, r"<\1>", regex=True), ("<joe>x", 1))

    def test_qt_positions_with_emoji(self):
        s = "a😀b"
        self.assertEqual(search.to_qt(s, 2), 3)
        self.assertEqual(search.from_qt(s, 3), 2)
        self.assertEqual(search.from_qt("abc", 2), 2)

    def test_snippet(self):
        s = "first line\n" + "x" * 50 + " needle " + "y" * 50 + "\nlast"
        i = s.index("needle")
        snip = search.snippet(s, i, i + 6, width=30)
        self.assertIn("needle", snip)
        self.assertNotIn("\n", snip)
        self.assertTrue(snip.startswith("…") and snip.endswith("…"))


class ExportTests(unittest.TestCase):
    def test_outline(self):
        a = Node("A", "alpha")
        a.add_child(Node("B", "")).add_child(Node("C", "gamma\n"))
        text = export.outline_text([a, Node("D", "delta")])
        self.assertEqual(text, "1. A\n====\nalpha\n\n1.1. B\n------\n\n1.1.1. C\n--------\ngamma\n\n"
                               "2. D\n====\ndelta\n")
        html = export.outline_html([Node("<x>", "a & b")])
        self.assertIn("<h1>&lt;x&gt;</h1>", html)
        self.assertIn("<pre>a &amp; b</pre>", html)


if __name__ == "__main__":
    unittest.main()
