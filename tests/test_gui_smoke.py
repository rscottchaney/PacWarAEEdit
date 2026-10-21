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
        self.assertEqual(len(app.tree.get_children()), 781 + 271 + 102)
        app.search_var.set("pearl")
        app.side_var.set("Allied")
        app.refresh_list()
        self.assertEqual(app.tree.get_children(), ("584",))
        app.tree.selection_set("584")
        self.root.update()
        self.assertEqual(app.field_vars["supply"].get(), "982531")
        for name in ("supply_cap", "garrison_allied", "garrison_japanese"):
            self.assertIn(name, app.field_vars)
        app.field_vars["supply"].set("5")
        app.apply()
        self.assertEqual(app.bases[584].get("supply"), 5)
        self.assertIn(584, app.edited)
        self.assertTrue(app.dirty)
        app.sort_by("supply")
        self.root.update()

    def test_pbem_save_cannot_be_saved_even_after_retitling(self):
        import tempfile
        from unittest import mock
        import witpae_editor
        from witpae import bases
        from witpae.container import SaveFile
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "pbem.pws")
            sf = SaveFile.load(SAVE_015)
            bases.set_title(sf, "(PBEM) game")
            sf.save(src)
            app = witpae_editor.EditorApp(self.root)
            self.assertTrue(app.load(src))
            self.assertTrue(app.pbem)
            self.assertIn("PBEM", app.status.get())
            app.title_var.set("not pbem")
            out = os.path.join(tmp, "out.pws")
            with mock.patch.object(witpae_editor.messagebox, "showerror") as err,                     mock.patch.object(witpae_editor.filedialog, "asksaveasfilename", return_value=out) as ask:
                app.save_as()
            err.assert_called_once()
            ask.assert_not_called()
            self.assertFalse(os.path.exists(out))
            self.assertTrue(app.load(SAVE_015))
            self.assertFalse(app.pbem)
    def test_town_row_and_port_lock(self):
        from unittest import mock
        import witpae_editor
        app = witpae_editor.EditorApp(self.root)
        self.assertTrue(app.load(SAVE_015))
        app.tree.selection_set("696")
        self.root.update()
        self.assertEqual(app.tree.set("696", "kind"), "Town")
        for name in ("port", "port_max", "port_damage"):
            self.assertTrue(app.field_entries[name].instate(["disabled"]), name)
        self.assertTrue(app.building_checks["port"].instate(["disabled"]))
        self.assertFalse(app.field_entries["supply"].instate(["disabled"]))
        app.field_vars["supply"].set("77")
        with mock.patch("tkinter.messagebox.showerror") as err:
            app.apply()
        err.assert_not_called()
        self.assertEqual(app.bases[696].get("supply"), 77)
        self.assertIn(696, app.edited)
        app.tree.selection_set("584")
        self.root.update()
        for name in ("port", "port_max", "port_damage"):
            self.assertFalse(app.field_entries[name].instate(["disabled"]), name)
        self.assertFalse(app.building_checks["port"].instate(["disabled"]))

    def test_minor_place_row_and_locks(self):
        from unittest import mock
        import witpae_editor
        from witpae import bases
        app = witpae_editor.EditorApp(self.root)
        self.assertTrue(app.load(SAVE_015))
        app.tree.selection_set("233")
        self.root.update()
        self.assertEqual(app.tree.set("233", "kind"), "Minor")
        self.assertIn("Kofu", app.detail_title.get())
        for name in bases.MINOR_READONLY_FIELDS:
            self.assertTrue(app.field_entries[name].instate(["disabled"]), name)
        for name in bases.MINOR_READONLY_BUILD:
            self.assertTrue(app.building_checks[name].instate(["disabled"]), name)
        self.assertFalse(app.field_entries["supply"].instate(["disabled"]))
        self.assertFalse(app.building_checks["forts"].instate(["disabled"]))
        app.field_vars["supply"].set("88")
        with mock.patch("tkinter.messagebox.showerror") as err:
            app.apply()
        err.assert_not_called()
        self.assertEqual(app.bases[233].get("supply"), 88)
        self.assertIn(233, app.edited)
        self.assertTrue(app.tree.item("233", "tags"))
        app.tree.selection_set("584")
        self.root.update()
        self.assertFalse(app.field_entries["airfield"].instate(["disabled"]))
        self.assertFalse(app.building_checks["airfield"].instate(["disabled"]))
        # Not move destinations, and not in the spoilage report.
        label = "Kofu (233)"
        self.assertNotIn(label, app.place_ids)
        self.assertTrue(all(p.id != 233 for p, _label in app.tf_dest_items))
        self.assertNotIn("233", app.spoilage_tree.get_children())
        self.assertTrue(all(app.bases[int(i)].kind != "Minor" for i in app.spoilage_tree.get_children()))

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

    def test_aircraft_pictures_and_comparison(self):
        import witpae_editor
        from witpae import aircraft
        better = aircraft.BETTER
        has_art = os.path.exists(os.path.join(os.path.dirname(SAVE_015), "..", "..", "..", "ART", "J_PlaneSide.bmp"))
        app = witpae_editor.EditorApp(self.root)
        self.assertTrue(app.load(SAVE_015))
        last = app.reports_notebook.tabs()[-1]
        self.assertEqual(app.reports_notebook.tab(last, "text"), "Aircraft comparison")
        col_a, col_b = app.compare_cols
        # Defaults: the first Japanese and the first Allied fighter.
        model_a = app.aircraft[app.compare_ids[col_a["model"].get()]]
        model_b = app.aircraft[app.compare_ids[col_b["model"].get()]]
        self.assertEqual((model_a.side_id, model_a.type), (0, "Fighter"))
        self.assertEqual((model_b.side_id, model_b.type), (1, "Fighter"))
        rows = [app.compare_tree.item(i, "values") for i in app.compare_tree.get_children()]
        self.assertEqual([r[0] for r in rows[:2]], ["Type", "Nation"])
        self.assertTrue(any(r[1].startswith(better) or r[2].startswith(better) for r in rows))
        # Filters narrow the model list; a model that no longer fits is cleared and the table emptied.
        col_a["side"].set("Allied")
        app.refresh_compare_choices(col_a)
        values = col_a["model_box"].cget("values")
        self.assertTrue(values and all(app.aircraft[app.compare_ids[v]].side_id == 1 for v in values))
        self.assertEqual(col_a["model"].get(), "")
        self.assertEqual(app.compare_tree.get_children(), ())
        col_a["type"].set("Dive Bomber")
        app.refresh_compare_choices(col_a)
        values = col_a["model_box"].cget("values")
        self.assertTrue(values and all(app.aircraft[app.compare_ids[v]].type == "Dive Bomber" for v in values))
        # Choosing models fills the table for both columns.
        col_a["model"].set("SBD-3 Dauntless (#487), USN")
        col_b["model"].set("A6M2 Zero (#603), IJN")
        app.refresh_compare_table()
        rows = {app.compare_tree.item(i, "values")[0]: app.compare_tree.item(i, "values")
                for i in app.compare_tree.get_children()}
        self.assertEqual(rows["Upgrade"][1:], ("488 SBD-5 Dauntless", "604 A6M2 Sen Baku"))
        self.assertEqual(rows["Max speed"][1:], ("250", better + "331"))
        self.assertIn("Armament, reduced load", rows)
        # Pictures, and the Aircraft tab's own.
        app.aircraft_tree.selection_set("603")
        self.root.update()
        if has_art:
            self.assertTrue(str(col_a["picture"].cget("image")))
            self.assertTrue(str(col_b["picture"].cget("image")))
            self.assertTrue(str(app.aircraft_picture.cget("image")))
            self.assertEqual(col_b["picture"].cget("text"), "")
        else:
            self.assertIn("No picture", app.aircraft_picture.cget("text"))
        self.assertEqual(app.aircraft_info["upgrade"].get(), "604 A6M2 Sen Baku (unverified)")
        # "Compare as" sends the Aircraft tab's model to a column.
        app.compare_aircraft(0)
        self.assertEqual(col_a["model"].get(), "A6M2 Zero (#603), IJN")
        self.assertEqual(col_a["side"].get(), "All")

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
        for name in ("capacity", "troop_capacity", "bulk_cargo", "liquid_cargo"):
            self.assertIn(name, app.ship_vars)
        app.ship_search_var.set("Harris")
        app.ship_tree.selection_set("2443")  # Troop Capacity 1700
        self.root.update()
        self.assertEqual(app.ship_vars["troop_capacity"].get(), "1700")
        app.ship_search_var.set("Lexington")
        app.ship_tree.selection_set("674")
        self.root.update()
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

    def test_ship_records_tab_edit_applies(self):
        import witpae_editor
        app = witpae_editor.EditorApp(self.root)
        self.assertTrue(app.load(SAVE_015))
        tabs = [app.notebook.tab(i, "text") for i in range(app.notebook.index("end"))]
        self.assertEqual(tabs[tabs.index("Ship Classes") + 1], "Ships")
        self.assertEqual(len(app.shiprec_tree.get_children()), 10757)
        app.shiprec_side_var.set("Japanese")
        app.refresh_shiprec_list()
        self.assertNotIn("3144", app.shiprec_tree.get_children())
        app.shiprec_side_var.set("Allied")
        app.shiprec_search_var.set("maryland")
        self.assertIn("3144", app.shiprec_tree.get_children())
        self.assertEqual(app.shiprec_tree.set("3144", "location"), "Pearl Harbor")
        app.shiprec_tree.selection_set("3144")
        self.root.update()
        self.assertEqual(app.shiprec_vars["fuel"].get(), "4700")
        self.assertEqual(app.shiprec_vars["maj_float_dmg"].get(), "23")
        self.assertEqual(app.shiprec_info["base"].get(), "Pearl Harbor")
        app.shiprec_vars["fuel"].set("4000")
        app.shiprec_vars["sys_dmg"].set("10")
        app.apply_shiprec()
        self.assertEqual(app.shiprecs[3144].get("fuel"), 4000)
        self.assertIn(3144, app.shiprecs_edited)
        self.assertTrue(app.dirty)
        self.assertEqual(app.shiprec_tree.item("3144", "tags"), ("edited",))
        self.root.update()
        app.shiprec_weapon_tree.selection_set("0")
        self.root.update()
        self.assertEqual(app.shiprec_weapon_vars["num"].get(), "4")
        app.shiprec_weapon_vars["num"].set("6")
        app.apply_shiprec_weapon()
        self.assertEqual(app.shiprecs[3144].get_weapon(0)["num"], 6)
        self.assertEqual(app.shiprec_weapon_tree.selection(), ("0",))
        app.repair_shiprec()
        self.assertEqual(app.shiprec_vars["float_dmg"].get(), "0")
        self.assertEqual(app.shiprecs[3144].get("maj_eng_dmg"), 0)
        self.assertTrue(app.load(SAVE_015))
        self.assertEqual(app.shiprecs_edited, set())

    def test_ship_records_tab_moves_ship(self):
        import witpae_editor
        app = witpae_editor.EditorApp(self.root)
        self.assertTrue(app.load(SAVE_015))
        app.shiprec_search_var.set("elliot")
        app.shiprec_tree.selection_set("4342")
        self.root.update()
        self.assertEqual(app.shiprec_info["tf"].get(), "14409 USN minesweepers (flagship Elliot)")
        labels = list(app.shiprec_move_box.cget("values"))
        self.assertIn("Pearl Harbor (port)", labels)
        self.assertIn("TF 14416 Pearl Harbor Patrol (1 ships)", labels)
        self.assertEqual(str(app.shiprec_move_button.cget("state")), "normal")
        app.shiprec_move_var.set("Pearl Harbor (port)")
        app.move_shiprec()
        self.assertEqual(app.shiprec_tree.set("4342", "location"), "Pearl Harbor")
        self.assertEqual(app.shiprec_info["tf"].get(), "none")
        self.assertEqual(app.shiprec_info["base"].get(), "Pearl Harbor")
        self.assertIn(4342, app.shiprecs_edited)
        self.assertEqual(app.shiprec_tree.item("4342", "tags"), ("edited",))
        self.assertTrue(app.dirty)
        # The Task Forces tab follows a move made here: count, new flagship, edited mark.
        self.assertEqual(app.tf_tree.set("14409", "ships"), "3")
        self.assertEqual(app.tf_tree.set("14409", "flagship"), "Long")
        self.assertIn(14409, app.tfs_edited)
        # Now docked: the TFs at Pearl are offered, not another port.
        labels = list(app.shiprec_move_box.cget("values"))
        self.assertIn("TF 14409 USN minesweepers (3 ships)", labels)
        self.assertFalse([l for l in labels if l.endswith("(port)")])
        # A lone ship has nowhere to go and the Move button is disabled.
        app.shiprec_search_var.set("")
        app.shiprec_tree.selection_set("3684")
        self.root.update()
        self.assertEqual(app.shiprec_destinations, [])
        self.assertIn("disabled", app.shiprec_move_button.state())
        self.assertTrue(app.load(SAVE_015))
        self.assertEqual(app.shiprecs_edited, set())

    def test_task_forces_tab(self):
        from unittest import mock
        import witpae_editor
        app = witpae_editor.EditorApp(self.root)
        self.assertTrue(app.load(SAVE_015))
        self.root.update()
        tabs = [app.notebook.tab(t, "text") for t in app.notebook.tabs()]
        self.assertEqual(tabs[tabs.index("Ships") + 1], "Task Forces")
        self.assertEqual(len(app.tf_tree.get_children()), 236)
        app.tf_side_var.set("Japanese")
        app.refresh_tf_list()
        self.assertNotIn("14409", app.tf_tree.get_children())
        app.tf_side_var.set("Allied")
        app.tf_search_var.set("minesweepers")
        self.assertEqual(app.tf_tree.get_children(), ("14409",))
        self.assertEqual(app.tf_tree.item("14409", "values"),
                         ("14409", "USN minesweepers", "Allied", "Pearl Harbor (in port)", "Surface Combat", "-", "4", "Elliot"))
        app.sort_tfs_by("ships")
        app.sort_tfs_by("location")
        app.tf_tree.selection_set("14409")
        self.root.update()
        self.assertEqual(app.tf_title.get(), "USN minesweepers (TF 14409)")
        self.assertEqual(app.tf_info["location"].get(), "Pearl Harbor (in port)")
        grid = app.tf_ship_tree
        self.assertEqual(grid.get_children(), ("4315", "4324", "4326", "4342"))
        self.assertEqual(grid.set("4342", "flag"), "*")
        self.assertEqual(grid.set("4326", "flag"), "")
        self.assertEqual(grid.set("4315", "fuel"), "435/435")
        with mock.patch.object(witpae_editor.messagebox, "showerror") as err:
            app.tf_flag_var.set("Long (4326)")
            app.set_tf_flagship()
            self.assertEqual(app.taskforces[14409].flagship, 4326)
            self.assertEqual(grid.set("4326", "flag"), "*")
            self.assertIn(14409, app.tfs_edited)
            self.assertEqual(app.tf_tree.item("14409", "tags"), ("edited",))
            self.assertEqual(app.tf_tree.set("14409", "flagship"), "Long")
            self.assertTrue(app.dirty)
            # Move Elliot to the port.
            self.root.update()  # let the list's re-selection event settle
            grid.selection_set("4342")
            self.root.update()
            self.assertEqual(app.tf_ship_current, 4342)
            self.assertIn("Pearl Harbor (port)", app.tf_move_box.cget("values"))
            app.tf_move_var.set("Pearl Harbor (port)")
            app.move_tf_ship()
            self.assertEqual(grid.get_children(), ("4315", "4324", "4326"))
            self.assertEqual(app.tf_tree.set("14409", "ships"), "3")
            self.assertEqual(app.shiprec_tree.set("4342", "location"), "Pearl Harbor")
            self.assertEqual(app.shiprec_tree.item("4342", "tags"), ("edited",))
            self.assertEqual(app.tf_move_note.get(), "select a ship")
            self.root.update()
            # Add Zane from port.
            zane = "%s (4319)" % app.shiprecs[4319].name
            self.assertIn(zane, app.tf_add_box.cget("values"))
            app.tf_add_var.set(zane)
            app.add_tf_ship()
            self.assertEqual(grid.get_children(), ("4315", "4319", "4324", "4326"))
            self.assertEqual(app.tf_tree.set("14409", "ships"), "4")
            self.assertEqual(app.shiprec_tree.set("4319", "location"), "TF 14409")
            self.assertIn(4319, app.shiprecs_edited)
            # Quick edits: Dorsey is damaged; nothing is short of fuel until we lower one.
            self.assertEqual(grid.set("4324", "sys"), "1")
            app.repair_tf()
            self.assertEqual(grid.set("4324", "sys"), "0")
            app.shiprecs[4315].set("fuel", 10)
            app.show_tf(app.taskforces[14409])
            self.assertEqual(grid.set("4315", "fuel"), "10/435")
            app.refuel_tf()
            self.assertEqual(grid.set("4315", "fuel"), "435/435")
            self.assertEqual(app.shiprecs[4315].get("fuel"), 435)
            app.repair_tf()  # nothing left to do
            app.refuel_tf()
            err.assert_not_called()
        self.assertIn(4324, app.shiprecs_edited)

    def test_task_force_orders(self):
        from unittest import mock
        import witpae_editor
        app = witpae_editor.EditorApp(self.root)
        self.assertTrue(app.load(SAVE_015))
        self.root.update()
        app.tf_tree.selection_set("14409")
        self.root.update()
        self.assertEqual(app.tf_info["mission"].get(), "02 - Surface Combat")
        self.assertEqual(app.tf_info["home_port"].get(), "Pearl Harbor (584)")
        self.assertEqual(app.tf_info["destination"].get(), "-")
        with mock.patch.object(witpae_editor.messagebox, "showerror") as err:
            app.tf_mission_var.set("23 - Local Minesweeper")
            app.set_tf_mission()
            self.assertEqual(app.tf_tree.set("14409", "mission"), "Local Minesweeper")
            self.assertEqual(app.tf_info["mission"].get(), "23 - Local Minesweeper")
            self.assertIn(14409, app.tfs_edited)
            self.assertTrue(app.dirty)
            home = app.tf_home_box.cget("values")
            self.assertIn("Lahaina (577)", home)
            self.assertNotIn("Akita (222)", home)  # the other side's port
            self.assertNotIn("Boise (501)", home)  # no port
            app.tf_home_var.set("Lahaina (577)")
            app.set_tf_home_port()
            self.assertEqual(app.taskforces[14409].home_port, 577)
            self.assertEqual(app.tf_info["home_port"].get(), "Lahaina (577)")
            total = len(app.tf_dest_box.cget("values"))
            self.assertEqual(total, 1052)
            app.tf_dest_filter_var.set("LAHAI")
            self.assertEqual(app.tf_dest_box.cget("values"), ("Lahaina (577, Allied)",))
            app.tf_dest_var.set("Lahaina (577, Allied)")
            app.set_tf_destination()
            self.assertEqual(app.taskforces[14409].destination, 577)
            self.assertEqual(app.tf_tree.set("14409", "destination"), "Lahaina")
            self.assertEqual(app.tf_info["destination"].get(), "Lahaina (577)")
            app.tf_dest_filter_var.set("")
            self.assertEqual(len(app.tf_dest_box.cget("values")), total)
            err.assert_not_called()
            # A refusal shows an error and writes nothing.
            app.tf_dest_filter_var.set("pearl")
            app.tf_dest_var.set("Pearl Harbor (584, Allied)")
            app.set_tf_destination()
            err.assert_called_once()
            self.assertEqual(app.taskforces[14409].destination, 577)

    def test_air_groups_tab_edit_applies(self):
        from witpae import airgroups
        import witpae_editor
        app = witpae_editor.EditorApp(self.root)
        self.assertTrue(app.load(SAVE_015))
        self.assertEqual(len(app.group_tree.get_children()), 2895)
        for side, count in (("Allied", 2004), ("Japanese", 891), ("All", 2895)):
            app.group_side_var.set(side)
            app.refresh_group_list()
            self.assertEqual(len(app.group_tree.get_children()), count, side)
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

    def test_air_group_schedule_and_dates(self):
        from unittest import mock
        from witpae import airgroups
        import witpae_editor
        app = witpae_editor.EditorApp(self.root)
        self.assertTrue(app.load(SAVE_015))
        app.group_tree.selection_set("1694")
        self.root.update()
        self.assertEqual(app.group_info["formation"].get(), "Squadron")
        self.assertEqual([(d.get(), s.get()) for d, s in app.schedule_vars],
                         [("Jul 1942", "36"), ("Jan 1944", "40"), ("Jul 1944", "42"), ("Jan 1945", "36"), ("", "")])
        app.group_vars["withdraw"].set("14 Dec 43")
        app.group_vars["return_date"].set("15 Feb 1944")
        app.group_vars["max_size"].set("30")
        app.apply_group()
        g = app.groups[1694]
        self.assertEqual((g.get("withdraw"), g.get("return_date"), g.get("max_size")), (431214, 440215, 30))
        self.assertEqual(app.group_vars["withdraw"].get(), "14 Dec 1943")
        self.assertIn(1694, app.groups_edited)
        app.schedule_vars[4][0].set("Jul 46")
        app.schedule_vars[4][1].set("20")
        app.apply_schedule()
        self.assertEqual(g.size_schedule()[4], (4607, 20))
        self.assertEqual(app.schedule_vars[4][0].get(), "Jul 1946")
        # Bad input is refused and changes nothing.
        before = bytes(app.save[airgroups.GROUP_SECTION].data)
        app.schedule_vars[0][0].set("-")
        with mock.patch.object(witpae_editor.messagebox, "showerror") as err:
            app.apply_schedule()
        self.assertTrue(err.called)
        app.group_vars["withdraw"].set("31 Feb 1943")
        with mock.patch.object(witpae_editor.messagebox, "showerror") as err:
            app.apply_group()
        self.assertTrue(err.called)
        self.assertEqual(bytes(app.save[airgroups.GROUP_SECTION].data), before)
        # Groups that have not arrived are still editable for schedule data.
        app.group_tree.selection_set("2")
        self.root.update()
        app.schedule_vars[0][0].set("Mar 42")
        app.schedule_vars[0][1].set("12")
        app.apply_schedule()
        self.assertEqual(app.groups[2].size_schedule()[0], (4203, 12))

    def test_pilot_pool_grid(self):
        from unittest import mock
        from witpae import pilotpool
        import witpae_editor
        app = witpae_editor.EditorApp(self.root)
        self.assertTrue(app.load(SAVE_015))
        self.root.update()
        tabs = [app.groups_notebook.tab(t, "text") for t in app.groups_notebook.tabs()]
        self.assertEqual(tabs, ["Groups", "Pilot pool"])
        shown = app.pool_tree.get_children()
        self.assertIn("1", shown)
        self.assertNotIn("10", shown)  # French pool is empty
        self.assertEqual(app.pool_tree.set("4", "pool"), "6770")
        self.assertEqual(app.pool_tree.set("4", "t1"), "606 (0)")
        self.assertEqual(app.pool_tree.set("4", "training"), str(sum(app.pools[4].counts)))
        app.pool_empty_var.set(True)
        app.refresh_pool_list()
        self.assertEqual(len(app.pool_tree.get_children()), 18)
        app.pool_empty_var.set(False)
        app.pool_side_var.set("Japanese")
        app.refresh_pool_list()
        japanese = app.pool_tree.get_children()
        self.assertIn("1", japanese)
        self.assertTrue(set(japanese) <= {"1", "2"})
        app.pool_side_var.set("Allied")
        app.refresh_pool_list()
        self.assertNotIn("1", app.pool_tree.get_children())
        self.assertIn("4", app.pool_tree.get_children())
        app.pool_tree.selection_set("4")
        self.root.update()
        self.assertEqual((app.pool_vars["pool"].get(), app.pool_vars["rate"].get(), app.pool_vars["count1"].get(),
                          app.pool_vars["exp11"].get()), ("6770", "600", "558", "33"))
        app.pool_vars["pool"].set("7000")
        app.pool_vars["exp3"].set("12")
        with mock.patch.object(witpae_editor.messagebox, "showerror") as err:
            app.apply_pool()
        err.assert_not_called()
        self.assertEqual((app.pools[4].get("pool"), app.pools[4].get("exp3")), (7000, 12))
        self.assertIn(4, app.pools_edited)
        self.assertTrue(app.dirty)
        self.assertEqual(app.pool_tree.item("4", "tags"), ("edited",))
        self.assertEqual(app.pool_tree.set("4", "pool"), "7000")
        self.assertIn("USN", app.status.get())
        # Bad input is refused and writes nothing.
        before = bytes(app.save[pilotpool.SECTION].data)
        for name, text in (("rate", "-1"), ("exp0", "100"), ("count2", "x"), ("pool", "32768")):
            self.root.update()
            app.show_pool(app.pools[4])
            app.pool_vars[name].set(text)
            with mock.patch.object(witpae_editor.messagebox, "showerror") as err:
                app.apply_pool()
            err.assert_called_once()
            self.assertEqual(bytes(app.save[pilotpool.SECTION].data), before, name)
        self.assertTrue(app.load(SAVE_015))
        self.assertEqual(app.pools_edited, set())
        self.assertFalse(app.dirty)

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

    def test_change_air_group_aircraft(self):
        from unittest import mock
        import witpae_editor
        app = witpae_editor.EditorApp(self.root)
        self.assertTrue(app.load(SAVE_015))
        self.assertTrue(app.group_aircraft_button.instate(["disabled"]))
        app.group_tree.selection_set("4020")
        self.root.update()
        self.assertFalse(app.group_aircraft_button.instate(["disabled"]))
        values = app.group_aircraft_box.cget("values")
        self.assertIn("P-40E Warhawk (342, 12/41)", values)
        self.assertNotIn("A6M2 Zero (603, 12/41)", values)
        self.assertTrue(all(app.save and app.aircraft[app.aircraft_ids[v]].side_id == 1 for v in values))
        app.group_aircraft_var.set("P-40E Warhawk (155, 3/42)")
        app.change_group_aircraft()
        self.assertEqual((app.groups[4020].aircraft_id, app.groups[4020].upgrade_id), (155, 342))
        self.assertIn(4020, app.groups_edited)
        self.assertTrue(app.dirty)
        self.assertEqual(app.group_tree.set("4020", "aircraft"), "P-40E Warhawk")
        self.assertEqual(app.group_info["aircraft"].get(), "155 P-40E Warhawk")
        self.assertEqual(app.group_info["upgrade"].get(), "342 P-40E Warhawk")
        self.assertEqual(app.group_upgrade_box.cget("values"), values)
        app.group_upgrade_var.set("P-40B Warhawk (341, 12/41)")
        app.change_group_upgrade()
        self.assertEqual((app.groups[4020].aircraft_id, app.groups[4020].upgrade_id), (155, 341))
        self.assertEqual(app.group_info["upgrade"].get(), "341 P-40B Warhawk")
        app.group_aircraft_var.set("")
        app.group_upgrade_var.set("")
        with mock.patch("witpae_editor.messagebox.showerror") as err:
            app.change_group_aircraft()
            app.change_group_upgrade()
        self.assertEqual(err.call_count, 2)

    def test_air_group_plane_status(self):
        from unittest import mock
        import witpae_editor
        app = witpae_editor.EditorApp(self.root)
        self.assertTrue(app.load(SAVE_015))
        self.assertTrue(app.plane_apply_button.instate(["disabled"]))
        app.group_tree.selection_set("4020")
        self.root.update()
        self.assertEqual([app.plane_vars[k].get() for k in ("ready", "maintenance", "damaged", "reserve")],
                         ["11", "6", "3", "0"])
        self.assertEqual(app.plane_total.get(), "20")
        self.assertFalse(app.plane_apply_button.instate(["disabled"]))
        app.plane_vars["ready"].set("8")
        app.plane_vars["maintenance"].set("5")
        app.plane_vars["damaged"].set("6")
        app.plane_vars["reserve"].set("1")
        app.apply_planes()
        g = app.groups[4020]
        self.assertEqual((g.ready, g.maintenance, g.damaged, g.reserve, g.planes), (8, 5, 6, 1, 20))
        self.assertIn(4020, app.groups_edited)
        self.assertTrue(app.dirty)
        self.assertEqual(app.plane_vars["damaged"].get(), "6")
        # A wrong sum and a non-number are refused and change nothing.
        app.plane_vars["ready"].set("9")
        with mock.patch.object(witpae_editor.messagebox, "showerror") as err:
            app.apply_planes()
        self.assertTrue(err.called)
        app.plane_vars["ready"].set("x")
        with mock.patch.object(witpae_editor.messagebox, "showerror") as err:
            app.apply_planes()
        self.assertTrue(err.called)
        self.assertEqual((g.ready, g.maintenance, g.damaged, g.reserve), (8, 5, 6, 1))
        app.repair_planes()
        self.assertEqual((g.ready, g.maintenance, g.damaged, g.reserve), (19, 0, 0, 1))
        self.assertEqual(app.plane_vars["ready"].get(), "19")
        app.group_tree.selection_set("2")  # not arrived
        self.root.update()
        self.assertTrue(app.plane_apply_button.instate(["disabled"]))
        self.assertTrue(app.plane_repair_button.instate(["disabled"]))
        self.assertTrue(all(e.instate(["disabled"]) for e in app.plane_entries))
        self.assertEqual(app.plane_vars["ready"].get(), "10")
        self.assertIn("not arrived", app.plane_note.get())

    def test_reports_tab(self):
        import witpae_editor
        app = witpae_editor.EditorApp(self.root)
        self.assertEqual(app.game_date_var.get(), "Game date: unknown")
        self.assertTrue(app.load(SAVE_015))
        self.root.update()
        self.assertEqual(app.game_date_var.get(), "Game date: 10 Dec 1941")
        self.assertEqual(len(app.spoilage_tree.get_children()), 7)
        self.assertEqual(app.spoilage_tree.get_children()[0], "369")  # largest total excess first
        self.assertEqual(app.spoilage_tree.set("731", "supply_over"), "-")
        self.assertEqual(app.spoilage_tree.set("731", "fuel_over"), "7238")
        app.spoilage_side_var.set("Japanese")
        app.refresh_spoilage_list()
        self.assertNotIn("582", app.spoilage_tree.get_children())
        app.sort_spoilage_by("fuel")
        app.sort_spoilage_by("fuel")
        app.spoilage_side_var.set("All")
        app.refresh_spoilage_list()
        # Due within: Maryland is due in 1 month, Kanawha in 6.
        app.upgrade_due_var.set("1 month")
        app.refresh_upgrade_list()
        self.assertIn("3144", app.upgrade_tree.get_children())
        self.assertNotIn("4988", app.upgrade_tree.get_children())
        self.assertEqual(app.upgrade_tree.set("3144", "due"), "1 month")
        self.assertEqual(app.upgrade_tree.set("3144", "date"), "1/42")
        app.upgrade_due_var.set("All")
        app.refresh_upgrade_list()
        self.assertIn("4988", app.upgrade_tree.get_children())
        app.upgrade_search_var.set("kanawha")  # matches the class name too
        self.assertEqual(app.upgrade_tree.get_children(), ("4986", "4987", "4988", "4989", "4990"))
        app.upgrade_search_var.set("neches")
        self.assertEqual(app.upgrade_tree.get_children(), ("4989",))
        app.upgrade_search_var.set("kanawha")
        self.assertEqual(app.upgrade_tree.set("4988", "target"), "Kanawha #2389")
        app.sort_upgrades_by("ship")
        # Jumping clears the filters of the target tab so the row is visible.
        app.shiprec_search_var.set("zzz")
        app.upgrade_tree.selection_set("4988")
        app.jump_to_upgrade_ship()
        self.root.update()
        self.assertEqual(app.notebook.select(), str(app.shiprec_tab))
        self.assertEqual(app.shiprec_tree.selection(), ("4988",))
        app.search_var.set("zzz")
        app.spoilage_tree.selection_set("731")
        app.jump_to_spoilage_base()
        self.root.update()
        self.assertEqual(app.notebook.select(), str(app.bases_tab))
        self.assertEqual(app.tree.selection(), ("731",))
        # Edits are picked up when the Reports tab is shown again.
        app.bases[731].set("fuel", 0)
        app.notebook.select(app.reports_tab)
        self.root.update()
        self.assertNotIn("731", app.spoilage_tree.get_children())

    def test_industry_reports(self):
        import witpae_editor
        app = witpae_editor.EditorApp(self.root)
        self.assertTrue(app.load(SAVE_015))
        self.root.update()
        # Industry: Allied by default, one row per factory type present.
        self.assertEqual(app.industry_side_var.get(), "Allied")
        self.assertEqual(app.industry_tree.set("Resources", "count"), "252")
        self.assertEqual(app.industry_tree.set("Resources", "size"), "25,969")
        self.assertEqual(app.industry_tree.set("Heavy Industry", "output"), "14,548 HI, 14,548 supply")
        self.assertEqual(app.industry_tree.set("Heavy Industry", "input"), "145,480 resources, 14,548 fuel")
        self.assertEqual(app.industry_tree.set("Aircraft", "input"), "67.8 HI")
        self.assertEqual(app.balance_tree.set("supply", "produced"), "40,049")
        self.assertEqual(app.balance_tree.set("manpower", "stored"), "17,555")
        self.assertEqual(app.balance_tree.set("hi", "stored"), "37,846")
        self.assertEqual(app.balance_tree.set("supply", "allotted"), "98,992")
        self.assertEqual(app.balance_tree.set("supply", "net"), "+139,041")
        self.assertEqual(app.balance_tree.set("oil", "net"), "-15,270")
        self.assertEqual(app.balance_tree.set("oil", "days"), "10")
        self.assertEqual(app.balance_tree.set("fuel", "days"), "-")
        app.industry_region_var.set("Continental US")
        app.refresh_industry_report()
        self.assertNotEqual(app.industry_tree.set("Resources", "count"), "252")
        self.assertEqual(app.balance_tree.set("manpower", "stored"), "17,555")  # side-wide pool
        self.assertEqual(app.balance_tree.set("manpower", "days"), "-")
        app.industry_side_var.set("Japanese")
        app.industry_region_var.set("All regions")
        app.refresh_industry_report()
        self.assertEqual(app.balance_tree.set("armament", "stored"), "18,387")
        self.assertEqual(app.balance_tree.set("supply", "allotted"), "0")
        app.industry_side_var.set("Allied")
        app.industry_region_var.set("Continental US")
        app.refresh_industry_report()
        app.industry_side_var.set("Japanese")
        app.industry_region_var.set("All regions")
        app.refresh_industry_report()
        self.assertIn("Oil", app.industry_tree.get_children())
        self.assertNotEqual(app.industry_tree.set("Oil", "size"), "6,133")
        app.industry_side_var.set("Allied")
        app.refresh_industry_report()

        # Unreadable pools (section missing) must not stop the report; pool rows show "?".
        from witpae import industry as industry_module
        saved = app.save._by_id.pop(industry_module.POOL_SECTION)
        app.refresh_industry_report()
        self.assertEqual(app.balance_tree.set("manpower", "stored"), "?")
        self.assertEqual(app.balance_tree.set("supply", "produced"), "40,049")
        app.save._by_id[industry_module.POOL_SECTION] = saved
        app.refresh_industry_report()

        # Factories
        everything = len(app.factory_report_tree.get_children())
        self.assertGreater(everything, 500)
        self.assertEqual(app.factory_report_tree.set("506:0", "region"), "Continental US")
        app.factory_report_type_var.set("Resources")
        app.refresh_factory_report()
        self.assertTrue(all(app.factory_report_tree.set(i, "factory") == "Resources" for i in app.factory_report_tree.get_children()))
        app.factory_report_type_var.set("All types")
        app.factory_report_side_var.set("Japanese")
        app.refresh_factory_report()
        self.assertTrue(all(app.factory_report_tree.set(i, "side") == "Japanese" for i in app.factory_report_tree.get_children()))
        app.factory_report_side_var.set("All")
        app.factory_report_region_var.set("Unassigned")
        app.refresh_factory_report()
        self.assertTrue(all(app.factory_report_tree.set(i, "region") == "Unassigned" for i in app.factory_report_tree.get_children()))
        app.factory_report_region_var.set("All regions")
        app.factory_report_problem_var.set(True)
        app.refresh_factory_report()
        damaged = len(app.factory_report_tree.get_children())
        self.assertTrue(0 < damaged < everything)
        app.factory_report_problem_var.set(False)
        app.sort_factory_report_by("size")
        app.sort_factory_report_by("size")
        self.assertEqual(len(app.factory_report_tree.get_children()), everything)
        sizes = [int(app.factory_report_tree.set(i, "size")) for i in app.factory_report_tree.get_children()]
        self.assertEqual(sizes, sorted(sizes, reverse=True))

        # Raw materials
        rows = len(app.raw_tree.get_children())
        self.assertIn("926", app.raw_tree.get_children())  # Corunna Downs, a minor place
        self.assertEqual(app.raw_tree.set("926", "kind"), "Minor")
        self.assertEqual(app.raw_tree.set("615", "allotment"), "40,000 fuel, 65,000 supply")  # Eastern USA
        self.assertEqual(app.raw_tree.set("926", "allotment"), "-")
        shortest = [app.raw_tree.set(i, "shortest") for i in app.raw_tree.get_children()]
        self.assertTrue(shortest[0].endswith(("day", "days")) and shortest[0] != "-")
        self.assertEqual(shortest[-1], "-")
        app.raw_only_var.set(False)
        app.refresh_raw_list()
        self.assertGreater(len(app.raw_tree.get_children()), rows)
        app.raw_only_var.set(True)
        app.raw_side_var.set("Japanese")
        app.raw_region_var.set("Japan")
        app.refresh_raw_list()
        self.assertNotIn("926", app.raw_tree.get_children())
        app.raw_side_var.set("All")
        app.raw_region_var.set("All regions")
        app.sort_raw_by("resources")
        app.refresh_raw_list()
        self.assertIn("926", app.raw_tree.get_children())

        # Double-click targets: bases and minor places open the Bases tab.
        app.search_var.set("zzz")
        app.raw_tree.selection_set("506")
        app.jump_to_industry_place(app.raw_tree)
        self.root.update()
        self.assertEqual(app.notebook.select(), str(app.bases_tab))
        self.assertEqual(app.tree.selection(), ("506",))
        app.notebook.select(app.reports_tab)
        app.factory_report_tree.selection_set("506:0")
        app.search_var.set("zzz")
        app.jump_to_industry_place(app.factory_report_tree)
        self.assertEqual(app.tree.selection(), ("506",))
        app.notebook.select(app.reports_tab)
        app.search_var.set("zzz")
        app.raw_tree.selection_set("926")
        app.jump_to_industry_place(app.raw_tree)
        self.root.update()
        self.assertEqual(app.notebook.select(), str(app.bases_tab))
        self.assertEqual(app.tree.selection(), ("926",))
        app.notebook.select(app.reports_tab)

        # Edits in the Bases tab show up when the Reports tab is shown again.
        from witpae import factories
        before = app.industry_tree.set("Heavy Industry", "output")
        place, f = next((p, f) for p in app.industry_places if p.base.side == "Allied"
                        for f in factories.list_factories(p.base) if f.type == 521 and f.size > 0)
        factories.set_factory(place.base, f.slot, f.size, f.damage, False, f.repair_on)
        app.notebook.select(app.bases_tab)
        app.notebook.select(app.reports_tab)
        self.root.update()
        self.assertNotEqual(app.industry_tree.set("Heavy Industry", "output"), before)

    def test_air_production_reports(self):
        import witpae_editor
        app = witpae_editor.EditorApp(self.root)
        self.assertTrue(app.load(SAVE_015))
        self.root.update()
        tabs = [app.reports_notebook.tab(t, "text") for t in app.reports_notebook.tabs()]
        self.assertEqual(tabs[-3:-1], ["Air production", "Engines"])
        self.assertEqual(tabs.index("Raw materials") + 1, tabs.index("Air production"))
        # Air production: the Zero is Japanese, built by one factory (place 236, slot 6).
        shown = len(app.air_tree.get_children())
        self.assertGreater(shown, 100)
        self.assertEqual(app.air_count.get(), f"{shown} models")
        self.assertEqual(app.air_tree.set("603", "engines"), "1 x Nakajima Ha-35")
        self.assertEqual(app.air_tree.set("603", "size"), "56")
        self.assertEqual(app.air_tree.set("603", "planes_day"), "1.9")
        self.assertEqual(app.air_tree.set("603", "hi_day"), "33.6")
        self.assertEqual(app.air_tree.set("2", "engines_day"), "-")
        self.assertEqual(app.air_tree.set("2", "engines"), "2 engines")
        self.assertEqual(app.air_tree.set("603", "next_group"), "112")
        self.assertEqual(app.air_tree.set("332", "research"), "20")
        app.air_only_var.set(False)
        app.refresh_air_list()
        self.assertGreater(len(app.air_tree.get_children()), shown)
        app.air_only_var.set(True)
        app.air_search_var.set("zero")
        self.assertIn("603", app.air_tree.get_children())
        self.assertTrue(all("zero" in app.air_tree.set(i, "name").lower() for i in app.air_tree.get_children()))
        app.air_search_var.set("")
        app.air_side_var.set("Allied")
        app.refresh_air_list()
        self.assertTrue(all(app.air_tree.set(i, "side") == "Allied" for i in app.air_tree.get_children()))
        app.air_side_var.set("All")
        for col in ("engines", "next_group", "engines_day", "hi_day", "size", "size"):
            app.sort_air_by(col)
        sizes = [int(app.air_tree.set(i, "size").replace(",", "")) for i in app.air_tree.get_children()]
        self.assertEqual(sizes, sorted(sizes, reverse=True))
        # Selecting a model fills the factory table; double-click jumps to the place.
        app.air_tree.selection_set("603")
        self.root.update()
        self.assertEqual(app.air_factory_tree.get_children(), ("236:6",))
        self.assertEqual(app.air_factory_tree.set("236:6", "size"), "56")
        self.assertEqual(app.air_factory_tree.set("236:6", "production"), "Yes")
        app.search_var.set("zzz")
        app.air_factory_tree.selection_set("236:6")
        app.jump_to_industry_place(app.air_factory_tree)
        self.root.update()
        self.assertEqual(app.notebook.select(), str(app.bases_tab))
        self.assertEqual(app.tree.selection(), ("236",))
        app.notebook.select(app.reports_tab)
        self.root.update()
        self.assertEqual(app.air_tree.selection(), ("603",))
        # Bulk switches mark the bases edited and change only that model.
        self.assertFalse(app.edited)
        app.apply_air_switch("Production off", False, None)
        self.assertEqual(app.edited, {236})
        self.assertTrue(app.dirty)
        self.assertIn("1 of 1 factories changed", app.status.get())
        self.assertEqual(app.air_factory_tree.set("236:6", "production"), "No")
        self.assertEqual(app.air_tree.set("603", "size"), "0")
        self.assertEqual(app.air_tree.set("603", "production_off"), "56")
        app.apply_air_switch("Repair off", None, False)
        self.assertEqual(app.air_factory_tree.set("236:6", "repair"), "No")
        app.apply_air_switch("Production on", True, None)
        app.apply_air_switch("Repair on", None, True)
        self.assertEqual(app.air_tree.set("603", "size"), "56")
        self.assertEqual(app.air_factory_tree.set("236:6", "repair"), "Yes")
        app.air_tree.selection_remove("603")
        self.root.update()
        app.apply_air_switch("Production off", False, None)
        self.assertIn("select a model", app.status.get())
        # Engines: Japanese only.
        self.assertEqual(app.engine_count.get(), f"{len(app.engine_tree.get_children())} engines")
        self.assertEqual(app.engine_tree.set("1932", "name"), "Nakajima Ha-35")
        self.assertEqual(app.engine_tree.set("1932", "size"), "180")
        self.assertEqual(app.engine_tree.set("244", "pool"), "119")
        self.assertEqual(app.engine_tree.set("244", "size"), "65")
        self.assertNotIn("1852", app.engine_tree.get_children())
        for col in ("name", "pool", "net", "used_by", "size", "size"):
            app.sort_engines_by(col)
        sizes = [int(app.engine_tree.set(i, "size").replace(",", "")) for i in app.engine_tree.get_children()]
        self.assertEqual(sizes, sorted(sizes, reverse=True))
        # The Aircraft tab shows the engines read-only.
        app.aircraft_tree.selection_set("746")
        self.root.update()
        self.assertEqual(app.aircraft_info["engines"].get(), "2 x Nakajima Ha-5")

    def test_factory_model_box(self):
        from unittest import mock
        from witpae import factories
        import witpae_editor
        app = witpae_editor.EditorApp(self.root)
        self.assertTrue(app.load(SAVE_015))
        self.assertTrue(app.factory_model_box.instate(["disabled"]))
        app.tree.selection_set("506")
        self.root.update()
        app.factory_tree.selection_set("2")  # Oil: no model
        self.root.update()
        self.assertTrue(app.factory_model_box.instate(["disabled"]))
        self.assertTrue(app.factory_model_button.instate(["disabled"]))
        app.factory_tree.selection_set("8")  # P-38G Lightning
        self.root.update()
        self.assertFalse(app.factory_model_box.instate(["disabled"]))
        self.assertEqual(app.factory_model_var.get(), "P-38G Lightning (#332)")
        labels = list(app.factory_model_box.cget("values"))
        self.assertIn("A-29A Hudson (#2)", labels)
        self.assertNotIn("A6M2 Zero (#603)", labels)
        self.assertEqual(len(labels), sum(1 for a in app.aircraft.values() if a.side_id == 1))
        # Set model changes the row and keeps size and switches.
        factories.set_factory(app.bases[506], 8, 20, 0, False, True)
        app.factory_model_var.set("A-29A Hudson (#2)")
        app.apply_factory_model()
        self.root.update()
        f = factories.get_factory(app.bases[506], 8)
        self.assertEqual((f.type, f.size, f.production_on), (2002, 20, False))
        self.assertEqual(app.factory_tree.set("8", "name"), "A-29A Hudson")
        self.assertEqual(app.factory_model_var.get(), "A-29A Hudson (#2)")
        self.assertIn(506, app.edited)
        self.assertTrue(app.dirty)
        # The same model again is refused with a message and changes nothing.
        with mock.patch.object(witpae_editor.messagebox, "showerror") as err:
            app.apply_factory_model()
        err.assert_called_once()
        self.assertIn("already", err.call_args[0][1])
        # Japanese factories list Japanese models only.
        app.tree.selection_set("236")
        self.root.update()
        slot = next(f.slot for f in factories.list_factories(app.bases[236]) if f.type == 2603)
        app.factory_tree.selection_set(str(slot))
        self.root.update()
        labels = list(app.factory_model_box.cget("values"))
        self.assertIn("A6M2 Zero (#603)", labels)
        self.assertNotIn("A-29A Hudson (#2)", labels)

    def test_reports_without_game_date(self):
        import witpae_editor
        from witpae import reports
        app = witpae_editor.EditorApp(self.root)
        self.assertTrue(app.load(SAVE_015))
        del app.save[reports.DATE_SECTION].data[reports.YEAR_OFFSET:]
        app.refresh_reports()
        self.assertEqual(app.game_date_var.get(), "Game date: unknown")
        self.assertEqual(app.upgrade_tree.get_children(), ())
        self.assertEqual(len(app.spoilage_tree.get_children()), 7)
        # The pools sit in the same truncated section, so the air tables are empty rather than failing.
        self.assertEqual(app.air_tree.get_children(), ())
        self.assertEqual(app.engine_tree.get_children(), ())

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
