# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for .twig files: formatted text, pictures, note icons and colours,
and password protection."""
import os
import shutil
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QMimeData, QSettings, Qt  # noqa: E402
from PyQt5.QtGui import QColor, QFont, QImage, QTextCursor, QTextListFormat  # noqa: E402
from PyQt5.QtWidgets import QApplication  # noqa: E402

from twigpad import export, hjt, textfmt, twig  # noqa: E402
from twigpad.model import Document, Node  # noqa: E402
from twigpad.ui.editor import image_to_png  # noqa: E402
from twigpad.ui.mainwindow import MainWindow  # noqa: E402
from tests.test_hjt import SAMPLE, windows_file  # noqa: E402

app = QApplication.instance() or QApplication([])
needs_crypto = unittest.skipUnless(twig.encryption_available(), "cryptography is not installed")


def png(color="red", w=8, h=6):
    img = QImage(w, h, QImage.Format_RGB32)
    img.fill(QColor(color))
    return image_to_png(img)


def read(path):
    with open(path, "rb") as fh:
        return fh.read()


def sample_doc():
    doc = Document()
    top = doc.root.add_child(Node("Top", "plain top"))
    top.add_child(Node("Rich", "bold text", html="<p><b>bold</b> text<img src=\"twigimg:a.png\"></p>",
                       icon="star", color="#c0392b"))
    doc.images = {"a.png": b"\x89PNG-data", "unused.png": b"x"}
    return doc


class TwigFormatTests(unittest.TestCase):
    def test_round_trip_keeps_everything(self):
        raw = twig.serialize(sample_doc())
        self.assertTrue(twig.looks_like_twig(raw))
        self.assertFalse(twig.looks_like_twig(b"<Treepad version 2.7>\r\n"))
        doc = twig.load_bytes(raw)
        rich = doc.top_nodes[0].children[0]
        self.assertEqual((rich.title, rich.text, rich.icon, rich.color), ("Rich", "bold text", "star", "#c0392b"))
        self.assertIn("<b>bold</b>", rich.html)
        self.assertEqual(doc.images, {"a.png": b"\x89PNG-data"})   # unused pictures are dropped
        self.assertIsNone(doc.crypto)

    def test_needs_twig(self):
        doc = Document()
        doc.root.add_child(Node("Plain", "text"))
        self.assertFalse(doc.needs_twig())
        doc.top_nodes[0].color = "#112233"
        self.assertTrue(doc.needs_twig())

    def test_bad_colour_is_ignored_and_damage_reported(self):
        raw = b'{"format": "twigpad", "nodes": [{"title": "x", "color": "red\' onload=1"}]}'
        self.assertEqual(twig.load_bytes(raw).top_nodes[0].color, "")
        with self.assertRaises(twig.TwigFormatError):
            twig.load_bytes(b'{"format": "twigpad", "nodes": [')
        with self.assertRaises(twig.TwigFormatError):
            twig.load_bytes(b'{"format": "something-else"}')

    @needs_crypto
    def test_encryption(self):
        doc = sample_doc()
        doc.crypto = twig.derive_key("correct horse")
        raw = twig.serialize(doc)
        self.assertTrue(raw.startswith(twig.ENC_MAGIC))
        self.assertNotIn(b"plain top", raw)
        with self.assertRaises(twig.PasswordRequired):
            twig.load_bytes(raw)
        with self.assertRaises(twig.WrongPassword):
            twig.load_bytes(raw, "wrong")
        back = twig.load_bytes(raw, "correct horse")
        self.assertEqual(back.top_nodes[0].text, "plain top")
        self.assertEqual(back.crypto.salt, doc.crypto.salt)
        # Two saves with the same key differ (fresh nonce) and both open.
        self.assertNotEqual(raw, twig.serialize(doc))
        # Any change to the file is detected.
        tampered = raw[:-5] + bytes([raw[-5] ^ 1]) + raw[-4:]
        with self.assertRaises(twig.WrongPassword):
            twig.load_bytes(tampered, "correct horse")

    def test_export_html_embeds_pictures_and_drops_scripts(self):
        doc = sample_doc()
        doc.top_nodes[0].children[0].html += "<script>alert(1)</script>"
        page = export.html_page(doc.top_nodes, "t", doc.images)
        self.assertIn("<b>bold</b>", page)
        self.assertIn("data:image/png;base64,", page)
        self.assertNotIn("<script", page)
        self.assertIn("style='color:#c0392b'", page)
        self.assertNotIn("￼", export.outline_text([Node("a", "x￼y")]))


class TwigWindowTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        settings = QSettings(os.path.join(self.dir, "settings.ini"), QSettings.IniFormat)
        self.win = MainWindow(settings)
        self.sample = os.path.join(self.dir, "notes.hjt")
        with open(self.sample, "wb") as fh:
            fh.write(windows_file(SAMPLE))
        self.assertTrue(self.win.load_path(self.sample))
        self.tree = self.win.tree
        self.ed = self.win.editor

    def tearDown(self):
        self.win.setWindowModified(False)
        self.win.close()
        self.win.deleteLater()
        app.processEvents()
        shutil.rmtree(self.dir)

    def find(self, title):
        return next(i for i in self.tree.all_items() if i.title == title)

    def select(self, title):
        self.tree.setCurrentItem(self.find(title))

    def select_text(self, start, end):
        cur = self.ed.textCursor()
        cur.setPosition(start)
        cur.setPosition(end, QTextCursor.KeepAnchor)
        self.ed.setTextCursor(cur)

    def make_bold_note(self, title="Work", text="hello world"):
        self.select(title)
        self.ed.setPlainText(text)
        self.select_text(0, 5)
        self.win.toggle_char("bold")
        self.assertTrue(self.ed.rich)

    def save_as_twig(self, name="notes.twig"):
        path = os.path.join(self.dir, name)
        self.assertTrue(self.win._write(path))
        return path

    # ------------------------------------------------------------ formatting

    def test_formatting_makes_a_formatted_note(self):
        self.make_bold_note()
        self.select("Recipes")                     # commit
        item = self.find("Work")
        self.assertIn("font-weight:", item.html)
        self.assertEqual(item.body, "hello world")
        self.select("Work")
        self.assertTrue(self.ed.rich)
        self.select_text(0, 1)
        self.assertGreater(self.ed.currentCharFormat().fontWeight(), QFont.Normal)

    def test_plain_notes_paste_plain_text(self):
        self.select("Work")
        self.assertFalse(self.ed.rich)
        mime = QMimeData()
        mime.setHtml("<b>bold</b> text")
        mime.setText("bold text")
        self.ed.setPlainText("")
        self.ed.insertFromMimeData(mime)
        self.assertFalse(self.ed.rich)
        self.select("Recipes")
        self.assertEqual(self.find("Work").html, "")
        self.assertEqual(self.find("Work").body, "bold text")

    def test_more_formatting_commands(self):
        self.make_bold_note()
        self.win.set_heading(1)
        self.assertEqual(self.ed.textCursor().blockFormat().headingLevel(), 1)
        self.win.toggle_list(QTextListFormat.ListDisc)
        self.assertIsNotNone(self.ed.textCursor().currentList())
        self.win.toggle_list(QTextListFormat.ListDisc)
        self.assertIsNone(self.ed.textCursor().currentList())
        self.win._pick_color = lambda initial, title="": QColor("#00aa00")
        self.select_text(6, 11)
        self.win.choose_color(False)
        self.assertEqual(self.ed.currentCharFormat().foreground().color().name(), "#00aa00")
        self.win.clear_formatting()
        self.assertNotEqual(self.ed.currentCharFormat().foreground().color().name(), "#00aa00")
        self.ed.moveCursor(QTextCursor.End)
        self.assertTrue(self.win.insert_table(2, 3))
        self.assertIsNotNone(self.ed.textCursor().currentTable())
        self.win.table_edit("row")
        self.win.table_edit("col")
        table = self.ed.textCursor().currentTable()
        self.assertEqual((table.rows(), table.columns()), (3, 4))

    def test_enter_after_heading_starts_normal_text(self):
        from PyQt5.QtTest import QTest
        self.make_bold_note(text="Title")
        self.ed.moveCursor(QTextCursor.End)
        self.win.set_heading(1)
        QTest.keyClick(self.ed, Qt.Key_Return)
        QTest.keyClicks(self.ed, "body")
        cur = self.ed.textCursor()
        self.assertEqual(cur.blockFormat().headingLevel(), 0)
        self.assertEqual(self.ed.currentCharFormat().fontWeight(), QFont.Normal)
        self.assertEqual(self.ed.toPlainText(), "Title\nbody")

    def test_case_change_keeps_formatting(self):
        self.make_bold_note(text="hello world")
        self.select_text(0, 0)
        self.assertTrue(self.win.format_text(textfmt.to_upper))
        self.assertEqual(self.ed.toPlainText(), "HELLO WORLD")
        self.select_text(0, 1)
        self.assertGreater(self.ed.currentCharFormat().fontWeight(), QFont.Normal)
        self.select_text(7, 8)
        self.assertEqual(self.ed.currentCharFormat().fontWeight(), QFont.Normal)

    def test_replace_all_keeps_formatting(self):
        self.make_bold_note(text="hello world")
        self.select("Recipes")
        dlg = self.win.find_dialog()
        dlg.show_dialog(replace=True)
        dlg.find_edit.setText("hello")
        dlg.replace_edit.setText("howdy")
        self.assertEqual(dlg.replace_all(), 1)
        item = self.find("Work")
        self.assertEqual(item.body, "howdy world")
        self.assertIn("howdy", item.html)
        self.select("Work")
        self.select_text(0, 1)
        self.assertGreater(self.ed.currentCharFormat().fontWeight(), QFont.Normal)
        dlg.close()

    def test_make_plain(self):
        self.make_bold_note()
        self.assertTrue(self.win.make_plain(confirm=False))
        self.assertFalse(self.ed.rich)
        self.select("Recipes")
        self.assertEqual(self.find("Work").html, "")
        self.assertEqual(self.find("Work").body, "hello world")

    # ------------------------------------------------------------ pictures

    def test_pictures_are_saved_in_twig_files(self):
        self.select("Work")
        self.ed.setPlainText("Picture: ")
        self.ed.moveCursor(QTextCursor.End)
        path = os.path.join(self.dir, "pic.png")
        with open(path, "wb") as fh:
            fh.write(png("blue"))
        self.assertTrue(self.win.insert_image_file(path))
        self.assertTrue(self.ed.rich)                    # a picture makes the note formatted
        self.assertEqual(len(self.ed.images), 1)
        out = self.save_as_twig()
        doc = twig.load(out)
        work = next(n for n, _ in doc.walk() if n.title == "Work")
        self.assertIn("twigimg:", work.html)
        self.assertEqual(list(doc.images.values()), [png("blue")])
        self.assertTrue(self.win.load_path(out))
        self.assertEqual(len(self.win.editor.images), 1)
        self.select("Work")
        self.assertIn("twigimg:", self.ed.toHtml())

    def test_pasted_screenshot_becomes_a_picture(self):
        self.select("Work")
        mime = QMimeData()
        img = QImage(4, 4, QImage.Format_RGB32)
        img.fill(QColor("green"))
        mime.setImageData(img)
        self.ed.insertFromMimeData(mime)
        self.assertTrue(self.ed.rich)
        self.assertEqual(len(self.ed.images), 1)

    def test_copy_paste_node_keeps_formatting_and_pictures(self):
        self.make_bold_note()
        self.ed.moveCursor(QTextCursor.End)
        self.ed.insert_image(png())
        self.select("Work")
        self.win.copy_node()
        other = MainWindow(self.win.settings)
        try:
            other.paste_node(as_child=True)
            pasted = other.tree.currentItem()
            self.assertEqual(pasted.title, "Work")
            self.assertIn("font-weight", pasted.html)
            self.assertEqual(len(other.editor.images), 1)
        finally:
            other.setWindowModified(False)
            other.close()
            other.deleteLater()

    # ------------------------------------------------------------ icons and colours

    def test_note_icon_and_colour(self):
        self.select("Soup")
        self.win.setWindowModified(False)
        self.assertTrue(self.win.set_note_look(icon="star"))
        self.assertTrue(self.win.set_note_look(color="#1e8449"))
        item = self.find("Soup")
        self.assertEqual((item.icon, item.color), ("star", "#1e8449"))
        self.assertEqual(item.foreground(0).color().name(), "#1e8449")
        self.assertTrue(self.win.isWindowModified())
        self.win.grab()   # draws the coloured star in the tree
        doc = twig.load(self.save_as_twig())
        soup = next(n for n, _ in doc.walk() if n.title == "Soup")
        self.assertEqual((soup.icon, soup.color), ("star", "#1e8449"))
        self.win.set_note_look(icon="", color="")
        self.assertIsNone(self.find("Soup").data(0, Qt.DecorationRole))

    # ------------------------------------------------------------ .hjt or .twig

    def test_saving_hjt_with_formatting_asks(self):
        self.select("Soup")
        self.win.set_note_look(icon="flag")
        asked = []
        self.win._ask_save_format = lambda name, reasons: asked.append(reasons) or None
        self.assertFalse(self.win.save())                     # cancelled
        self.assertEqual(asked, [["note icons or colours"]])
        self.win._ask_save_format = lambda name, reasons: "hjt"
        self.assertTrue(self.win.save())                       # plain .hjt, icon dropped
        self.assertEqual(hjt.load(self.sample).node_count(), 4)
        self.win._ask_save_format = lambda name, reasons: self.fail("asked twice")
        self.win.setWindowModified(True)
        self.assertTrue(self.win.save())

    def test_choosing_twig_saves_a_twig_file(self):
        self.make_bold_note()
        target = os.path.join(self.dir, "notes.twig")
        self.win._ask_save_format = lambda name, reasons: "twig"
        self.win.save_as = lambda twig_format=None: self.win._write(target)
        self.assertTrue(self.win.save())
        self.assertEqual(self.win.path, target)
        self.assertTrue(twig.looks_like_twig(read(target)))
        self.assertEqual(read(self.sample), windows_file(SAMPLE))   # .hjt untouched

    def test_open_and_save_twig(self):
        self.make_bold_note()
        out = self.save_as_twig()
        self.assertTrue(self.win.load_path(out))
        self.assertEqual(self.win.path, out)          # .twig opens as itself, not as an import
        self.assertFalse(self.win.isWindowModified())
        self.assertEqual(self.win.encoding, "cp1252")
        self.select("Work")
        self.ed.insertPlainText("!")
        self.assertTrue(self.win.save())              # no format question for .twig

    def test_export_branch_as_twig(self):
        self.make_bold_note()
        self.select("My notes")
        out = os.path.join(self.dir, "branch.twig")
        self.assertTrue(self.win.export_file("twig", "branch", out))
        self.assertIn("font-weight", twig.load(out).top_nodes[0].children[1].html)

    # ------------------------------------------------------------ passwords

    @needs_crypto
    def test_password_protected_file(self):
        self.assertTrue(self.win.set_password("s3cret"))
        self.assertTrue(self.win.crypto_label.isVisibleTo(self.win))
        out = self.save_as_twig("locked.twig")
        raw = read(out)
        self.assertTrue(raw.startswith(twig.ENC_MAGIC))
        self.assertNotIn(b"Welcome", raw)
        answers = ["wrong", "s3cret"]
        asked = []
        self.win._ask_password = lambda name, retry: asked.append(retry) or answers.pop(0)
        self.assertTrue(self.win.load_path(out))
        self.assertEqual(asked, [False, True])
        self.assertEqual(self.find("My notes").body, "Welcome text\nsecond line")
        self.assertIsNotNone(self.win.crypto)
        # Saving again keeps it encrypted without asking.
        self.win.editor.setPlainText("changed")
        self.assertTrue(self.win.save())
        self.assertTrue(read(out).startswith(twig.ENC_MAGIC))
        # Cancelling the password question opens nothing.
        self.win._ask_password = lambda name, retry: None
        self.win.new_file(confirm=False)
        self.assertFalse(self.win.load_path(out))
        # Remove the password.
        self.win._ask_password = lambda name, retry: "s3cret"
        self.assertTrue(self.win.load_path(out))
        self.win.remove_password()
        self.assertTrue(self.win.save())
        self.assertFalse(read(out).startswith(twig.ENC_MAGIC))

    @needs_crypto
    def test_no_unencrypted_backup_after_setting_a_password(self):
        self.win.act_backup.setChecked(True)
        out = self.save_as_twig("plain.twig")
        self.win.editor.setPlainText("first change")
        self.assertTrue(self.win.save())               # makes plain.twig.bak (unencrypted)
        self.assertTrue(os.path.exists(out + ".bak"))
        self.win.set_password("pw")                     # that backup is removed
        self.assertFalse(os.path.exists(out + ".bak"))
        self.assertTrue(self.win.save())
        self.assertFalse(os.path.exists(out + ".bak"))  # and no plain one is made
        self.assertTrue(read(out).startswith(twig.ENC_MAGIC))

    @needs_crypto
    def test_password_on_hjt_needs_twig(self):
        self.win.set_password("pw")
        reasons = []
        self.win._ask_save_format = lambda name, r: reasons.append(r) or None
        self.assertFalse(self.win.save())
        self.assertEqual(reasons, [["a password"]])

    def test_read_only_blocks_formatting(self):
        self.win.set_read_only(True)
        for act in (self.win.act_bold, self.win.act_image, self.win.act_set_password,
                    self.win.act_icons["star"]):
            self.assertFalse(act.isEnabled(), act.text())
        self.win.toggle_char("bold")
        self.assertFalse(self.ed.rich)
        self.win.set_read_only(False)


if __name__ == "__main__":
    unittest.main()
