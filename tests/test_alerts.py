import os
import struct
import unittest
from types import SimpleNamespace
from unittest import mock

from witpae import aircraft, alerts, bases, minefields, pilotpool, shiprecords, shiprepair
from witpae.container import SaveFile

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
SAVE_015 = os.path.join(DATA_DIR, "going2_411210.pws")
PEARL, BATAAN, SOERABAJA, MIDWAY, JAVA = 584, 621, 1160, 581, 3231
BARBICAN = 9979  # Allied ACM


class SortTests(unittest.TestCase):
    def test_collect_sort_order(self):
        fake = {
            "Low supply": lambda ctx, s, p: [alerts.Alert("Low supply", "Allied", "b", "", "base", 1, 5),
                                              alerts.Alert("Low supply", "Allied", "A", "", "base", 2, 5),
                                              alerts.Alert("Low supply", "Allied", "z", "", "base", 3, 9)],
            "Engines": lambda ctx, s, p: [alerts.Alert("Engines", "Japanese", "e", "", "engine", 4, 1)],
            "Spoilage": lambda ctx, s, p: [alerts.Alert("Spoilage", "Allied", "s", "", "base", 5, 0)],
        }
        with mock.patch.dict(alerts.CHECKS, {c: (lambda ctx, s, p: []) for c in alerts.CATEGORIES}), \
                mock.patch.dict(alerts.CHECKS, fake):
            found, skipped = alerts.collect(None)
        self.assertEqual([a.subject for a in found], ["z", "A", "b", "s", "e"])
        self.assertEqual(skipped, [])

    def test_defaults_and_categories(self):
        self.assertEqual(alerts.DEFAULTS, {"supply_pct": 50, "pilot_pool": 100})
        self.assertEqual(alerts.CATEGORIES, ("Low supply", "Spoilage", "Repair", "Minefields", "Pilots", "Aircraft",
                                             "Engines"))
        self.assertEqual(set(alerts.CHECKS), set(alerts.CATEGORIES))

    def test_failing_check_is_skipped_alone(self):
        def boom(ctx, s, p):
            raise IndexError("short")
        ok = alerts.Alert("Spoilage", "Allied", "s", "", "base", 5, 0)
        with mock.patch.dict(alerts.CHECKS, {c: (lambda ctx, s, p: []) for c in alerts.CATEGORIES}), \
                mock.patch.dict(alerts.CHECKS, {"Pilots": boom, "Spoilage": lambda ctx, s, p: [ok]}):
            found, skipped = alerts.collect(None)
        self.assertEqual((found, skipped), ([ok], ["Pilots"]))


@unittest.skipUnless(os.path.exists(SAVE_015), "sample save missing")
class AlertTests(unittest.TestCase):
    def setUp(self):
        self.sf = SaveFile.load(SAVE_015)

    def poke_base(self, loc_id, **values):
        base = bases.Base(self.sf, loc_id, "")
        for name, value in values.items():
            f = bases.FIELD_BY_NAME[name]
            struct.pack_into("<" + f.fmt, self.sf[bases.LOCATION_SECTION].data, base._offset + f.offset, value)

    def poke_ship(self, ship_id, offset, value, fmt="H"):
        rec = {r.id: r for r in shiprecords.list_ship_records(self.sf)}[ship_id]
        struct.pack_into("<" + fmt, rec._data, rec._offset + offset, value)

    def put_mines(self, rec, x, y, side, mines):
        struct.pack_into("<6H", self.sf[minefields.SECTION].data, rec * minefields.RECORD_SIZE,
                         x, y, side, 0, 1645, mines)

    def found(self, category, **kwargs):
        alert_list, skipped = alerts.collect(self.sf, **kwargs)
        return [a for a in alert_list if a.category == category], skipped

    # ---- the sample save -------------------------------------------------------

    def test_counts_on_the_sample(self):
        found, skipped = alerts.collect(self.sf)
        self.assertEqual(skipped, [])
        counts = {c: sum(1 for a in found if a.category == c) for c in alerts.CATEGORIES}
        self.assertEqual(counts, {"Low supply": 4, "Spoilage": 7, "Repair": 0, "Minefields": 2, "Pilots": 0,
                                  "Aircraft": 3, "Engines": 5})
        order = [alerts.CATEGORIES.index(a.category) for a in found]
        self.assertEqual(order, sorted(order))
        self.assertTrue(all(a.kind in alerts.KINDS for a in found))

    def test_sorted_within_a_category(self):
        for category in ("Low supply", "Minefields", "Aircraft", "Engines"):
            rows, _ = self.found(category)
            self.assertEqual([r.sort_value for r in rows], sorted((r.sort_value for r in rows), reverse=True))

    # ---- low supply --------------------------------------------------------------

    def test_low_supply_boundary_and_threshold(self):
        self.poke_base(PEARL, supply=49, supply_required=100, value_japan=0, value_allies=0)
        rows, _ = self.found("Low supply")
        self.assertIn(PEARL, [r.target_id for r in rows])
        self.poke_base(PEARL, supply=50)
        self.assertNotIn(PEARL, [r.target_id for r in self.found("Low supply")[0]])
        self.assertIn(PEARL, [r.target_id for r in self.found("Low supply", supply_pct=51)[0]])
        self.assertNotIn(PEARL, [r.target_id for r in self.found("Low supply", supply_pct=50)[0]])
        self.poke_base(PEARL, supply=0, supply_required=0)  # nothing required
        self.assertNotIn(PEARL, [r.target_id for r in self.found("Low supply", supply_pct=100)[0]])

    def test_low_supply_detail_and_victory_value(self):
        self.poke_base(PEARL, supply=30, supply_required=100, value_japan=1, value_allies=3, port=7, airfield=8)
        a = next(r for r in self.found("Low supply")[0] if r.target_id == PEARL)
        self.assertEqual((a.side, a.kind, a.detail), ("Allied", "base", "Supply 30 of 100 needed (30%); scores 33 of 69 VP"))
        self.assertEqual(a.sort_value, (69 - 33) * 1000 + 20)
        self.poke_base(PEARL, value_japan=0, value_allies=0)
        a = next(r for r in self.found("Low supply")[0] if r.target_id == PEARL)
        self.assertEqual((a.detail, a.sort_value), ("Supply 30 of 100 needed (30%)", 20))

    def test_low_supply_thousands_separator(self):
        self.poke_base(PEARL, supply=1200, supply_required=3400, value_japan=0, value_allies=0)
        a = next(r for r in self.found("Low supply")[0] if r.target_id == PEARL)
        self.assertEqual(a.detail, "Supply 1,200 of 3,400 needed (35%)")

    # ---- spoilage ----------------------------------------------------------------

    def test_spoilage_boundary(self):
        self.poke_base(PEARL, port=1, airfield=0, supply=8000, fuel=0)  # limits 8,000 and 3,000
        self.assertNotIn(PEARL, [r.target_id for r in self.found("Spoilage")[0]])
        self.poke_base(PEARL, supply=8001)
        a = next(r for r in self.found("Spoilage")[0] if r.target_id == PEARL)
        self.assertEqual((a.detail, a.sort_value, a.side, a.kind),
                         ("Supply 1 over the 8,000 limit", 1, "Allied", "base"))
        self.poke_base(PEARL, supply=0, fuel=3000)
        self.assertNotIn(PEARL, [r.target_id for r in self.found("Spoilage")[0]])
        self.poke_base(PEARL, supply=8002, fuel=3005)
        a = next(r for r in self.found("Spoilage")[0] if r.target_id == PEARL)
        self.assertEqual((a.detail, a.sort_value),
                         ("Supply 2 over the 8,000 limit; Fuel 5 over the 3,000 limit", 7))

    # ---- repair ------------------------------------------------------------------

    def test_repair_ship_too_big_for_its_port(self):
        # Midway holds a damaged 1,700 t ship; at port size 0 with no yard it is too big.
        self.assertEqual(self.found("Repair")[0], [])
        self.poke_base(MIDWAY, port=0)
        rows, _ = self.found("Repair")
        ships = [r for r in rows if r.kind == "ship"]
        self.assertEqual(len(ships), 1)
        self.assertEqual((ships[0].detail.startswith("Too big for "), ships[0].sort_value), (True, 1700))
        self.assertTrue(ships[0].detail.endswith(": 1,700 t; port takes 0 t, yard 0 t"))
        self.assertEqual(ships[0].side, "Allied")

    def fake_repair(self, tons, largest, capacity, shipyard_tons=0, port_id=7):
        ship = SimpleNamespace(id=99, name="Big", side="Allied", tons=tons, port_id=port_id)
        port = SimpleNamespace(id=7, name="Port", side="Allied", largest=largest, yard_capacity=capacity,
                               shipyard_tons=shipyard_tons)
        return (mock.patch.object(alerts.shiprepair, "damaged_ships", return_value=[ship]),
                mock.patch.object(alerts.shiprepair, "repair_ports", return_value=[port]))

    def test_repair_oversize_boundaries(self):
        for tons, largest, capacity, expected in ((24000, 24000, 12000, 0), (24000, 6000, 24000, 0), (24001, 24000, 24000, 1),
                                                   (24001, 24000, 12000, 1), (31000, 24000, 12000, 1),
                                                   (12000, 6000, 12000, 0)):
            a, b = self.fake_repair(tons, largest, capacity)
            with a, b:
                rows, _ = self.found("Repair")
            self.assertEqual(len(rows), expected, (tons, largest, capacity))
        a, b = self.fake_repair(31000, 24000, 12000)
        with a, b:
            self.assertEqual(self.found("Repair")[0][0].detail,
                             "Too big for Port: 31,000 t; port takes 24,000 t, yard 12,000 t")

    def test_repair_ship_at_sea_is_ignored(self):
        a, b = self.fake_repair(31000, 24000, 12000, port_id=None)
        with a, b:
            self.assertEqual(self.found("Repair")[0], [])

    def test_repair_shipyard_queue(self):
        a, b = self.fake_repair(100, 24000, 12000, shipyard_tons=12000)
        with a, b:
            self.assertEqual(self.found("Repair")[0], [])
        a, b = self.fake_repair(100, 24000, 12000, shipyard_tons=45000)
        with a, b:
            row = self.found("Repair")[0][0]
        self.assertEqual((row.detail, row.kind, row.target_id, row.sort_value),
                         ("Shipyard queue 33,000 t over a 12,000 t yard", "base", 7, 33000))

    def test_repair_shipyard_queue_on_the_sample(self):
        for r in shiprepair.damaged_ships(self.sf):
            if r.port_id == SOERABAJA:
                self.poke_ship(r.id, shiprepair.MODE_OFFSET, 3, "B")
        a = next(r for r in self.found("Repair")[0] if r.kind == "base")
        self.assertEqual((a.subject, a.target_id, a.detail), ("Soerabaja", SOERABAJA,
                                                             "Shipyard queue 5,113 t over a 8,000 t yard"))

    # ---- minefields --------------------------------------------------------------

    def allied(self):
        rows, _ = self.found("Minefields")
        return next(r for r in rows if r.side == "Allied")

    def test_minefields_one_alert_per_side(self):
        rows, _ = self.found("Minefields")
        self.assertEqual([(r.side, r.subject, r.kind, r.target_id) for r in sorted(rows, key=lambda r: r.side)],
                         [("Allied", "Own-port minefields", "minefields", "Allied"),
                          ("Japanese", "Own-port minefields", "minefields", "Japanese")])
        a = self.allied()
        self.assertEqual(a.sort_value, 9358)
        self.assertEqual(a.detail, "33 ports with 9,358 unprotected mines, losing about 94 a day "
                                   "(each docked ACM protects 150)")

    def test_minefield_protection_changes_the_total(self):
        before = self.allied().sort_value
        self.put_mines(1, 78, 77, 1, 100)
        self.put_mines(2, 78, 77, 1, 50)  # Bataan: 150 mines instead of 995
        self.assertEqual(self.allied().sort_value, before - 995 + 150)
        self.poke_ship(BARBICAN, shiprecords.BASE_OFFSET, BATAAN)  # one ACM protects exactly 150
        self.assertEqual(self.allied().sort_value, before - 995)
        self.put_mines(2, 78, 77, 1, 51)
        self.assertEqual(self.allied().sort_value, before - 995 + 1)

    def test_minefield_in_open_sea_is_ignored_on_the_save(self):
        before = self.allied().sort_value
        self.put_mines(5000, 5, 5, 1, 400)
        self.assertEqual(minefields.hex_rows(self.sf, [f for f in minefields.list_fields(self.sf)
                                                       if (f.x, f.y) == (5, 5)])[0].place, minefields.OPEN_SEA)
        self.assertEqual(self.allied().sort_value, before)

    def fake_hexes(self, rows, place_side=1):
        return (mock.patch.object(alerts.minefields, "list_fields", return_value=[]),
                mock.patch.object(alerts.minefields, "hex_rows", return_value=rows),
                mock.patch.object(alerts.bases, "place_side_id", return_value=place_side))

    @staticmethod
    def hex_row(side, mines, protected, decay, place_id=7):
        return SimpleNamespace(side=side, place_id=place_id, mines=mines, protected=protected, decay=decay)

    def test_minefield_aggregation_and_decay(self):
        rows = [self.hex_row("Allied", 1000, 400, minefields.DECAY_PORT),
                self.hex_row("Allied", 500, 0, minefields.DECAY_OPEN),
                self.hex_row("Allied", 300, 300, minefields.DECAY_PORT)]  # fully protected: not counted
        a, b, c = self.fake_hexes(rows)
        with a, b, c:
            found = self.found("Minefields")[0]
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].sort_value, 1100)
        self.assertTrue(found[0].detail.startswith("2 ports with 1,100 unprotected mines, losing about 31 a day ("))

    def test_minefield_side_with_everything_protected_has_no_alert(self):
        rows = [self.hex_row("Allied", 300, 300, minefields.DECAY_PORT), self.hex_row("Japanese", 50, 0, "1%/day")]
        a, b, c = self.fake_hexes(rows, place_side=0)  # the place is Japanese: the Allied hex is on an enemy base
        with a, b, c:
            found = self.found("Minefields")[0]
        self.assertEqual([(r.side, r.sort_value) for r in found], [("Japanese", 50)])
        self.assertTrue(found[0].detail.startswith("1 port with 50 unprotected mines, losing about 0 a day"))
        a, b, c = self.fake_hexes([self.hex_row("Allied", 300, 300, minefields.DECAY_PORT)])
        with a, b, c:
            self.assertEqual(self.found("Minefields")[0], [])

    def test_minefield_in_open_sea_has_no_place(self):
        a, b, c = self.fake_hexes([self.hex_row("Allied", 400, 0, minefields.DECAY_OPEN, place_id=None)])
        with a, b, c:
            self.assertEqual(self.found("Minefields")[0], [])

    # ---- pilots ------------------------------------------------------------------

    def one_pool(self):
        return next(p for p in pilotpool.list_pools(self.sf) if not p.is_empty)

    def test_pilots_boundary_and_threshold(self):
        p = self.one_pool()
        p.set("pool", 100)
        self.assertNotIn(p.nation_id, [r.target_id for r in self.found("Pilots")[0]])
        p.set("pool", 99)
        a = next(r for r in self.found("Pilots")[0] if r.target_id == p.nation_id)
        self.assertEqual((a.side, a.subject, a.kind, a.sort_value), (p.side, p.label, "pilots", 1))
        self.assertEqual(a.detail, f"Pool 99 pilots (rate {p.get('rate')}/month, {p.in_training:,} in training)")
        self.assertNotIn(p.nation_id, [r.target_id for r in self.found("Pilots", pilot_pool=99)[0]])
        p.set("pool", 120)
        self.assertIn(p.nation_id, [r.target_id for r in self.found("Pilots", pilot_pool=121)[0]])

    def test_pilots_empty_nation_is_ignored(self):
        p = self.one_pool()
        p.set_many({"pool": 0, "rate": 0, **{f"count{k}": 0 for k in range(pilotpool.INTAKES)}})
        self.assertTrue(p.is_empty)
        self.assertNotIn(p.nation_id, [r.target_id for r in self.found("Pilots", pilot_pool=500)[0]])

    # ---- aircraft ----------------------------------------------------------------

    def test_aircraft_on_the_sample(self):
        rows, _ = self.found("Aircraft")
        self.assertEqual(len(rows), 3)
        nate = next(r for r in rows if r.subject.startswith("Ki-27b Nate"))
        self.assertEqual((nate.side, nate.kind, nate.target_id, nate.sort_value), ("Japanese", "aircraft", 752, 92))
        self.assertEqual(nate.detail, "Groups short 139 planes; pool 2 + 45 in 30 days at 1.5/day")

    def test_aircraft_pool_removes_the_alert(self):
        top = self.found("Aircraft")[0][0]
        model = next(a for a in aircraft.list_aircraft(self.sf) if a.id == top.target_id)
        model.set_pool(model.pool + int(top.sort_value))  # short == pool + production: not above
        self.assertNotIn(top.target_id, [r.target_id for r in self.found("Aircraft")[0]])

    def fake_air(self, short, pool, planes_day):
        row = SimpleNamespace(id=5, name="Plane", side="Allied", short=short, pool=pool, planes_day=planes_day)
        return mock.patch.object(alerts.airproduction, "air_rows", return_value=[row])

    def test_aircraft_boundary(self):
        self.assertEqual(alerts.PRODUCTION_DAYS, 30)
        for short, pool, per_day, expected in ((57, 12, 1.5, 0), (58, 12, 1.5, 1), (13, 12, 0, 0), (1000, 0, 0, 0),
                                               (30, 0, 1, 0), (31, 0, 1, 1)):
            with self.fake_air(short, pool, per_day):
                self.assertEqual(len(self.found("Aircraft")[0]), expected, (short, pool, per_day))
        with self.fake_air(139, 2, 1.5):
            a = self.found("Aircraft")[0][0]
        self.assertEqual((a.detail, a.sort_value, a.target_id),
                         ("Groups short 139 planes; pool 2 + 45 in 30 days at 1.5/day", 92, 5))

    # ---- engines -----------------------------------------------------------------

    def test_engines_on_the_sample(self):
        rows, _ = self.found("Engines")
        ha33 = next(r for r in rows if r.subject == "Mitsubishi Ha-33")
        self.assertEqual((ha33.side, ha33.kind, ha33.target_id, ha33.sort_value), ("Japanese", "engine", 244, 42))
        self.assertEqual(ha33.detail, "Factories build 65 of 107 needed (pool 119)")

    def test_engines_boundary(self):
        def fake(net, pool=120):
            row = SimpleNamespace(id=9, name="Ha-1", size=45 + net, needed=45, net=net, pool=pool)
            return mock.patch.object(alerts.airproduction, "engine_rows", return_value=[row])
        with fake(0):
            self.assertEqual(self.found("Engines")[0], [])
        with fake(-15, pool=None):
            a = self.found("Engines")[0][0]
        self.assertEqual((a.detail, a.sort_value), ("Factories build 30 of 45 needed (pool unknown)", 15))

    # ---- skipped checks ----------------------------------------------------------

    def test_missing_minefield_section_skips_only_that_check(self):
        del self.sf._by_id[minefields.SECTION]
        found, skipped = alerts.collect(self.sf)
        self.assertEqual(skipped, ["Minefields"])
        self.assertEqual({a.category for a in found}, {"Low supply", "Spoilage", "Aircraft", "Engines"})

    def test_short_pilot_section_skips_only_that_check(self):
        del self.sf[pilotpool.SECTION].data[pilotpool.SECTION_END - 1:]
        found, skipped = alerts.collect(self.sf)
        self.assertIn("Pilots", skipped)
        self.assertTrue(any(a.category == "Low supply" for a in found))
        self.assertTrue(any(a.category == "Minefields" for a in found))


if __name__ == "__main__":
    unittest.main()
