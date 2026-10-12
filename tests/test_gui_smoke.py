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
        app.aircraft_vars["pool"].set("15")
        app.apply_aircraft()
        self.assertEqual(app.aircraft[487].get("speed"), 260)
        self.assertEqual(app.aircraft[487].pool, 15)
        self.assertEqual(app.aircraft_tree.set("487", "pool"), "15")
        self.assertIn(487, app.aircraft_edited)
        self.assertTrue(app.dirty)
        self.assertEqual(app.aircraft_tree.item("487", "tags"), ("edited",))
        app.aircraft_vars["pool"].set("-1")
        with mock.patch.object(witpae_editor.messagebox, "showerror") as err:
            app.apply_aircraft()
        self.assertTrue(err.called)
        self.assertEqual(app.aircraft[487].pool, 15)
        app.aircraft_vars["from"].set("13/41")
        with mock.patch.object(witpae_editor.messagebox, "showerror") as err:
            app.apply_aircraft()
        self.assertTrue(err.called)
        self.assertEqual(app.aircraft[487].get_date("from"), (12, 41))
        app.sort_aircraft_by("from")
        self.assertTrue(app.load(SAVE_015))
        self.assertEqual(app.aircraft_edited, set())

    def test_ships_tab_edit_applies(self):
        import witpae_editor
        app = witpae_editor.EditorApp(self.root)
        self.assertTrue(app.load(SAVE_015))
        self.assertEqual(len(app.ship_tree.get_children()), 1721)
        app.ship_search_var.set("Lexington")
        self.assertEqual(set(app.ship_tree.get_children()), {str(i) for i in range(674, 680)})
        self.assertEqual(app.ship_tree.set("675", "date"), "3/42")
        app.ship_tree.selection_set("674")
        self.root.update()
        self.assertEqual(app.ship_vars["speed"].get(), "33")
        self.assertEqual(len(app.ship_weapon_tree.get_children()), 13)
        app.ship_vars["speed"].set("35")
        app.apply_ship()
        self.assertEqual(app.ships[674].get("speed"), 35)
        self.assertIn(674, app.ships_edited)
        self.assertTrue(app.dirty)
        self.assertEqual(app.ship_tree.item("674", "tags"), ("edited",))
        self.root.update()  # let the list refresh's reselect event settle first
        app.ship_weapon_tree.selection_set("2")
        self.root.update()
        self.assertEqual(app.ship_weapon_vars["face"].get(), "RS")
        app.ship_weapon_vars["num"].set("8")
        app.ship_weapon_vars["face"].set("LS")
        app.apply_ship_weapon()
        w = app.ships[674].get_weapon(2)
        self.assertEqual((w["num"], w["face"]), (8, 4))
        self.assertEqual(app.ship_weapon_tree.selection(), ("2",))
        self.assertTrue(app.load(SAVE_015))
        self.assertEqual(app.ships_edited, set())

    def test_air_groups_tab_edit_applies(self):
        from witpae import airgroups
        import witpae_editor
        app = witpae_editor.EditorApp(self.root)
        self.assertTrue(app.load(SAVE_015))
        self.assertEqual(len(app.group_tree.get_children()), 2895)
        app.group_search_var.set("19th TS")
        self.assertIn("4205", app.group_tree.get_children())
        app.group_tree.selection_set("4205")
        self.root.update()
        self.assertEqual(app.group_vars["morale"].get(), "50")
        self.assertEqual(set(app.pilot_tree.get_children()), {"5041", "18570"})
        self.assertEqual(app.leader_name.get(), "Dionne E.")
        app.group_vars["morale"].set("60")
        app.apply_group()
        self.assertEqual(app.groups[4205].get("morale"), 60)
        self.assertIn(4205, app.groups_edited)
        self.assertTrue(app.dirty)
        self.assertEqual(app.group_tree.item("4205", "tags"), ("edited",))
        self.root.update()  # let the list refresh's reselect event settle first
        app.pilot_tree.selection_set("18570")
        self.root.update()
        self.assertEqual(app.pilot_vars["skill_air"].get(), "20")
        app.pilot_vars["skill_air"].set("33")
        app.apply_pilot()
        pilot = next(p for p in app.pilot_index[4205] if p.id == 18570)
        self.assertEqual(pilot.get("skill_air"), 33)
        self.assertEqual(app.pilot_tree.set("18570", "skill_air"), "33")
        app.leader_vars["leadership"].set("77")
        app.apply_leader()
        self.assertEqual(airgroups.get_leader(app.save, 27701).get("leadership"), 77)
        app.leader_vars["leadership"].set("100")
        from unittest import mock
        with mock.patch.object(witpae_editor.messagebox, "showerror") as err:
            app.apply_leader()
        self.assertTrue(err.called)
        self.assertEqual(airgroups.get_leader(app.save, 27701).get("leadership"), 77)
        app.group_search_var.set("")
        app.group_tree.selection_set("4156")  # no commander
        self.root.update()
        self.assertTrue(app.leader_button.instate(["disabled"]))
        self.assertTrue(app.load(SAVE_015))
        self.assertEqual(app.groups_edited, set())

    def test_land_units_tab_edit_applies(self):
        from unittest import mock
        import witpae_editor
        app = witpae_editor.EditorApp(self.root)
        self.assertTrue(app.load(SAVE_015))
        self.assertGreater(len(app.unit_tree.get_children()), 1000)
        self.assertNotIn("584", app.unit_tree.get_children())  # a base
        app.unit_search_var.set("1/153rd")
        self.assertIn("5639", app.unit_tree.get_children())
        app.unit_tree.selection_set("5639")
        self.root.update()
        self.assertEqual(app.unit_vars["morale"].get(), "52")
        self.assertEqual(len(app.unit_equipment_tree.get_children()), 6)
        app.unit_vars["morale"].set("75")
        app.apply_unit()
        self.assertEqual(app.units[5639].get("morale"), 75)
        self.assertIn(5639, app.units_edited)
        self.assertTrue(app.dirty)
        self.assertEqual(app.unit_tree.item("5639", "tags"), ("edited",))
        self.root.update()  # let the list refresh's reselect event settle first
        app.unit_equipment_tree.selection_set("0")
        self.root.update()
        self.assertEqual(app.unit_equipment_vars["count"].get(), "28")
        app.unit_equipment_vars["count"].set("25")
        app.apply_unit_equipment()
        self.assertEqual(app.units[5639].get_equipment(0)["count"], 25)
        self.assertEqual(app.unit_equipment_tree.set("0", "count"), "25")
        app.unit_equipment_vars["disabled"].set("26")
        with mock.patch.object(witpae_editor.messagebox, "showerror") as err:
            app.apply_unit_equipment()
        self.assertTrue(err.called)
        self.assertEqual(app.units[5639].get_equipment(0)["disabled"], 3)
        self.assertTrue(app.load(SAVE_015))
        self.assertEqual(app.units_edited, set())

    def test_add_land_unit_equipment(self):
        from unittest import mock
        import witpae_editor
        app = witpae_editor.EditorApp(self.root)
        self.assertTrue(app.load(SAVE_015))
        self.assertTrue(app.unit_add_button.instate(["disabled"]))
        app.unit_tree.selection_set("5639")  # Allied
        self.root.update()
        values = app.unit_add_box.cget("values")
        self.assertIn("Dutch Rifle Squad (367)", values)
        self.assertNotIn("IJA Infantry Squad (264)", values)
        self.assertFalse(app.unit_add_button.instate(["disabled"]))
        app.unit_add_device_var.set("Dutch Rifle Squad (367)")
        app.unit_add_vars["count"].set("9")
        app.unit_add_vars["disabled"].set("4")
        app.add_unit_equipment()
        self.root.update()
        self.assertEqual(app.units[5639].get_equipment(5)["device"], "Dutch Rifle Squad")
        self.assertEqual(app.unit_equipment_tree.set("5", "device"), "Dutch Rifle Squad")
        self.assertEqual(app.unit_equipment_tree.selection(), ("5",))
        self.assertEqual((app.unit_equipment_vars["count"].get(), app.unit_equipment_vars["disabled"].get()),
                         ("9", "4"))
        self.assertIn(5639, app.units_edited)
        self.assertTrue(app.dirty)
        self.assertEqual(app.unit_add_vars["count"].get(), "")
        # A device from the other side is refused and nothing changes.
        app.unit_add_device_var.set("IJA Infantry Squad (264)")
        app.unit_add_vars["count"].set("3")
        with mock.patch.object(witpae_editor.messagebox, "showerror") as err:
            app.add_unit_equipment()
        self.assertTrue(err.called)
        self.assertEqual(len(app.unit_equipment_tree.get_children()), 7)

    def test_move_air_group_and_land_unit(self):
        from unittest import mock
        import witpae_editor
        app = witpae_editor.EditorApp(self.root)
        self.assertTrue(app.load(SAVE_015))
        app.group_tree.selection_set("3626")
        self.root.update()
        self.assertEqual(app.group_tree.set("3626", "location"), "Pearl Harbor")
        values = app.group_move_box.cget("values")
        self.assertIn("Midway Island (581)", values)
        self.assertIn("Chungking (1091)", values)
        self.assertNotIn("Akita (222)", values)
        self.assertFalse(app.group_move_button.instate(["disabled"]))
        app.group_move_var.set("Midway Island (581)")
        app.move_group()
        self.assertEqual(app.groups[3626].location_id, 581)
        self.assertIn(3626, app.groups_edited)
        self.assertTrue(app.dirty)
        self.assertEqual(app.group_tree.set("3626", "location"), "Midway Island")
        app.group_tree.selection_set("144")  # aboard a ship
        self.root.update()
        self.assertTrue(app.group_move_button.instate(["disabled"]))
        self.assertIn("ship", app.group_move_note.get())

        self.assertTrue(app.load(SAVE_015))
        self.assertFalse(app.dirty)
        app.unit_tree.selection_set("5560")
        self.root.update()
        self.assertIn("Midway Island (581)", app.unit_move_box.cget("values"))
        app.unit_move_var.set("Midway Island (581)")
        app.move_unit()
        self.assertEqual((app.units[5560].location_id, app.units[5560].target_id), (581, 581))
        self.assertIn(5560, app.units_edited)
        self.assertTrue(app.dirty)
        self.assertEqual(app.unit_info["location"].get(), "581 Midway Island")
        app.unit_tree.selection_set("6652")  # on the march
        self.root.update()
        self.assertTrue(app.unit_move_button.instate(["disabled"]))
        self.assertIn("march", app.unit_move_note.get())
        app.unit_tree.selection_set("5639")
        self.root.update()
        app.unit_move_var.set("")
        with mock.patch.object(witpae_editor.messagebox, "showerror") as err:
            app.move_unit()
        self.assertTrue(err.called)

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
