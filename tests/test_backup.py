# SPDX-License-Identifier: GPL-3.0-or-later
"""Backup and restore, for moving to a new computer."""
import json
import os
import shutil
import tempfile
import unittest
import zipfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QSettings  # noqa: E402
from PyQt5.QtWidgets import QApplication  # noqa: E402

from twigpad import backup  # noqa: E402
from twigpad.ui import backupdialog, popups  # noqa: E402
from twigpad.ui.mainwindow import MainWindow  # noqa: E402

app = QApplication.instance() or QApplication([])


class BackupCoreTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.old_home = os.path.join(self.dir, "old", "home", "ann")
        self.new_home = os.path.join(self.dir, "new", "home", "bob")
        os.makedirs(os.path.join(self.old_home, "Notes"))
        os.makedirs(self.new_home)
        self.a = self.write(os.path.join(self.old_home, "Notes", "work.hjt"), b"<Treepad version 3.0>\nwork")
        self.b = self.write(os.path.join(self.old_home, "diary.twig"), b"TWIGPAD-ENCRYPTED secret")
        self.zip = os.path.join(self.dir, backup.default_name())

    def tearDown(self):
        shutil.rmtree(self.dir)

    @staticmethod
    def write(path, data):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as fh:
            fh.write(data)
        return path

    def test_backup_holds_files_and_manifest(self):
        saved = backup.create(self.zip, [self.a, self.b, self.a, "/nope/missing.hjt"], None, "0.1",
                              home=self.old_home)
        self.assertEqual([e.original for e in saved], [self.a, self.b])   # no duplicates, no missing
        manifest = backup.read_manifest(self.zip)
        self.assertEqual(manifest["home"], self.old_home)
        self.assertFalse(manifest["settings"])
        with zipfile.ZipFile(self.zip) as zf:
            self.assertEqual(zf.read(saved[1].member), b"TWIGPAD-ENCRYPTED secret")

    def test_restore_on_new_computer_skips_files_already_there(self):
        backup.create(self.zip, [self.a, self.b], None, home=self.old_home)
        # On the new computer the diary is already there (same), work.hjt is not.
        self.write(os.path.join(self.new_home, "diary.twig"), b"TWIGPAD-ENCRYPTED secret")
        plan = backup.plan(self.zip, os.path.join(self.new_home, "Restored"), home=self.new_home)
        status = {os.path.basename(p.target): p.status for p in plan}
        self.assertEqual(status, {"work.hjt": backup.NEW, "diary.twig": backup.SAME})
        self.assertEqual(plan[0].target, os.path.join(self.new_home, "Notes", "work.hjt"))
        self.assertEqual(backup.restore_files(self.zip, plan), [])
        with open(plan[0].target, "rb") as fh:
            self.assertEqual(fh.read(), b"<Treepad version 3.0>\nwork")
        # A second restore changes nothing.
        again = backup.plan(self.zip, os.path.join(self.new_home, "Restored"), home=self.new_home)
        self.assertTrue(all(p.status == backup.SAME for p in again))

    def test_different_file_already_there_is_left_alone(self):
        backup.create(self.zip, [self.b], None, home=self.old_home)
        mine = self.write(os.path.join(self.new_home, "diary.twig"), b"newer diary")
        plan = backup.plan(self.zip, self.dir, home=self.new_home)
        self.assertEqual(plan[0].status, backup.EXISTS)
        backup.restore_files(self.zip, plan)
        with open(mine, "rb") as fh:
            self.assertEqual(fh.read(), b"newer diary")

    def test_unusable_folder_goes_to_fallback(self):
        if os.geteuid() == 0:
            self.skipTest("root can write anywhere")
        odd = self.write(os.path.join(self.dir, "usb", "x.hjt"), b"x")
        backup.create(self.zip, [odd], None, home=self.old_home)
        shutil.rmtree(os.path.join(self.dir, "usb"))
        os.chmod(self.dir, 0o555)
        try:
            plan = backup.plan(self.zip, os.path.join(self.new_home, "Restored"), home=self.new_home)
        finally:
            os.chmod(self.dir, 0o755)
        self.assertEqual(plan[0].target, os.path.join(self.new_home, "Restored", "x.hjt"))

    def test_damaged_or_foreign_zip(self):
        with zipfile.ZipFile(self.zip, "w") as zf:
            zf.writestr("hello.txt", "hi")
        with self.assertRaises(backup.BackupError):
            backup.read_manifest(self.zip)
        with open(self.zip, "wb") as fh:
            fh.write(b"not a zip")
        with self.assertRaises(backup.BackupError):
            backup.read_manifest(self.zip)
        with zipfile.ZipFile(self.zip, "w") as zf:
            zf.writestr(backup.MANIFEST, json.dumps({"format": backup.FORMAT, "version": 99, "files": []}))
        with self.assertRaisesRegex(backup.BackupError, "newer"):
            backup.read_manifest(self.zip)

    def test_path_mapping(self):
        self.assertEqual(backup.map_path("/home/ann/Notes/a.hjt", "/home/ann", "/home/bob"),
                         "/home/bob/Notes/a.hjt")
        self.assertEqual(backup.map_path("/home/anna/a.hjt", "/home/ann", "/home/bob"), "/home/anna/a.hjt")
        self.assertEqual(backup.map_path("/media/usb/a.hjt", "/home/ann", "/home/bob"), "/media/usb/a.hjt")


class BackupWindowTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.answers = []
        popups.auto_answer = lambda dlg: self.answers.append(dlg.title_label.text()) or None
        self.win = MainWindow(QSettings(os.path.join(self.dir, "s.ini"), QSettings.IniFormat))

    def tearDown(self):
        popups.auto_answer = None
        self.win.setWindowModified(False)
        self.win.close()
        self.win.deleteLater()
        app.processEvents()
        shutil.rmtree(self.dir)

    def test_back_up_and_restore_settings_and_files(self):
        notes = os.path.join(self.dir, "notes.hjt")
        self.win.tree.topLevelItem(0).setText(0, "Hello")
        self.assertTrue(self.win._write(notes))
        self.win.settings.setValue("view/theme", "dark")
        self.win.settings.setValue("spell/words", ["Twigpad", "hoisting"])
        zip_path = os.path.join(self.dir, "b.zip")
        self.assertTrue(self.win.make_backup(zip_path))
        self.assertEqual(self.answers[-1], "Backup saved")
        manifest = backup.read_manifest(zip_path)
        self.assertTrue(manifest["settings"])
        self.assertEqual([f["original"] for f in manifest["files"]], [notes])

        # A "new computer": other settings, and the notes file is gone.
        other = MainWindow(QSettings(os.path.join(self.dir, "new.ini"), QSettings.IniFormat))
        try:
            os.remove(notes)
            plan = other.restore_backup(zip_path, confirm=False)
            self.assertEqual(self.answers[-1], "Restore finished")
            self.assertTrue(os.path.exists(notes))
            self.assertEqual(plan[0].status, backup.NEW)
            self.assertEqual(other.settings.value("view/theme"), "dark")
            self.assertTrue(other.act_themes["dark"].isChecked())
            self.assertIn(notes, other.recent_files())
            # Restoring again leaves everything alone.
            plan = other.restore_backup(zip_path, confirm=False)
            self.assertEqual(plan[0].status, backup.SAME)
        finally:
            other.set_theme("auto")
            other.close()
            other.deleteLater()

    def test_restore_rejects_other_zips(self):
        bad = os.path.join(self.dir, "x.zip")
        with zipfile.ZipFile(bad, "w") as zf:
            zf.writestr("a.txt", "a")
        self.assertIsNone(self.win.restore_backup(bad, confirm=False))
        self.assertEqual(self.answers[-1], "This is not a Twigpad backup")

    def test_menu(self):
        file_menu = next(a.menu() for a in self.win.menuBar().actions() if a.text() == "&File")
        sub = next(a.menu() for a in file_menu.actions() if a.menu() and "Backup" in a.text())
        self.assertEqual(sub.actions(), [self.win.act_make_backup, self.win.act_restore_backup])

    def test_candidates_are_open_and_recent_files(self):
        a = os.path.join(self.dir, "a.hjt")
        open(a, "w").close()
        self.win.settings.setValue("files/recent", [a, os.path.join(self.dir, "gone.hjt"), a])
        self.assertEqual(backupdialog.backup_candidates(self.win), [a])


if __name__ == "__main__":
    unittest.main()
