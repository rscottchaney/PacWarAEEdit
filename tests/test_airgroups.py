import os
import tempfile
import unittest

from witpae import airgroups, bases
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


if __name__ == "__main__":
    unittest.main()
