import os
import tempfile
import unittest

from witpae import shiprecords
from witpae.container import SaveFile

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
SAVE_015 = os.path.join(DATA_DIR, "going2_411210.pws")
SECTION = shiprecords.SHIP_SECTION
RECORD = shiprecords.SHIP_RECORD_SIZE
MARYLAND, MONTANES = 3144, 8133
FIELD_NAMES = ("exp_day", "exp_night", "fuel", "fires", "sys_dmg", "float_dmg", "maj_float_dmg",
               "eng_dmg", "maj_eng_dmg")


@unittest.skipUnless(os.path.exists(SAVE_015), "sample save missing")
class ShipRecordTests(unittest.TestCase):
    def setUp(self):
        self.sf = SaveFile.load(SAVE_015)
        self.by_id = {x.id: x for x in shiprecords.list_ship_records(self.sf)}

    def roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "out.pws")
            self.sf.save(path)
            return SaveFile.load(path)

    def changed_offsets(self, before, other, ship_id):
        after = bytes(other[SECTION].data)
        self.assertEqual(len(before), len(after))
        return {i - ship_id * RECORD for i in range(len(before)) if before[i] != after[i]}

    def values(self, ship_id):
        return {n: self.by_id[ship_id].get(n) for n in FIELD_NAMES}

    def test_maryland(self):
        x = self.by_id[MARYLAND]
        self.assertEqual(x.name, "Maryland")
        self.assertEqual(self.values(MARYLAND), {
            "exp_day": 53, "exp_night": 33, "fuel": 4700, "fires": 0, "sys_dmg": 32, "float_dmg": 42,
            "maj_float_dmg": 23, "eng_dmg": 34, "maj_eng_dmg": 23})
        self.assertEqual((x.class_id, x.class_name, x.type), (337, "Maryland", "BB"))
        self.assertEqual((x.nation, x.side, x.location, x.task_force, x.days_to_arrival),
                         ("USN", "Allied", "Pearl Harbor", 0, 0))
        self.assertEqual(x.base_name, "Pearl Harbor")

    def test_montanes(self):
        x = self.by_id[MONTANES]
        self.assertEqual(self.values(MONTANES), {
            "exp_day": 20, "exp_night": 17, "fuel": 221, "fires": 47, "sys_dmg": 77, "float_dmg": 50,
            "maj_float_dmg": 34, "eng_dmg": 18, "maj_eng_dmg": 4})
        self.assertEqual((x.class_id, x.class_name, x.side), (2428, "Coastal Cargo", "Allied"))
        self.assertEqual(x.weapon_slots(), [])

    def test_list_excludes_empty_records_and_locations(self):
        data = self.sf[SECTION].data
        self.assertTrue(all(x.name for x in self.by_id.values()))
        self.assertEqual(len(self.by_id), 10757)
        locations = {x.location for x in self.by_id.values()}
        self.assertIn("at sea", locations)
        self.assertTrue(any(loc.startswith("TF ") for loc in locations))

    def test_side_filter(self):
        japanese = [x for x in self.by_id.values() if x.side == "Japanese"]
        allied = [x for x in self.by_id.values() if x.side == "Allied"]
        self.assertEqual(len(japanese) + len(allied), len(self.by_id))
        self.assertTrue(japanese and allied)
        self.assertEqual({x.nation for x in japanese}, {"IJN"})
        self.assertNotIn("IJN", {x.nation for x in allied})

    def test_set_many_roundtrip_changes_only_expected_bytes(self):
        before = bytes(self.sf[SECTION].data)
        x = self.by_id[MARYLAND]
        x.set_many({"fuel": 4600, "exp_day": 60, "fires": 5, "maj_float_dmg": 10, "eng_dmg": 40})
        other = self.roundtrip()
        # fuel 4700 -> 4600 (0x125c -> 0x11f8) changes both bytes.
        self.assertEqual(self.changed_offsets(before, other, MARYLAND),
                         {27, 56, 57, 331, 334, 335})
        y = {s.id: s for s in shiprecords.list_ship_records(other)}[MARYLAND]
        self.assertEqual((y.get("fuel"), y.get("exp_day"), y.get("fires"), y.get("maj_float_dmg"),
                          y.get("eng_dmg"), y.get("exp_night")), (4600, 60, 5, 10, 40, 33))

    def test_other_sections_untouched(self):
        pristine = SaveFile.load(SAVE_015)
        self.by_id[MARYLAND].set("sys_dmg", 10)
        self.by_id[MARYLAND].set_weapon(0, num=1, ammo=2)
        other = self.roundtrip()
        for sec in pristine.sections:
            if sec.sid != SECTION:
                self.assertEqual(bytes(sec.data), bytes(other[sec.sid].data), hex(sec.sid))

    def test_validation_failures_leave_bytes_unchanged(self):
        before = bytes(self.sf[SECTION].data)
        x = self.by_id[MARYLAND]
        for values in ({"fuel": 32768}, {"fuel": -1}, {"exp_day": 100}, {"fires": 100, "sys_dmg": 5},
                       {"sys_dmg": 5, "exp_night": 100}, {"fuel": True}, {"fires": 1, "fuel": "5"},
                       {"fuel": 1.5}, {"nope": 1}, {"fires": 1, "float_dmg": 10},  # major 23 > 10
                       {"maj_float_dmg": 43}, {"eng_dmg": 22, "sys_dmg": 1}, {"maj_eng_dmg": 35, "fires": 1}):
            with self.assertRaises(ValueError, msg=str(values)):
                x.set_many(values)
        with self.assertRaises(ValueError):
            x.set("maj_eng_dmg", 99)
        self.assertEqual(bytes(self.sf[SECTION].data), before)

    def test_error_names_field(self):
        x = self.by_id[MARYLAND]
        with self.assertRaisesRegex(ValueError, "Fuel"):
            x.set_many({"fuel": 40000})
        with self.assertRaisesRegex(ValueError, "Major flotation damage"):
            x.set_many({"maj_float_dmg": 43})

    def test_pair_rule_applies_to_final_values(self):
        x = self.by_id[MARYLAND]
        x.set_many({"float_dmg": 30, "maj_float_dmg": 30})  # lowering both together is fine
        self.assertEqual((x.get("float_dmg"), x.get("maj_float_dmg")), (30, 30))

    def test_existing_violation_allowed_until_pair_changes(self):
        x = self.by_id[MARYLAND]
        data = self.sf[SECTION].data
        data[MARYLAND * RECORD + 334] = 80  # maj_float 80 > float 42, as in sinking ships
        x.set_many({"fuel": 100, "float_dmg": 42, "maj_float_dmg": 80})  # unchanged pair
        self.assertEqual(x.get("fuel"), 100)
        before = bytes(data)
        with self.assertRaises(ValueError):
            x.set("float_dmg", 43)  # changes the pair and leaves it invalid
        self.assertEqual(bytes(data), before)
        x.set("maj_float_dmg", 42)
        self.assertEqual(x.get("maj_float_dmg"), 42)

    def test_repair_all(self):
        x = self.by_id[MONTANES]
        before = bytes(self.sf[SECTION].data)
        x.repair_all()
        other = self.roundtrip()
        self.assertEqual(self.changed_offsets(before, other, MONTANES), {331, 332, 333, 334, 335, 336})
        y = {s.id: s for s in shiprecords.list_ship_records(other)}[MONTANES]
        self.assertEqual([y.get(n) for n in shiprecords.DAMAGE_FIELDS], [0] * 6)
        self.assertEqual((y.get("fuel"), y.get("exp_day")), (221, 20))

    def test_repair_all_noop_on_undamaged_ship(self):
        x = self.by_id[MARYLAND]
        x.repair_all()
        before = bytes(self.sf[SECTION].data)
        x.repair_all()
        self.assertEqual(bytes(self.sf[SECTION].data), before)
        self.assertEqual([x.get(n) for n in shiprecords.DAMAGE_FIELDS], [0] * 6)

    def test_weapons_read(self):
        weapons = dict(self.by_id[MARYLAND].list_weapons())
        self.assertEqual(weapons[0], {"name": "16in/45 Mk 5  Gun", "device": 1559, "num": 4, "face": 0,
                                      "mount": 2, "armor": 450, "ammo": 10})
        self.assertEqual(weapons[1]["face"], 2)
        self.assertEqual(weapons[2]["name"], "5in/51 Mk 7 Gun")

    def test_weapon_edit_roundtrip(self):
        before = bytes(self.sf[SECTION].data)
        x = self.by_id[MARYLAND]
        x.set_weapon(0, num=5, ammo=999)
        other = self.roundtrip()
        # num 4 -> 5 changes one byte; ammo 10 -> 999 (0x03e7) changes both.
        self.assertEqual(self.changed_offsets(before, other, MARYLAND), {110, 170, 171})
        y = {s.id: s for s in shiprecords.list_ship_records(other)}[MARYLAND].get_weapon(0)
        self.assertEqual((y["num"], y["ammo"], y["device"], y["face"], y["mount"], y["armor"]),
                         (5, 999, 1559, 0, 2, 450))

    def test_weapon_validation_failures_leave_bytes_unchanged(self):
        before = bytes(self.sf[SECTION].data)
        x = self.by_id[MARYLAND]
        for values in ({"num": 1000}, {"num": 5, "ammo": -1}, {"ammo": 1000}, {"num": True}, {"num": "5"},
                       {"num": 1.5}, {"num": 5, "device": 3}, {"face": 1}, {"mount": 1}, {"armor": 1}):
            with self.assertRaises(ValueError, msg=str(values)):
                x.set_weapon(0, **values)
        slot = next(k for k in range(shiprecords.SLOTS) if k not in x.weapon_slots())
        for bad in (slot, 20, -1, True, "0"):
            with self.assertRaises(ValueError, msg=str(bad)):
                x.set_weapon(bad, num=1)
        with self.assertRaises(ValueError):
            self.by_id[MONTANES].set_weapon(0, num=1)  # no weapons at all
        self.assertEqual(bytes(self.sf[SECTION].data), before)


if __name__ == "__main__":
    unittest.main()
