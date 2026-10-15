import os
import tempfile
import unittest

from witpae import bases
from witpae.container import SaveFile
from witpae.fileio import is_pbem, save_with_backup

SAVE_015 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "going2_411210.pws")


@unittest.skipUnless(os.path.exists(SAVE_015), "sample save missing")
class BackupTests(unittest.TestCase):
    def test_existing_file_is_backed_up(self):
        sf = SaveFile.load(SAVE_015)
        bases.set_title(sf, "changed")
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "x.pws")
            with open(path, "wb") as fh:
                fh.write(b"original")
            backup = save_with_backup(sf, path)
            self.assertEqual(backup, path + ".bak")
            with open(backup, "rb") as fh:
                self.assertEqual(fh.read(), b"original")
            self.assertEqual(SaveFile.load(path).description, "changed")

    def test_new_file_has_no_backup(self):
        sf = SaveFile.load(SAVE_015)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "new.pws")
            self.assertIsNone(save_with_backup(sf, path))
            self.assertFalse(os.path.exists(path + ".bak"))

    def test_pbem_save_is_refused_and_nothing_is_written(self):
        sf = SaveFile.load(SAVE_015)
        self.assertFalse(is_pbem(sf))
        bases.set_title(sf, "(PBEM) game Date: 12/10/41")
        self.assertTrue(is_pbem(sf))
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "x.pws")
            with open(path, "wb") as fh:
                fh.write(b"original")
            with self.assertRaisesRegex(PermissionError, "PBEM"):
                save_with_backup(sf, path)
            with open(path, "rb") as fh:
                self.assertEqual(fh.read(), b"original")
            self.assertFalse(os.path.exists(path + ".bak"))
            new = os.path.join(tmp, "new.pws")
            with self.assertRaises(PermissionError):
                save_with_backup(sf, new)
            self.assertFalse(os.path.exists(new))

    def test_pbem_only_as_a_title_prefix(self):
        sf = SaveFile.load(SAVE_015)
        bases.set_title(sf, "game (PBEM)")
        self.assertFalse(is_pbem(sf))


if __name__ == "__main__":
    unittest.main()
