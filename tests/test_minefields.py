import os
import struct
import unittest

from witpae import bases, minefields, shiprecords
from witpae.container import SaveFile, SaveFormatError

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
SAVE_015 = os.path.join(DATA_DIR, "going2_411210.pws")
BATAAN, SINGAPORE, OSAKA, HIROSHIMA, SAN_FRANCISCO, PEARL = 621, 722, 246, 228, 519, 584
BARBICAN, BASTION = 9979, 9980  # Allied ACMs docked at Anchorage and Seattle
FREE_RECORD = 5999


class HelperTests(unittest.TestCase):
    def test_types_text(self):
        self.assertEqual(minefields.types_text([("Mk 6 Mine", 995)]), "Mk 6 Mine 995")
        self.assertEqual(minefields.types_text([("Mk 6 Mine", 145), ("Mk XVII Mine", 300)]),
                         "Mk XVII Mine 300; Mk 6 Mine 145")
        self.assertEqual(minefields.types_text([("Mk 6 Mine", 495), ("Mk 6 Mine", 500)]), "Mk 6 Mine 995")
        self.assertEqual(minefields.types_text([("B", 5), ("A", 5)]), "A 5; B 5")
        self.assertEqual(minefields.types_text([]), "")


@unittest.skipUnless(os.path.exists(SAVE_015), "sample save missing")
class MinefieldTests(unittest.TestCase):
    def setUp(self):
        self.sf = SaveFile.load(SAVE_015)

    def put(self, rec, x, y, side, detection, device, mines):
        struct.pack_into("<6H", self.sf[minefields.SECTION].data, rec * minefields.RECORD_SIZE,
                         x, y, side, detection, device, mines)

    def fields(self):
        return minefields.list_fields(self.sf)

    def hexes(self):
        return {(h.x, h.y, h.side): h for h in minefields.hex_rows(self.sf, self.fields())}

    def poke_ship(self, ship_id, offset, value, fmt="H"):
        rec = {r.id: r for r in shiprecords.list_ship_records(self.sf)}[ship_id]
        struct.pack_into("<" + fmt, rec._data, rec._offset + offset, value)

    # ---- the sample save ---------------------------------------------------

    def test_counts(self):
        fields = self.fields()
        self.assertEqual(len(fields), 67)
        self.assertEqual(sum(1 for f in fields if f.side == "Allied"), 34)
        self.assertEqual(sum(1 for f in fields if f.side == "Japanese"), 33)
        self.assertEqual(len(minefields.hex_rows(self.sf, fields)), 65)

    def test_field_row(self):
        f = {r.id: r for r in self.fields()}[2]
        self.assertEqual((f.x, f.y, f.side, f.place_id, f.place_name), (78, 77, "Allied", BATAAN, "Bataan"))
        self.assertEqual((f.device_id, f.device_name, f.mines, f.detection), (1645, "Mk 6 Mine", 500, 9))
        self.assertEqual({r.id: r.mines for r in self.fields()}[1], 495)

    def test_biggest_hexes(self):
        rows = minefields.hex_rows(self.sf, self.fields())
        top = [(r.x, r.y, r.side, r.place, r.mines) for r in rows[:4]]
        self.assertEqual(top, [(78, 77, "Allied", "Bataan", 995), (109, 59, "Japanese", "Osaka/Kyoto", 496),
                               (103, 57, "Japanese", "Fukuoka", 495), (114, 60, "Japanese", "Tokyo", 490)])
        self.assertEqual(rows, sorted(rows, key=lambda r: (-r.mines, r.side, r.y, r.x)))
        by = {(r.x, r.y, r.side): r for r in rows}
        self.assertEqual(by[(50, 84, "Allied")].mines, 445)
        self.assertEqual(by[(218, 70, "Allied")].mines, 444)
        self.assertEqual(by[(29, 48, "Allied")].mines, 435)

    def test_two_fields_in_one_hex(self):
        h = self.hexes()[(78, 77, "Allied")]
        self.assertEqual((h.place_id, h.fields, h.mines, h.types, h.detection),
                         (BATAAN, 2, 995, "Mk 6 Mine 995", 9))

    def test_mixed_types_in_one_hex(self):
        self.put(FREE_RECORD, 78, 77, 1, 0, 1650, 300)
        h = self.hexes()[(78, 77, "Allied")]
        self.assertEqual((h.fields, h.mines, h.types), (3, 1295, "Mk 6 Mine 995; Mk XVII Mine 300"))

    def test_open_sea_hex(self):
        h = self.hexes()[(70, 83, "Japanese")]
        self.assertEqual((h.place_id, h.place, h.mines, h.types, h.decay), (None, "-", 11, "Type 88 Mine 11",
                                                                            minefields.DECAY_OPEN))
        f = [f for f in self.fields() if (f.x, f.y) == (70, 83)][0]
        self.assertEqual((f.place_id, f.place_name), (None, None))

    def test_enemy_base_text(self):
        by = self.hexes()
        h = by[(50, 84, "Japanese")]
        self.assertEqual((h.place_id, h.place, h.mines, h.fields), (SINGAPORE, "Singapore (enemy base)", 68, 2))
        self.assertEqual(h.decay, minefields.DECAY_OPEN)  # not a friendly port
        self.assertEqual(by[(50, 84, "Allied")].place, "Singapore")
        self.assertEqual(by[(78, 77, "Japanese")].place, "Bataan (enemy base)")

    # ---- decay ---------------------------------------------------------------

    def test_decay_at_friendly_port(self):
        self.assertEqual(self.hexes()[(78, 77, "Allied")].decay, minefields.DECAY_PORT)
        self.assertEqual(minefields.DECAY_PORT, "1%/day (friendly port)")

    def test_decay_without_port_or_water(self):
        base = bases.Base(self.sf, BATAAN, "Bataan")
        struct.pack_into("<h", self.sf[bases.LOCATION_SECTION].data, base._offset + 422, 0)
        self.assertEqual(self.hexes()[(78, 77, "Allied")].decay, "5-33%/day")
        self.assertEqual(self.hexes()[(70, 83, "Japanese")].decay, "5-33%/day")

    # ---- minefield tenders ---------------------------------------------------

    def test_acms_docked_at_the_base(self):
        by = self.hexes()
        self.assertEqual((by[(109, 59, "Japanese")].acms, by[(109, 59, "Japanese")].protected), (2, 300))
        self.assertEqual((by[(106, 58, "Japanese")].acms, by[(106, 58, "Japanese")].protected), (5, 450))  # capped
        self.assertEqual((by[(218, 70, "Allied")].acms, by[(218, 70, "Allied")].protected), (1, 150))
        self.assertEqual((by[(78, 77, "Allied")].acms, by[(78, 77, "Allied")].protected), (0, 0))

    def test_acm_moved_to_a_minefield_base(self):
        self.poke_ship(BARBICAN, shiprecords.BASE_OFFSET, BATAAN)
        h = self.hexes()[(78, 77, "Allied")]
        self.assertEqual((h.acms, h.protected), (1, 150))
        self.poke_ship(BASTION, shiprecords.BASE_OFFSET, BATAAN)
        h = self.hexes()[(78, 77, "Allied")]
        self.assertEqual((h.acms, h.protected), (2, 300))
        # The enemy minefield in the same hex gets nothing from Allied ACMs.
        self.assertEqual(self.hexes()[(78, 77, "Japanese")].acms, 0)

    def test_acm_in_a_task_force_does_not_count(self):
        self.poke_ship(BARBICAN, shiprecords.BASE_OFFSET, BATAAN)
        self.poke_ship(BASTION, shiprecords.BASE_OFFSET, BATAAN)
        self.poke_ship(BASTION, shiprecords.TASK_FORCE_OFFSET, 14016)
        h = self.hexes()[(78, 77, "Allied")]
        self.assertEqual((h.acms, h.protected), (1, 150))

    def test_unarrived_acm_does_not_count(self):
        self.poke_ship(BARBICAN, shiprecords.BASE_OFFSET, BATAAN)
        self.poke_ship(BARBICAN, shiprecords.ARRIVAL_OFFSET, 5, "I")
        self.assertEqual(self.hexes()[(78, 77, "Allied")].acms, 0)

    def test_protection_is_capped_at_the_mines(self):
        for ship in (BARBICAN, BASTION, 9981, 9982, 9983, 9984, 9985):
            self.poke_ship(ship, shiprecords.BASE_OFFSET, BATAAN)
        h = self.hexes()[(78, 77, "Allied")]
        self.assertEqual((h.acms, h.protected), (7, 995))

    # ---- summary -------------------------------------------------------------

    def test_summary(self):
        fields = self.fields()
        rows = minefields.summary_rows(fields, minefields.hex_rows(self.sf, fields))
        self.assertEqual([r.side for r in rows], ["Allied", "Japanese"])
        allied, japanese = rows
        self.assertEqual(tuple(allied)[:4], ("Allied", 34, 33, 10108))
        self.assertEqual(tuple(japanese)[:4], ("Japanese", 33, 32, 8988))
        self.assertEqual(allied.by_device, (("Mk XVII Mine", 6018), ("Mk 6 Mine", 3258), ("VH Mk II Mine", 832)))
        self.assertEqual(japanese.by_device, (("Type 4 Mine", 8876), ("Type 88 Mine", 112)))
        self.assertEqual(sum(m for _n, m in allied.by_device), allied.mines)

    def test_summary_of_nothing(self):
        rows = minefields.summary_rows([], [])
        self.assertEqual([tuple(r) for r in rows], [("Allied", 0, 0, 0, ()), ("Japanese", 0, 0, 0, ())])

    # ---- filtering and bad data ----------------------------------------------

    def test_invalid_records_are_skipped(self):
        before = len(self.fields())
        bad = [(0, 50, 1, 0, 1645, 10), (50, 0, 1, 0, 1645, 10), (251, 50, 1, 0, 1645, 10),
               (50, 251, 1, 0, 1645, 10), (50, 50, 1, 0, 1645, 0), (50, 50, 1, 0, 1645, 32768),
               (50, 50, 1, 0, 1645, 65535), (50, 50, 2, 0, 1645, 10)]
        for n, row in enumerate(bad):
            self.put(FREE_RECORD - n, *row)
        self.assertEqual(len(self.fields()), before)

    def test_limits_are_inclusive(self):
        before = len(self.fields())
        self.put(FREE_RECORD, 250, 250, 0, 0, 1710, 32767)
        self.put(FREE_RECORD - 1, 1, 1, 1, 0, 1710, 1)
        fields = self.fields()
        self.assertEqual(len(fields), before + 2)
        self.assertEqual({(f.x, f.y, f.mines) for f in fields if f.id >= FREE_RECORD - 1},
                         {(250, 250, 32767), (1, 1, 1)})

    def test_device_name_fallback(self):
        self.put(FREE_RECORD, 50, 50, 1, 0, 65535, 10)
        f = self.fields()[-1]
        self.assertEqual((f.device_id, f.device_name), (65535, "#65535"))
        self.assertEqual(self.hexes()[(50, 50, "Allied")].types, "#65535 10")

    def test_hex_beyond_the_location_table_has_no_place(self):
        self.put(FREE_RECORD, 249, 249, 1, 0, 1645, 10)
        h = self.hexes()[(249, 249, "Allied")]
        self.assertEqual((h.place_id, h.place), (None, "-"))

    def test_short_section_is_read_as_far_as_it_goes(self):
        section = self.sf[minefields.SECTION]
        section.data = section.data[:minefields.RECORD_SIZE * 10 + 7]
        fields = self.fields()
        self.assertTrue(all(f.id < 10 for f in fields))
        self.assertGreater(len(fields), 0)
        minefields.hex_rows(self.sf, fields)

    def test_missing_section_is_a_format_error(self):
        del self.sf._by_id[minefields.SECTION]
        with self.assertRaises(SaveFormatError):
            minefields.list_fields(self.sf)


if __name__ == "__main__":
    unittest.main()
