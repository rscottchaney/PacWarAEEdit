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
        # Opening a save records its turn; keep that out of tests/data.
        import tempfile
        from unittest import mock
        import witpae_editor
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.history_root = os.path.join(tmp.name, "history")
        patch = mock.patch.object(witpae_editor.EditorApp, "history_root", self.history_root)
        patch.start()
        self.addCleanup(patch.stop)

    def tearDown(self):
        # destroy() leaves variable traces in the interpreter; each callback holds the app and its save, and unittest
        # keeps every test (and so its interpreter) until the run ends. Removing them lets the app be freed.
        import gc
        import tkinter as tk
        for var in [o for o in gc.get_objects() if isinstance(o, tk.Variable) and o._tk is self.root.tk]:
            for mode, callback in var.trace_info():
                var.trace_remove(mode, callback)
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
        tabs = [app.reports_notebook.tab(t, "text") for t in app.reports_notebook.tabs()]
        self.assertEqual(tabs[-5:], ["Aircraft comparison", "Losses", "Ship repair", "Minefields", "Victory points"])
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

    def test_air_group_bulk_pilot_edit(self):
        from unittest import mock
        from witpae import airgroups
        import witpae_editor
        app = witpae_editor.EditorApp(self.root)
        self.assertTrue(app.load(SAVE_015))
        app.group_search_var.set("19th TS")
        app.group_tree.selection_set("4205")
        self.root.update()
        pilots = {p.id: p for p in app.pilot_index[4205]}
        original = {i: p.get("skill_air") for i, p in pilots.items()}
        self.assertEqual(app.bulk_scope.get(), "all 2 active pilots")
        # Invalid amounts show an error and change nothing.
        with mock.patch.object(witpae_editor.messagebox, "showerror") as err:
            for bad in ("", "abc", "100"):
                app.bulk_amount_var.set(bad)
                app.apply_bulk_pilots()
        self.assertEqual(err.call_count, 3)
        self.assertEqual({i: p.get("skill_air") for i, p in pilots.items()}, original)
        self.assertFalse(app.dirty)
        self.assertEqual(app.groups_edited, set())
        # No selection: every active pilot of the group.
        app.bulk_field_var.set("All skills")
        app.bulk_mode_var.set("Set to")
        app.bulk_amount_var.set("55")
        app.apply_bulk_pilots()
        for p in pilots.values():
            self.assertEqual([p.get("skill_" + n.lower()) for n in airgroups.SKILLS], [55] * 12)
        self.assertIn(4205, app.groups_edited)
        self.assertTrue(app.dirty)
        self.assertIn("changed 2 pilots", app.status.get())
        # Several selected: the single-pilot editor is cleared and idle.
        app.pilot_tree.selection_set("5041")
        self.root.update()
        self.assertEqual(app.pilot_vars["skill_air"].get(), "55")
        app.pilot_tree.selection_set(("5041", "18570"))
        self.root.update()
        self.assertEqual(app.bulk_scope.get(), "2 selected pilots")
        self.assertIsNone(app.pilot_current)
        self.assertEqual(app.pilot_vars["skill_air"].get(), "")
        app.apply_pilot()  # does nothing
        # One of several selected: only that pilot changes, and the selection is kept.
        app.pilot_tree.selection_set(("18570",))
        self.root.update()
        app.bulk_field_var.set("Air combat")
        app.bulk_mode_var.set("Add")
        app.bulk_amount_var.set("-5")
        app.apply_bulk_pilots()
        self.root.update()
        self.assertEqual(pilots[18570].get("skill_air"), 50)
        self.assertEqual(pilots[5041].get("skill_air"), 55)
        self.assertEqual(app.pilot_tree.set("18570", "skill_air"), "50")
        self.assertEqual(app.pilot_tree.selection(), ("18570",))
        # Raise lifts only the pilot below the amount.
        app.pilot_tree.selection_set(("5041", "18570"))
        self.root.update()
        app.bulk_mode_var.set("Raise to at least")
        app.bulk_amount_var.set("52")
        app.apply_bulk_pilots()
        self.root.update()
        self.assertEqual((pilots[5041].get("skill_air"), pilots[18570].get("skill_air")), (55, 52))
        self.assertEqual(app.pilot_tree.selection(), ("5041", "18570"))

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

    def test_inactive_rows_are_dimmed(self):
        import witpae_editor
        app = witpae_editor.EditorApp(self.root)
        self.assertTrue(app.load(SAVE_015))
        self.root.update()
        # (tree, active id, inactive id): ship 7 is a reinforcement, 3152 is sunk; aircraft 2 is not yet available
        for tree, active, inactive in ((app.shiprec_tree, "3144", "7"), (app.shiprec_tree, "3144", "3152"),
                                       (app.group_tree, "4205", "2"), (app.ldr_tree, "27701", "1"),
                                       (app.aircraft_tree, "487", "2")):
            self.assertNotIn("pending", tree.item(active, "tags"))
            self.assertEqual(tree.item(inactive, "tags"), ("pending",))
        app.shiprecs_edited.add(7)
        app.groups_edited.add(2)
        app.ldr_edited.add(1)
        app.aircraft_edited.add(2)
        app.refresh_shiprec_list()
        app.refresh_group_list()
        app.refresh_ldr_list()
        app.refresh_aircraft_list()
        for tree, iid in ((app.shiprec_tree, "7"), (app.group_tree, "2"), (app.ldr_tree, "1"),
                          (app.aircraft_tree, "2")):
            self.assertEqual(tree.item(iid, "tags"), ("edited", "pending"))

    def test_leaders_tab(self):
        from unittest import mock
        from witpae import airgroups, leaders
        import witpae_editor
        app = witpae_editor.EditorApp(self.root)
        self.assertTrue(app.load(SAVE_015))
        self.root.update()
        tabs = [app.notebook.tab(t, "text") for t in app.notebook.tabs()]
        self.assertEqual(tabs[tabs.index("Land Units") + 1], "Leaders")
        self.assertEqual(len(app.ldr_tree.get_children()), 27732)
        self.assertEqual(app.ldr_count.get(), "27732 of 27732 leaders")
        for key, value, count in (("side", "Japanese", 9410), ("branch", "Air", None), ("type", "Task Force", None),
                                  ("assigned", "Unassigned", None)):
            app.ldr_filter_vars[key].set(value)
            app.refresh_ldr_list()
            if count is not None:
                self.assertEqual(len(app.ldr_tree.get_children()), count)
            app.ldr_filter_vars[key].set("All")
        app.ldr_filter_vars["type"].set("Task Force")
        app.refresh_ldr_list()
        self.assertEqual(len(app.ldr_tree.get_children()), 396)
        app.ldr_filter_vars["type"].set("All")
        # Rating: blank until a weight is set; a preset sets the filters and ranks the first row highest.
        app.refresh_ldr_list()
        self.assertEqual(app.ldr_tree.set("27701", "rating"), "")
        app.ldr_preset_var.set("Carrier TF")
        app.choose_ldr_preset()
        self.assertEqual((app.ldr_filter_vars["type"].get(), app.ldr_filter_vars["branch"].get()),
                         ("Task Force", "Navy"))
        self.assertEqual(app.ldr_filter_vars["side"].get(), "All")
        ids = app.ldr_tree.get_children()
        ratings = [int(app.ldr_tree.set(i, "rating")) for i in ids]
        self.assertEqual(ratings, sorted(ratings, reverse=True))
        self.assertEqual(ids[0], "7816")
        self.assertEqual(ratings[0], max(leaders.weighted_rating(app.ldr_rows[int(i)], app.ldr_weights) for i in ids))
        # Changing a weight reorders; text that is not an integer in range is ignored.
        app.ldr_weight_vars["air"].set("-5")
        self.assertEqual(app.ldr_weights["air"], -5)
        self.assertNotEqual(app.ldr_tree.get_children()[0], "7816")
        for text in ("x", "", "-", "9", "2.5"):
            app.ldr_weight_vars["naval"].set(text)
        self.assertEqual(app.ldr_weights["naval"], 1)
        app.clear_ldr_weights()
        self.assertEqual(set(app.ldr_weights.values()), {0})
        self.assertEqual(app.ldr_preset_var.get(), "(none)")
        self.assertEqual(app.ldr_filter_vars["type"].get(), "Task Force")
        self.assertEqual({app.ldr_tree.set(i, "rating") for i in app.ldr_tree.get_children()}, {""})
        app.ldr_filter_vars["type"].set("All")
        app.ldr_filter_vars["branch"].set("All")
        app.refresh_ldr_list()
        app.ldr_search_var.set("19th TS")  # matches the Commands column
        app.refresh_ldr_list()
        self.assertIn("27701", app.ldr_tree.get_children())
        app.ldr_tree.selection_set("27701")
        self.root.update()
        self.assertEqual(app.ldr_vars["leadership"].get(), "49")
        self.assertEqual(app.ldr_info["rank"].get(), "LTC (37)")
        self.assertEqual(app.ldr_info["commands"].get(), "Air group: 19th TS")
        self.assertEqual(app.ldr_tree.set("27701", "rank"), "LTC")
        app.sort_ldr_by("leadership")
        app.sort_ldr_by("leadership")
        self.assertEqual(app.ldr_sort_reverse, True)
        # Edit in the Leaders tab: the Air Groups commander box shows the same value.
        app.group_tree.selection_set("4205")
        self.root.update()
        self.assertEqual(app.leader_rank.get(), "LTC (37)")
        app.ldr_tree.selection_set("27701")
        self.root.update()
        app.ldr_vars["leadership"].set("77")
        app.apply_ldr()
        self.assertEqual(airgroups.get_leader(app.save, 27701).get("leadership"), 77)
        self.assertEqual(app.ldr_tree.set("27701", "leadership"), "77")
        self.assertEqual(app.ldr_tree.item("27701", "tags"), ("edited",))
        self.assertEqual(app.leader_vars["leadership"].get(), "77")
        self.assertIn(4205, app.groups_edited)
        self.assertTrue(app.dirty)
        # Edit in the Air Groups tab: the Leaders list follows.
        app.leader_vars["naval"].set("12")
        app.apply_leader()
        self.assertEqual(app.ldr_rows[27701].naval, 12)
        self.assertEqual(app.ldr_tree.set("27701", "naval"), "12")
        self.root.update()
        self.assertEqual(app.ldr_vars["naval"].get(), "12")
        # Refused values change nothing.
        app.ldr_tree.selection_set("27701")
        self.root.update()
        app.ldr_vars["leadership"].set("100")
        with mock.patch.object(witpae_editor.messagebox, "showerror") as err:
            app.apply_ldr()
        self.assertTrue(err.called)
        self.assertEqual(airgroups.get_leader(app.save, 27701).get("leadership"), 77)
        # Double-click jumps to the unit in its own tab, clearing that tab's filters.
        for iid, tab, tree_name, unit in (("27701", "groups_tab", "group_tree", "4205"),
                                          ("1478", "shiprec_tab", "shiprec_tree", "1549"),
                                          ("1467", "tf_tab", "tf_tree", "14070"),
                                          ("9", "units_tab", "unit_tree", "3788")):
            app.ldr_search_var.set("")
            app.refresh_ldr_list()
            app.notebook.select(app.leaders_tab)
            app.ldr_tree.selection_set(iid)
            self.root.update()
            app.group_search_var.set("zzz")
            app.jump_to_ldr_unit()
            self.root.update()
            self.assertEqual(app.notebook.select(), str(getattr(app, tab)), iid)
            self.assertEqual(getattr(app, tree_name).selection(), (unit,), iid)
        # An unassigned leader does nothing.
        app.notebook.select(app.leaders_tab)
        app.ldr_tree.selection_set("1")
        self.root.update()
        app.jump_to_ldr_unit()
        self.assertEqual(app.notebook.select(), str(app.leaders_tab))
        self.assertTrue(app.load(SAVE_015))
        self.assertEqual(app.ldr_edited, set())
        self.assertEqual(app.ldr_rows[27701].leadership, 49)

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

    def test_fill_land_unit_to_toe(self):
        import witpae_editor
        app = witpae_editor.EditorApp(self.root)
        self.assertTrue(app.load(SAVE_015))
        app.fill_unit_to_toe(10)  # nothing selected
        self.assertEqual(app.units_edited, set())
        self.assertFalse(app.dirty)
        app.unit_search_var.set("1/153rd")
        app.unit_tree.selection_set("5639")
        self.root.update()
        self.assertEqual(app.unit_equipment_tree.set("0", "count"), "28")
        app.fill_unit_to_toe(10)
        self.root.update()
        self.assertEqual(app.unit_equipment_tree.set("0", "count"), "35")  # ceil(31 * 1.1)
        self.assertEqual(app.unit_equipment_tree.set("0", "disabled"), "0")
        self.assertIn(5639, app.units_edited)
        self.assertTrue(app.dirty)
        self.assertEqual(app.unit_tree.item("5639", "tags"), ("edited",))
        self.assertIn("TOE +10%", app.status.get())
        self.assertIn("not yet saved", app.status.get())
        app.fill_unit_to_toe(10)
        self.assertIn("already at TOE +10%", app.status.get())

    def test_land_unit_support_estimate(self):
        from unittest import mock
        import witpae_editor
        app = witpae_editor.EditorApp(self.root)
        self.assertTrue(app.load(SAVE_015))
        app.raise_unit_support()  # nothing selected
        self.assertEqual(app.units_edited, set())
        self.assertFalse(app.dirty)
        self.assertEqual(app.unit_info["support_estimate"].get(), "")
        app.unit_tree.selection_set("2038")
        self.root.update()
        self.assertEqual(app.unit_info["support_estimate"].get(), "30 (6 short)")
        app.raise_unit_support()
        self.root.update()
        self.assertEqual(app.unit_info["support_estimate"].get(), "30")
        self.assertIn(2038, app.units_edited)
        self.assertTrue(app.dirty)
        self.assertEqual(app.unit_tree.item("2038", "tags"), ("edited", "pending"))  # 2038 has not arrived
        self.assertEqual(app.unit_equipment_tree.set("3", "count"), "30")
        self.assertIn("Added 6 support squads", app.status.get())
        self.assertIn("not yet saved", app.status.get())
        app.raise_unit_support()
        self.assertIn("already has enough support", app.status.get())
        # Fill to TOE changes the equipment, so the estimate follows.
        app.unit_tree.selection_set("5639")
        self.root.update()
        u = app.units[5639]
        before = u.support_estimate()
        app.fill_unit_to_toe(25)
        support, needed = u.support_estimate()
        self.assertNotEqual((support, needed), before)
        expected = f"{needed} ({needed - support} short)" if needed > support else str(needed)
        self.assertEqual(app.unit_info["support_estimate"].get(), expected)
        with mock.patch.object(witpae_editor.messagebox, "showerror") as err:
            with mock.patch.object(type(u), "raise_support_to_estimate", side_effect=ValueError("no slot")):
                app.raise_unit_support()
        self.assertTrue(err.called)

    def test_land_unit_supplies_short_highlight(self):
        import witpae_editor
        app = witpae_editor.EditorApp(self.root)
        self.assertTrue(app.load(SAVE_015))
        self.assertIn("short", app.unit_tree.item("3447", "tags"))  # 271 of 277
        self.assertNotIn("short", app.unit_tree.item("5639", "tags"))  # 99 of 89
        self.assertEqual(app.unit_tree.set("3447", "supplies"), "271 / 277")
        self.assertEqual(app.unit_tree.set("5639", "supplies"), "99")
        # Not yet arrived: dimmed, and a shortage is not flagged in the list.
        self.assertEqual(app.unit_tree.item("8", "tags"), ("pending",))  # Burma Area, reinforcement
        self.assertEqual(app.unit_tree.item("6652", "tags"), ("pending",))  # 3rd ISF, short but not arrived
        self.assertNotIn("/", app.unit_tree.set("6652", "supplies"))
        self.assertEqual(app.unit_tree.item("5639", "tags"), "")
        app.sort_units_by("supplies")  # still sorts on the number, not the "have / required" text
        order = [int(app.unit_tree.set(i, "supplies").split(" /")[0]) for i in app.unit_tree.get_children()]
        self.assertEqual(order, sorted(order))
        app.unit_tree.selection_set("3447")
        self.root.update()
        self.assertEqual(app.unit_info["required"].get(), "277 (short)")
        self.assertEqual(str(app.unit_info_labels["required"].cget("foreground")), "red")
        app.unit_vars["supplies"].set("300")
        app.apply_unit()
        self.root.update()
        self.assertEqual(app.unit_tree.item("3447", "tags"), ("edited",))
        self.assertEqual(app.unit_tree.set("3447", "supplies"), "300")
        self.assertEqual(app.unit_info["required"].get(), "277")
        self.assertEqual(str(app.unit_info_labels["required"].cget("foreground")), "")

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
        # Ship class ratings follow Ship upgrades; classes with ships by default.
        tabs = [app.reports_notebook.tab(t, "text") for t in app.reports_notebook.tabs()]
        self.assertEqual(tabs[tabs.index("Ship upgrades") + 1], "Ship class ratings")
        self.assertEqual(len(app.rating_tree.get_children()), 861)
        self.assertEqual(app.rating_count.get(), "861 class records")
        self.assertEqual(app.rating_tree.set("674", "main"), "8in/55 Mk 9 Gun x8 (12 salvoes)")
        self.assertEqual(app.rating_tree.set("674", "high_aa"), "324 (27400)")
        self.assertEqual(app.rating_tree.set("1472", "torps"), "16 (8 tubes)")
        self.assertEqual(app.rating_tree.set("1472", "abs"), "18/0/0")
        self.assertNotIn("526", app.rating_tree.get_children())
        app.rating_show_var.set("All stages")
        app.refresh_rating_list()
        self.assertEqual(len(app.rating_tree.get_children()), 1721)
        self.assertEqual(app.rating_tree.set("526", "asw"), "252 (8)")
        app.rating_show_var.set("With ships")
        app.rating_type_var.set("CV")
        app.refresh_rating_list()
        self.assertEqual(len(app.rating_tree.get_children()), 22)
        app.rating_side_var.set("Japanese")
        app.refresh_rating_list()
        self.assertEqual(len(app.rating_tree.get_children()), 10)
        app.rating_side_var.set("All")
        app.sort_ratings_by("high_aa")  # sorts by ceiling, ascending first
        ceilings = {r.class_id: r.aa_ceiling for r in app.ratings_all}
        order = [ceilings[int(i)] for i in app.rating_tree.get_children()]
        self.assertEqual(order, sorted(order))
        self.assertGreater(order[-1], order[0])
        app.rating_search_var.set("lexing")
        self.assertEqual(app.rating_tree.get_children(), ("674",))
        # Double-click opens the class in Ship Classes, clearing that tab's search when it hides the row.
        app.ship_search_var.set("zzz")
        app.rating_tree.selection_set("674")
        app.jump_to_rating_class()
        self.root.update()
        self.assertEqual(app.notebook.select(), str(app.ships_tab))
        self.assertEqual(app.ship_tree.selection(), ("674",))
        app.notebook.select(app.reports_tab)
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
        self.assertEqual(tabs[-7:-5], ["Air production", "Engines"])
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

    def test_ship_production_report(self):
        import witpae_editor
        from witpae import shipproduction
        app = witpae_editor.EditorApp(self.root)
        self.assertTrue(app.load(SAVE_015))
        app.notebook.select(app.reports_tab)
        self.root.update()
        tree = app.production_tree
        self.assertEqual(len(tree.get_children()), 2041)
        self.assertEqual(app.production_count.get(), "2041 ships")
        self.assertEqual(app.production_summary_tree.set("Naval", "size"), "1,384")
        self.assertEqual(app.production_summary_tree.set("Naval", "needed"), "1,385")
        self.assertEqual(app.production_summary_tree.set("Naval", "net"), "-1")
        self.assertEqual(app.production_summary_tree.set("Merchant", "net"), "+371")
        self.assertEqual(app.production_summary_tree.set("Merchant", "pool"), "1,113")
        self.assertEqual(tree.set("7", "status"), "Building")
        self.assertEqual(tree.set("7", "arrival"), "3 May 1942")
        self.assertEqual(tree.set("7", "accel"), "252")
        self.assertEqual(tree.set("30", "yard"), "Merchant")
        self.assertEqual(tree.set("30", "accel"), "-")
        # Filters.
        app.production_yard_var.set("Naval")
        app.production_status_var.set("Building")
        app.refresh_production_list()
        self.assertEqual(len(tree.get_children()), 24)
        app.production_status_var.set(shipproduction.MIDGET)
        app.refresh_production_list()
        self.assertEqual(len(tree.get_children()), 86)
        app.production_status_var.set("Building")
        app.production_yard_var.set("Merchant")
        app.production_status_var.set("Can accelerate")
        app.refresh_production_list()
        self.assertEqual(len(tree.get_children()), 77)
        app.production_yard_var.set("All")
        app.production_status_var.set("All")
        self.assertIn("CVE", app.production_type_box.cget("values"))
        app.production_type_var.set("CVE")
        app.refresh_production_list()
        self.assertIn("30", tree.get_children())
        self.assertNotIn("7", tree.get_children())
        app.production_type_var.set("All")
        app.production_search_var.set("junyo")
        self.assertIn("7", tree.get_children())  # matches the class name too
        self.assertNotIn("30", tree.get_children())
        app.production_search_var.set("")
        # Sorting.
        delays = [int(tree.set(i, "delay").replace(",", "")) for i in tree.get_children()]
        self.assertEqual(delays, sorted(delays))  # shortest delay first by default
        app.sort_production_by("delay")
        delays = [int(tree.set(i, "delay").replace(",", "")) for i in tree.get_children()]
        self.assertEqual(delays, sorted(delays, reverse=True))
        app.sort_production_by("durability")
        values = [int(tree.set(i, "durability")) for i in tree.get_children()]
        self.assertEqual(values, sorted(values))
        # Double-click target: the Ships tab, with its filters cleared.
        app.shiprec_search_var.set("zzz")
        tree.selection_set("7")
        app.jump_to_production_ship()
        self.root.update()
        self.assertEqual(app.notebook.select(), str(app.shiprec_tab))
        self.assertEqual(app.shiprec_tree.selection(), ("7",))

    def test_lcu_production_report(self):
        import witpae_editor
        from witpae import lcuproduction
        app = witpae_editor.EditorApp(self.root)
        self.assertTrue(app.load(SAVE_015))
        app.notebook.select(app.reports_tab)
        self.root.update()
        tabs = [app.reports_notebook.tab(t, "text") for t in app.reports_notebook.tabs()]
        self.assertEqual(tabs.index("LCU production"), tabs.index("Ship production") + 1)
        summary = app.lcu_summary_tree
        self.assertEqual(summary.set("armament", "pool"), "18,387")
        self.assertEqual(summary.set("armament", "per_day"), "620")
        self.assertEqual(summary.set("armament", "arrived"), "44,612")
        self.assertEqual(summary.set("armament", "reinforcement"), "1,834")
        self.assertEqual(summary.set("manpower", "reinforcement"), "10,331")
        tree = app.lcu_unit_tree
        # Units view: Japanese by default, the 14 reinforcements of the 30 day window are listed.
        app.lcu_status_var.set(lcuproduction.REINFORCEMENT)
        app.refresh_lcu_list()
        self.assertEqual(len(tree.get_children()), 14)
        self.assertEqual(app.lcu_count.get(), "14 units")
        app.lcu_window_var.set("All")
        app.refresh_lcu_reports()
        self.assertGreater(len(tree.get_children()), 14)
        self.assertEqual(summary.set("armament", "arrived"), "44,612")
        app.lcu_window_var.set("7 days")
        app.refresh_lcu_reports()
        self.assertLess(len(tree.get_children()), 14)
        app.lcu_window_var.set("30 days")
        app.lcu_status_var.set(lcuproduction.NOT_SCHEDULED)
        app.refresh_lcu_reports()
        iid = tree.get_children()[0]
        self.assertEqual(tree.set(iid, "days"), "-")
        # Sorting.
        app.lcu_status_var.set("All")
        app.refresh_lcu_list()
        app.sort_lcu_units_by("armament")
        values = [int(tree.set(i, "armament").replace(",", "")) for i in tree.get_children()]
        self.assertEqual(values, sorted(values))
        app.sort_lcu_units_by("armament")
        values = [int(tree.set(i, "armament").replace(",", "")) for i in tree.get_children()]
        self.assertEqual(values, sorted(values, reverse=True))
        # Search.
        app.lcu_search_var.set("zzzz")
        self.assertEqual(tree.get_children(), ())
        app.lcu_search_var.set("")
        # Devices view.
        app.lcu_view_var.set("Devices")
        app._show_lcu_view()
        self.root.update()
        dev = app.lcu_device_tree
        self.assertEqual(app.lcu_device_frame.winfo_manager(), "pack")
        self.assertEqual(app.lcu_unit_frame.winfo_manager(), "")
        self.assertEqual(app.lcu_count.get().split()[1], "devices")
        self.assertIn("707", dev.get_children())
        self.assertEqual(dev.set("707", "name"), "IJA Infantry Squad")
        self.assertEqual(dev.set("707", "load"), "17")
        self.assertEqual(dev.set("707", "pool"), "6")
        self.assertEqual(dev.set("707", "type"), "Squad")
        app.lcu_search_var.set("infantry squad")
        self.assertIn("707", dev.get_children())
        app.lcu_search_var.set("")
        app.sort_lcu_devices_by("name")
        names = [dev.set(i, "name").lower() for i in dev.get_children()]
        self.assertEqual(names, sorted(names))
        # Allied side: no production figures.
        app.lcu_view_var.set("Units")
        app._show_lcu_view()
        app.lcu_side_var.set("Allied")
        app.refresh_lcu_reports()
        self.assertEqual(summary.set("armament", "per_day"), "-")
        self.assertEqual(summary.set("armament", "days"), "-")
        self.assertNotEqual(summary.set("armament", "pool"), "18,387")
        app.lcu_side_var.set("Japanese")
        app.refresh_lcu_reports()
        # Double-click target: the Land Units tab, with its filters cleared.
        app.lcu_status_var.set(lcuproduction.ACTIVE)
        app.refresh_lcu_list()
        unit_id = tree.get_children()[0]
        app.unit_search_var.set("zzz")
        app.unit_side_var.set("Allied")
        tree.selection_set(unit_id)
        app.jump_to_lcu_unit()
        self.root.update()
        self.assertEqual(app.notebook.select(), str(app.units_tab))
        self.assertEqual(app.unit_tree.selection(), (unit_id,))
        self.assertEqual(app.unit_search_var.get(), "")

    def test_lcu_targets_report(self):
        import witpae_editor
        app = witpae_editor.EditorApp(self.root)
        self.assertTrue(app.load(SAVE_015))
        app.notebook.select(app.reports_tab)
        self.root.update()
        tabs = [app.reports_notebook.tab(t, "text") for t in app.reports_notebook.tabs()]
        self.assertEqual(tabs.index("LCU targets"), tabs.index("LCU production") + 1)
        top, low = app.lcut_tree, app.lcut_unit_tree
        self.assertEqual(len(top.get_children()), 103)
        self.assertEqual(len(low.get_children()), 400)
        self.assertEqual(app.lcut_count.get(), "103 targets, 398 units (584 records)")
        # The first row is the enemy target with the most units; selecting it narrows the unit table.
        first = top.get_children()[0]
        self.assertEqual((top.set(first, "name"), top.set(first, "owner"), top.set(first, "units")),
                         ("Vigan", "Allied", "18"))
        top.selection_set(first)
        self.root.update()
        self.assertEqual(len(low.get_children()), 18)
        self.assertIn("Parts", [low.heading(c, "text") for c in low["columns"]])
        # Filters.
        app.lcut_side_var.set("Allied")
        app.refresh_lcu_targets()
        self.assertEqual(app.lcut_count.get(), "54 targets, 161 units (177 records)")
        app.lcut_side_var.set("All")
        app.refresh_lcu_targets()
        app.lcut_target_var.set("Own bases")
        app.show_lcu_targets()
        self.assertEqual(app.lcut_count.get(), "61 targets, 238 units (326 records)")
        app.lcut_target_var.set("All")
        app.lcut_status_var.set("On the march")
        app.show_lcu_targets()
        self.assertEqual(app.lcut_count.get(), "7 targets, 10 units (10 records)")
        app.lcut_status_var.set("All")
        app.show_lcu_targets()
        # Sorting the target table.
        app.sort_lcu_targets_by("units")
        values = [int(top.set(i, "units")) for i in top.get_children()]
        self.assertEqual(values, sorted(values))
        # Double-click target: the Bases tab; double-click unit: the Land Units tab with its filters cleared.
        unit_id = low.get_children()[0]
        app.unit_search_var.set("zzz")
        app.unit_side_var.set("Allied")
        low.selection_set(unit_id)
        app.jump_to_lcu_target_unit()
        self.root.update()
        self.assertEqual(app.notebook.select(), str(app.units_tab))
        self.assertEqual(app.unit_tree.selection(), (unit_id,))
        self.assertEqual(app.unit_search_var.get(), "")
        app.notebook.select(app.reports_tab)
        top.selection_set(first)
        app.jump_to_industry_place(top)
        self.assertEqual(app.notebook.select(), str(app.bases_tab))
        self.assertEqual(app.tree.selection(), (first,))

    def test_losses_report(self):
        import witpae_editor
        app = witpae_editor.EditorApp(self.root)
        self.assertTrue(app.load(SAVE_015))
        app.notebook.select(app.reports_tab)
        self.root.update()
        summary, tree = app.losses_summary_tree, app.losses_sunk_tree
        self.assertEqual(summary.set("Allied", "ships"), "11")
        self.assertEqual(summary.set("Japanese", "ships"), "3")
        self.assertEqual(len(tree.get_children()), 14)
        self.assertEqual(app.losses_count.get(), "14 ships")
        self.assertEqual(tree.set("3152", "date"), "7 Dec 1941")
        self.assertEqual(tree.set("3168", "location"), "52,82 near Mersing")
        self.assertEqual(tree.set("3152", "scuttled"), "")
        # Side filter and search.
        app.losses_side_var.set("Japanese")
        app.refresh_losses_list()
        self.assertEqual(sorted(tree.get_children()), ["10037", "10042", "10045"])
        app.losses_side_var.set("All")
        app.losses_search_var.set("tennessee")
        self.assertEqual(tree.get_children(), ("3152",))
        app.losses_search_var.set("")
        # Sorting by date: the default (date column) is ascending, a second click reverses it.
        dates = [tree.set(i, "date") for i in tree.get_children()]
        self.assertEqual((dates[0], dates[-1]), ("7 Dec 1941", "8 Dec 1941"))
        app.sort_losses_sunk_by("date")
        dates = [tree.set(i, "date") for i in tree.get_children()]
        self.assertEqual((dates[0], dates[-1]), ("8 Dec 1941", "7 Dec 1941"))
        # Aircraft view.
        app.losses_view_var.set("Aircraft")
        app._show_losses_view()
        self.root.update()
        air = app.losses_aircraft_tree
        self.assertEqual(app.losses_aircraft_frame.winfo_manager(), "pack")
        self.assertEqual(app.losses_sunk_frame.winfo_manager(), "")
        self.assertEqual(air.set("284", "ground"), "9")
        self.assertEqual(air.set("342", "turn_total"), "21")
        self.assertEqual(app.losses_count.get().split()[1], "models")
        app.losses_side_var.set("Japanese")
        app.refresh_losses_list()
        self.assertTrue(all(air.set(i, "side") == "Japanese" for i in air.get_children()))
        app.sort_losses_aircraft_by("name")
        names = [air.set(i, "name").lower() for i in air.get_children()]
        self.assertEqual(names, sorted(names))
        # Double-click on a sunk ship opens it in the Ships tab, clearing the filters.
        app.losses_view_var.set("Ships sunk")
        app.losses_side_var.set("All")
        app._show_losses_view()
        app.shiprec_search_var.set("zzz")
        tree.selection_set("3152")
        app.jump_to_losses_ship()
        self.root.update()
        self.assertEqual(app.notebook.select(), str(app.shiprec_tab))
        self.assertEqual(app.shiprec_tree.selection(), ("3152",))

    def test_ship_repair_report(self):
        import witpae_editor
        app = witpae_editor.EditorApp(self.root)
        self.assertTrue(app.load(SAVE_015))
        app.notebook.select(app.reports_tab)
        self.root.update()
        summary, tree = app.repair_summary_tree, app.repair_ship_tree
        self.assertEqual(summary.set("Allied", "ships"), "69")
        self.assertEqual(summary.set("Japanese", "ships"), "36")
        self.assertEqual(summary.set("Allied", "tons"), "554,621")
        self.assertEqual(len(tree.get_children()), 105)
        self.assertEqual(app.repair_count.get(), "105 ships")
        self.assertEqual(tree.set("240", "location"), "TF 14141 at sea 143,56")
        self.assertEqual(tree.set("125", "weapon_text"), "2x 25mm Type 96 AA Gun")
        self.assertEqual(tree.set("1228", "tons"), "6,825")
        self.assertEqual(tree.set("1228", "min_port"), "2")
        # Default sort: tons, largest first; a second click on the column reverses it.
        tons = [int(tree.set(i, "tons").replace(",", "")) for i in tree.get_children()]
        self.assertEqual(tons, sorted(tons, reverse=True))
        app.sort_repair_ships_by("tons")
        tons = [int(tree.set(i, "tons").replace(",", "")) for i in tree.get_children()]
        self.assertEqual(tons, sorted(tons))
        # Side filter and search.
        app.repair_side_var.set("Japanese")
        app.refresh_repair_list()
        self.assertEqual(len(tree.get_children()), 36)
        self.assertTrue(all(tree.set(i, "side") == "Japanese" for i in tree.get_children()))
        app.repair_side_var.set("All")
        app.repair_search_var.set("soerabaja")
        self.assertEqual(len(tree.get_children()), 5)
        self.assertIn("3231", tree.get_children())
        self.assertEqual(app.repair_count.get(), "5 ships")
        app.repair_search_var.set("")
        # Ports view.
        app.repair_view_var.set("Ports")
        app._show_repair_view()
        self.root.update()
        ports = app.repair_port_tree
        self.assertEqual(app.repair_port_frame.winfo_manager(), "pack")
        self.assertEqual(app.repair_ship_frame.winfo_manager(), "")
        self.assertEqual(ports.set("1160", "ships"), "5")
        self.assertEqual(ports.set("1160", "tons"), "13,113")
        self.assertEqual(ports.set("229", "repair_points"), "100")
        self.assertEqual(ports.set("1160", "oversize"), "")
        self.assertEqual(app.repair_count.get(), f"{len(ports.get_children())} ports")
        app.repair_search_var.set("soerabaja")
        self.assertEqual(ports.get_children(), ("1160",))
        self.assertEqual(app.repair_count.get(), "1 port")
        app.repair_search_var.set("")
        app.repair_side_var.set("Japanese")
        app.refresh_repair_list()
        self.assertTrue(all(ports.set(i, "side") == "Japanese" for i in ports.get_children()))
        app.sort_repair_ports_by("name")
        names = [ports.set(i, "name").lower() for i in ports.get_children()]
        self.assertEqual(names, sorted(names))
        # Double-click on a port opens it in the Bases tab; on a ship, in the Ships tab.
        app.repair_side_var.set("All")
        app.refresh_repair_list()
        app.search_var.set("zzz")
        ports.selection_set("1160")
        app.jump_to_repair_port()
        self.root.update()
        self.assertEqual(app.notebook.select(), str(app.bases_tab))
        self.assertEqual(app.tree.selection(), ("1160",))
        app.repair_view_var.set("Ships")
        app._show_repair_view()
        app.shiprec_search_var.set("zzz")
        tree.selection_set("240")
        app.jump_to_repair_ship()
        self.root.update()
        self.assertEqual(app.notebook.select(), str(app.shiprec_tab))
        self.assertEqual(app.shiprec_tree.selection(), ("240",))

    def test_minefield_report(self):
        import witpae_editor
        app = witpae_editor.EditorApp(self.root)
        self.assertTrue(app.load(SAVE_015))
        app.notebook.select(app.reports_tab)
        self.root.update()
        tabs = [app.reports_notebook.tab(t, "text") for t in app.reports_notebook.tabs()]
        self.assertEqual(tabs.index("Minefields"), tabs.index("Ship repair") + 1)
        summary, tree = app.minefield_summary_tree, app.minefield_hex_tree
        self.assertEqual(summary.set("Allied", "fields"), "34")
        self.assertEqual(summary.set("Allied", "hexes"), "33")
        self.assertEqual(summary.set("Allied", "mines"), "10,108")
        self.assertEqual(summary.set("Japanese", "mines"), "8,988")
        self.assertEqual(summary.set("Japanese", "types"), "Type 4 Mine 8876; Type 88 Mine 112")
        self.assertEqual(len(tree.get_children()), 65)
        self.assertEqual(app.minefield_count.get(), "65 hexes")
        first = tree.get_children()[0]  # default sort: most mines first
        self.assertEqual(first, "621:78,77,Allied")
        self.assertEqual(tree.set(first, "place"), "Bataan")
        self.assertEqual(tree.set(first, "mines"), "995")
        self.assertEqual(tree.set(first, "decay"), "1%/day (friendly port)")
        self.assertEqual(tree.set("-:70,83,Japanese", "place"), "-")
        self.assertEqual(tree.set("722:50,84,Japanese", "place"), "Singapore (enemy base)")
        self.assertEqual(tree.set("246:109,59,Japanese", "protected"), "300")
        mines = [int(tree.set(i, "mines").replace(",", "")) for i in tree.get_children()]
        self.assertEqual(mines, sorted(mines, reverse=True))
        app.sort_minefield_hexes_by("mines")
        mines = [int(tree.set(i, "mines").replace(",", "")) for i in tree.get_children()]
        self.assertEqual(mines, sorted(mines))
        app.sort_minefield_hexes_by("place")
        places = [tree.set(i, "place").lower() for i in tree.get_children()]
        self.assertEqual(places, sorted(places))
        # Side filter and search (place name, mine type).
        app.minefield_side_var.set("Japanese")
        app.refresh_minefield_list()
        self.assertEqual(len(tree.get_children()), 32)
        self.assertTrue(all(tree.set(i, "side") == "Japanese" for i in tree.get_children()))
        app.minefield_side_var.set("All")
        app.minefield_search_var.set("bataan")
        self.assertEqual(len(tree.get_children()), 2)
        app.minefield_search_var.set("type 88")
        self.assertTrue(all("Type 88" in tree.set(i, "types") for i in tree.get_children()))
        app.minefield_search_var.set("osaka")
        self.assertEqual(app.minefield_count.get(), "1 hex")
        app.minefield_search_var.set("")
        # Double-click: a row with a place opens it in the Bases tab, an open-sea row does nothing.
        app.search_var.set("zzz")
        tree.selection_set("621:78,77,Allied")
        app.jump_to_minefield_place()
        self.root.update()
        self.assertEqual(app.notebook.select(), str(app.bases_tab))
        self.assertEqual(app.tree.selection(), ("621",))
        app.notebook.select(app.reports_tab)
        app.tree.selection_set("584")
        tree.selection_set("-:70,83,Japanese")
        app.jump_to_minefield_place()
        self.root.update()
        self.assertEqual(app.notebook.select(), str(app.reports_tab))
        self.assertEqual(app.tree.selection(), ("584",))
        # Fields view.
        app.minefield_view_var.set("Fields")
        app._show_minefield_view()
        self.root.update()
        fields = app.minefield_field_tree
        self.assertEqual(app.minefield_field_frame.winfo_manager(), "pack")
        self.assertEqual(app.minefield_hex_frame.winfo_manager(), "")
        self.assertEqual(len(fields.get_children()), 67)
        self.assertEqual(app.minefield_count.get(), "67 fields")
        self.assertEqual(fields.set("621:2", "mines"), "500")
        self.assertEqual(fields.set("621:2", "device"), "Mk 6 Mine")
        self.assertEqual(fields.set("621:2", "detection"), "9")
        app.minefield_search_var.set("mk xvii")
        self.assertTrue(all(fields.set(i, "device") == "Mk XVII Mine" for i in fields.get_children()))
        app.minefield_search_var.set("")
        app.minefield_side_var.set("Allied")
        app.refresh_minefield_list()
        self.assertEqual(app.minefield_count.get(), "34 fields")
        app.sort_minefield_fields_by("id")
        ids = [int(fields.set(i, "id")) for i in fields.get_children()]
        self.assertEqual(ids, sorted(ids))
        app.minefield_side_var.set("All")
        app.refresh_minefield_list()
        app.search_var.set("zzz")
        app.notebook.select(app.reports_tab)
        fields.selection_set("621:2")
        app.jump_to_minefield_place()
        self.root.update()
        self.assertEqual(app.notebook.select(), str(app.bases_tab))
        self.assertEqual(app.tree.selection(), ("621",))

    def test_victory_report(self):
        import witpae_editor
        app = witpae_editor.EditorApp(self.root)
        self.assertTrue(app.load(SAVE_015))
        app.notebook.select(app.reports_tab)
        self.root.update()
        tabs = [app.reports_notebook.tab(t, "text") for t in app.reports_notebook.tabs()]
        self.assertEqual(tabs.index("Victory points"), tabs.index("Minefields") + 1)
        summary, tree = app.vp_summary_tree, app.vp_tree
        self.assertEqual(summary.set("Allied", "score"), "11,303")
        self.assertEqual(summary.set("Japanese", "score"), "2,165")
        self.assertEqual(summary.set("Allied", "political_points"), "250")
        self.assertEqual(summary.set("Japanese", "ground_points"), "72")
        self.assertEqual(summary.set("Allied", "ground_points"), "2")
        self.assertEqual(app.vp_status.get(),
                         "Allied Decisive Victory (Allied 5.22 : 1). No automatic victory before 1943.")
        rows = {r.id: r for r in app.vp_bases_all}
        self.assertEqual(len(tree.get_children()), len(rows))
        self.assertEqual(app.vp_count.get(), f"{len(rows)} bases")
        first = tree.get_children()[0]  # default sort: best scored value first
        self.assertEqual(tree.set(first, "name"), "Singapore")
        self.assertEqual(tree.set(first, "scored"), f"{rows[int(first)].scored:,}")
        scored = [int(tree.set(i, "scored").replace(",", "")) for i in tree.get_children()]
        self.assertEqual(scored, sorted(scored, reverse=True))
        app.sort_vp_by("scored")
        scored = [int(tree.set(i, "scored").replace(",", "")) for i in tree.get_children()]
        self.assertEqual(scored, sorted(scored))
        app.sort_vp_by("name")
        names = [tree.set(i, "name").lower() for i in tree.get_children()]
        self.assertEqual(names, sorted(names))
        # Side filter and search (base name, region).
        app.vp_side_var.set("Japanese")
        app.refresh_vp_list()
        self.assertEqual(len(tree.get_children()), sum(1 for r in rows.values() if r.side == "Japanese"))
        self.assertTrue(all(tree.set(i, "side") == "Japanese" for i in tree.get_children()))
        app.vp_side_var.set("All")
        app.vp_search_var.set("bataan")
        self.assertEqual([tree.set(i, "name") for i in tree.get_children()], ["Bataan"])
        app.vp_search_var.set("luzon")
        self.assertTrue(all(tree.set(i, "region") == "Luzon" for i in tree.get_children()))
        app.vp_search_var.set("")
        self.assertEqual(app.vp_count.get(), f"{len(rows)} bases")
        # Double-click opens the base in the Bases tab.
        app.search_var.set("zzz")
        tree.selection_set("621")
        app.jump_to_vp_base()
        self.root.update()
        self.assertEqual(app.notebook.select(), str(app.bases_tab))
        self.assertEqual(app.tree.selection(), ("621",))

    def test_alerts_report(self):
        import witpae_editor
        from witpae import alerts
        app = witpae_editor.EditorApp(self.root)
        self.assertTrue(app.load(SAVE_015))
        app.notebook.select(app.reports_tab)
        self.root.update()
        tabs = [app.reports_notebook.tab(t, "text") for t in app.reports_notebook.tabs()]
        self.assertEqual(tabs[0], "Alerts")
        self.assertEqual(tabs.count("Alerts"), 1)
        tree = app.alert_tree
        everything = list(app.alerts_all)
        self.assertEqual(len(tree.get_children()), len(everything))
        self.assertEqual(app.alert_count.get(), f"{len(everything)} alerts")
        self.assertEqual((app.alert_supply_var.get(), app.alert_pool_var.get()), ("50", "100"))
        # Default order is the module's order: category order, worst first.
        cats = [tree.set(i, "category") for i in tree.get_children()]
        self.assertEqual(cats, [a.category for a in everything])
        self.assertEqual(cats[0], "Low supply")
        # Side and category filters, search.
        app.alert_side_var.set("Japanese")
        app.refresh_alert_list()
        self.assertEqual(len(tree.get_children()), sum(1 for a in everything if a.side == "Japanese"))
        self.assertTrue(all(tree.set(i, "side") == "Japanese" for i in tree.get_children()))
        app.alert_side_var.set("All")
        app.alert_category_var.set("Engines")
        app.refresh_alert_list()
        self.assertEqual(len(tree.get_children()), sum(1 for a in everything if a.category == "Engines"))
        self.assertEqual(app.alert_count.get(), f"{len(tree.get_children())} alerts")
        app.alert_category_var.set("All")
        app.alert_search_var.set("own-port")  # subject
        self.assertEqual({tree.set(i, "category") for i in tree.get_children()}, {"Minefields"})
        self.assertEqual(len(tree.get_children()), 2)
        app.alert_search_var.set("needed (pool")  # detail
        self.assertEqual({tree.set(i, "category") for i in tree.get_children()}, {"Engines"})
        app.alert_search_var.set("")
        self.assertEqual(len(tree.get_children()), len(everything))
        # Sorting by a header, then reversed.
        app.sort_alerts_by("subject")
        names = [tree.set(i, "subject").lower() for i in tree.get_children()]
        self.assertEqual(names, sorted(names))
        app.sort_alerts_by("subject")
        names = [tree.set(i, "subject").lower() for i in tree.get_children()]
        self.assertEqual(names, sorted(names, reverse=True))
        # Thresholds recompute the alerts.
        low = sum(1 for a in everything if a.category == "Low supply")
        app.alert_supply_var.set("0")
        self.assertEqual(sum(1 for a in app.alerts_all if a.category == "Low supply"), 0)
        app.alert_supply_var.set("100")
        self.assertGreater(sum(1 for a in app.alerts_all if a.category == "Low supply"), low)
        app.alert_supply_var.set("abc")  # not a number: back to the default
        self.assertEqual(sum(1 for a in app.alerts_all if a.category == "Low supply"), low)
        app.alert_supply_var.set("50")
        self.assertEqual(sum(1 for a in app.alerts_all if a.category == "Pilots"), 0)
        app.alert_pool_var.set("100000")
        pilots = [a for a in app.alerts_all if a.category == "Pilots"]
        self.assertTrue(pilots)
        app.alert_pool_var.set("100")
        # Jumps, one per kind.
        def alert_iid(kind):
            return next(i for i in tree.get_children() if app.alerts_by_iid[i].kind == kind)

        def open_alert(a):
            app.alerts_all = [a]
            app.alert_sort_col = None
            app.refresh_alert_list()
            tree.selection_set(tree.get_children()[0])
            app.open_alert()
            self.root.update()

        app.search_var.set("zzz")
        base_alert = next(a for a in everything if a.kind == "base")
        open_alert(base_alert)
        self.assertEqual(app.notebook.select(), str(app.bases_tab))
        self.assertEqual(app.tree.selection(), (str(base_alert.target_id),))
        app.notebook.select(app.reports_tab)
        app.shiprec_search_var.set("zzz")
        open_alert(alerts.Alert("Repair", "Japanese", "Ushio", "", "ship", 240, 1))
        self.assertEqual(app.notebook.select(), str(app.shiprec_tab))
        self.assertEqual(app.shiprec_tree.selection(), ("240",))
        app.notebook.select(app.reports_tab)
        open_alert(pilots[0])
        self.assertEqual(app.notebook.select(), str(app.groups_tab))
        self.assertEqual(app.groups_notebook.select(), str(app.pool_page))
        self.assertEqual(app.pool_tree.selection(), (str(pilots[0].target_id),))
        app.notebook.select(app.reports_tab)
        app.aircraft_search_var.set("zzz")
        plane = next(a for a in everything if a.kind == "aircraft")
        open_alert(plane)
        self.assertEqual(app.notebook.select(), str(app.aircraft_tab))
        self.assertEqual(app.aircraft_tree.selection(), (str(plane.target_id),))
        app.notebook.select(app.reports_tab)
        app.reports_notebook.select(app.alerts_frame)
        mines = next(a for a in everything if a.kind == "minefields" and a.side == "Japanese")
        app.minefield_side_var.set("All")
        app.minefield_view_var.set("Fields")
        open_alert(mines)
        self.assertEqual(app.reports_notebook.select(), str(app.minefield_frame))
        self.assertEqual((app.minefield_side_var.get(), app.minefield_view_var.get()), ("Japanese", "By hex"))
        self.assertTrue(all(app.minefield_hex_tree.set(i, "side") == "Japanese"
                            for i in app.minefield_hex_tree.get_children()))
        app.notebook.select(app.reports_tab)
        app.reports_notebook.select(app.alerts_frame)
        engine = next(a for a in everything if a.kind == "engine")
        open_alert(engine)
        self.assertEqual(app.reports_notebook.select(), str(app.engine_frame))
        self.assertEqual(app.engine_tree.selection(), (str(engine.target_id),))

    def test_inconsistencies_report(self):
        import witpae_editor
        from witpae import inconsistencies as inc
        app = witpae_editor.EditorApp(self.root)
        self.assertTrue(app.load(SAVE_015))
        app.notebook.select(app.reports_tab)
        self.root.update()
        tabs = [app.reports_notebook.tab(t, "text") for t in app.reports_notebook.tabs()]
        self.assertEqual(tabs.index("Inconsistencies"), tabs.index("Alerts") + 1)
        tree = app.incon_tree
        found = [i for i in app.incon_all if not i.future]
        self.assertEqual(len(tree.get_children()), len(found))
        self.assertEqual(app.incon_count.get(), f"{len(found)} inconsistencies")
        # Check and side filters.
        app.incon_check_var.set(inc.CHECK_HOME)
        app.refresh_incon_list()
        self.assertEqual(len(tree.get_children()), 1)
        self.assertEqual(app.incon_count.get(), "1 inconsistency")
        app.incon_side_var.set("Allied")
        app.refresh_incon_list()
        self.assertEqual(len(tree.get_children()), 0)
        app.incon_check_var.set("All")
        app.incon_side_var.set("All")
        # The not-yet-arrived checkbox adds the future issues.
        future = inc.Issue(inc.CHECK_SIDE, "Allied", "land unit", 100, "West Coast", "x", True)
        app.incon_all = app.incon_all + [future]
        app.refresh_incon_list()
        self.assertEqual(len(tree.get_children()), len(found))
        app.incon_future_var.set(True)
        app.refresh_incon_list()
        self.assertEqual(len(tree.get_children()), len(found) + 1)
        app.incon_future_var.set(False)
        # Header sort, then reversed.
        app.sort_incon_by("subject")
        names = [tree.set(i, "subject").lower() for i in tree.get_children()]
        self.assertEqual(names, sorted(names))
        app.sort_incon_by("subject")
        names = [tree.set(i, "subject").lower() for i in tree.get_children()]
        self.assertEqual(names, sorted(names, reverse=True))

        def open_issue(kind, subject_id):
            app.notebook.select(app.reports_tab)
            app.incon_all = [inc.Issue(inc.CHECK_SIDE, "Allied", kind, subject_id, "x", "y", False)]
            app.incon_sort_col = None
            app.refresh_incon_list()
            tree.selection_set(tree.get_children()[0])
            app.open_incon()
            self.root.update()

        app.search_var.set("zzz")
        open_issue("place", 584)
        self.assertEqual(app.notebook.select(), str(app.bases_tab))
        self.assertEqual(app.tree.selection(), ("584",))
        app.unit_search_var.set("zzz")
        open_issue("land unit", 100)
        self.assertEqual(app.notebook.select(), str(app.units_tab))
        self.assertEqual(app.unit_tree.selection(), ("100",))
        app.shiprec_search_var.set("zzz")
        open_issue("ship", 3002)
        self.assertEqual(app.notebook.select(), str(app.shiprec_tab))
        self.assertEqual(app.shiprec_tree.selection(), ("3002",))
        open_issue("task force", 14402)
        self.assertEqual(app.notebook.select(), str(app.tf_tab))
        self.assertEqual(app.tf_tree.selection(), ("14402",))
        app.group_search_var.set("zzz")
        open_issue("air group", 1)
        self.assertEqual(app.notebook.select(), str(app.groups_tab))
        self.assertEqual(app.group_tree.selection(), ("1",))
        app.ldr_search_var.set("zzz")
        open_issue("leader", 6652)
        self.assertEqual(app.notebook.select(), str(app.leaders_tab))
        self.assertEqual(app.ldr_tree.selection(), ("6652",))

    def test_alerts_report_lists_skipped_checks(self):
        import witpae_editor
        from witpae import minefields
        app = witpae_editor.EditorApp(self.root)
        self.assertTrue(app.load(SAVE_015))
        del app.save._by_id[minefields.SECTION]
        app.refresh_reports()
        self.assertEqual(app.alerts_skipped, ["Minefields"])
        self.assertTrue(app.alert_count.get().endswith(" alerts (skipped: Minefields)"))
        self.assertTrue(app.alert_tree.get_children())

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
        # Ship production needs no date: arrival is blank and the unreadable pools show as "?".
        self.assertEqual(len(app.production_tree.get_children()), 2041)
        self.assertEqual(app.production_tree.set("7", "arrival"), "-")
        self.assertEqual(app.production_summary_tree.set("Naval", "pool"), "?")
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

    def _intel_folder(self, files):
        """A temporary copy of the sample save with report files written next to it."""
        import shutil
        import tempfile
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = os.path.join(tmp.name, "going2_411210.pws")
        shutil.copy(SAVE_015, path)
        for name, lines in files.items():
            with open(os.path.join(tmp.name, name), "wb") as f:
                f.write("\r\n".join(lines).encode("latin-1") + b"\r\n")
        return path

    def test_intel_tab(self):
        import witpae_editor
        path = self._intel_folder({
            "asigint_411209.txt": ["SIG INT REPORT FOR Dec 9, 41", "Radio transmissions detected at 1,2."],
            "asigint_411210.txt": [
                "SIG INT REPORT FOR Dec 10, 41", "Radio transmissions detected at Pearl Harbor (180,107).",
                "Heavy Volume of Radio transmissions detected at 180,107.",
                "9th Tank Regiment is located at Yenki(110,44).",
                "4th Fleet is planning for an attack on Pearl Harbor.", "Odd new line."],
            "asigint.txt": ["SIG INT REPORT FOR Dec 10, 41", "Radio transmissions detected at 9,9."],
            "joperationsreport_411210.txt": ["OPERATIONAL REPORT FOR Dec 10, 41",
                                              "SS I-2 assigned to offensive patrol 225, 80 - 223, 81 off San Diego",
                                              "xAK Ewa arrives at Pearl Harbor"]})
        app = witpae_editor.EditorApp(self.root)
        self.assertTrue(app.load(path))
        self.root.update()
        tabs = [app.notebook.tab(t, "text") for t in app.notebook.tabs()]
        self.assertEqual(tabs[tabs.index("History") + 1], "Intel")
        self.assertEqual([app.intel_notebook.tab(t, "text") for t in app.intel_notebook.tabs()],
                         ["SigInt", "Operations", "Combat"])
        # Allied SIGINT exists, so Allied is shown; Latest keeps the newest turn only (the undated copy is a duplicate).
        self.assertEqual(app.intel_side_var.get(), "Allied")
        tree = app.intel_lines_tree
        self.assertEqual(len(tree.get_children()), 5)
        self.assertEqual(tree.set(tree.get_children()[0], "date"), "10 Dec 41")
        self.assertEqual(app.intel_count.get(), "SigInt: 5 of 6 lines    Operations: 0 of 0 lines")
        app.intel_turns_var.set("All")
        app.refresh_intel()
        self.assertEqual(len(tree.get_children()), 6)
        # Type filter and search.
        app.intel_kind_var.set("Radio")
        app.refresh_intel_sigint()
        self.assertEqual(len(tree.get_children()), 2)
        app.intel_kind_var.set("All")
        app.intel_search_var.set("yenki")
        self.assertEqual(len(tree.get_children()), 1)
        app.intel_search_var.set("")
        app.intel_kind_var.set("Other")
        app.refresh_intel_sigint()
        self.assertEqual([tree.set(i, "kind") for i in tree.get_children()], ["Other"])
        app.intel_kind_var.set("All")
        app.refresh_intel_sigint()
        # Sorting: by date (numeric), then reversed by clicking the heading again.
        app.sort_intel_by("lines", "date")
        self.assertEqual(tree.set(tree.get_children()[0], "date"), "9 Dec 41")
        app.sort_intel_by("lines", "date")
        self.assertEqual(tree.set(tree.get_children()[0], "date"), "10 Dec 41")
        # Double-click opens a row that resolves to a place; an Other line has none.
        other = next(i for i in tree.get_children() if tree.set(i, "kind") == "Other")
        tree.selection_set(other)
        app.notebook.select(app.history_tab)
        app.open_intel("lines")
        self.assertEqual(app.notebook.select(), str(app.history_tab))
        pearl = next(i for i in tree.get_children() if tree.set(i, "place") == "Pearl Harbor")
        tree.selection_set(pearl)
        app.open_intel("lines")
        self.assertEqual(app.notebook.select(), str(app.bases_tab))
        self.assertEqual(app.tree.selection(), ("584",))
        # By place view.
        app.intel_view_var.set("By place")
        app._show_intel_view()
        places = app.intel_places_tree
        row = places.get_children()[0]
        self.assertEqual([places.set(row, c) for c in ("place", "hex", "radio", "heavy", "units", "reports")],
                         ["Pearl Harbor", "180,107", "1", "1", "0", "3"])
        self.assertEqual(places.set(row, "last"), "10 Dec 41")
        self.assertEqual((app.intel_lines_frame.winfo_manager(), app.intel_places_frame.winfo_manager()), ("", "pack"))
        app.sort_intel_by("places", "place")
        app.notebook.select(app.history_tab)
        places.selection_set(places.get_children()[0])
        app.open_intel("places")
        self.assertEqual(app.notebook.select(), str(app.history_tab))  # the unnamed 1,2 row sorts first and is no place
        places.selection_set(next(i for i in places.get_children() if places.set(i, "place") == "Pearl Harbor"))
        app.open_intel("places")
        self.assertEqual(app.notebook.select(), str(app.bases_tab))
        # Operations of the other side.
        app.intel_side_var.set("Japanese")
        app.refresh_intel()
        ops = app.intel_ops_tree
        self.assertEqual(len(ops.get_children()), 2)
        app.intel_category_var.set("Arrival")
        app.refresh_intel_ops()
        self.assertEqual([ops.set(i, "place") for i in ops.get_children()], ["Pearl Harbor"])
        app.intel_category_var.set("All")
        app.intel_ops_search_var.set("patrol")
        self.assertEqual([ops.set(i, "kind") for i in ops.get_children()], ["Submarine"])
        app.intel_ops_search_var.set("")
        app.sort_intel_by("ops", "kind")
        self.assertEqual([ops.set(i, "kind") for i in ops.get_children()], ["Arrival", "Submarine"])
        app.notebook.select(app.history_tab)
        ops.selection_set(ops.get_children()[0])
        app.open_intel("ops")
        self.assertEqual(app.notebook.select(), str(app.bases_tab))
        # Reload picks up a new file.
        with open(os.path.join(os.path.dirname(path), "asigint_411211.txt"), "wb") as f:
            f.write(b"SIG INT REPORT FOR Dec 11, 41\r\nRadio transmissions detected at 5,5.\r\n")
        app.intel_side_var.set("Allied")
        app.intel_turns_var.set("Latest")
        app.load_intel_view()
        self.assertEqual(app.intel_count.get(), "SigInt: 1 of 7 lines    Operations: 0 of 0 lines")

    def test_intel_combat_tab(self):
        import witpae_editor
        air = ["Morning Air attack on Pearl Harbor , at 180,107 ", "Japanese aircraft", "      G4M1 Betty x 5",
               "Allied aircraft losses", "      P-40E Warhawk: 3 destroyed on ground", "Japanese aircraft losses",
               "      G4M1 Betty: 1 destroyed"]
        sunk = ["TF 12 encounters mine field at 5,5", "Allied Ships", "      SS Tarpon, Mine hits 1, and is sunk"]
        dash = "-" * 80
        path = self._intel_folder({
            "combatreport_411209.txt": ["AFTER ACTION REPORTS FOR Dec 9, 41", dash, "ASW attack near Laoag  at 80,71"],
            "combatreport_411210.txt": ["AFTER ACTION REPORTS FOR Dec 10, 41", dash, *air, "", dash, *sunk, dash,
                                        "Odd new block"],
            "combatreport.txt": ["AFTER ACTION REPORTS FOR Dec 10, 41", dash, "Ground combat at 9,9"]})
        app = witpae_editor.EditorApp(self.root)
        self.assertTrue(app.load(path))
        self.root.update()
        app.intel_notebook.select(2)
        tree = app.intel_combat_tree
        self.assertEqual(len(tree.get_children()), 3)  # Latest turn; the undated copy is a duplicate
        self.assertEqual(app.intel_combat_totals.get(),
                         "3 of 4 actions    Aircraft lost: Allied 3, Japanese 1    Ships sunk: Allied 1, Japanese 0")
        first = tree.get_children()[0]
        self.assertEqual([tree.set(first, c) for c in ("date", "kind", "phase", "place", "hex", "japanese_air",
                                                       "allied_lost", "japanese_lost", "ships_sunk", "ground")],
                         ["10 Dec 41", "Air attack", "Morning", "Pearl Harbor", "180,107", "5", "3", "1", "0", "0/0"])
        # Selecting a row fills the text pane; refreshing clears it.
        text = app.intel_combat_text
        self.assertEqual(text.get("1.0", "end").strip(), "")
        tree.selection_set(first)
        self.root.update()
        self.assertEqual(text.get("1.0", "end").strip(), "\n".join(l.rstrip() for l in air))
        self.assertEqual(str(text.cget("state")), "disabled")
        # Filters.
        app.intel_combat_kind_var.set("Mine field")
        app.refresh_intel_combat()
        self.assertEqual([tree.set(i, "kind") for i in tree.get_children()], ["Mine field"])
        self.assertEqual(text.get("1.0", "end").strip(), "")
        app.intel_combat_kind_var.set("All")
        app.intel_combat_involved_var.set("With ships sunk")
        app.refresh_intel_combat()
        self.assertEqual([tree.set(i, "kind") for i in tree.get_children()], ["Mine field"])
        app.intel_combat_involved_var.set("With aircraft lost")
        app.refresh_intel_combat()
        self.assertEqual([tree.set(i, "kind") for i in tree.get_children()], ["Air attack"])
        app.intel_combat_involved_var.set("All")
        app.intel_combat_search_var.set("odd new")
        self.assertEqual([tree.set(i, "kind") for i in tree.get_children()], ["Other"])
        app.intel_combat_search_var.set("")
        app.intel_turns_var.set("All")
        app.refresh_intel()
        self.assertEqual(len(tree.get_children()), 4)
        # Sorting: numeric by aircraft lost, reversed by clicking again.
        app.sort_intel_by("combat", "allied_lost")
        self.assertEqual(tree.set(tree.get_children()[-1], "allied_lost"), "3")
        app.sort_intel_by("combat", "allied_lost")
        self.assertEqual(tree.set(tree.get_children()[0], "allied_lost"), "3")
        # Double-click: a row naming a place opens it; an Other row has none.
        app.notebook.select(app.history_tab)
        tree.selection_set(next(i for i in tree.get_children() if tree.set(i, "kind") == "Other"))
        app.open_intel("combat")
        self.assertEqual(app.notebook.select(), str(app.history_tab))
        tree.selection_set(next(i for i in tree.get_children() if tree.set(i, "place") == "Pearl Harbor"))
        app.open_intel("combat")
        self.assertEqual(app.notebook.select(), str(app.bases_tab))
        self.assertEqual(app.tree.selection(), ("584",))

    def test_intel_default_side_and_empty_folder(self):
        import witpae_editor
        path = self._intel_folder({"jsigint_411210.txt": ["SIG INT REPORT FOR Dec 10, 41",
                                                          "Radio transmissions detected at 1,2."]})
        app = witpae_editor.EditorApp(self.root)
        self.assertTrue(app.load(path))
        self.assertEqual(app.intel_side_var.get(), "Japanese")
        self.assertEqual(len(app.intel_lines_tree.get_children()), 1)
        self.assertTrue(app.load(self._intel_folder({})))
        self.assertEqual(app.intel_lines_tree.get_children(), ())
        self.assertEqual(app.intel_ops_tree.get_children(), ())
        self.assertIn("No intel reports found", app.intel_count.get())
        app.open_intel("lines")  # nothing selected: no error
        app.sort_intel_by("lines", "place")

    def test_history_tab(self):
        import witpae_editor
        from witpae import history
        app = witpae_editor.EditorApp(self.root)
        self.assertTrue(app.load(SAVE_015))
        tabs = [app.notebook.tab(t, "text") for t in app.notebook.tabs()]
        self.assertEqual(tabs[tabs.index("Reports") + 1], "History")
        folder = os.path.join(self.history_root, "grand-campaign")
        self.assertEqual(os.listdir(folder), ["19411210.json.gz", "leaders.json.gz"])
        self.assertEqual(app.history_dir, folder)
        self.assertIn("10 Dec 41 recorded", app.history_status.get())
        self.assertIn("grand-campaign", app.history_info.get())
        self.assertIn("Turns recorded: 1", app.history_info.get())
        self.assertEqual(str(app.history_record_btn.cget("state")), "disabled")
        # Reopening the same file refreshes the turn.
        self.assertTrue(app.load(SAVE_015))
        self.assertIn("refreshed", app.history_status.get())
        # A second turn, made from the first by editing the dict.
        snap = history.read_snapshot(os.path.join(folder, "19411210.json.gz"))
        snap2 = dict(snap, date=411211, turn=5,
                     sides={s: dict({k: v for k, v in m.items() if k != "mines"}, supply=m["supply"] + 1000)
                            for s, m in snap["sides"].items()})
        snap2["bases"] = {k: v for k, v in snap["bases"].items() if k != "584"}
        history.write_snapshot(folder, snap2)
        app.load_history_view()
        self.root.update()
        tree = app.history_tree
        self.assertEqual(tree.get_children(), ("411211", "411210"))
        self.assertEqual(tree.set("411211", "allied"), "5,591,712")
        self.assertEqual(tree.set("411211", "allied_change"), "+1,000")
        self.assertEqual(tree.set("411210", "allied_change"), "-")
        self.assertEqual(tree.set("411210", "date"), "10 Dec 41")
        self.assertEqual(list(tree["displaycolumns"]),
                         ["date", "turn", "allied", "allied_change", "japanese", "japanese_change"])
        app.history_side_var.set("Japanese")
        app.refresh_history_view()
        self.assertEqual(list(tree["displaycolumns"]), ["date", "turn", "japanese", "japanese_change"])
        app.history_metric_var.set(history.SIDE_METRICS["ships_sunk"])
        app.refresh_history_view()
        self.assertEqual(tree.set("411210", "japanese"), "3")
        # The chart has drawn its axes, lines and legend.
        app.history_chart.configure(width=700, height=300)
        app.notebook.select(app.history_tab)
        self.root.update()
        self.assertGreater(len(app.history_chart.find_all()), 10)
        app.history_side_var.set("Japanese")
        app.history_metric_var.set(history.SIDE_METRICS["mines"])
        app.refresh_history_view()
        self.assertEqual(tree.set("411210", "japanese"), "8,988")
        self.assertEqual(tree.set("411211", "japanese"), "-")  # recorded without the metric: a gap
        app.history_metric_var.set(history.SIDE_METRICS["vp"])
        app.refresh_history_view()
        self.assertEqual(tree.set("411210", "japanese"), "2,165")
        app.history_side_var.set("Both")
        app.history_metric_var.set(history.SIDE_METRICS["supply"])
        app.refresh_history_view()
        self.assertEqual([s.label for s in app.history_chart.series], ["Allied", "Japanese"])

        # Base view through the Bases tab's History button.
        app.tree.selection_set("584")
        self.root.update()
        app.history_btn.invoke()
        self.assertEqual(app.notebook.select(), str(app.history_tab))
        self.assertEqual(app.history_view_var.get(), "Base")
        self.assertIn("(584)", app.history_base_var.get())
        self.assertEqual(list(tree["displaycolumns"]), ["date", "turn", "side", "value", "change"])
        self.assertEqual(tree.get_children(), ("411211", "411210"))
        self.assertEqual(tree.set("411210", "value"), "982,531")
        self.assertEqual(tree.set("411210", "side"), "Allied")
        self.assertEqual(tree.set("411211", "value"), "-")  # not recorded that turn: a gap
        app.history_filter_var.set("zzzz")
        self.assertFalse(app.history_base_box.cget("values"))
        app.history_filter_var.set("pearl")
        self.assertTrue(app.history_base_box.cget("values"))

    def test_history_events_view(self):
        import witpae_editor
        from witpae import history
        app = witpae_editor.EditorApp(self.root)
        self.assertTrue(app.load(SAVE_015))
        folder = os.path.join(self.history_root, "grand-campaign")
        snap = history.read_snapshot(os.path.join(folder, "19411210.json.gz"))
        # An older turn without the event keys, and a later one where Pearl Harbor falls and the Lexington sinks.
        history.write_snapshot(folder, dict({k: v for k, v in snap.items() if k not in history.EVENT_KEYS},
                                            date=411209, turn=3))
        history.write_snapshot(folder, dict(snap, date=411211, turn=5, places=dict(snap["places"], **{"584": 0}),
                                            ships=dict(snap["ships"], **{"3002": history.SHIP_SUNK})))
        history._write_gzip_json(folder, history.LEADER_LOG, {
            "version": 1, "date": 411211, "ratings": {}, "changes": [[411211, 27701, "30" * 7, "31" + "30" * 6]]})
        app.load_history_view()
        app.history_view_var.set("Events")
        app._show_history_view()
        self.root.update()
        tree = app.history_tree
        self.assertEqual(list(tree["displaycolumns"]), ["date", "kind", "side", "subject", "detail"])
        self.assertEqual(app.history_chart.winfo_manager(), "")  # no chart in this view
        self.assertEqual(app.history_event_count.get(), "3 events")
        self.assertEqual([tree.set(i, "kind") for i in tree.get_children()],
                         ["Base captured", "Ship sunk", "Leader skill changed"])
        self.assertEqual(tree.set("2", "detail"), "Leadership 48 -> 49")
        self.assertEqual(tree.set("0", "detail"), "Allied -> Japanese")
        self.assertEqual((tree.set("0", "date"), tree.set("0", "side"), tree.set("0", "subject")),
                         ("11 Dec 41", "Japanese", "Pearl Harbor"))
        self.assertIn("1 of 3 recorded turns", app.history_note.get())
        self.assertIn("older editor", app.history_note.get())
        app.history_kind_var.set("Ship sunk")
        app.refresh_history_view()
        self.assertEqual(app.history_event_count.get(), "1 event")
        app.history_kind_var.set("All")
        app.history_event_side_var.set("Japanese")
        app.refresh_history_view()
        self.assertEqual(app.history_event_count.get(), "1 event")
        app.history_event_side_var.set("All")
        app.history_turns_var.set("Last 7")
        app.refresh_history_view()
        self.assertEqual(app.history_event_count.get(), "3 events")  # the turn without keys adds none
        # Double-click opens the subject.
        tree.selection_set("0")
        app.open_history_event()
        self.assertEqual(app.notebook.select(), str(app.bases_tab))
        self.assertEqual(app.tree.selection(), ("584",))
        app.notebook.select(app.history_tab)
        tree.selection_set("1")
        app.open_history_event()
        self.assertEqual(app.notebook.select(), str(app.shiprec_tab))
        self.assertEqual(app.shiprec_tree.selection(), ("3002",))
        app.notebook.select(app.history_tab)
        tree.selection_set("2")
        app.open_history_event()
        self.assertEqual(app.notebook.select(), str(app.leaders_tab))
        self.assertEqual(app.ldr_tree.selection(), ("27701",))
        # Other views bring the chart back.
        app.history_view_var.set("Sides")
        app._show_history_view()
        self.assertEqual(app.history_chart.winfo_manager(), "pack")
        self.assertEqual(app.history_note.get(), "")

    def test_history_aircraft_view(self):
        import witpae_editor
        from witpae import history
        app = witpae_editor.EditorApp(self.root)
        self.assertTrue(app.load(SAVE_015))
        folder = app.history_dir
        snap = history.read_snapshot(os.path.join(folder, "19411210.json.gz"))
        plane_id, entry = next((int(k), v) for k, v in snap["aircraft"].items() if v[0] == 0 and v[1] > 0)
        snap2 = dict(snap, date=411211, turn=5, aircraft={})
        history.write_snapshot(folder, snap2)
        app.load_history_view()
        # The Aircraft tab's button opens the view with that model selected.
        app.aircraft_tree.selection_set(str(plane_id))
        self.root.update()
        app.show_aircraft_history()
        self.assertEqual(app.notebook.select(), str(app.history_tab))
        self.assertEqual(app.history_view_var.get(), "Aircraft")
        self.assertIn(f"({'Japanese'})", app.history_aircraft_var.get())
        tree = app.history_tree
        self.assertEqual(list(tree["displaycolumns"]), ["date", "turn", "value", "change"])
        self.assertEqual(tree.get_children(), ("411211", "411210"))
        self.assertEqual(tree.set("411210", "value"), f"{entry[1]:,}")
        self.assertEqual(tree.set("411211", "value"), "0")
        self.assertEqual(tree.set("411211", "change"), f"{-entry[1]:+,}")
        self.assertEqual([s.label for s in app.history_chart.series], ["Japanese"])
        app.history_aircraft_metric_var.set("Lost (total)")
        app.refresh_history_view()
        self.assertEqual(tree.set("411210", "value"), f"{sum(entry[2:]):,}")
        # The selection survives a reload of the folder.
        label = app.history_aircraft_var.get()
        app.load_history_view()
        self.assertEqual(app.history_aircraft_var.get(), label)
        app.history_aircraft_filter_var.set("zzzz")
        self.assertFalse(app.history_aircraft_box.cget("values"))
        app.history_aircraft_filter_var.set("")
        self.assertTrue(app.history_aircraft_box.cget("values"))

    def test_history_empty_state(self):
        import witpae_editor
        app = witpae_editor.EditorApp(self.root)
        app.history_chart.configure(width=500, height=250)
        app.notebook.select(app.history_tab)
        self.root.update()
        self.assertEqual(app.history_tree.get_children(), ())
        chart = app.history_chart
        texts = [chart.itemcget(i, "text") for i in chart.find_all() if chart.type(i) == "text"]
        self.assertEqual(texts, ["No turns recorded yet"])

    def test_history_keeps_other_source_and_records_on_request(self):
        import shutil
        import tempfile
        import witpae_editor
        from witpae import history
        app = witpae_editor.EditorApp(self.root)
        self.assertTrue(app.load(SAVE_015))
        with tempfile.TemporaryDirectory() as tmp:
            other = os.path.join(tmp, "edited.pws")
            shutil.copyfile(SAVE_015, other)
            self.assertTrue(app.load(other))
            self.assertIn("10 Dec 41 already recorded from going2_411210.pws", app.history_status.get())
            self.assertEqual(str(app.history_record_btn.cget("state")), "normal")
            path = os.path.join(app.history_dir, "19411210.json.gz")
            self.assertEqual(history.read_snapshot(path)["source"], "going2_411210.pws")
            app.history_record_btn.invoke()
            self.assertIn("replaced", app.history_status.get())
            self.assertEqual(history.read_snapshot(path)["source"], "edited.pws")
            self.assertEqual(str(app.history_record_btn.cget("state")), "disabled")

    def test_history_failure_does_not_block_opening(self):
        from unittest import mock
        import witpae_editor
        app = witpae_editor.EditorApp(self.root)
        with mock.patch.object(witpae_editor.history, "record", side_effect=PermissionError("denied")), \
                mock.patch.object(witpae_editor.messagebox, "showerror") as err:
            self.assertTrue(app.load(SAVE_015))
        err.assert_not_called()
        self.assertIn("History not recorded: denied", app.history_status.get())
        self.assertIsNotNone(app.save)

    def test_history_pbem_records_nothing(self):
        import tempfile
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
        self.assertIn("PBEM", app.history_status.get())
        self.assertFalse(os.path.exists(self.history_root))

    def test_history_import_and_delete(self):
        import tempfile
        from unittest import mock
        import witpae_editor
        app = witpae_editor.EditorApp(self.root)
        self.assertTrue(app.load(SAVE_015))
        with tempfile.TemporaryDirectory() as tmp:
            bad = os.path.join(tmp, "bad.pws")
            with open(bad, "wb") as f:
                f.write(b"nope")
            with mock.patch.object(witpae_editor.filedialog, "askopenfilenames",
                                   return_value=(SAVE_015, bad)) as ask:
                app.import_history()
        self.assertEqual(ask.call_args[1]["initialdir"], os.path.dirname(SAVE_015))
        self.assertTrue(app.history_status.get().startswith("1 imported, 1 skipped (bad.pws: unreadable"))
        tree = app.history_tree
        self.assertEqual(tree.get_children(), ("411210",))
        app.delete_history_turn()  # nothing selected
        self.assertEqual(tree.get_children(), ("411210",))
        tree.selection_set("411210")
        with mock.patch.object(witpae_editor.messagebox, "askyesno", return_value=False):
            app.delete_history_turn()
        self.assertEqual(tree.get_children(), ("411210",))
        with mock.patch.object(witpae_editor.messagebox, "askyesno", return_value=True):
            app.delete_history_turn()
        self.assertEqual(tree.get_children(), ())
        self.assertEqual(os.listdir(app.history_dir), ["leaders.json.gz"])  # deleting a turn leaves the leader log
        self.assertIn("deleted", app.history_status.get())


    def test_map_tab(self):
        import tempfile
        from unittest import mock
        import witpae_editor
        from tests.test_mapview import write_art
        from witpae import mapview
        art = tempfile.TemporaryDirectory()
        self.addCleanup(art.cleanup)
        write_art(art.name, "WPEH")
        write_art(art.name, "WPEN")
        dashes = "-" * 80
        path = self._intel_folder({"combatreport_411210.txt": [
            "AFTER ACTION REPORTS FOR Dec 10, 41", dashes, "ASW attack near Pearl Harbor at 180,107", " ",
            "Weather in hex: Clear sky", " ", dashes, "Ground combat at Nowhere", " ", "Weather in hex: Clear sky"]})
        with mock.patch.object(witpae_editor.EditorApp, "_art_dirs", lambda self: [art.name]):
            app = witpae_editor.EditorApp(self.root)
            tabs = [app.notebook.tab(t, "text") for t in app.notebook.tabs()]
            self.assertEqual(tabs[tabs.index("Intel") + 1], "Map")
            self.assertEqual(app.map_info.get(), "Open a save to see the map")
            self.assertTrue(app.load(path))
            self.root.update()
            self.assertIsNone(app.map_shown)  # not drawn until the tab is shown
            app.notebook.select(app.map_tab)
            self.root.update()
            self.assertEqual(app.map_shown, ("Hexes", 4))
            self.assertEqual(app.map_message, "")
            self.assertIsNotNone(app.map_image)
            self.assertEqual(len(app.map_canvas.find_withtag("bg")), 1)
            self.assertEqual(app.map_info.get(), "781 bases")
            self.assertGreaterEqual(len(app.map_canvas.find_withtag("overlay")), 781)
            # Filters of the Locations overlay.
            app.map_towns_var.set("Bases and towns")
            app.refresh_map()
            self.assertEqual(app.map_info.get(), "1052 bases and towns")
            app.map_side_var.set("Allied")
            app.map_region_var.set(next(r for r in app.region_ids if r != witpae_editor.REGION_ALL))
            app.refresh_map()
            self.assertTrue(app.map_info.get().endswith("bases and towns"))
            app.map_side_var.set("All")
            app.map_region_var.set(witpae_editor.REGION_ALL)
            # Every overlay draws, at every scale, on either background.
            counts = {}
            for overlay in witpae_editor.MAP_OVERLAYS:
                app.map_overlay_var.set(overlay)
                app._map_overlay_changed()
                counts[overlay] = len(app.map_canvas.find_withtag("overlay"))
                self.assertTrue(app.map_info.get().startswith(
                    {"Locations": "1052", "Search arcs": "173", "Task forces": "236",
                     "Support": "664 hexes with land units (359 short",
                     "Supply": "665 hexes with supply (10 lacking, 10 with units short, 2 spoiling)",
                     "Transport": "154 ports (21 with more waiting than ships can carry)",
                     "Ship track": "Type a ship name",
                     "Combat": "1"}[overlay]
                ), (overlay, app.map_info.get()))
            self.assertTrue(all(n for overlay, n in counts.items() if overlay != "Ship track"), counts)
            self.assertEqual(counts["Ship track"], 0)  # no ship chosen yet
            self.assertEqual(str(app.map_side_box.cget("state")), "disabled")  # Side does not apply to combat
            app.map_overlay_var.set("Search arcs")
            app._map_overlay_changed()
            self.assertEqual(str(app.map_side_box.cget("state")), "readonly")
            app.map_arc_kind_var.set("ASW")
            app.map_arc_mode_var.set("Defined")
            app.refresh_map()
            self.assertTrue(app.map_info.get().startswith("0 ASW search arcs"))
            app.map_arc_mode_var.set("All")
            app.map_overlay_var.set("Combat")
            app.map_combat_kind_var.set("ASW")
            app._map_overlay_changed()
            self.assertEqual(app.map_info.get(), "1 combat actions")
            app.map_combat_kind_var.set("Submarine")
            app.refresh_map()
            self.assertEqual(app.map_info.get(), "0 combat actions")
            for style in mapview.STYLES:
                for scale in witpae_editor.MAP_SCALES:
                    app.map_style_var.set(style)
                    app.map_scale_var.set(scale)
                    app.map_overlay_var.set("Task forces")
                    app._map_overlay_changed()
                    self.assertEqual(app.map_shown, (style, witpae_editor.MAP_SCALES[scale]))
                    self.assertEqual(app.map_message, "")
            self.assertNotIn(1, {step for _style, step in app.map_images})  # full size is never cached
            # Click report and Find.
            app.map_find_var.set("pearl")
            app.find_map_place()
            text = app.map_detail.get("1.0", "end")
            self.assertTrue(text.startswith("Hex 180,107"))
            for expected in ("Places:", "Pearl Harbor (base, Allied)", "Air groups searching:", "Combat:", "ASW:"):
                self.assertIn(expected, text)
            self.assertEqual(len(app.map_canvas.find_withtag("pick")), 1)
            for expected in ("Land units:", "Support:", "Allied: support 1985, needed 1532 (453 spare)"):
                self.assertIn(expected, text)
            # Edits in the Land Units tab show in the support overlay and the click report.
            app.map_overlay_var.set("Support")
            app._map_overlay_changed()
            self.assertEqual(len(app.map_canvas.find_withtag("overlay")), 664)
            short = next(m for m in mapview.support_marks(app.save) if m.support < m.needed)
            unit = next(u for u in short.units if u.support < u.needed)
            app.show_map_hex(short.x, short.y)
            before = app.map_detail.get("1.0", "end")
            app.notebook.select(app.units_tab)  # the map is not showing, so it is redrawn when shown
            self.root.update()
            app.unit_tree.selection_set(str(unit.id))
            self.root.update()
            app.raise_unit_support()
            self.assertEqual(app.units_edited, {unit.id})
            self.assertTrue(app.map_stale)
            app.notebook.select(app.map_tab)
            self.root.update()
            self.assertFalse(app.map_stale)
            app.show_map_hex(short.x, short.y)
            self.assertNotEqual(app.map_detail.get("1.0", "end"), before)
            after = next(m for m in mapview.support_marks(app.save)
                         if (m.side, m.x, m.y) == (short.side, short.x, short.y))
            self.assertGreater(after.support, short.support)
            self.assertIn(f"support {after.support}, needed {after.needed}", app.map_detail.get("1.0", "end"))
            # Supply: a lacking hex lists the nearest supply, and a Supplies edit through apply_unit refreshes it.
            app.map_overlay_var.set("Supply")
            app._map_overlay_changed()
            self.assertEqual(len(app.map_canvas.find_withtag("overlay")), 665 + 10 + 2)  # bars, rings, triangles
            lacking = next(m for m in mapview.supply_marks(app.save) if m.available < m.required and m.units)
            app.show_map_hex(lacking.x, lacking.y)
            text = app.map_detail.get("1.0", "end")
            self.assertIn("Supply:", text)
            self.assertIn("Nearest supply (straight line):", text)
            self.assertIn("short", text)
            app.notebook.select(app.units_tab)
            self.root.update()
            u = app.units[lacking.units[0].id]
            app.unit_tree.selection_set(str(u.id))
            self.root.update()
            app.map_stale = False
            app.unit_vars["supplies"].set(str(u.get("supplies") + 1))
            app.apply_unit()
            self.assertTrue(app.map_stale)
            self.assertTrue(all(k[0] != "supply" for k in app.map_cache))
            app.notebook.select(app.map_tab)
            self.root.update()
            # Transport: two bars per port, the Mode switch and the click report.
            app.map_overlay_var.set("Transport")
            app._map_overlay_changed()
            self.assertTrue(app.map_info.get().startswith("154 ports (21 with more waiting"))
            ports = mapview.transport_marks(app.save)
            self.assertEqual(len(app.map_canvas.find_withtag("overlay")),
                             sum((mapview.transport_capacity(m) > 0) + (m.need > 0) for m in ports))
            app.map_transport_mode_var.set("Bulk")
            app.refresh_map()
            self.assertTrue(app.map_info.get().startswith("551 ports (485 with more waiting"))
            pearl = next(m for m in ports if m.base.name == "Pearl Harbor")
            app.show_map_hex(pearl.x, pearl.y)
            text = app.map_detail.get("1.0", "end")
            self.assertIn("Transport:", text)
            self.assertIn(f"Allied Pearl Harbor: {pearl.ships} ships, troop {pearl.available[0]}", text)
            self.assertIn("waiting (bulk): resources", text)
            self.assertIn("waiting (troops):", text)
            busy = next(m for m in ports if m.units)
            app.show_map_hex(busy.x, busy.y)
            self.assertIn(f"{busy.units[0].name} troop {busy.units[0].troop}, cargo {busy.units[0].cargo} to "
                          f"{busy.units[0].target}", app.map_detail.get("1.0", "end"))
            app.map_transport_mode_var.set("Troops")
            app.notebook.select(app.units_tab)
            self.root.update()
            app.map_stale = False
            app._map_data_changed()
            self.assertTrue(all(k[0] != "transport" for k in app.map_cache))
            app.notebook.select(app.map_tab)
            self.root.update()
            app.show_map_hex(0, 0)
            self.assertIn("Nothing here", app.map_detail.get("1.0", "end"))
            app.map_find_var.set("no such place")
            app.find_map_place()
            self.assertIn("No base or town matches", app.map_info.get())
            # Opening another save clears what was drawn.
            app.load(path)
            self.assertEqual(app.map_canvas.find_withtag("pick"), ())

    def test_map_ship_track(self):
        from unittest import mock
        import witpae_editor
        from witpae import history
        with mock.patch.object(witpae_editor.EditorApp, "_art_dirs", lambda self: []):
            app = witpae_editor.EditorApp(self.root)
            self.assertTrue(app.load(SAVE_015))
            self.assertIn("Ship track", witpae_editor.MAP_OVERLAYS)
            self.assertLess(witpae_editor.MAP_OVERLAYS.index("Ship track"), witpae_editor.MAP_OVERLAYS.index("Combat"))
            folder = os.path.join(self.history_root, "grand-campaign")
            snap = history.read_snapshot(os.path.join(folder, "19411210.json.gz"))
            self.assertEqual(snap["ship_hexes"]["3002"], [154, 104])
            # No positions recorded: the message.
            history.write_snapshot(folder, {k: v for k, v in snap.items() if k != "ship_hexes"})
            app.load_history_view()
            app.map_overlay_var.set("Ship track")
            app._map_overlay_changed(draw=False)
            app.notebook.select(app.map_tab)
            self.root.update()
            self.assertTrue(app.map_info.get().endswith(
                "No ship positions recorded yet: open or import saves to record them."))
            # Three turns: it moves, then stays.
            for date in (411211, 411212):
                moved = dict(snap["ship_hexes"], **{"3002": [155, 104]})
                history.write_snapshot(folder, dict(snap, date=date, ship_hexes=moved))
            history.write_snapshot(folder, snap)
            app.load_history_view()  # a reload redraws the visible map
            self.assertIn("Type a ship name", app.map_info.get())
            app.map_track_turns_var.set("All")
            app.map_ship_var.set("lexing")
            app.find_map_ship()
            self.root.update()
            self.assertEqual(app.map_track_ship, 3002)
            self.assertEqual(app.map_ship_var.get(), "Lexington")
            self.assertTrue(app.map_info.get().endswith("Lexington: 3 turns recorded, 1 moves"))
            # One arrow, one dot for the turn it stayed, the hollow circle on the latest position.
            kinds = sorted(app.map_canvas.type(i) for i in app.map_canvas.find_withtag("overlay"))
            self.assertEqual(kinds, ["line", "oval", "oval"])
            text = app.map_detail.get("1.0", "end")
            self.assertTrue(text.startswith("Hex 155,104"))
            self.assertIn("Ship track:\n  Lexington: 11 Dec 41, 12 Dec 41", text)
            app.show_map_hex(154, 104)
            self.assertIn("Lexington: 10 Dec 41\n", app.map_detail.get("1.0", "end"))
            app.show_map_hex(1, 1)
            self.assertNotIn("Ship track:", app.map_detail.get("1.0", "end"))
            app.map_track_turns_var.set("Latest")
            app.refresh_map()
            self.assertTrue(app.map_info.get().endswith("Lexington: 1 turns recorded, 0 moves"))
            app.map_ship_var.set("no such ship")
            app.find_map_ship()
            self.assertIn("No ship matches", app.map_info.get())
            # The Ships tab button.
            app.load(SAVE_015)
            self.assertIsNone(app.map_track_ship)
            app.notebook.select(app.shiprec_tab)
            app.shiprec_tree.selection_set("3002")
            self.root.update()
            app.map_overlay_var.set("Locations")
            app.show_shiprec_track()
            self.root.update()
            self.assertEqual(app.notebook.select(), str(app.map_tab))
            self.assertEqual(app.map_overlay_var.get(), "Ship track")
            self.assertEqual(app.map_track_ship, 3002)
            self.assertIn("Lexington: ", app.map_info.get())

    def test_map_tab_without_art(self):
        from types import SimpleNamespace
        from unittest import mock
        from witpae import mapview
        import witpae_editor
        with mock.patch.object(witpae_editor.EditorApp, "_art_dirs", lambda self: []):
            app = witpae_editor.EditorApp(self.root)
            self.assertTrue(app.load(SAVE_015))
            app.notebook.select(app.map_tab)
            self.root.update()
            self.assertIn("not found", app.map_message)
            self.assertIsNone(app.map_image)
            self.assertTrue(app.map_info.get().startswith("Map art"))
            self.assertEqual(len(app.map_canvas.find_withtag("bg")), 1)
            self.assertGreaterEqual(len(app.map_canvas.find_withtag("overlay")), 781)
            # Ctrl+wheel steps the scale and keeps the map point under the mouse in place.
            c, event = app.map_canvas, SimpleNamespace(x=100, y=80)
            c.xview_moveto(0.4)
            c.yview_moveto(0.3)
            width, height = app.map_size
            before = (c.canvasx(event.x) / width, c.canvasy(event.y) / height)
            app.zoom_map(event, 1)
            self.assertEqual(app.map_scale_var.get(), "50%")
            width, height = app.map_size
            self.assertEqual(app.map_size, (-(-mapview.FULL_SIZE[0] // 2), -(-mapview.FULL_SIZE[1] // 2)))
            self.assertAlmostEqual(c.canvasx(event.x) / width, before[0], delta=2 / width)
            self.assertAlmostEqual(c.canvasy(event.y) / height, before[1], delta=2 / height)
            app.zoom_map(event, 1)
            app.zoom_map(event, 1)  # already at the closest scale
            self.assertEqual(app.map_scale_var.get(), "100%")
            for _ in range(4):
                app.zoom_map(event, -1)
            self.assertEqual(app.map_scale_var.get(), "12%")


if __name__ == "__main__":
    unittest.main()
