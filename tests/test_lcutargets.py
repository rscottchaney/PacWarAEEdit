import os
import unittest

from witpae import bases, landunits, lcutargets as lt, mapview, shiprecords, taskforces
from witpae.container import SaveFile

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
SAVE_015 = os.path.join(DATA_DIR, "going2_411210.pws")


class LcuTargetsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.save = SaveFile.load(SAVE_015)
        cls.rows = lt.target_rows(cls.save)
        cls.by_unit = {r.unit_id: r for r in cls.rows}

    def test_row_counts(self):
        self.assertEqual(len(self.rows), 584)
        counts = {s: sum(r.status == s for r in self.rows) for s in lt.STATUSES}
        self.assertEqual(counts, {lt.PREPARING: 341, lt.MARCHING: 10, lt.ABOARD: 233})
        self.assertEqual(sum(r.enemy for r in self.rows), 258)

    def test_no_row_targets_its_own_location_or_nothing(self):
        units = {u.id: u for u in landunits.list_land_units(self.save)}
        for r in self.rows:
            u = units[r.unit_id]
            self.assertNotEqual(r.target_id, 0)
            self.assertNotEqual(r.target_id, u.location_id)
            self.assertTrue(r.target_name)
            self.assertTrue(u.arrived)

    def test_targets_include_named_minor_places(self):
        minor = [r for r in self.rows if not bases.is_place(self.save, r.target_id)]
        self.assertEqual(len(minor), 15)
        self.assertTrue(all(r.target_side in bases.SIDES.values() for r in minor))

    def test_embarked_unit(self):
        r = self.by_unit[4401]
        self.assertEqual((r.status, r.location), (lt.ABOARD, "aboard Higari Maru"))
        self.assertEqual((r.x, r.y), (97, 108))
        self.assertEqual(r.distance, mapview.hex_distance((97, 108), bases.place_hex(self.save, r.target_id)))
        aboard = [x for x in self.rows if x.status == lt.ABOARD]
        self.assertTrue(all(x.location.startswith("aboard ") and x.x is not None for x in aboard))

    def test_preparing_unit(self):
        r = self.by_unit[3942]
        self.assertEqual((r.name, r.status, r.location, r.prep), ("Imperial Guards Div", lt.PREPARING, "Bangkok", 100))
        self.assertEqual((r.target_name, r.target_side, r.enemy, r.side), ("Alor Star", "Allied", True, "Japanese"))
        self.assertEqual(r.distance, 12)

    def test_marching_unit(self):
        r = self.by_unit[7579]
        self.assertEqual((r.status, r.target_name, r.enemy, r.distance), (lt.MARCHING, "Ichang", True, 1))

    def test_unit_without_a_position(self):
        unknown = [r for r in self.rows if r.x is None]
        self.assertEqual(len(unknown), 30)
        self.assertTrue(all(r.location == "unknown" and r.distance is None for r in unknown))

    def test_side_filter(self):
        allied, japanese = lt.target_rows(self.save, "Allied"), lt.target_rows(self.save, "Japanese")
        self.assertEqual((len(allied), len(japanese)), (177, 407))
        self.assertTrue(all(r.side == "Allied" for r in allied))
        self.assertTrue(all(r.side == "Japanese" for r in japanese))
        self.assertEqual(sorted(r.unit_id for r in allied + japanese), sorted(self.by_unit))
        with self.assertRaises(ValueError):
            lt.target_rows(self.save, "Neutral")

    def test_rows_sorted_by_target_then_unit(self):
        keys = [(r.target_name.lower(), r.name.lower(), r.unit_id) for r in self.rows]
        self.assertEqual(keys, sorted(keys))

    def test_summaries_count_formations_not_records(self):
        summaries = lt.target_summaries(self.rows)
        self.assertEqual(len(summaries), 103)
        self.assertEqual(sum(s.units for s in summaries), 398)
        self.assertEqual(len({(r.side, r.name, r.target_id) for r in self.rows}), 398)
        s = next(s for s in summaries if s.target_id == 635)
        self.assertEqual((s.name, s.side, s.enemy, s.units), ("Vigan", "Allied", True, 18))
        self.assertEqual((s.preparing, s.marching, s.aboard, s.ready, s.nearest), (13, 0, 5, 8, 0))
        mine = [r for r in self.rows if r.target_id == 635]
        self.assertGreater(len(mine), s.units)
        self.assertEqual(s.nearest, min(r.distance for r in mine))
        # A formation split across statuses counts under each, so the columns can exceed Units.
        over = {s.name: s for s in summaries if s.preparing + s.marching + s.aboard > s.units}
        self.assertEqual((over["Kota Bharu"].units, over["Kota Bharu"].preparing, over["Kota Bharu"].aboard),
                         (25, 13, 13))

    def test_group_parts_folds_a_split_unit(self):
        groups = lt.group_parts(self.rows)
        self.assertEqual(len(groups), 400)
        self.assertEqual(sum(g.parts for g in groups), len(self.rows))
        g = next(g for g in groups if g.unit_id == 4401)
        self.assertEqual((g.name, g.status, g.parts, g.location), ("1st JNAF Coy", lt.ABOARD, 2, "aboard 2 ships"))
        key = (g.side, g.name, g.target_id, g.status)
        parts = [r for r in self.rows if (r.side, r.name, r.target_id, r.status) == key]
        self.assertEqual(len(parts), 2)
        self.assertEqual(g.unit_id, min(r.unit_id for r in parts))
        self.assertEqual(g.prep, min(r.prep for r in parts))
        self.assertEqual(g.distance, min(r.distance for r in parts))
        places = next(g for g in groups if g.unit_id == 6749)
        self.assertEqual((places.parts, places.location, places.distance), (3, "3 places", None))
        single = next(g for g in groups if g.unit_id == 3942)
        self.assertEqual((single.parts, single.location, single.prep), (1, "Bangkok", 100))
        keys = [(g.target_name.lower(), g.name.lower(), g.unit_id) for g in groups]
        self.assertEqual(keys, sorted(keys))

    def test_group_parts_by_hand(self):
        def row(uid, name, status, location, prep, distance, target=9):
            return lt.TargetRow(uid, name, "Allied", status, location, prep, target, "T", "Allied", False, 1, 1,
                                distance)

        rows = [row(10007, "X Rgt", lt.ABOARD, "aboard A", 40, 5), row(3961, "X Rgt", lt.ABOARD, "aboard B", 30, None),
                row(10015, "X Rgt", lt.PREPARING, "Manila", 100, 2), row(5, "Y Rgt", lt.PREPARING, "hex 1,1", 0, None)]
        groups = lt.group_parts(rows)
        self.assertEqual([(g.unit_id, g.status, g.parts, g.location, g.prep, g.distance) for g in groups],
                         [(3961, lt.ABOARD, 2, "aboard 2 ships", 30, 5), (10015, lt.PREPARING, 1, "Manila", 100, 2),
                          (5, lt.PREPARING, 1, "hex 1,1", 0, None)])
        s = lt.target_summaries(rows)[0]
        self.assertEqual((s.units, s.preparing, s.aboard, s.ready, s.nearest), (2, 2, 1, 1, 2))
        self.assertEqual(lt.group_parts([]), [])

    def test_summaries_enemy_first_then_units_then_name(self):
        summaries = lt.target_summaries(self.rows)
        keys = [(not s.enemy, -s.units, s.name.lower(), s.target_id) for s in summaries]
        self.assertEqual(keys, sorted(keys))
        self.assertTrue(summaries[0].enemy)
        self.assertFalse(summaries[-1].enemy)

    def test_summary_without_positions(self):
        row = lt.TargetRow(1, "A", "Japanese", lt.PREPARING, "unknown", 5, 9, "T", "Allied", True, None, None, None)
        s = lt.target_summaries([row])[0]
        self.assertEqual((s.units, s.preparing, s.ready, s.nearest), (1, 1, 0, None))
        self.assertEqual(lt.target_summaries([]), [])


class ShipHexTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.save = SaveFile.load(SAVE_015)

    def test_ship_in_task_force_and_in_port(self):
        in_tf = in_port = None
        for s in shiprecords.list_ship_records(self.save):
            tf = taskforces._ship(self.save, s.id, shiprecords.TASK_FORCE_OFFSET)
            if tf and taskforces.is_task_force(self.save, tf):
                in_tf = in_tf or (s.id, bases.place_hex(self.save, tf))
            else:
                port = taskforces._ship(self.save, s.id, shiprecords.BASE_OFFSET)
                if bases.is_place(self.save, port):
                    in_port = in_port or (s.id, bases.place_hex(self.save, port))
        self.assertIsNotNone(in_tf)
        self.assertIsNotNone(in_port)
        self.assertEqual(mapview.ship_hex(self.save, in_tf[0]), in_tf[1])
        self.assertEqual(mapview.ship_hex(self.save, in_port[0]), in_port[1])

    def test_unknown_ship(self):
        self.assertIsNone(mapview.ship_hex(self.save, 0))
        self.assertIsNone(mapview.ship_hex(self.save, 99999))

    def test_group_hex_matches_the_original_rule(self):
        from witpae import airgroups

        def original(group):
            loc = group.location_id
            if bases.is_place(self.save, loc):
                return bases.place_hex(self.save, loc)
            if loc < airgroups.SHIP_LOCATION_BASE:
                return None
            ship = loc - airgroups.SHIP_LOCATION_BASE
            if not taskforces._ship_exists(self.save, ship):
                return None
            tf = taskforces._ship(self.save, ship, shiprecords.TASK_FORCE_OFFSET)
            if tf and taskforces.is_task_force(self.save, tf):
                return bases.place_hex(self.save, tf)
            port = taskforces._ship(self.save, ship, shiprecords.BASE_OFFSET)
            return bases.place_hex(self.save, port) if bases.is_place(self.save, port) else None

        groups = airgroups.list_airgroups(self.save)
        self.assertTrue(any(g.location_id >= airgroups.SHIP_LOCATION_BASE for g in groups))
        for g in groups:
            self.assertEqual(mapview.group_hex(self.save, g), original(g))


if __name__ == "__main__":
    unittest.main()
