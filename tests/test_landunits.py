import os
import tempfile
import unittest

from witpae import bases, landunits
from witpae.container import SaveFile

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
SAVE_015 = os.path.join(DATA_DIR, "going2_411210.pws")
SECTION = landunits.LOCATION_SECTION
RECORD = landunits.RECORD_SIZE


@unittest.skipUnless(os.path.exists(SAVE_015), "sample save missing")
class LandUnitTests(unittest.TestCase):
    def setUp(self):
        self.sf = SaveFile.load(SAVE_015)
        self.units = {u.id: u for u in landunits.list_land_units(self.sf)}

    def roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "out.pws")
            self.sf.save(path)
            return SaveFile.load(path)

    def test_list_excludes_bases_and_other_types(self):
        base_ids = {b.id for b in bases.list_bases(self.sf)}
        self.assertFalse(base_ids & set(self.units))
        self.assertTrue({u.type_id for u in self.units.values()} <= landunits.LAND_TYPES)
        self.assertIn(5639, self.units)
        self.assertIn(5635, self.units)

    def test_infantry_battalion(self):
        u = self.units[5639]
        self.assertEqual((u.name, u.type, u.side), ("1/153rd Infantry", "INF", "Allied"))
        self.assertEqual((u.hq_id, u.hq_name, u.location_name), (100, "West Coast", "Seattle"))
        self.assertEqual([u.get(n) for n in ("experience", "morale", "fatigue", "supplies")], [50, 52, 4, 99])
        self.assertEqual(u.supplies_required, 89)
        self.assertEqual(u.target_id, 569)
        eq = dict(u.list_equipment())
        self.assertEqual(sorted(eq), [0, 1, 2, 3, 4, 6])
        self.assertEqual(eq[0], {"device": "USA Rifle Squad", "count": 28, "disabled": 3,
                                 "toe_device": "USA Rifle Squad", "toe_count": 31})
        self.assertEqual([(eq[k]["device"], eq[k]["count"]) for k in (1, 2, 3, 4)],
                         [("US MMG Section", 4), ("US HMG Section", 4), ("37mm M3 AT Gun", 6),
                          ("81mm M1 Mortar", 6)])
        self.assertEqual(eq[6], {"device": "Support", "count": 38, "disabled": 7,
                                 "toe_device": "Support", "toe_count": 45})

    def test_coast_defence_with_upgrade_target(self):
        u = self.units[5635]
        self.assertEqual((u.name, u.type, u.hq_name, u.location_name), ("1/250th", "CD", "West Coast", "Anchorage"))
        self.assertEqual([u.get(n) for n in ("experience", "morale", "fatigue", "supplies")], [50, 53, 2, 37])
        eq = dict(u.list_equipment())
        self.assertEqual((eq[0]["device"], eq[0]["count"]), ("0.5in M2HB AAMG", 6))
        self.assertEqual((eq[1]["device"], eq[1]["count"], eq[1]["toe_device"]),
                         ("155mm M1918 GPF", 8, "155mm M1A1 GPF"))
        self.assertEqual((eq[3]["device"], eq[3]["count"], eq[3]["toe_count"]), ("Motorized Support", 2, 6))

    def test_display_names_match_game(self):
        # Names as shown on the game's ground unit list and detail screens.
        expected = {5621: "131st FA Bn", 5639: "1/153rd Infantry Bn", 5635: "1/250th Cst Art Bn",
                    5630: "1/151st Combat Engr Bn", 5542: "Johnston (Det.) Def Bn", 5055: "101st USN Base Force",
                    102: "Pacific Fleet"}
        for unit_id, name in expected.items():
            self.assertEqual(self.units[unit_id].display_name, name)
        # Unknown classes fall back to the category.
        self.assertEqual(self.units[5638].display_name, "153rd(Sep) Infantry (Infantry)")

    def test_disruption_and_support(self):
        u = self.units[10143]
        self.assertEqual((u.name, u.type), ("131st", "ART"))
        self.assertEqual(u.get("disruption"), 9)
        self.assertIsInstance(u.support, int)
        self.assertIsInstance(u.support_required, int)
        before = bytes(self.sf[SECTION].data)
        u.set("disruption", 10)
        after = bytes(self.sf[SECTION].data)
        self.assertEqual([i - 10143 * RECORD for i in range(len(before)) if before[i] != after[i]], [440])
        with self.assertRaises(ValueError):
            u.set("disruption", 100)

    def test_labels(self):
        self.assertEqual(landunits.type_label(4), "HQ")
        self.assertEqual(landunits.type_label(8), "ARM?")
        self.assertEqual(landunits.type_label(99), "99")

    def test_edit_roundtrip_changes_only_expected_bytes(self):
        before = bytes(self.sf[SECTION].data)
        u = self.units[5639]
        u.set_many({"morale": 70, "fatigue": 0, "supplies": 1000})
        u.set_equipment(0, 20, 5)
        after = bytes(self.roundtrip()[SECTION].data)
        changed = {i - 5639 * RECORD for i in range(len(before)) if before[i] != after[i]}
        # supplies 99 -> 1000 changes both low bytes; counts and disabled are one byte each.
        self.assertEqual(changed, {649, 650, 536, 537, 176, 216})
        self.assertTrue(all(i // RECORD == 5639 for i in range(len(before)) if before[i] != after[i]))
        v = {x.id: x for x in landunits.list_land_units(self.roundtrip())}[5639]
        self.assertEqual((v.get("morale"), v.get("supplies")), (70, 1000))
        self.assertEqual((v.get_equipment(0)["count"], v.get_equipment(0)["disabled"]), (20, 5))

    def test_bases_unaffected_by_unit_edit(self):
        before = {b.id: b.get("supply") for b in bases.list_bases(self.sf)}
        self.units[5639].set("supplies", 5)
        self.assertEqual({b.id: b.get("supply") for b in bases.list_bases(self.sf)}, before)

    def test_validation_failures_leave_bytes_unchanged(self):
        before = bytes(self.sf[SECTION].data)
        u = self.units[5639]
        for values in ({"morale": 100}, {"morale": 5, "fatigue": -1}, {"experience": 100}, {"supplies": -1},
                       {"supplies": bases.MAX_VALUE + 1}, {"morale": True}, {"morale": "5"}, {"nope": 1}):
            with self.assertRaises(ValueError, msg=str(values)):
                u.set_many(values)
        for args in ((0, 5, 6), (0, -1, 0), (0, 10, -1), (0, 10000, 0), (0, 1.5, 0), (5, 1, 0), (20, 1, 0),
                     (True, 1, 0)):
            with self.assertRaises(ValueError, msg=str(args)):
                u.set_equipment(*args)
        self.assertEqual(bytes(self.sf[SECTION].data), before)


if __name__ == "__main__":
    unittest.main()
