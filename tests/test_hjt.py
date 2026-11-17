# SPDX-License-Identifier: GPL-3.0-or-later
import io
import os
import tempfile
import unittest
import zipfile

from twigpad import hjt
from twigpad.model import Document, Node

M = hjt.MAGIC


def windows_file(text: str) -> bytes:
    """What the Windows program writes: CRLF line endings, cp1252 bytes."""
    return text.replace("\n", "\r\n").encode("cp1252")


SAMPLE = f"""<Treepad version 2.7>
dt=Text
<node>
My notes
0
Welcome text
second line
<end node> {M}
dt=Text
<node>
Recipes
1
Café crème — 2€
<end node> {M}
dt=Text
<node>
Soup
2
<end node> {M}
dt=Text
<node>
Work
1
Line before

Line after blank
<end node> {M}
"""


def titles(doc):
    return [(n.title, lvl) for n, lvl in doc.walk()]


class ParseTests(unittest.TestCase):
    def test_windows_file(self):
        doc = hjt.load_bytes(windows_file(SAMPLE))
        self.assertEqual(doc.version, "2.7")
        self.assertEqual(doc.encoding, "cp1252")
        self.assertEqual(titles(doc), [("My notes", 0), ("Recipes", 1), ("Soup", 2), ("Work", 1)])
        root = doc.top_nodes[0]
        self.assertEqual(root.text, "Welcome text\nsecond line")
        self.assertEqual(root.children[0].text, "Café crème — 2€")
        self.assertEqual(root.children[0].children[0].text, "")
        self.assertEqual(root.children[1].text, "Line before\n\nLine after blank")
        self.assertIs(root.children[0].parent, root)
        self.assertEqual(doc.warnings, [])

    def test_utf8_with_bom_and_lf(self):
        data = b"\xef\xbb\xbf" + SAMPLE.encode("utf-8")
        doc = hjt.load_bytes(data)
        self.assertEqual(doc.encoding, "utf-8-sig")
        self.assertEqual(doc.top_nodes[0].children[0].text, "Café crème — 2€")

    def test_old_format_without_magic_or_dt(self):
        text = ("<hj-Treepad version 0.9>\n<node>\nRoot\n0\nhello\n<end node>\n"
                "<node>\nChild\n1\nworld\n<end node>\n")
        doc = hjt.parse(text)
        self.assertEqual(doc.version, "0.9")
        self.assertEqual(titles(doc), [("Root", 0), ("Child", 1)])
        self.assertEqual(doc.top_nodes[0].children[0].text, "world")

    def test_article_containing_plain_end_marker(self):
        text = (f"<Treepad version 2.7>\ndt=Text\n<node>\nA\n0\n"
                f"before\n<end node>\nafter\n<end node> {M}\n")
        doc = hjt.parse(text)
        self.assertEqual(doc.top_nodes[0].text, "before\n<end node>\nafter")

    def test_multiple_top_level_nodes_and_level_jump(self):
        text = (f"<Treepad version 2.7>\ndt=Text\n<node>\nA\n0\n<end node> {M}\n"
                f"dt=Text\n<node>\nDeep\n3\n<end node> {M}\n"
                f"dt=Text\n<node>\nB\n0\n<end node> {M}\n")
        doc = hjt.parse(text)
        self.assertEqual(titles(doc), [("A", 0), ("Deep", 1), ("B", 0)])
        self.assertTrue(any("skipped levels" in w for w in doc.warnings))

    def test_truncated_backup_is_recovered(self):
        text = (f"<Treepad version 2.7>\ndt=Text\n<node>\nA\n0\nfull\n<end node> {M}\n"
                f"dt=Text\n<node>\nB\n1\npartial text\n")
        doc = hjt.parse(text)
        self.assertEqual(titles(doc), [("A", 0), ("B", 1)])
        self.assertEqual(doc.top_nodes[0].children[0].text, "partial text")
        self.assertTrue(any("truncated" in w for w in doc.warnings))

    def test_rtf_article_becomes_plain_text(self):
        rtf = (r"{\rtf1\ansi\deff0{\fonttbl{\f0 Arial;}}{\colortbl;\red255\green0\blue0;}"
               r"\f0\fs20 Hello \b bold\b0  caf\'e9\par Second line\tab x" + "\\" + "u8364?\\par}")
        text = f"<Treepad version 4.0>\ndt=RTF\n<node>\nR\n0\n{rtf}\n<end node> {M}\n"
        doc = hjt.parse(text)
        self.assertEqual(doc.top_nodes[0].text, "Hello bold café\nSecond line\tx€")

    def test_not_a_tree_file(self):
        with self.assertRaises(hjt.HjtFormatError):
            hjt.parse("just some notes\nnothing else\n")
        with self.assertRaises(hjt.HjtFormatError):
            hjt.parse("\n\n")

    def test_zip_backup(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("readme.txt", "hello")
            zf.writestr("backup/notes.hjt", windows_file(SAMPLE))
        doc = hjt.load_bytes(buf.getvalue(), "backup.zip")
        self.assertEqual(doc.node_count(), 4)


class WriteTests(unittest.TestCase):
    def test_round_trip(self):
        doc = hjt.load_bytes(windows_file(SAMPLE))
        again = hjt.parse(hjt.serialize(doc))
        self.assertEqual(titles(again), titles(doc))
        self.assertEqual([n.text for n, _ in again.walk()], [n.text for n, _ in doc.walk()])

    def test_output_matches_original_format(self):
        doc = hjt.load_bytes(windows_file(SAMPLE))
        data, enc = hjt.encode_text(hjt.serialize(doc))
        self.assertEqual(enc, "cp1252")
        self.assertEqual(data, windows_file(SAMPLE))

    def test_tricky_text_round_trips(self):
        doc = Document()
        a = doc.root.add_child(Node("Multi\nline title", f"x\n<end node> {M}\n\n"))
        a.add_child(Node("日本語", "unicode ✓"))
        again = hjt.parse(hjt.serialize(doc))
        self.assertEqual(again.top_nodes[0].title, "Multi line title")
        self.assertEqual(again.top_nodes[0].text.rstrip("\n").split("\n")[0], "x")
        self.assertEqual(again.top_nodes[0].children[0].text, "unicode ✓")
        data, enc = hjt.encode_text(hjt.serialize(doc))
        self.assertEqual(enc, "utf-8")

    def test_save_and_load_file(self):
        doc = hjt.load_bytes(windows_file(SAMPLE))
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "out.hjt")
            hjt.save(doc, path)
            hjt.save(doc, path)  # overwrite existing
            self.assertEqual(os.listdir(d), ["out.hjt"])
            loaded = hjt.load(path)
            self.assertEqual(titles(loaded), titles(doc))
            self.assertEqual(loaded.path, path)


if __name__ == "__main__":
    unittest.main()
