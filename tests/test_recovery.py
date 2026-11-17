# SPDX-License-Identifier: GPL-3.0-or-later
"""Crash recovery: copies of unsaved changes, offered back after a crash."""
import json
import os
import shutil
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QSettings  # noqa: E402
from PyQt5.QtWidgets import QApplication  # noqa: E402

from twigpad import recovery, twig  # noqa: E402
from twigpad.model import Document, Node  # noqa: E402
from twigpad.ui import popups  # noqa: E402
from twigpad.ui.mainwindow import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.old_folder = recovery.FOLDER
        recovery.FOLDER = os.path.join(self.dir, "recovery")
        self.answers = []
        self.windows = []

    def tearDown(self):
        popups.auto_answer = None
        for win in self.windows:
            win.setWindowModified(False)
            win.close()
            win.deleteLater()
        app.processEvents()
        recovery.FOLDER = self.old_folder
        shutil.rmtree(self.dir)

    def window(self):
        win = MainWindow(QSettings(os.path.join(self.dir, f"s{len(self.windows)}.ini"), QSettings.IniFormat))
        self.windows.append(win)
        return win

    def answer(self, *keys):
        keys = list(keys)
        popups.auto_answer = lambda d: self.answers.append(d.title_label.text()) or keys.pop(0)

    def crash(self, win):
        """Lose the window without closing it, as in a crash."""
        win.recovery_timer.stop()
        win._drop_recovery = lambda: None
        self.windows.remove(win)

    def pending(self):
        return recovery.pending(running=lambda pid: False)

    def test_copy_written_only_with_unsaved_changes(self):
        win = self.window()
        self.assertFalse(win.write_recovery())
        win.tree.topLevelItem(0).setText(0, "Changed")
        win.setWindowModified(True)
        self.assertTrue(win.write_recovery())
        self.assertFalse(win.write_recovery())          # nothing new since
        self.assertEqual(len(self.pending()), 1)
        self.assertEqual(recovery.pending(), [])        # this Twigpad is still running
        win.setWindowModified(False)                    # saved: the copy goes
        self.assertEqual(self.pending(), [])

    def test_closing_normally_removes_the_copy(self):
        win = self.window()
        win.setWindowModified(True)
        win.write_recovery()
        self.answer("discard")                          # Don't Save
        win.close()
        self.assertEqual(self.pending(), [])

    def test_recover_after_crash(self):
        path = os.path.join(self.dir, "notes.twig")
        doc = Document()
        doc.root.add_child(Node("My notes", "old text"))
        twig.save(doc, path)
        win = self.window()
        self.assertTrue(win.load_path(path))
        win.tree.topLevelItem(0).body = "new text that was never saved"
        win.setWindowModified(True)
        self.assertTrue(win.write_recovery())
        self.crash(win)

        entries = recovery.pending(running=lambda pid: False)
        self.assertEqual([(e.name, e.original) for e in entries], [("notes.twig", path)])
        fresh = self.window()
        recovery_pending = recovery.pending
        recovery.pending = lambda running=None: recovery_pending(running=lambda pid: False)
        try:
            self.answer("recover")
            self.assertTrue(fresh.check_recovery())
        finally:
            recovery.pending = recovery_pending
        self.assertEqual(self.answers, ["Recover unsaved changes?"])
        self.assertEqual(fresh.tree.topLevelItem(0).body, "new text that was never saved")
        self.assertEqual(fresh.path, path)               # Save goes back to the original file
        self.assertTrue(fresh.isWindowModified())
        ids = os.listdir(recovery.FOLDER)
        self.assertEqual(ids, [fresh._recovery_id])      # the old copy is gone, the new window has its own
        self.assertTrue(fresh.save())
        self.assertEqual(twig.load(path).top_nodes[0].text, "new text that was never saved")
        self.assertEqual(os.listdir(recovery.FOLDER), [])

    def test_not_now_keeps_and_discard_deletes(self):
        win = self.window()
        win.setWindowModified(True)
        win.write_recovery()
        self.crash(win)
        fresh = self.window()
        real = recovery.pending
        recovery.pending = lambda running=None: real(running=lambda pid: False)
        try:
            self.answer("later")
            self.assertFalse(fresh.check_recovery())
            self.assertEqual(len(real(running=lambda pid: False)), 1)
            self.answer("discard", "cancel")             # changed their mind
            fresh.check_recovery()
            self.assertEqual(len(real(running=lambda pid: False)), 1)
            self.answer("discard", "ok")
            fresh.check_recovery()
            self.assertEqual(real(running=lambda pid: False), [])
        finally:
            recovery.pending = real

    @unittest.skipUnless(twig.encryption_available(), "PyCryptodome is not installed")
    def test_protected_file_copy_stays_encrypted(self):
        win = self.window()
        win.crypto = twig.derive_key("s3cret")
        win.tree.topLevelItem(0).body = "secret diary"
        win.setWindowModified(True)
        win.write_recovery()
        entry = self.pending()[0]
        with open(entry.data_path, "rb") as fh:
            data = fh.read()
        self.assertTrue(twig.is_encrypted(data))
        self.assertNotIn(b"secret diary", data)
        self.assertEqual(twig.load(entry.data_path, "s3cret").top_nodes[0].text, "secret diary")

    def test_unsaved_new_file(self):
        win = self.window()
        win.setWindowModified(True)
        win.write_recovery()
        entry = self.pending()[0]
        self.assertEqual((entry.name, entry.original), ("Untitled", ""))
        with open(os.path.join(recovery.FOLDER, entry.id, recovery.META)) as fh:
            self.assertEqual(json.load(fh)["pid"], os.getpid())

    def test_half_written_and_running_copies_are_ignored(self):
        os.makedirs(os.path.join(recovery.FOLDER, "broken"))
        with open(os.path.join(recovery.FOLDER, "broken", recovery.META), "w") as fh:
            fh.write("{not json")
        self.assertEqual(self.pending(), [])
        self.assertTrue(recovery.is_running(os.getpid()))
        self.assertFalse(recovery.is_running(2 ** 22 + 12345))


if __name__ == "__main__":
    unittest.main()
