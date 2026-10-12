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

    def test_stockpile_checkbox_applies(self):
        import witpae_editor
        app = witpae_editor.EditorApp(self.root)
        self.assertTrue(app.load(SAVE_015))
        app.tree.selection_set("506")
        self.root.update()
        self.assertFalse(any(v.get() for v in app.stockpile_vars.values()))
        app.stockpile_vars["fuel"].set(True)
        app.apply()
        self.assertTrue(app.bases[506].get_stockpile()["fuel"])
        self.assertTrue(app.building_vars["port"].get())
        app.building_vars["port"].set(False)
        app.apply()
        self.assertFalse(app.bases[506].get_building()["port"])
        self.assertTrue(app.bases[506].get_building()["forts"])
        self.assertFalse(app.bases[506].get_stockpile()["supply"])
        self.assertIn(506, app.edited)
        self.assertTrue(app.dirty)

    def test_factory_edit_applies(self):
        from witpae import factories
        import witpae_editor
        app = witpae_editor.EditorApp(self.root)
        self.assertTrue(app.load(SAVE_015))
        self.assertEqual(app.factory_tree.get_children(), ())
        app.tree.selection_set("506")
        self.root.update()
        self.assertEqual(len(app.factory_tree.get_children()), 20)
        app.factory_tree.selection_set("2")  # Oil
        self.root.update()
        self.assertTrue(app.factory_production_check.instate(["disabled"]))
        self.assertTrue(app.factory_upgrade_check.instate(["disabled"]))
        self.assertEqual(app.factory_tree.set("2", "upgrade"), "-")
        self.assertEqual(app.factory_tree.set("8", "available"), "42/10")
        app.factory_tree.selection_set("4")  # Refinery
        self.root.update()
        self.assertFalse(app.factory_production_check.instate(["disabled"]))
        app.factory_production_var.set(False)
        app.apply_factory()
        self.assertFalse(factories.get_factory(app.bases[506], 4).production_on)
        self.assertIn(506, app.edited)
        self.assertTrue(app.dirty)
        self.assertEqual(app.factory_tree.selection(), ("4",))
        self.assertEqual(app.factory_tree.set("4", "production"), "No")
        app.tree.selection_remove("506")
        app.show_detail(None)
        self.assertEqual(app.factory_tree.get_children(), ())

    def test_aircraft_tab_edit_applies(self):
        from unittest import mock
        import witpae_editor
        app = witpae_editor.EditorApp(self.root)
        self.assertTrue(app.load(SAVE_015))
        self.assertEqual(len(app.aircraft_tree.get_children()), 555)
        app.aircraft_search_var.set("SBD-3")
        self.assertIn("260", app.aircraft_tree.get_children())
        self.assertIn("487", app.aircraft_tree.get_children())
        app.aircraft_tree.selection_set("487")
        self.root.update()
        self.assertEqual(app.aircraft_vars["speed"].get(), "250")
        self.assertEqual(app.aircraft_vars["from"].get(), "12/41")
        self.assertEqual(len(app.aircraft_weapon_trees["max"].get_children()), 4)
        app.aircraft_vars["speed"].set("260")
        app.apply_aircraft()
        self.assertEqual(app.aircraft[487].get("speed"), 260)
        self.assertIn(487, app.aircraft_edited)
        self.assertTrue(app.dirty)
        self.assertEqual(app.aircraft_tree.item("487", "tags"), ("edited",))
        app.aircraft_vars["from"].set("13/41")
        with mock.patch.object(witpae_editor.messagebox, "showerror") as err:
            app.apply_aircraft()
        self.assertTrue(err.called)
        self.assertEqual(app.aircraft[487].get_date("from"), (12, 41))
        app.sort_aircraft_by("from")
        self.assertTrue(app.load(SAVE_015))
        self.assertEqual(app.aircraft_edited, set())

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
