import os
import tempfile
import unittest

from witpae import aircraft
from witpae.container import SaveFile

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
SAVE_015 = os.path.join(DATA_DIR, "going2_411210.pws")
SECTION = aircraft.AIRCRAFT_SECTION
RECORD = aircraft.AIRCRAFT_RECORD_SIZE


@unittest.skipUnless(os.path.exists(SAVE_015), "sample save missing")
class AircraftTests(unittest.TestCase):
    def setUp(self):
        self.sf = SaveFile.load(SAVE_015)
        self.by_id = {a.id: a for a in aircraft.list_aircraft(self.sf)}

    @staticmethod
    def ranges(a):
        return {name: (a.get(name + "_hex"), a.get(name + "_miles")) for name, *_ in aircraft.RANGES}

    def roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "out.pws")
            self.sf.save(path)
            return SaveFile.load(path)

    def test_pool_matches_production_screen(self):
        # (in pool, used, last turn, this month, rate) from the game's aircraft and engine production screen.
        expected = {336: (3, 0, 1, 3, 25), 342: (0, 4, 1, 4, 35), 435: (12, 0, 4, 12, 130), 447: (32, 9, 0, 1, 14)}
        for aid, values in expected.items():
            a = self.by_id[aid]
            self.assertEqual((a.pool, a.used, a.last_turn, a.this_month, a.get("rate")), values, a.name)

    def test_pool_edit_roundtrip(self):
        self.by_id[342].set_pool(50)
        self.by_id[342].set("rate", 40)
        again = self.roundtrip()
        a = {x.id: x for x in aircraft.list_aircraft(again)}[342]
        self.assertEqual((a.pool, a.used, a.get("rate")), (50, 4, 40))
        old = bytes(SaveFile.load(SAVE_015)[aircraft.POOL_SECTION].data)
        new = bytes(again[aircraft.POOL_SECTION].data)
        pos = aircraft.POOL[0] + 342 * aircraft.POOL[1]
        self.assertEqual({i for i in range(len(old)) if old[i] != new[i]}, {pos})

    def test_pool_validation(self):
        before = bytes(self.sf[aircraft.POOL_SECTION].data)
        for value in (-1, aircraft.MAX_POOL + 1, True, "5"):
            with self.assertRaises(ValueError, msg=value):
                self.by_id[342].set_pool(value)
        self.assertEqual(bytes(self.sf[aircraft.POOL_SECTION].data), before)

    def test_list_skips_empty_and_keeps_duplicate_names(self):
        self.assertEqual(len(self.by_id), 555)
        sbd = [a.id for a in self.by_id.values() if a.name == "SBD-3 Dauntless"]
        self.assertIn(260, sbd)
        self.assertIn(487, sbd)
        self.assertTrue(all(a.name for a in self.by_id.values()))

    def test_p38(self):
        a = self.by_id[332]
        self.assertEqual(a.name, "P-38G Lightning")
        self.assertEqual([a.get(n) for n in ("max_alt", "speed", "cruise", "climb", "maneuver",
                                             "armor", "durability", "load")],
                         [39000, 400, 340, 2350, 14, 1, 37, 3200])
        self.assertEqual((a.type_id, a.type, a.nation_id, a.nation), (0, "Fighter", 5, "USA"))
        self.assertEqual((a.get_date("from"), a.get_date("to")), ((10, 42), (5, 43)))
        self.assertFalse(a.get_carrier())
        self.assertEqual(a.gun_value, 16)
        self.assertEqual(a.max_weapons, [
            ("20mm Hispano Cannon", 1, "C"), (".50 Browning MG", 4, "C"), ("500 lb GP Bomb", 2, "XT"),
            ("300 gal Drop Tank", 2, "XT"), ("Engine", 2, "F")])
        self.assertEqual(a.maneuver_mods, [14, 14, 14, 13, 10])
        self.assertEqual(self.ranges(a), {
            "max_range": (16, 630), "normal_radius": (5, 190), "extended_radius": (6, 240),
            "max_range_tanks": (40, 1590), "normal_radius_tanks": (13, 485),
            "extended_radius_tanks": (16, 610)})
        self.assertEqual(a.endurance, 322)
        self.assertTrue(a.reduced_weapons)

    def test_sbd3_usn(self):
        a = self.by_id[487]
        self.assertEqual([a.get(n) for n in ("speed", "cruise", "max_alt", "climb", "maneuver", "durability",
                                             "armor", "load")],
                         [250, 173, 26000, 1190, 13, 31, 1, 2250])
        self.assertEqual((a.type, a.nation), ("Dive Bomber", "USN"))
        self.assertEqual((a.get_date("from"), a.get_date("to")), ((12, 41), (4, 43)))
        self.assertTrue(a.get_carrier())
        self.assertEqual(a.gun_value, 10)
        self.assertEqual(a.max_weapons, [
            (".50 Browning MG", 2, "C"), (".30 Browning MG", 2, "TR"), ("1000 lb GP Bomb", 1, "XT"),
            ("Engine", 1, "F")])
        self.assertEqual(self.ranges(a), {
            "max_range": (30, 1170), "normal_radius": (7, 250), "extended_radius": (8, 315),
            "max_range_tanks": (0, 0), "normal_radius_tanks": (0, 0), "extended_radius_tanks": (0, 0)})
        self.assertEqual(a.endurance, 466)

    def test_endurance_is_calculated(self):
        a = self.by_id[487]
        a.set("cruise", 180)
        self.assertEqual(a.endurance, 448)
        a.set_many({"max_range_miles": 2340})
        self.assertEqual(a.endurance, 897)
        a.set("cruise", 0)
        self.assertIsNone(a.endurance)
        with self.assertRaises(ValueError):
            a.validate("endurance", 5)
        with self.assertRaises(ValueError):
            a.set("endurance", 5)

    def test_range_edit_writes_only_range_bytes(self):
        before = bytes(self.sf[SECTION].data)
        self.by_id[332].set_many({"normal_radius_tanks_hex": 14, "normal_radius_tanks_miles": 500})
        after = bytes(self.sf[SECTION].data)
        changed = {i - 332 * RECORD for i in range(len(before)) if before[i] != after[i]}
        self.assertEqual(changed, {294, 296})
        self.assertEqual(self.ranges(self.by_id[332])["normal_radius_tanks"], (14, 500))
        for bad in ({"max_range_hex": 201}, {"max_range_miles": 10001}, {"max_range_hex": -1}):
            with self.assertRaises(ValueError):
                self.by_id[332].set_many(bad)
        self.assertEqual(bytes(self.sf[SECTION].data), after)

    def test_sbd3_nz(self):
        a = self.by_id[260]
        self.assertEqual((a.get_date("from"), a.get_date("to")), ((7, 42), (2, 44)))
        self.assertEqual((a.nation, a.get_carrier()), ("NZ", False))
        self.assertIn(("1000 lb GP Bomb", 1, "C"), a.max_weapons)

    def test_labels(self):
        self.assertEqual(aircraft.type_label(12), "Torpedo Bomber?")
        self.assertEqual(aircraft.type_label(99), "99")
        self.assertEqual(aircraft.nation_label(2), "IJN")
        self.assertEqual(aircraft.nation_label(9), "UK")
        self.assertEqual(aircraft.nation_label(12), "China?")
        self.assertEqual(aircraft.nation_label(77), "77")

    def test_upgrade(self):
        a = self.by_id[332]
        self.assertEqual(a.upgrade_name, aircraft._plain_name(self.sf[SECTION].data, a.upgrade_id * RECORD)
                         if 0 <= a.upgrade_id < 1000 else "")

    def test_parse_date(self):
        self.assertEqual(aircraft.parse_date("12/41"), (12, 41))
        self.assertEqual(aircraft.parse_date(" 1/05 "), (1, 5))
        self.assertEqual(aircraft.parse_date("0/0"), (0, 0))
        self.assertEqual(aircraft.format_date(5, 43), "5/43")
        self.assertEqual(aircraft.format_date(1, 5), "1/05")
        self.assertEqual(aircraft.parse_date(aircraft.format_date(0, 0)), (0, 0))
        for bad in ("", "13/41", "0/41", "5/100", "5", "a/b", "5/-1", "1/2/3"):
            with self.assertRaises(ValueError, msg=bad):
                aircraft.parse_date(bad)

    def test_stored_none_dates_are_editable(self):
        a = next(a for a in self.by_id.values() if a.get_date("to") == (0, 0))
        a.set_date("to", (0, 0))
        a.set_date("to", (3, 45))
        a.set_date("to", (0, 0))
        self.assertEqual(a.get_date("to"), (0, 0))

    def test_edit_roundtrip_changes_only_expected_bytes(self):
        before = bytes(self.sf[SECTION].data)
        a = self.by_id[487]
        a.set_many({"speed": 260, "max_alt": 41000, "armor": 3})
        a.set_date("from", (1, 42))
        a.set_date("to", (6, 44))
        a.set_carrier(False)
        other = self.roundtrip()
        after = bytes(other[SECTION].data)
        changed = {i for i in range(len(before)) if before[i] != after[i]}
        base = 487 * RECORD
        self.assertEqual(changed, {base + o for o in (28, 29, 30, 31, 40, 184, 185, 282, 283, 232)})
        b = {x.id: x for x in aircraft.list_aircraft(other)}[487]
        self.assertEqual((b.get("speed"), b.get("max_alt"), b.get("armor")), (260, 41000, 3))
        self.assertEqual((b.get_date("from"), b.get_date("to"), b.get_carrier()), ((1, 42), (6, 44), False))

    def test_other_sections_untouched(self):
        pristine = SaveFile.load(SAVE_015)
        self.by_id[332].set("speed", 123)
        other = self.roundtrip()
        for sec in pristine.sections:
            if sec.sid != SECTION:
                self.assertEqual(bytes(sec.data), bytes(other[sec.sid].data), hex(sec.sid))
        self.assertEqual(len(pristine.sections), len(other.sections))

    def test_carrier_preserves_other_bits(self):
        a = self.by_id[332]
        data = self.sf[SECTION].data
        pos = 332 * RECORD + aircraft.CARRIER_OFFSET
        data[pos] = 0xF5
        a.set_carrier(True)
        self.assertEqual(data[pos], 0xFD)
        self.assertTrue(a.get_carrier())
        a.set_carrier(False)
        self.assertEqual(data[pos], 0xF5)
        with self.assertRaises(ValueError):
            a.set_carrier(1)

    def test_validation_failures_leave_bytes_unchanged(self):
        before = bytes(self.sf[SECTION].data)
        a = self.by_id[332]
        bad_sets = [
            {"speed": 5, "armor": 11},
            {"speed": 5, "maneuver": -1},
            {"max_alt": 60001},
            {"speed": True},
            {"speed": "5"},
            {"nope": 1},
        ]
        for values in bad_sets:
            with self.assertRaises(ValueError, msg=str(values)):
                a.set_many(values)
        for name, value in (("from", (13, 41)), ("to", (5, 100)), ("from", (0, 5)), ("from", "1/42"),
                            ("when", (1, 42))):
            with self.assertRaises(ValueError):
                a.set_date(name, value)
        self.assertEqual(bytes(self.sf[SECTION].data), before)


if __name__ == "__main__":
    unittest.main()
