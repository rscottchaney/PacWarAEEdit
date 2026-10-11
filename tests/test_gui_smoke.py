import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

SAVE_015 = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "going2_411210.pws")


@unittest.skipUnless(os.path.exists(SAVE_015), "sample save missing")
class GuiSmokeTests(unittest.TestCase):
    def setUp(self):
        import tkinter as tk
        try:
            self.root = tk.Tk()
        except tk.TclError:
            self.skipTest("no display")
        self.root.withdraw()

    def tearDown(self):
        self.root.destroy()

    def test_builds_and_loads(self):
        import witpae_editor
        app = witpae_editor.EditorApp(self.root)
        self.assertTrue(app.load(SAVE_015))
        self.root.update()
        self.assertEqual(len(app.tree.get_children()), 781)
        app.search_var.set("pearl")
        app.side_var.set("Allied")
        app.refresh_list()
        self.assertEqual(app.tree.get_children(), ("584",))
        app.tree.selection_set("584")
        self.root.update()
        self.assertEqual(app.field_vars["supply"].get(), "982531")
        app.field_vars["supply"].set("5")
        app.apply()
        self.assertEqual(app.bases[584].get("supply"), 5)
        self.assertIn(584, app.edited)
        self.assertTrue(app.dirty)
        app.sort_by("supply")
        self.root.update()

    def test_load_folder_gives_clear_error(self):
        from unittest import mock
        import witpae_editor
        app = witpae_editor.EditorApp(self.root)
        with mock.patch.object(witpae_editor.messagebox, "showerror") as err:
            self.assertFalse(app.load(os.path.dirname(SAVE_015)))
        self.assertIn("folder", err.call_args[0][1])
        self.assertIsNone(app.save)


if __name__ == "__main__":
    unittest.main()
