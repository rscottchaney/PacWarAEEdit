import os
import struct
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
        self.assertFalse(u.supplies_short)
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

    def test_supplies_short(self):
        u = self.units[3447]
        self.assertEqual((u.get("supplies"), u.supplies_required), (271, 277))
        self.assertTrue(u.supplies_short)
        u.set("supplies", 277)
        self.assertFalse(u.supplies_short)  # equal to the requirement is not short

    def test_coast_defence_with_upgrade_target(self):
        u = self.units[5635]
        self.assertEqual((u.name, u.type, u.hq_name, u.location_name), ("1/250th", "CD", "West Coast", "Anchorage"))
        self.assertEqual([u.get(n) for n in ("experience", "morale", "fatigue", "supplies")], [50, 53, 2, 37])
        eq = dict(u.list_equipment())
        self.assertEqual((eq[0]["device"], eq[0]["count"]), ("0.5in M2HB AAMG", 6))
        self.assertEqual((eq[1]["device"], eq[1]["count"], eq[1]["toe_device"]),
                         ("155mm M1918 GPF", 8, "155mm M1A1 GPF"))
        self.assertEqual((eq[3]["device"], eq[3]["count"], eq[3]["toe_count"]), ("Motorized Support", 2, 6))

    # ---- fill to TOE ----------------------------------------------------

    FILL_UNITS = (2, 68, 106, 124, 3064, 3435, 5635, 5639)

    def record_bytes(self, unit_id):
        return bytes(self.sf[SECTION].data[unit_id * RECORD:(unit_id + 1) * RECORD])

    def slot(self, unit_id, k):
        eq = self.units[unit_id]
        return tuple(eq._i16(off + 2 * k) for off in (landunits.DEVICE_OFFSET, landunits.COUNT_OFFSET,
                                                      landunits.DISABLED_OFFSET))

    def test_fill_to_toe_below_toe(self):
        # Unit 2 slot 0: 218 of TOE 240 with 22 disabled.
        for percent, expected in ((0, 240), (10, 264), (25, 300)):
            with self.subTest(percent=percent):
                self.setUp()
                u = self.units[2]
                self.assertEqual(self.slot(2, 0), (252, 218, 22))
                self.assertGreater(u.fill_to_toe(percent), 0)
                self.assertEqual(self.slot(2, 0), (252, expected, 0))

    def test_fill_to_toe_empty_slot_gets_toe_device(self):
        # Unit 124 slot 1: no device, TOE 50 of device 253.
        for percent, expected in ((0, 50), (10, 55), (25, 63)):
            with self.subTest(percent=percent):
                self.setUp()
                self.assertEqual(self.slot(124, 1), (0, 0, 0))
                self.units[124].fill_to_toe(percent)
                self.assertEqual(self.slot(124, 1), (253, expected, 0))

    def test_fill_to_toe_keeps_older_device(self):
        # Unit 106 slot 1 holds device 1318 (TOE device 1415), 16 of 20, 4 disabled.
        for percent, expected in ((0, 20), (10, 22), (25, 25)):
            with self.subTest(percent=percent):
                self.setUp()
                self.assertEqual(self.slot(106, 1), (1318, 16, 4))
                self.units[106].fill_to_toe(percent)
                self.assertEqual(self.slot(106, 1), (1318, expected, 0))

    def test_fill_to_toe_never_lowers_count(self):
        # Unit 68 slot 0: 158 against TOE 120 with 2 disabled.
        for percent, expected in ((0, 158), (10, 158), (25, 158)):
            with self.subTest(percent=percent):
                self.setUp()
                self.assertEqual(self.slot(68, 0), (252, 158, 2))
                self.units[68].fill_to_toe(percent)
                self.assertEqual(self.slot(68, 0), (252, expected, 0))

    def test_fill_to_toe_rounds_up(self):
        # Unit 3064 slot 2: TOE 9 -> 9, 10 (9.9), 12 (11.25).
        for percent, expected in ((0, 9), (10, 10), (25, 12)):
            with self.subTest(percent=percent):
                self.setUp()
                self.units[3064].fill_to_toe(percent)
                self.assertEqual(self.slot(3064, 2), (704, expected, 0))

    def test_fill_to_toe_only_touches_toe_slots(self):
        toe_fields = (landunits.DEVICE_OFFSET, landunits.COUNT_OFFSET, landunits.DISABLED_OFFSET)
        for unit_id in self.FILL_UNITS:
            u = self.units[unit_id]
            toe_slots = [k for k in range(landunits.SLOTS)
                         if u._i16(landunits.TOE_DEVICE_OFFSET + 2 * k) and u._i16(landunits.TOE_COUNT_OFFSET + 2 * k) > 0]
            allowed = {off + 2 * k + i for off in toe_fields for k in toe_slots for i in (0, 1)}
            before = self.record_bytes(unit_id)
            changed = u.fill_to_toe(25)
            after = self.record_bytes(unit_id)
            diff = {i for i in range(RECORD) if before[i] != after[i]}
            with self.subTest(unit=unit_id):
                self.assertTrue(diff <= allowed)
                self.assertGreater(changed, 0)
                self.assertLessEqual(changed, len(toe_slots))

    def test_fill_to_toe_leaves_slots_without_toe(self):
        # Unit 3435 slot 5 holds 11 (1 disabled) with no TOE entry.
        self.assertEqual(self.slot(3435, 5), (self.slot(3435, 5)[0], 11, 1))
        before = self.slot(3435, 5)
        self.assertGreater(self.units[3435].fill_to_toe(25), 0)
        self.assertEqual(self.slot(3435, 5), before)

    def test_fill_to_toe_is_idempotent(self):
        for percent in (0, 10, 25):
            with self.subTest(percent=percent):
                self.setUp()
                u = self.units[2]
                self.assertGreater(u.fill_to_toe(percent), 0)
                snapshot = self.record_bytes(2)
                self.assertEqual(u.fill_to_toe(percent), 0)
                self.assertEqual(self.record_bytes(2), snapshot)

    def test_fill_to_toe_clears_disabled_on_full_slot(self):
        # Unit 69 slot 0 is above target with 0 disabled; unit 68 slot 1 has 1 disabled and is above TOE.
        self.assertEqual(self.slot(68, 1), (253, 79, 1))
        self.units[68].fill_to_toe(0)
        self.assertEqual(self.slot(68, 1), (253, 79, 0))

    def test_fill_to_toe_caps_at_max_count(self):
        u = self.units[2]
        struct.pack_into("<h", u._data, u._offset + landunits.TOE_COUNT_OFFSET, landunits.MAX_COUNT)
        u.fill_to_toe(25)
        self.assertEqual(self.slot(2, 0)[1], landunits.MAX_COUNT)

    def full_slot(self, unit_id, k):
        u = self.units[unit_id]
        return tuple(u._i16(off + 2 * k) for off in (landunits.DEVICE_OFFSET, landunits.COUNT_OFFSET,
                                                     landunits.DISABLED_OFFSET, landunits.TOE_DEVICE_OFFSET,
                                                     landunits.TOE_COUNT_OFFSET))

    def test_support_estimate(self):
        self.assertEqual(self.units[2038].support_estimate(), (24, 30))  # only Support
        self.assertEqual(self.units[2081].support_estimate(), (4, 6))  # only Motorized Support
        self.assertEqual(self.units[2063].support_estimate(), (475, 597))  # both
        self.assertEqual(self.units[6684].support_estimate(), (0, 121))  # neither
        self.assertEqual(self.units[56].support_estimate(), (95, 19))  # disabled counts are included

    def test_support_estimate_excludes_aviation_and_naval_support(self):
        u = self.units[2220]  # 251 x16, Support x14, Aviation Support x0
        self.assertEqual(u.support_estimate(), (14, 16))
        for device in (254, 255):
            struct.pack_into("<h", u._data, u._offset + landunits.DEVICE_OFFSET + 4, device)
            struct.pack_into("<h", u._data, u._offset + landunits.COUNT_OFFSET + 4, 9)
            self.assertEqual(u.support_estimate(), (14, 16))

    def test_raise_support_tops_up_support_slot(self):
        before = self.record_bytes(2038)
        self.assertEqual(self.units[2038].raise_support_to_estimate(), 6)
        self.assertEqual(self.full_slot(2038, 3), (252, 30, 0, 0, 0))
        self.assertEqual(self.units[2038].support_estimate(), (30, 30))
        changed = [i for i, (a, b) in enumerate(zip(before, self.record_bytes(2038))) if a != b]
        self.assertEqual(changed, [landunits.COUNT_OFFSET + 6])

    def test_raise_support_prefers_support_over_motorized(self):
        self.assertEqual(self.units[2063].raise_support_to_estimate(), 122)
        self.assertEqual(self.full_slot(2063, 14)[1], 552)
        self.assertEqual(self.full_slot(2063, 13)[1], 45)

    def test_raise_support_uses_motorized_when_only_that(self):
        self.assertEqual(self.units[2081].raise_support_to_estimate(), 2)
        self.assertEqual(self.full_slot(2081, 2), (253, 6, 0, 0, 0))
        self.assertEqual(self.units[2081].equipment_slots(), [0, 1, 2])

    def test_raise_support_adds_support_to_empty_slot_when_neither(self):
        self.assertEqual(self.units[6684].raise_support_to_estimate(), 121)
        self.assertEqual(self.full_slot(6684, 4), (252, 121, 0, 0, 0))
        self.assertEqual(self.units[6684].equipment_slots(), [0, 1, 2, 3, 4])

    def test_raise_support_without_empty_slot_raises(self):
        u = self.units[7967]  # 20 slots, Motorized Support only
        for k in range(20):
            if self.full_slot(7967, k)[0] == 253:
                struct.pack_into("<h", u._data, u._offset + landunits.DEVICE_OFFSET + 2 * k, 1002)
                struct.pack_into("<h", u._data, u._offset + landunits.TOE_DEVICE_OFFSET + 2 * k, 1002)
        before = self.record_bytes(7967)
        with self.assertRaises(ValueError):
            u.raise_support_to_estimate()
        self.assertEqual(self.record_bytes(7967), before)

    def test_raise_support_already_enough_changes_nothing(self):
        for unit_id in (56, 6, 2220):
            before = self.record_bytes(unit_id)
            if unit_id == 2220:
                self.units[unit_id].raise_support_to_estimate()
                before = self.record_bytes(unit_id)
            with self.subTest(unit=unit_id):
                self.assertEqual(self.units[unit_id].raise_support_to_estimate(), 0)
                self.assertEqual(self.record_bytes(unit_id), before)

    def test_raise_support_caps_at_max_count(self):
        u = self.units[2038]
        struct.pack_into("<h", u._data, u._offset + landunits.COUNT_OFFSET + 6, landunits.MAX_COUNT - 2)
        struct.pack_into("<h", u._data, u._offset + landunits.COUNT_OFFSET, landunits.MAX_COUNT)
        self.assertEqual(u.raise_support_to_estimate(), 2)
        self.assertEqual(self.full_slot(2038, 3)[1], landunits.MAX_COUNT)

    def test_raise_support_is_idempotent(self):
        u = self.units[2063]
        self.assertGreater(u.raise_support_to_estimate(), 0)
        after = self.record_bytes(2063)
        self.assertEqual(u.raise_support_to_estimate(), 0)
        self.assertEqual(self.record_bytes(2063), after)

    def test_fill_to_toe_rejects_bad_percent(self):
        u = self.units[2]
        before = self.record_bytes(2)
        for bad in (-1, 5, 11, 100, True, False, 10.0, "10", None):
            with self.subTest(percent=bad):
                with self.assertRaises(ValueError):
                    u.fill_to_toe(bad)
                self.assertEqual(self.record_bytes(2), before)

    def test_display_names_match_game(self):
        # Names as shown on the game's ground unit list and detail screens.
        expected = {5621: "131st FA Bn", 5639: "1/153rd Infantry Bn", 5635: "1/250th Cst Art Bn",
                    5630: "1/151st Combat Engr Bn", 5542: "Johnston (Det.) Def Bn", 5055: "101st USN Base Force",
                    102: "Pacific Fleet", 6622: "29 Battery/3 HAA", 7836: "41st AA Rgt",
                    7468: "408th PVO AA Bn", 7372: "61st Tank Div", 7072: "73rd Tank Bde",
                    7164: "29th Motorcycle Rgt", 7377: "82nd Tank Bn", 5802: "Lijfwacht Cav Sqn",
                    6632: "Malayan Air Wing", 6673: "Madras Fort", 5506: "11th PA Infantry Div",
                    6225: "11th NZ Bde", 5574: "11th Cavalry (Hrse) Rgt", 7583: "11th Chinese Corps",
                    7418: "1233rd Cannon Rgt", 7645: "120th Red Chinese Div", 5638: "153rd(Sep) Infantry Rgt",
                    5558: "251st Cst AA Rgt", 6414: "24th Indian Mtn Gun Rgt",
                    7816: "1st Const Rgt", 6014: "1st Australian Bde", 6301: "1st Burma Auxiliary AA Rgt",
                    5511: "57th PS Infantry RCT", 7828: "57th AT Rgt", 5601: "56th Cst Art Rgt",
                    5525: "803rd EAB", 6170: "7th RAA Cst Art Rgt",
                    5517: "88th PS FA Rgt", 6970: "8th Cav Div", 7447: "8th Mongolian Cav Div",
                    5642: "G/153rd Infantry Co", 6675: "Fort William", 6181: "Geraldton Fort",
                    7090: "192nd OM Gun Bn", 5585: "19th Combat Engr Rgt",
                    6865: "15th Army", 7538: "14th Group Army", 109: "Malaya Army", 171: "III Indian Corps",
                    7516: "7th War Area", 5805: "Batavia Cst Gun Bn", 6178: "Banks Fort",
                    205: "Soviet Pacific Fleet", 5528: "Subic Bay Defenses"}
        for unit_id, name in expected.items():
            self.assertEqual(self.units[unit_id].display_name, name)
        # The HQ column uses the HQ's game-style name too.
        self.assertEqual(self.units[7164].hq_name, "35th Army")
        self.assertEqual(self.units[7225].hq_name, "Soviet Far East Cmd")
        # Unknown classes fall back to the category.
        self.assertEqual(self.units[2132].display_name, "IJN (AA/Coastal)")

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

    def test_available_devices_by_side(self):
        devices = landunits.available_devices(self.sf)
        ids = {side: {d for d, _ in items} for side, items in devices.items()}
        self.assertIn(367, ids[1])  # Dutch Rifle Squad
        self.assertNotIn(367, ids[0])
        self.assertIn(264, ids[0])  # IJA Infantry Squad
        self.assertNotIn(264, ids[1])
        self.assertTrue(252 in ids[0] and 252 in ids[1])  # Support
        self.assertIn((252, "Support"), devices[1])
        for side, items in devices.items():
            self.assertTrue(all(0 < d < 2000 for d, _ in items))
            self.assertEqual(items, sorted(items, key=lambda i: (i[1].lower(), i[0])))

    def test_add_equipment_changes_only_the_new_slot(self):
        allowed = {d for d, _ in landunits.available_devices(self.sf)[1]}
        for unit_id, expected_slot in ((5639, 5), (2671, 4)):  # 2671 has a gap at slot 4
            before = bytes(self.sf[SECTION].data)
            u = self.units[unit_id]
            self.assertEqual(u.add_equipment(367, 12, 2, allowed), expected_slot)
            k = 2 * expected_slot
            self.assertEqual(self.diff_offsets(before, unit_id),
                             # Device 367 spans two bytes; count 12 and disabled 2 fit in the low byte.
                             {landunits.DEVICE_OFFSET + k, landunits.DEVICE_OFFSET + k + 1,
                              landunits.COUNT_OFFSET + k, landunits.DISABLED_OFFSET + k})
            v = {x.id: x for x in landunits.list_land_units(self.roundtrip())}[unit_id]
            self.assertEqual(v.get_equipment(expected_slot), {"device": "Dutch Rifle Squad", "count": 12,
                                                              "disabled": 2, "toe_device": "", "toe_count": 0})
            u.set_equipment(expected_slot, 7, 7)
            self.assertEqual((u.get_equipment(expected_slot)["count"], u.get_equipment(expected_slot)["disabled"]),
                             (7, 7))

    def test_add_equipment_failures_leave_bytes_unchanged(self):
        allowed = {d for d, _ in landunits.available_devices(self.sf)[1]}
        before = bytes(self.sf[SECTION].data)
        u = self.units[5639]
        for args in ((264, 5, 0), (0, 5, 0), (367, 0, 0), (367, 5, 6), (367, 5, -1), (367, 10000, 0),
                     (True, 5, 0), (367, True, 0), (367, 5, False), (367, 1.5, 0), (367, 5, "0")):
            with self.assertRaises(ValueError, msg=str(args)):
                u.add_equipment(*args, allowed)
        with self.assertRaisesRegex(ValueError, "not available to Allied units"):
            u.add_equipment(264, 5, 0, allowed)
        full = self.units[7967]
        self.assertEqual(len(full.equipment_slots()), landunits.SLOTS)
        with self.assertRaisesRegex(ValueError, "no empty equipment slot"):
            full.add_equipment(367, 5, 0, allowed)
        self.assertEqual(bytes(self.sf[SECTION].data), before)

    def diff_offsets(self, before, record):
        after = bytes(self.sf[SECTION].data)
        diff = [i for i in range(len(before)) if before[i] != after[i]]
        self.assertTrue(all(i // RECORD == record for i in diff), "bytes changed in other records")
        return {i % RECORD for i in diff}

    def test_move_changes_only_location_hex_and_target(self):
        before = bytes(self.sf[SECTION].data)
        sf_before = SaveFile.load(SAVE_015)
        u = self.units[5560]
        self.assertTrue(u.can_move)
        self.assertEqual((u.location_id, u.target_id), (584, 584))
        u.move_to(581)
        # Pearl Harbor hex 180,107 -> Midway hex 158,91; the high bytes are zero for both.
        self.assertEqual(self.diff_offsets(before, 5560), {86, 36, 38, 102})
        for sec in self.sf.sections:
            if sec.sid not in (SECTION, bases.INDEX_SECTION):
                self.assertEqual(sec.data, sf_before[sec.sid].data)
        # Map position: Midway's pixel (6657, 3445) shifted left and down like other Allied units.
        index, index_before = self.sf[bases.INDEX_SECTION].data, sf_before[bases.INDEX_SECTION].data
        diff = {i for i in range(len(index)) if index[i] != index_before[i]}
        self.assertTrue(diff and all(5560 * 20 <= i < 5560 * 20 + 8 for i in diff), diff)
        self.assertEqual(bases.place_pixel(self.sf, 5560), (6643, 3454))
        v = {x.id: x for x in landunits.list_land_units(self.roundtrip())}[5560]
        self.assertEqual((v.location_id, v.target_id, v.location_name), (581, 581, "Midway Island"))
        self.assertTrue(v.can_move)
        self.assertEqual((v._i16(landunits.X_OFFSET), v._i16(landunits.Y_OFFSET)), (158, 91))

    def test_move_to_current_location_is_noop(self):
        before = bytes(self.sf[SECTION].data)
        index = bytes(self.sf[bases.INDEX_SECTION].data)
        self.units[5560].move_to(584)
        self.assertEqual(bytes(self.sf[SECTION].data), before)
        self.assertEqual(bytes(self.sf[bases.INDEX_SECTION].data), index)

    def test_move_to_town(self):
        self.units[5560].move_to(1091)  # Chungking, a type 5 place
        self.assertEqual(self.units[5560].location_name, "Chungking")
        # Same spot as the Allied units already at Chungking, e.g. 7588.
        self.assertEqual(bases.place_pixel(self.sf, 5560), (3199, 1706))
        self.assertEqual(bases.place_pixel(self.sf, 7588), (3199, 1706))

    def test_move_failures_leave_bytes_unchanged(self):
        before = bytes(self.sf[SECTION].data)
        index = bytes(self.sf[bases.INDEX_SECTION].data)
        japanese = next(p.id for p in bases.list_places(self.sf) if p.side_id == 0)
        marching, not_arrived = self.units[6652], self.units[8]
        self.assertEqual(marching.move_blocker, "on the march")
        self.assertFalse(not_arrived.can_move)
        cases = [(self.units[5560], japanese),   # wrong side
                 (self.units[5560], 5639),       # a land unit, not a place
                 (self.units[5560], 0), (self.units[5560], -1), (self.units[5560], 18000),
                 (self.units[5560], True), (self.units[5560], "581"),
                 (marching, 581), (not_arrived, 581)]
        for unit, dest in cases:
            with self.assertRaises(ValueError, msg=str((unit.id, dest))):
                unit.move_to(dest)
        self.assertEqual(bytes(self.sf[SECTION].data), before)
        self.assertEqual(bytes(self.sf[bases.INDEX_SECTION].data), index)


if __name__ == "__main__":
    unittest.main()
