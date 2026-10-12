import os
import tempfile
import unittest

from witpae import aircraft, ships
from witpae.container import SaveFile

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
SAVE_015 = os.path.join(DATA_DIR, "going2_411210.pws")
SECTION = ships.SHIP_SECTION
RECORD = ships.RECORD_SIZE


@unittest.skipUnless(os.path.exists(SAVE_015), "sample save missing")
class ShipTests(unittest.TestCase):
    def setUp(self):
        self.sf = SaveFile.load(SAVE_015)
        self.by_id = {x.id: x for x in ships.list_ships(self.sf)}

    def roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "out.pws")
            self.sf.save(path)
            return SaveFile.load(path)

    def test_list_and_refit_stages(self):
        self.assertEqual(len(self.by_id), 1721)
        lex = sorted(x.id for x in self.by_id.values() if x.name == "Lexington")
        self.assertEqual(lex, [674, 675, 676, 677, 678, 679])
        self.assertEqual([self.by_id[i].date for i in lex],
                         [(12, 41), (3, 42), (6, 42), (10, 42), (1, 44), (1, 45)])

    def test_lexington(self):
        x = self.by_id[674]
        self.assertEqual((x.type, x.nation, x.nation_id, x.displacement), ("CV", "USN", 4, 36000))
        self.assertEqual({n: x.get(n) for n in ("speed", "cruise", "endurance", "fuel", "maneuver", "durability",
                                                "belt", "deck", "tower", "capacity")},
                         {"speed": 33, "cruise": 15, "endurance": 10000, "fuel": 5432, "maneuver": 26,
                          "durability": 126, "belt": 175, "deck": 50, "tower": 50, "capacity": 90})
        weapons = dict(x.list_weapons())
        self.assertEqual(weapons[0], {"name": "8in/55 Mk 9 Gun", "num": 4, "face": 0, "mount": 2,
                                      "armor": 5, "ammo": 12})
        # Armor is two bytes per slot: the game shows 5, 5, then "-" for the 5in/25 rows.
        self.assertEqual((weapons[1]["name"], weapons[1]["face"], weapons[1]["armor"]), ("8in/55 Mk 9 Gun", 2, 5))
        self.assertEqual((weapons[2]["name"], weapons[2]["num"], ships.face_label(weapons[2]["face"]),
                          weapons[2]["mount"], weapons[2]["armor"], weapons[2]["ammo"]),
                         ("5in/25 Mk 10 Gun", 6, "RS", 1, 0, 18))
        self.assertEqual((weapons[9]["name"], weapons[9]["num"], ships.face_label(weapons[9]["face"])),
                         ("CXAM AS Radar", 1, "A"))
        self.assertEqual(weapons[10]["name"], "CXAM SS Radar")
        self.assertEqual(sorted(weapons)[:11], list(range(11)))

    def test_labels(self):
        self.assertEqual(ships.type_label(12), "DD")
        self.assertEqual(ships.type_label(13), "DE?")
        self.assertEqual(ships.type_label(99), "99")
        self.assertEqual(aircraft.nation_label(10), "French")
        self.assertEqual(aircraft.nation_label(14), "India?")
        self.assertEqual(aircraft.nation_label(9), "UK")

    def test_edit_roundtrip_changes_only_expected_bytes(self):
        before = bytes(self.sf[SECTION].data)
        x = self.by_id[674]
        x.set_many({"speed": 30, "fuel": 6000, "belt": 200})
        x.set_weapon(0, num=5, face="C", ammo=20, mount=3, armor=7)
        other = self.roundtrip()
        after = bytes(other[SECTION].data)
        changed = {i - 674 * RECORD for i in range(len(before)) if before[i] != after[i]}
        # fuel 5432 -> 6000 changes both bytes; belt 175 -> 200 only the low one.
        expected = {32, 33, 36, 42, 96, 136, 156, 196, 216}
        self.assertEqual(changed, expected)
        y = {s.id: s for s in ships.list_ships(other)}[674]
        self.assertEqual((y.get("speed"), y.get("fuel"), y.get("belt")), (30, 6000, 200))
        self.assertEqual(y.get_weapon(0), {"name": "8in/55 Mk 9 Gun", "num": 5, "face": 1, "mount": 3,
                                           "armor": 7, "ammo": 20})
        self.assertEqual(y.get_weapon(1)["num"], 4)

    def test_other_sections_untouched(self):
        pristine = SaveFile.load(SAVE_015)
        self.by_id[674].set("speed", 31)
        other = self.roundtrip()
        for sec in pristine.sections:
            if sec.sid != SECTION:
                self.assertEqual(bytes(sec.data), bytes(other[sec.sid].data), hex(sec.sid))

    def test_validation_failures_leave_bytes_unchanged(self):
        before = bytes(self.sf[SECTION].data)
        x = self.by_id[674]
        for values in ({"speed": 61}, {"speed": 5, "maneuver": 101}, {"fuel": 32768}, {"belt": 2001},
                       {"durability": -1}, {"speed": True}, {"speed": "5"}, {"nope": 1}):
            with self.assertRaises(ValueError, msg=str(values)):
                x.set_many(values)
        for values in ({"num": 1000}, {"num": 5, "mount": 100}, {"armor": 1000}, {"ammo": -1},
                       {"num": 5, "face": "Z"}, {"face": 256}, {"num": 1.5}, {"device": 5}):
            with self.assertRaises(ValueError, msg=str(values)):
                x.set_weapon(0, **values)
        for slot in (17, 20, -1, True):  # empty or nonexistent slots
            with self.assertRaises(ValueError, msg=str(slot)):
                x.set_weapon(slot, num=1)
        self.assertEqual(bytes(self.sf[SECTION].data), before)

    def test_unknown_face_code_preserved(self):
        x = self.by_id[674]
        self.sf[SECTION].data[674 * RECORD + ships.FACE_OFFSET + 0] = 9
        self.assertEqual(ships.face_label(x.get_weapon(0)["face"]), "9")
        x.set_weapon(0, num=3, face=ships.face_label(x.get_weapon(0)["face"]))
        self.assertEqual(x.get_weapon(0)["face"], 9)


if __name__ == "__main__":
    unittest.main()
