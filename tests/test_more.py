# SPDX-License-Identifier: GPL-3.0-or-later
"""Tests for focus (hoisting) and tabs, backlinks, tags, word count, files
changed by other programs, and spell checking."""
import os
import shutil
import tempfile
import time
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QSettings  # noqa: E402
from PyQt5.QtGui import QTextCursor  # noqa: E402
from PyQt5.QtWidgets import QApplication  # noqa: E402

from twigpad import hjt, spell, tags  # noqa: E402
from twigpad.ui.mainwindow import MainWindow  # noqa: E402
from tests.test_hjt import SAMPLE, windows_file  # noqa: E402

app = QApplication.instance() or QApplication([])
LANGS = spell.available_languages()


class TagTests(unittest.TestCase):
    def test_find_tags(self):
        text = "#work and #to-do, not http://x.com/#frag, &#38;, #2026, a#b or ##x. (#Home) #end-"
        self.assertEqual(tags.tags_in(text), ["work", "to-do", "Home", "end"])

    def test_collect_groups_without_case(self):
        groups = tags.collect([("a", "#Work #work"), ("b", "#WORK #home")])
        self.assertEqual(groups["work"], ("Work", ["a", "b"]))
        self.assertEqual(groups["home"], ("home", ["b"]))


@unittest.skipUnless(LANGS, "no Hunspell dictionary installed")
class SpellTests(unittest.TestCase):
    def setUp(self):
        code = spell.best_language("en_US", LANGS)
        self.sp = spell.get_speller(LANGS[code])

    def test_check_and_suggest(self):
        self.assertTrue(self.sp.check("hello"))
        self.assertFalse(self.sp.check("helo"))
        self.assertIn("hello", self.sp.suggest("helo"))

    def test_misspelled_skips_acronyms_and_ranges(self):
        text = "Thiss is NASA [www.exampel.com] speling"
        found = [text[s:e] for s, e in spell.misspelled(text, self.sp, [(14, 31)])]
        self.assertEqual(found, ["Thiss", "speling"])

    def test_best_language(self):
        self.assertEqual(spell.best_language("xx_YY", {"en_US": "a", "de_DE": "b"}), "en_US")
        self.assertEqual(spell.best_language("de_AT", {"en_US": "a", "de_DE": "b"}), "de_DE")
        self.assertIsNone(spell.best_language("en_US", {}))


class MoreWindowTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.settings = QSettings(os.path.join(self.dir, "settings.ini"), QSettings.IniFormat)
        self.win = MainWindow(self.settings)
        self.sample = os.path.join(self.dir, "notes.hjt")
        with open(self.sample, "wb") as fh:
            fh.write(windows_file(SAMPLE))
        self.assertTrue(self.win.load_path(self.sample))
        self.tree = self.win.tree

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

    def visible_titles(self):
        """Titles the user can see (and reach with the keyboard)."""
        out = []

        def walk(it):
            if it.isHidden():
                return
            out.append(it.title)
            if it.isExpanded():
                for i in range(it.childCount()):
                    walk(it.child(i))

        root = self.tree.itemFromIndex(self.tree.rootIndex()) or self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            walk(root.child(i))
        return out

    # ------------------------------------------------------------ focus and tabs

    def test_focus_on_branch(self):
        self.tree.expandAll()
        self.select("Recipes")
        self.win.focus_branch()
        self.assertEqual(self.visible_titles(), ["Recipes", "Soup"])
        self.assertTrue(self.win.act_focus_out.isEnabled())
        # The focused node acts as the top: no siblings, no moving or deleting it.
        self.assertFalse(self.win.act_add_after.isEnabled())
        self.assertFalse(self.win.act_delete.isEnabled())
        self.assertIsNone(self.tree.add_sibling())
        self.select("Soup")
        self.assertFalse(self.tree.move_left())
        self.tree.add_child("Stock")
        self.assertEqual(self.visible_titles(), ["Recipes", "Soup", "Stock"])
        self.win.grab()   # the classic tree look draws the focused node as the top
        self.win.focus_out()
        self.assertIsNone(self.tree.hoisted)
        self.assertIn("Work", self.visible_titles())
        self.assertEqual(self.tree.currentItem().title, "Recipes")

    def test_jumping_outside_the_focus_shows_whole_tree(self):
        self.select("Recipes")
        self.win.focus_branch()
        self.select("Work")    # e.g. from Find, a link or a backlink
        self.assertIsNone(self.tree.hoisted)
        self.assertIn("Work", self.visible_titles())

    def test_tabs(self):
        self.assertFalse(self.win.tabs.isVisibleTo(self.win))
        self.select("Recipes")
        self.win.open_branch_tab()
        self.assertEqual(self.win.tabs.count(), 2)
        self.assertTrue(self.win.tabs.isVisibleTo(self.win))
        self.assertEqual(self.win.tabs.tabText(1), "Recipes")
        self.assertIs(self.tree.hoisted, self.find("Recipes"))
        self.select("Soup")
        self.win.tabs.setCurrentIndex(0)
        self.assertIsNone(self.tree.hoisted)
        self.select("Work")
        self.win.tabs.setCurrentIndex(1)
        self.assertEqual(self.tree.currentItem().title, "Soup")    # each tab keeps its place
        self.find("Recipes").setText(0, "Cooking")                  # renaming updates the tab
        self.assertEqual(self.win.tabs.tabText(1), "Cooking")
        self.win.close_tab(1)
        self.assertEqual(self.win.tabs.count(), 1)
        self.assertIsNone(self.tree.hoisted)

    def test_tab_of_deleted_branch_falls_back(self):
        self.select("Recipes")
        self.win.open_branch_tab()
        self.win.tabs.setCurrentIndex(0)
        self.select("Recipes")
        self.win.delete_node(confirm=False)
        self.win.tabs.setCurrentIndex(1)
        self.assertIsNone(self.tree.hoisted)
        self.assertEqual(self.win.tabs.tabText(1), "My notes")

    def test_new_file_resets_tabs(self):
        self.select("Recipes")
        self.win.open_branch_tab()
        self.win.new_file(confirm=False)
        self.assertEqual(self.win.tabs.count(), 1)
        self.assertIsNone(self.tree.hoisted)

    # ------------------------------------------------------------ backlinks and tags

    def test_backlinks(self):
        self.find("Work").body = "See [node://My notes/Recipes/Soup] and [www.example.com]"
        self.find("Recipes").body = 'Also "node://my notes/recipes/soup"'
        self.assertEqual([i.title for i in self.win.backlinks(self.find("Soup"))], ["Recipes", "Work"])
        self.assertEqual(self.win.backlinks(self.find("Work")), [])
        self.win.backlinks_panel.show()
        self.select("Soup")
        self.win.refresh_info()
        self.assertEqual(self.win.backlinks_panel.list.count(), 2)
        self.assertIn("2 notes link", self.win.backlinks_panel.label.text())
        self.win.backlinks_panel.list.noteActivated.emit(self.find("Work"))
        self.assertEqual(self.tree.currentItem().title, "Work")

    def test_backlinks_see_unsaved_typing(self):
        self.select("Work")
        self.win.editor.setPlainText("[node://My notes/Work]... and [node://My notes/Recipes]")
        self.assertEqual([i.title for i in self.win.backlinks(self.find("Recipes"))], ["Work"])

    def test_tags_panel(self):
        self.find("Soup").body = "Lentils #recipe #quick"
        self.find("Work").body = "#Quick notes"
        self.win.tags_panel.show()
        self.win.refresh_info()
        self.assertEqual(self.win.tags_panel.tag_names(), ["quick", "recipe"])
        self.assertTrue(self.win.tags_panel.select_tag("QUICK"))
        notes = self.win.tags_panel.notes
        self.assertEqual([notes.item(i).text() for i in range(notes.count())], ["Soup", "Work"])
        notes.noteActivated.emit(self.find("Work"))
        self.assertEqual(self.tree.currentItem().title, "Work")

    # ------------------------------------------------------------ word count

    def test_word_count(self):
        self.select("Work")
        self.win.editor.setPlainText("one two  three\nfour")
        self.win.refresh_info()
        self.assertEqual(self.win.words_label.text().strip(), "4 words")
        cur = self.win.editor.textCursor()
        cur.setPosition(0)
        cur.setPosition(7, QTextCursor.KeepAnchor)
        self.win.editor.setTextCursor(cur)
        self.assertEqual(self.win.words_label.text().strip(), "2 of 4 words")
        rows = {r[0]: r for r in self.win.word_counts()}
        self.assertEqual(rows["Selection"][1], 2)
        self.assertEqual(rows["This note"][1:], (4, 19, 1))
        self.assertEqual(rows["Whole file"][3], 4)

    # ------------------------------------------------------------ changed on disk

    def _change_on_disk(self, text="changed elsewhere"):
        time.sleep(0.01)
        doc = hjt.load(self.sample)
        doc.top_nodes[0].text = text
        hjt.save(doc, self.sample)

    def test_reload_when_changed_by_another_program(self):
        asked = []
        self.win._ask_reload = lambda name, modified: asked.append((name, modified)) or True
        self._change_on_disk()
        self.win.check_disk()
        self.assertEqual(asked, [("notes.hjt", False)])
        self.assertEqual(self.find("My notes").body, "changed elsewhere")
        self.win.check_disk()           # nothing new: no second question
        self.assertEqual(len(asked), 1)

    def test_keep_mine_and_confirm_before_overwriting(self):
        self.win._ask_reload = lambda name, modified: False
        self.win.editor.setPlainText("mine")
        self._change_on_disk()
        self.win.check_disk()
        self.assertEqual(self.win.editor.toPlainText(), "mine")
        self.assertTrue(self.win.save())     # kept: Save overwrites without asking again
        self.assertEqual(hjt.load(self.sample).top_nodes[0].text, "mine")
        # Changed again, then saved without looking: ask first.
        self._change_on_disk("theirs")
        asked = []
        self.win._confirm_overwrite = lambda name: asked.append(name) or False
        self.win.editor.setPlainText("mine again")
        self.assertFalse(self.win.save())
        self.assertEqual(asked, ["notes.hjt"])
        self.assertEqual(hjt.load(self.sample).top_nodes[0].text, "theirs")

    def test_own_save_is_not_reported(self):
        self.win._ask_reload = lambda name, modified: self.fail("asked about our own save")
        self.win.editor.setPlainText("saved here")
        self.assertTrue(self.win.save())
        self.win.check_disk()

    def test_deleted_file(self):
        os.remove(self.sample)
        self.win.check_disk()
        self.assertTrue(self.win.isWindowModified())
        self.assertTrue(self.win.save())
        self.assertTrue(os.path.exists(self.sample))

    # ------------------------------------------------------------ spelling

    @unittest.skipUnless(LANGS, "no Hunspell dictionary installed")
    def test_spell_check_in_window(self):
        self.assertTrue(self.win.act_spell.isChecked())
        self.assertIsNotNone(self.win.speller)
        word = "Twigpadd"
        self.assertFalse(self.win.speller.check(word))
        self.win.add_to_dictionary(word)
        self.assertTrue(self.win.speller.check(word))
        self.assertIn(word, self.settings.value("spell/words"))
        self.win.act_spell.setChecked(False)
        self.assertIsNone(self.win.speller)
        self.assertIsNone(self.win.link_highlighter.speller)
        self.win.act_spell.setChecked(True)
        self.assertIsNotNone(self.win.link_highlighter.speller)

    @unittest.skipUnless(LANGS, "no Hunspell dictionary installed")
    def test_replace_word_from_suggestion(self):
        self.win.editor.setPlainText("a speling test")
        cur = self.win.editor.textCursor()
        cur.setPosition(4)
        word, start, end = self.win._word_at(cur)
        self.assertEqual(word, "speling")
        self.win._replace_word(start, end, "spelling")
        self.assertEqual(self.win.editor.toPlainText(), "a spelling test")


if __name__ == "__main__":
    unittest.main()
