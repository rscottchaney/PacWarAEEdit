import os
import struct
import unittest

from witpae import shipratings, shiprecords, ships
from witpae.container import SaveFile
from witpae.factories import DEVICE_RECORD_SIZE, DEVICE_SECTION
from witpae.shipratings import Slot

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
SAVE_015 = os.path.join(DATA_DIR, "going2_411210.pws")
KAGERO, LEXINGTON, FLETCHER_LB = 1472, 674, 526


def slot(type_, effect=0, num=1, ammo=0, ceiling=0, accuracy=0, name="dev", device=1):
    return Slot(device, name, type_, effect, accuracy, ceiling, num, ammo)


class FormulaTests(unittest.TestCase):
    def test_main_gun_is_the_highest_effect_of_navy_and_dp_guns(self):
        slots = [slot(17, 55, 4, 20, name="5in DP", device=1), slot(18, 260, 2, 12, name="8in", device=2),
                 slot(18, 260, 3, 9, name="8in", device=2), slot(18, 300, 0, 5, name="unused", device=3),
                 slot(12, 900, 4, 1, name="flak", device=4)]
        # Slots of the best device add up; disagreeing ammo gives the smallest.
        self.assertEqual(shipratings.main_gun(slots), ("8in", 260, 5, 9))
        self.assertEqual(shipratings.main_gun([slot(12, 5), slot(16, 800)]), ("", 0, 0, 0))

    def test_main_gun_merges_devices_of_equal_effect(self):
        slots = [slot(17, 55, 2, 20, name="EBR", device=9), slot(17, 55, 1, 18, name="OBR", device=7),
                 slot(17, 55, 1, 20, name="OBR", device=7), slot(17, 55, 1, 20, name="EBR", device=9),
                 slot(18, 40, 8, 5, name="small", device=3)]
        self.assertEqual(shipratings.main_gun(slots), ("EBR", 55, 5, 18))  # EBR has 3 guns, OBR 2

    def test_main_gun_name_tie_takes_the_lowest_device_id(self):
        slots = [slot(17, 50, 2, 10, name="b", device=5), slot(18, 50, 2, 12, name="a", device=2)]
        self.assertEqual(shipratings.main_gun(slots), ("a", 50, 4, 10))

    def test_anti_air_splits_at_a_ceiling_of_20000_and_halves(self):
        slots = [slot(12, 20, 4, ceiling=6600), slot(12, 10, 3, ceiling=19999), slot(17, 55, 5, ceiling=20000),
                 slot(17, 54, 2, ceiling=27400), slot(11, 30, 1, ceiling=12000),
                 slot(18, 500, 9, ceiling=30000), slot(12, 7, 0, ceiling=50000)]
        low = (20 * 4 + 10 * 3 + 30) / 2
        high = (55 * 5 + 54 * 2) / 2
        self.assertEqual(shipratings.anti_air(slots), (low, high, 27400))
        self.assertEqual(shipratings.anti_air([slot(18, 5, 2)]), (0, 0, 0))

    def test_asw_count_and_rating(self):
        slots = [slot(20, 300, 3, accuracy=8), slot(20, 600, 2, accuracy=9), slot(12, 99, 9, accuracy=99)]
        self.assertEqual(shipratings.anti_submarine(slots), (5, round(300 * 8 / 100 * 3 + 600 * 9 / 100 * 2, 1)))
        self.assertEqual(shipratings.anti_submarine([]), (0, 0))

    def test_torpedo_tubes_and_total(self):
        slots = [slot(16, 1080, 8, ammo=2), slot(16, 0, 0, ammo=0, name="Torpedo Ordnance"), slot(20, 5, 9, ammo=9)]
        self.assertEqual(shipratings.torpedoes(slots), (8, 16))

    def test_specials_lists_radars_and_rockets_once(self):
        slots = [slot(10, name="SC-2 AS Radar"), slot(10, name="SG SS Radar"), slot(10, name="SC-2 AS Radar"),
                 slot(11, name="12cm AA Rocket"), slot(8, name="Nav Radar"), slot(12, name="Some Radar"),
                 slot(10, name="Dead Radar", num=0)]
        self.assertEqual(shipratings.specials(slots), "SC-2 AS, SG SS, 12cm AA Rocket, Nav")
        self.assertEqual(shipratings.specials([]), "")


@unittest.skipUnless(os.path.exists(SAVE_015), "sample save missing")
class SaveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sf = SaveFile.load(SAVE_015)
        cls.rows = shipratings.class_ratings(cls.sf)
        cls.by_id = {r.class_id: r for r in cls.rows}
        cls.classes = {x.id: x for x in ships.list_ships(cls.sf)}

    def raw_slots(self, class_id):
        """(device, num, ammo, type, effect, ceiling) per slot, read without shipratings."""
        devices = self.sf[DEVICE_SECTION].data
        data = self.sf[ships.SHIP_SECTION].data
        base = class_id * ships.RECORD_SIZE
        out = []
        for k in range(20):
            device = struct.unpack_from("<h", data, base + 56 + 2 * k)[0]
            if device:
                at = device * DEVICE_RECORD_SIZE
                out.append((device, struct.unpack_from("<h", data, base + 96 + 2 * k)[0],
                            struct.unpack_from("<h", data, base + 156 + 2 * k)[0], devices[at + 26],
                            struct.unpack_from("<h", devices, at + 32)[0],
                            struct.unpack_from("<H", devices, at + 48)[0]))
        return out

    def test_one_row_per_class_record(self):
        self.assertEqual([r.class_id for r in self.rows], sorted(self.classes))
        self.assertEqual(len(self.rows), 1721)

    def test_counts_add_up_to_the_ships_of_the_class(self):
        ships_of = {}
        for rec in shiprecords.list_ship_records(self.sf):
            ships_of[rec.class_id] = ships_of.get(rec.class_id, 0) + 1
        for r in self.rows:
            self.assertEqual(r.available + r.building + r.sunk, ships_of.get(r.class_id, 0), r.name)
        self.assertEqual(sum(r.available + r.building + r.sunk for r in self.rows), sum(ships_of.values()))
        self.assertEqual(sum(r.sunk for r in self.rows),
                         sum(1 for rec in shiprecords.list_ship_records(self.sf) if rec.days_to_arrival == 19999))
        self.assertEqual(sum(1 for r in self.rows if r.available + r.building + r.sunk), 861)

    def test_side_follows_the_ships_or_the_nation(self):
        side_of = {rec.class_id: rec.side for rec in shiprecords.list_ship_records(self.sf)}
        for r in self.rows:
            nation_side = "Japanese" if self.classes[r.class_id].nation_id in (1, 2) else "Allied"
            self.assertEqual(r.side, side_of.get(r.class_id, nation_side), r.name)
        self.assertEqual({r.side for r in self.rows}, {"Allied", "Japanese"})
        self.assertEqual(self.by_id[KAGERO].side, "Japanese")
        self.assertEqual(self.by_id[LEXINGTON].side, "Allied")

    def test_types_are_the_class_type_labels(self):
        self.assertTrue({r.type for r in self.rows} >= {"CV", "DD", "CA", "SS"})
        for r in self.rows:
            self.assertEqual(r.type, self.classes[r.class_id].type)

    def test_lexington_from_raw_slots(self):
        r = self.by_id[LEXINGTON]
        raw = self.raw_slots(LEXINGTON)
        guns = [s for s in raw if s[3] in (17, 18)]
        best = max(s[4] for s in guns)
        self.assertEqual((r.main_effect, r.main_num), (best, sum(s[1] for s in guns if s[4] == best)))
        aa = [s for s in raw if s[3] in (11, 12, 17)]
        self.assertEqual((r.low_aa, r.high_aa),
                         (sum(s[4] * s[1] for s in aa if s[5] < 20000) / 2,
                          sum(s[4] * s[1] for s in aa if s[5] >= 20000) / 2))
        self.assertEqual(r.aa_ceiling, max(s[5] for s in aa if s[1] > 0))
        # Literal values confirmed against the slots.
        self.assertEqual((r.type, r.nation, r.date, r.speed, r.endurance, r.durability, r.belt, r.deck),
                         ("CV", "USN", (12, 41), 33, 10000, 126, 175, 50))
        self.assertEqual((r.main_gun, r.main_effect, r.main_num, r.main_salvoes),
                         ("8in/55 Mk 9 Gun", 260, 8, 12))
        self.assertEqual((r.low_aa, r.high_aa, r.aa_ceiling), (500, 324, 27400))
        self.assertEqual((r.asw_count, r.asw_rating, r.torp_tubes, r.torp_total), (0, 0, 0, 0))
        self.assertEqual((r.specials, r.available, r.building, r.sunk), ("CXAM AS, CXAM SS", 2, 0, 0))

    def test_kagero_from_raw_slots(self):
        r = self.by_id[KAGERO]
        raw = self.raw_slots(KAGERO)
        self.assertEqual(r.torp_tubes, sum(s[1] for s in raw if s[3] == 16))
        self.assertEqual(r.torp_total, sum(s[1] * s[2] for s in raw if s[3] == 16))
        self.assertEqual(r.asw_count, sum(s[1] for s in raw if s[3] == 20))
        self.assertEqual((r.side, r.type, r.nation, r.date), ("Japanese", "DD", "IJN", (12, 41)))
        self.assertEqual((r.main_gun, r.main_effect, r.main_num, r.main_salvoes),
                         ("12.7cm/50 3YT T. B.", 51, 6, 18))
        self.assertEqual((r.low_aa, r.high_aa, r.aa_ceiling), (36, 153, 40000))
        self.assertEqual((r.asw_count, r.asw_rating, r.torp_tubes, r.torp_total), (2, 45.4, 8, 16))
        self.assertEqual((r.specials, r.available, r.building, r.sunk), ("", 18, 0, 0))

    def test_benson_merges_mounts_of_equal_effect(self):
        r = self.by_id[496]
        raw = [s for s in self.raw_slots(496) if s[3] in (17, 18)]
        self.assertEqual(len({s[0] for s in raw}), 2)  # EBR and OBR devices
        self.assertEqual((r.main_gun, r.main_effect, r.main_num, r.main_salvoes),
                         ("5in/38 Mk 12 EBR", 55, 5, 18))

    def test_fletcher_without_ships(self):
        r = self.by_id[FLETCHER_LB]
        self.assertEqual((r.name, r.type, r.side, r.date), ("Fletcher LB", "DD", "Allied", (5, 42)))
        self.assertEqual((r.main_gun, r.main_num, r.main_salvoes), ("5in/38 Mk 12 EBR", 5, 20))
        self.assertEqual((r.low_aa, r.high_aa, r.aa_ceiling), (70, 137.5, 37200))
        self.assertEqual((r.asw_count, r.asw_rating, r.torp_tubes, r.torp_total), (8, 252, 10, 10))
        self.assertEqual((r.specials, r.available + r.building + r.sunk), ("SC AS, SG SS", 0))


if __name__ == "__main__":
    unittest.main()
