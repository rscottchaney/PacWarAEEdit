import os
import tempfile
import unittest

from witpae import aircraft, airgroups, bases
from witpae.container import SaveFile

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
SAVE_015 = os.path.join(DATA_DIR, "going2_411210.pws")

SKILLS_5041 = [24, 26, 22, 22, 18, 29, 62, 19, 23, 26, 20, 49]
SKILLS_18570 = [20, 20, 26, 29, 20, 21, 41, 30, 25, 27, 21, 48]


def skills(pilot):
    return [pilot.get("skill_" + n.lower()) for n in airgroups.SKILLS]


@unittest.skipUnless(os.path.exists(SAVE_015), "sample save missing")
class AirGroupTests(unittest.TestCase):
    def setUp(self):
        self.sf = SaveFile.load(SAVE_015)
        self.groups = {g.id: g for g in airgroups.list_airgroups(self.sf)}
        self.pilots = airgroups.pilots_by_group(self.sf)

    def roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "out.pws")
            self.sf.save(path)
            return SaveFile.load(path)

    def changed(self, other, section, record_size, record):
        before = bytes(SaveFile.load(SAVE_015)[section].data)
        after = bytes(other[section].data)
        diff = [i for i in range(len(before)) if before[i] != after[i]]
        self.assertTrue(all(i // record_size == record for i in diff), "bytes changed in other records")
        return {i % record_size for i in diff}

    def test_list(self):
        self.assertEqual(len(self.groups), 2895)

    def test_group_without_pilots(self):
        g = self.groups[4156]
        self.assertEqual(g.name, "10th BS PAAC")
        self.assertEqual(g.aircraft_name, "B-10B")
        self.assertEqual([g.get(n) for n in ("morale", "experience", "altitude", "range")], [48, 43, 14200, 7])
        self.assertEqual((g.leader_id, g.pilot_count), (0, 0))
        self.assertIsNone(airgroups.get_leader(self.sf, g.leader_id))
        # Velasco I. is still linked to the group but the game shows no pilots: status 2, not active.
        velasco = [p for p in airgroups.pilots_by_group(self.sf)[4156] if p.name == "Velasco I."]
        self.assertEqual([(p.status, p.status_label) for p in velasco], [(2, "Status 2")])
        # The pilot-count byte can disagree with the pilot table (588 groups in this save).

    def test_group_with_pilots_and_leader(self):
        g = self.groups[4205]
        self.assertEqual((g.name, g.aircraft_name), ("19th TS", "C-33"))
        self.assertEqual([g.get(n) for n in ("morale", "experience", "altitude", "range", "train")],
                         [50, 47, 6000, 12, 40])
        self.assertEqual((g.planes, g.pilot_count, g.leader_id), (1, 2, 27701))
        pilots = {p.id: p for p in self.pilots[4205]}
        self.assertEqual(sorted(pilots), [5041, 18570])
        self.assertEqual((pilots[5041].name, pilots[5041].get("experience"), skills(pilots[5041])),
                         ("Dionne E.", 48, SKILLS_5041))
        self.assertEqual((pilots[18570].name, pilots[18570].get("experience"), skills(pilots[18570])),
                         ("Burke J.", 46, SKILLS_18570))
        self.assertEqual((pilots[5041].age, pilots[5041].group_id), (37, 4205))
        leader = airgroups.get_leader(self.sf, g.leader_id)
        self.assertEqual(leader.name, "Dionne E.")
        self.assertEqual([leader.get(f.name) for f in airgroups.LEADER_FIELDS], [49, 41, 15, 57, 42, 59, 36])
        self.assertEqual(leader.age, 37)

    def test_patrol_levels(self):
        # 19th TS trains 40%; the naval search groups patrol 50%; the Dutch fighters fly 30% CAP.
        g = self.groups
        self.assertEqual([g[4205].get(n) for n in ("cap", "lrcap", "asw", "search", "train", "rest")],
                         [0, 0, 0, 0, 40, 0])
        self.assertEqual(g[2946].get("search"), 50)
        self.assertEqual((g[2910].get("cap"), g[2910].get("train")), (30, 40))

    def test_search_arc_in_degrees(self):
        g = self.groups[2946]
        self.assertEqual((g.get("arc_start"), g.get("arc_end")), (0, 0))
        g.set_many({"arc_start": 90, "arc_end": 180})
        # The game stored 090-180 as 9 and 18.
        self.assertEqual((g._data[g._offset + 630], g._data[g._offset + 631]), (9, 18))
        self.assertEqual((g.get("arc_start"), g.get("arc_end")), (90, 180))
        for bad in (95, 360, -10):
            with self.assertRaises(ValueError, msg=bad):
                g.set("arc_start", bad)
        self.assertEqual(g.get("arc_start"), 90)

    def test_group_edit_roundtrip(self):
        g = self.groups[4205]
        g.set_many({"morale": 80, "altitude": 20000, "range": 3})
        other = self.roundtrip()
        # altitude 6000 -> 20000 changes both bytes of the u16.
        self.assertEqual(self.changed(other, 0x14, airgroups.GROUP_RECORD_SIZE, 4205), {184, 212, 213, 304})
        h = {x.id: x for x in airgroups.list_airgroups(other)}[4205]
        self.assertEqual([h.get(n) for n in ("morale", "altitude", "range")], [80, 20000, 3])

    def test_pilot_edit_roundtrip(self):
        pilot = self.pilots[4205][0]
        self.assertEqual(pilot.id, 5041)
        pilot.set_many({"experience": 60, "skill_air": 70})
        other = self.roundtrip()
        # The game shows the second skill copy (78); the first (65) is kept in step.
        self.assertEqual(self.changed(other, 0x16, airgroups.PILOT_RECORD_SIZE, 5041), {44, 65, 78})
        p = {x.id: x for x in airgroups.pilots_by_group(other)[4205]}[5041]
        self.assertEqual((p.get("experience"), p.get("skill_air")), (60, 70))

    def test_leader_edit_roundtrip(self):
        leader = airgroups.get_leader(self.sf, 27701)
        leader.set("leadership", 99)
        leader.set("aggression", 1)
        other = self.roundtrip()
        self.assertEqual(self.changed(other, 0x15, airgroups.LEADER_RECORD_SIZE, 27701), {26, 32})

    def test_other_sections_untouched(self):
        pristine = SaveFile.load(SAVE_015)
        self.groups[4205].set("morale", 1)
        other = self.roundtrip()
        for sec in pristine.sections:
            if sec.sid != 0x14:
                self.assertEqual(bytes(sec.data), bytes(other[sec.sid].data), hex(sec.sid))

    def test_validation_failures_leave_bytes_unchanged(self):
        sections = (0x14, 0x15, 0x16)
        before = [bytes(self.sf[s].data) for s in sections]
        g = self.groups[4205]
        pilot = self.pilots[4205][0]
        leader = airgroups.get_leader(self.sf, 27701)
        cases = [
            (g, {"morale": 100}), (g, {"morale": 5, "range": -1}), (g, {"altitude": 50001}),
            (g, {"train": 101}), (g, {"morale": True}), (g, {"morale": "5"}), (g, {"nope": 1}),
            (pilot, {"experience": 100}), (pilot, {"experience": 5, "skill_defn": 100}), (pilot, {"skill_air": -1}),
            (pilot, {"skill_air2": 1}), (leader, {"leadership": 100}), (leader, {"air": 5, "land": 100}),
        ]
        for record, values in cases:
            with self.assertRaises(ValueError, msg=str(values)):
                record.set_many(values)
        self.assertEqual([bytes(self.sf[s].data) for s in sections], before)

    def test_get_leader_bounds(self):
        for bad in (0, -1, 50000, 70000):
            self.assertIsNone(airgroups.get_leader(self.sf, bad))

    def test_move_changes_location_and_base(self):
        before = {sec.sid: bytes(sec.data) for sec in self.sf.sections}
        g = self.groups[3626]
        self.assertEqual((g.location_id, g.location_name, g.side, g.can_move), (584, "Pearl Harbor", "Allied", True))
        g.move_to(581)
        for k, data in before.items():
            if k != airgroups.GROUP_SECTION:
                self.assertEqual(bytes(self.sf[k].data), data)
        # Pearl Harbor 584 -> Midway 581: the low bytes of location and base change.
        self.assertEqual(self.changed(self.sf, airgroups.GROUP_SECTION, airgroups.GROUP_RECORD_SIZE, 3626), {40, 42})
        reloaded = {x.id: x for x in airgroups.list_airgroups(self.roundtrip())}[3626]
        self.assertEqual((reloaded.location_id, reloaded.location_name), (581, "Midway Island"))
        self.assertEqual(reloaded._i16(airgroups.BASE_OFFSET), 581)
        g.move_to(1091)  # a type 5 town
        self.assertEqual(g.location_name, "Chungking")

    def test_side_comes_from_the_group_record(self):
        # Groups aboard ships and groups not yet arrived have a side too.
        sides = {gid: self.groups[gid].side for gid in (3626, 482, 1694, 144, 2)}
        self.assertEqual(sides, {3626: "Allied", 482: "Japanese", 1694: "Allied", 144: "Japanese", 2: "Japanese"})
        placed = [g for g in self.groups.values() if g.can_move]
        self.assertEqual(len(placed), 512)
        for g in placed:
            self.assertEqual(g.side, bases.SIDES[bases.place_side_id(self.sf, g.location_id)], g.id)

    def test_move_keeps_a_detachment_base(self):
        det = self.groups[7]  # Chitose Ku S-1 Det: at Roi-Namur 490, base 486
        self.assertEqual((det.location_id, det._i16(airgroups.BASE_OFFSET)), (490, 486))
        dest = next(p.id for p in bases.list_places(self.sf) if p.side_id == 0 and p.id not in (490, 486))
        det.move_to(dest)
        self.assertEqual(self.changed(self.sf, airgroups.GROUP_SECTION, airgroups.GROUP_RECORD_SIZE, 7) - {40, 41},
                         set())
        self.assertEqual((det.location_id, det._i16(airgroups.BASE_OFFSET)), (dest, 486))

    def test_move_to_current_location_is_noop(self):
        before = bytes(self.sf[airgroups.GROUP_SECTION].data)
        self.groups[3626].move_to(584)
        self.assertEqual(bytes(self.sf[airgroups.GROUP_SECTION].data), before)

    def test_ship_borne_and_not_arrived_groups_cannot_move(self):
        ship = self.groups[144]
        self.assertEqual((ship.location_id, ship.location_name, ship.move_blocker),
                         (19441, "Teihoku Maru", "aboard a ship"))
        self.assertEqual((self.groups[482].location_name, self.groups[1694].location_name), ("Akagi", "Lexington"))
        arriving = self.groups[2]
        self.assertEqual((arriving.location_id, arriving.location_name, arriving.move_blocker), (0, "", "not arrived"))
        before = bytes(self.sf[airgroups.GROUP_SECTION].data)
        for g in (ship, arriving):
            with self.assertRaises(ValueError):
                g.move_to(584)
        self.assertEqual(bytes(self.sf[airgroups.GROUP_SECTION].data), before)

    def test_move_failures_leave_bytes_unchanged(self):
        before = bytes(self.sf[airgroups.GROUP_SECTION].data)
        japanese = next(p.id for p in bases.list_places(self.sf) if p.side_id == 0)
        for dest in (japanese, 5560, 0, -1, 18000, True, "581"):
            with self.assertRaises(ValueError, msg=str(dest)):
                self.groups[3626].move_to(dest)
        self.assertEqual(bytes(self.sf[airgroups.GROUP_SECTION].data), before)

    def test_aircraft_side(self):
        by_id = {a.id: a for a in aircraft.list_aircraft(self.sf)}
        self.assertEqual([by_id[i].side_id for i in (341, 342, 603)], [1, 1, 0])

    def assert_only_offsets(self, offsets, change):
        before = SaveFile.load(SAVE_015)
        change(self.groups[4020])
        for loaded in (self.sf, self.roundtrip()):
            for section in (s.sid for s in before.sections):
                old, new = bytes(before[section].data), bytes(loaded[section].data)
                self.assertEqual(len(old), len(new), section)
                diff = {i for i in range(len(old)) if old[i] != new[i]}
                if section == airgroups.GROUP_SECTION:
                    base = 4020 * airgroups.GROUP_RECORD_SIZE
                    self.assertEqual(diff, {base + o for o in offsets})
                else:
                    self.assertFalse(diff, section)

    def test_set_aircraft_changes_only_type(self):
        g = self.groups[4020]
        self.assertEqual((g.aircraft_id, g.upgrade_id, g.upgrade_name), (341, 342, "P-40E Warhawk"))
        self.assert_only_offsets((30, 31), lambda g: g.set_aircraft(155))
        self.assertEqual((g.aircraft_id, g.aircraft_name, g._i16(308), g._i16(574)),
                         (155, "P-40E Warhawk", 342, 342))

    def test_set_upgrade_changes_only_both_copies(self):
        g = self.groups[4020]
        self.assert_only_offsets((308, 309, 574, 575), lambda g: g.set_upgrade(155))
        self.assertEqual((g.aircraft_id, g.upgrade_id, g._i16(574)), (341, 155, 155))

    def test_set_aircraft_failures_leave_bytes_unchanged(self):
        before = [bytes(self.sf[k].data) for k in (airgroups.GROUP_SECTION, aircraft.AIRCRAFT_SECTION)]
        cases = [(4020, 603), (self.japanese_group(), 342), (4020, 0), (4020, -1), (4020, 1000),
                 (4020, 99999), (4020, 1), (4020, True), (4020, "342")]
        for group, aircraft_id in cases:
            with self.assertRaises(ValueError, msg=repr((group, aircraft_id))):
                self.groups[group].set_aircraft(aircraft_id)
            with self.assertRaises(ValueError, msg=repr((group, aircraft_id))):
                self.groups[group].set_upgrade(aircraft_id)
        self.assertEqual(before, [bytes(self.sf[k].data) for k in (airgroups.GROUP_SECTION,
                                                                    aircraft.AIRCRAFT_SECTION)])

    def test_plane_status_sums_to_total_for_arrived_groups(self):
        arrived = [g for g in self.groups.values() if g.arrived]
        self.assertGreater(len(arrived), 1000)
        for g in arrived:
            self.assertEqual(g.ready + g.maintenance + g.reserve + g.damaged, g.planes, g.id)
        g = self.groups[4020]
        self.assertEqual((g.ready, g.maintenance, g.damaged, g.reserve, g.planes), (11, 6, 3, 0, 20))
        self.assertFalse(self.groups[2].arrived)

    # Groups whose stored repair total (402) is off from their plane records in this save.
    OFF_REPAIR_TOTAL = {2700, 2913, 2937, 2941, 2993, 3076, 3102, 3184, 4017}

    def plane_records(self, sf, group_id):
        data = sf[airgroups.PLANE_SECTION].data
        size = airgroups.PLANE_RECORD_SIZE
        return {i: bytes(data[i * size:(i + 1) * size]) for i in range(len(data) // size)
                if int.from_bytes(data[i * size + 10:i * size + 12], "little", signed=True) == group_id}

    def status_counts(self, sf, group_id):
        c = [0, 0, 0, 0]
        for rec in self.plane_records(sf, group_id).values():
            for k, status in enumerate((6, 4, 1, 2)):
                c[k] += rec[160] == status
        return tuple(c)

    def check_group_consistent(self, sf, g):
        """Assert the status counts and total match the plane records; return whether 402 does too."""
        records = self.plane_records(sf, g.id).values()
        self.assertEqual(self.status_counts(sf, g.id), (g.ready, g.maintenance, g.damaged, g.reserve), g.id)
        self.assertEqual(len(records), g.planes, g.id)
        return g._i16(airgroups.REPAIR_OFFSET) == sum(r[162] for r in records)

    def changed_groups(self, before, after):
        old, new = before[0x14].data, after[0x14].data
        size = airgroups.GROUP_RECORD_SIZE
        return {i // size: i % size for i in range(len(old)) if old[i] != new[i]}

    def test_plane_records_match_group_counts_in_the_save(self):
        arrived = [g for g in self.groups.values() if g.arrived]
        off = {g.id for g in arrived if not self.check_group_consistent(self.sf, g)}
        self.assertEqual(off, self.OFF_REPAIR_TOTAL)

    def test_set_plane_status_rewrites_only_changed_records(self):
        g = self.groups[4020]
        self.assertTrue(self.check_group_consistent(self.sf, g))
        before = SaveFile.load(SAVE_015)
        old = self.plane_records(before, 4020)
        g.set_plane_status(ready=8, maintenance=5, damaged=5, reserve=2)
        for loaded in (self.sf, self.roundtrip()):
            h = {x.id: x for x in airgroups.list_airgroups(loaded)}[4020]
            self.assertEqual((h.ready, h.maintenance, h.damaged, h.reserve, h.planes), (8, 5, 5, 2, 20))
            self.assertTrue(self.check_group_consistent(loaded, h))
            new = self.plane_records(loaded, 4020)
            self.assertEqual(sorted(new), sorted(old))
            changed = [i for i in old if old[i] != new[i]]
            # 3 ready + 1 maintenance planes become 2 damaged + 2 reserve.
            self.assertEqual(len(changed), 4)
            for i in old:
                if i not in changed:
                    continue
                self.assertNotEqual(old[i][160], new[i][160])
                self.assertFalse({k for k in range(len(old[i])) if old[i][k] != new[i][k]} - {160, 161, 162})
                self.assertEqual(tuple(new[i][161:163]), {1: (1, 1), 2: (0, 0)}[new[i][160]])
            # Only this group's record and the plane section differ elsewhere.
            for sec in before.sections:
                if sec.sid not in (airgroups.GROUP_SECTION, airgroups.PLANE_SECTION):
                    self.assertEqual(bytes(sec.data), bytes(loaded[sec.sid].data), sec.sid)
            self.assertEqual(set(self.changed_groups(before, loaded)), {4020})

    def test_set_plane_status_keeps_unchanged_statuses(self):
        g = self.groups[4020]
        old = self.plane_records(self.sf, 4020)
        g.set_plane_status(ready=9, maintenance=4, damaged=7, reserve=0)
        new = self.plane_records(self.sf, 4020)
        # 2 ready and 2 maintenance planes become damaged; nothing else moves.
        self.assertEqual(len([i for i in old if old[i] != new[i]]), 4)
        self.assertTrue(self.check_group_consistent(self.sf, g))
        self.assertEqual(g._i16(airgroups.REPAIR_OFFSET), sum(r[162] for r in new.values()))

    def test_set_plane_status_to_same_split_writes_nothing(self):
        before = {s.sid: bytes(s.data) for s in self.sf.sections}
        g = self.groups[4020]
        g.set_plane_status(ready=g.ready, maintenance=g.maintenance, damaged=g.damaged, reserve=g.reserve)
        self.assertEqual({s.sid: bytes(s.data) for s in self.sf.sections}, before)

    def test_repair_all_moves_maintenance_and_damaged_to_ready(self):
        g = self.groups[4020]
        old = self.plane_records(self.sf, 4020)
        g.repair_all()
        self.assertEqual((g.ready, g.maintenance, g.damaged, g.reserve, g.planes), (20, 0, 0, 0, 20))
        new = self.plane_records(self.sf, 4020)
        self.assertEqual(len([i for i in old if old[i] != new[i]]), 9)
        self.assertTrue(all(r[160] == 6 and r[161] == 0 and r[162] == 0 for r in new.values()))
        self.assertEqual(g._i16(airgroups.REPAIR_OFFSET), 0)
        self.assertTrue(self.check_group_consistent(self.roundtrip(), g))

    def test_repair_total_follows_the_change_for_an_off_group(self):
        # 3102's stored total is 0 but its records sum to 2; the stored total moves by the same amount.
        g = self.groups[3102]
        self.assertEqual((g._i16(airgroups.REPAIR_OFFSET), g.maintenance), (0, 1))
        g.repair_all()
        self.assertEqual(g._i16(airgroups.REPAIR_OFFSET), 0)
        self.assertEqual(self.status_counts(self.sf, 3102), (13, 0, 0, 0))

    def test_plane_record_count_mismatch_leaves_bytes_unchanged(self):
        data = self.sf[airgroups.PLANE_SECTION].data
        pos = min(self.plane_records(self.sf, 4020)) * airgroups.PLANE_RECORD_SIZE
        data[pos + 10:pos + 12] = (0).to_bytes(2, "little")  # frees one of the group's 20 records
        sections = (airgroups.GROUP_SECTION, airgroups.PLANE_SECTION)
        before = [bytes(self.sf[k].data) for k in sections]
        for call in (lambda g: g.set_plane_status(8, 5, 5, 2), lambda g: g.repair_all()):
            with self.assertRaisesRegex(ValueError, "19 plane records"):
                call(self.groups[4020])
        self.assertEqual(before, [bytes(self.sf[k].data) for k in sections])

    def test_repair_all_keeps_reserve(self):
        g = self.groups[4020]
        g.set_plane_status(ready=8, maintenance=5, damaged=5, reserve=2)
        g.repair_all()
        self.assertEqual((g.ready, g.maintenance, g.damaged, g.reserve), (18, 0, 0, 2))

    def test_repair_all_without_damage_is_a_no_op(self):
        before = {s.sid: bytes(s.data) for s in self.sf.sections}
        g = self.groups[1]
        self.assertEqual((g.maintenance, g.damaged), (0, 0))
        g.repair_all()
        self.assertEqual({s.sid: bytes(s.data) for s in self.sf.sections}, before)

    def test_plane_status_failures_leave_bytes_unchanged(self):
        sections = (airgroups.GROUP_SECTION, airgroups.PLANE_SECTION)
        before = [bytes(self.sf[k].data) for k in sections]
        cases = [(4020, (10, 6, 3, 0)), (4020, (11, 6, 3, 1)), (4020, (-1, 12, 9, 0)), (4020, (21, 0, 0, -1)),
                 (4020, (True, 6, 3, 0)), (4020, ("11", 6, 3, 0)), (4020, (11.0, 6, 3, 0)),
                 (2, (10, 0, 2, 0)), (2, (0, 0, 0, 0))]
        for group, args in cases:
            with self.assertRaises(ValueError, msg=repr((group, args))):
                self.groups[group].set_plane_status(*args)
        with self.assertRaisesRegex(ValueError, "add up to 20"):
            self.groups[4020].set_plane_status(1, 1, 1, 1)
        with self.assertRaisesRegex(ValueError, "has not arrived"):
            self.groups[2].set_plane_status(0, 0, 0, 0)
        with self.assertRaisesRegex(ValueError, "has not arrived"):
            self.groups[2].repair_all()
        self.assertEqual([bytes(self.sf[k].data) for k in sections], before)

    def japanese_group(self):
        return next(g.id for g in self.groups.values() if g.side == "Japanese")


class DateHelperTests(unittest.TestCase):
    def test_day_date_round_trip(self):
        for text, value in (("14 Dec 1943", 431214), ("1 Jan 1941", 410101), ("29 Feb 1944", 440229)):
            self.assertEqual(airgroups.parse_day_date(text), value)
            self.assertEqual(airgroups.format_day_date(value), text)

    def test_day_date_input_forms(self):
        self.assertEqual(airgroups.parse_day_date("14 dec 43"), 431214)
        self.assertEqual(airgroups.parse_day_date("  14 DEC 1943 "), 431214)
        for blank in ("", "  ", "-"):
            self.assertEqual(airgroups.parse_day_date(blank), 0)
        self.assertEqual(airgroups.format_day_date(0), "-")
        # The sentinel stored by many groups survives a display/parse round trip.
        self.assertEqual(airgroups.parse_day_date(airgroups.format_day_date(9999)), 9999)

    def test_day_date_errors(self):
        for bad in ("31 Feb 1943", "29 Feb 1943", "0 Jan 43", "32 Jan 43", "14 Foo 43", "14 December 43",
                    "14 Dec 2043", "14 Dec 1843", "14 Dec 143", "14 Dec", "Dec 14 1943", "x"):
            with self.assertRaises(ValueError, msg=bad):
                airgroups.parse_day_date(bad)

    def test_month_date(self):
        for text, value in (("Jul 1942", 4207), ("Jan 1944", 4401)):
            self.assertEqual(airgroups.parse_month_date(text), value)
            self.assertEqual(airgroups.format_month_date(value), text)
        self.assertEqual(airgroups.parse_month_date("jul 42"), 4207)
        self.assertEqual(airgroups.parse_month_date("-"), 0)
        self.assertEqual(airgroups.parse_month_date(""), 0)
        self.assertEqual(airgroups.format_month_date(0), "-")
        for bad in ("Foo 42", "Jul", "Jul 2042", "Jul 4", "42 Jul", "Jul 42 1"):
            with self.assertRaises(ValueError, msg=bad):
                airgroups.parse_month_date(bad)

    def test_valid_yymmdd(self):
        self.assertTrue(all(airgroups.valid_yymmdd(v) for v in (0, 431214, 440229, 9999)))
        self.assertFalse(any(airgroups.valid_yymmdd(v) for v in (430231, 431301, 431200, 1000000, 431232, 100)))


@unittest.skipUnless(os.path.exists(SAVE_015), "sample save missing")
class AirGroupScheduleTests(unittest.TestCase):
    def setUp(self):
        self.sf = SaveFile.load(SAVE_015)
        self.groups = {g.id: g for g in airgroups.list_airgroups(self.sf)}
        self.before = bytes(self.sf[airgroups.GROUP_SECTION].data)

    def diff(self, record_id):
        after = bytes(self.sf[airgroups.GROUP_SECTION].data)
        offsets = [i for i in range(len(after)) if after[i] != self.before[i]]
        self.assertTrue(all(i // airgroups.GROUP_RECORD_SIZE == record_id for i in offsets))
        return {i % airgroups.GROUP_RECORD_SIZE for i in offsets}

    def reload(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "out.pws")
            self.sf.save(path)
            other = SaveFile.load(path)
        return {g.id: g for g in airgroups.list_airgroups(other)}

    def test_reads(self):
        g = self.groups[1694]
        self.assertEqual(g.size_schedule(), [(4207, 36), (4401, 40), (4407, 42), (4501, 36), (0, 0)])
        self.assertEqual((g.formation, g.formation_label), (7, "Squadron"))
        self.assertEqual(g.get("max_size"), 27)
        self.assertEqual(self.groups[2587].size_schedule(), [(4410, 24)] + [(0, 0)] * 4)
        self.assertEqual(self.groups[4].get("withdraw"), 450701)
        self.assertEqual(self.groups[9].get("withdraw"), 440710)
        self.assertEqual(self.groups[9].get("return_date"), 450205)
        self.assertEqual(self.groups[4].get("return_date"), 9999)

    def test_related_groups(self):
        g = self.groups[7]
        self.assertEqual((g.parent_id, g.related_label(g.parent_id)), (6, "6 - Chitose Ku S-1"))
        g = self.groups[9]
        self.assertEqual((g.parent_id, g.related_label(0), g.return_as_id), (0, "-", 355))
        self.assertTrue(g.related_label(355).startswith("355 - K-701 Hikotai"))
        self.assertEqual(g.related_label(29999), "29999")

    def test_formation_labels(self):
        by_formation = {}
        for g in self.groups.values():
            by_formation.setdefault(g.formation, g.formation_label)
        self.assertEqual((by_formation[7], by_formation[8], by_formation[9]), ("Squadron", "Flight", "Section"))
        self.assertEqual(by_formation[3], "3")

    def test_set_fields_round_trip(self):
        g = self.groups[1694]
        g.set_many({"withdraw": 431214, "return_date": 440215, "max_size": 30})
        # Byte 246, the near-copy of max_size, is never written.
        self.assertTrue(self.diff(1694) <= {245, 392, 393, 394, 395, 396, 397, 398, 399})
        self.assertIn(245, self.diff(1694))
        other = self.reload()[1694]
        self.assertEqual((other.get("withdraw"), other.get("return_date"), other.get("max_size")),
                         (431214, 440215, 30))

    def test_max_size_writes_only_245(self):
        self.groups[1694].set("max_size", 40)
        self.assertEqual(self.diff(1694), {245})

    def test_clear_dates(self):
        g = self.groups[9]
        g.set_many({"withdraw": 0, "return_date": 0})
        self.assertEqual((g.get("withdraw"), g.get("return_date")), (0, 0))

    def test_bad_field_values_change_nothing(self):
        g = self.groups[1694]
        for values in ({"withdraw": 430231}, {"return_date": 431301}, {"withdraw": 431214, "return_date": 12},
                       {"max_size": 256}, {"max_size": -1}, {"max_size": True}, {"withdraw": True},
                       {"withdraw": 431214, "max_size": 256}, {"withdraw": "431214"}):
            with self.assertRaises(ValueError, msg=values):
                g.set_many(values)
            self.assertEqual(bytes(self.sf[airgroups.GROUP_SECTION].data), self.before, values)

    def test_set_size_schedule(self):
        g = self.groups[1694]
        new = [(4208, 30), (4301, 33), (0, 0), (0, 0), (0, 0)]
        g.set_size_schedule(new)
        self.assertTrue(self.diff(1694) <= set(range(446, 456)) | set(range(456, 461)))
        self.assertEqual(g.size_schedule(), new)
        self.assertEqual(self.reload()[1694].size_schedule(), new)

    def test_set_size_schedule_changes_only_changed_bytes(self):
        g = self.groups[1694]
        entries = g.size_schedule()
        entries[1] = (4401, 41)
        g.set_size_schedule(entries)
        self.assertEqual(self.diff(1694), {457})

    def test_schedule_keeps_given_order(self):
        g = self.groups[2587]
        entries = [(4501, 20), (4401, 22), (0, 0), (0, 0), (0, 0)]
        g.set_size_schedule(entries)
        self.assertEqual(g.size_schedule(), entries)

    def test_bad_schedules_change_nothing(self):
        g = self.groups[1694]
        ok = [(4207, 36), (4401, 40), (4407, 42), (4501, 36), (0, 0)]
        none4 = [(0, 0)] * 4
        cases = {
            "size without date": [(4207, 36), (0, 5)] + [(0, 0)] * 3,
            "size too big": [(4207, 256)] + none4,
            "bad month": [(4213, 20)] + none4,
            "month zero": [(4200, 20)] + none4,
            "year too big": [(10001, 20)] + none4,
            "bool": [(True, 20)] + none4,
            "too few": ok[:4],
            "too many": ok + [(0, 0)],
            "later bad": ok[:4] + [(4601, 300)],
        }
        for label, entries in cases.items():
            with self.assertRaises(ValueError, msg=label):
                g.set_size_schedule(entries)
            self.assertEqual(bytes(self.sf[airgroups.GROUP_SECTION].data), self.before, label)

    def test_every_stored_schedule_is_accepted_unchanged(self):
        # Includes gaps (58th Sentai 1059) and dated size-0 entries (VS-2 1696).
        before = bytes(self.sf[airgroups.GROUP_SECTION].data)
        for g in self.groups.values():
            g.set_size_schedule(g.size_schedule())
        self.assertEqual(bytes(self.sf[airgroups.GROUP_SECTION].data), before)
        self.assertEqual(self.groups[1059].size_schedule()[:2], [(0, 0), (4403, 27)])
        self.assertEqual(self.groups[1696].size_schedule()[:2], [(4201, 18), (4303, 0)])

    def test_schedule_gap_and_size_zero_are_written(self):
        g = self.groups[2587]
        entries = [(0, 0), (4501, 0), (0, 0), (4602, 12), (0, 0)]
        g.set_size_schedule(entries)
        self.assertEqual(g.size_schedule(), entries)

    def test_schedule_fully_used_and_empty(self):
        g = self.groups[1694]
        full = [(4207 + k, 10 + k) for k in range(5)]
        g.set_size_schedule(full)
        self.assertEqual(g.size_schedule(), full)
        g.set_size_schedule([(0, 0)] * 5)
        self.assertEqual(g.size_schedule(), [(0, 0)] * 5)


if __name__ == "__main__":
    unittest.main()
