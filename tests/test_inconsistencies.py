import os
import struct
import unittest
from collections import Counter

from witpae import inconsistencies as inc
from witpae import landunits, shiprecords, taskforces
from witpae.container import SaveFile

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
SAVE_015 = os.path.join(DATA_DIR, "going2_411210.pws")
GROUPS, SHIPS, LOCS, LEADERS, TFS = 0x14, 0x08, 0x13, 0x15, 0x46
GROUP_SIZE, SHIP_SIZE, LOC_SIZE, TF_SIZE = 680, 464, 1172, 556
PEARL = 584  # Allied base
KIDO_BUTAI = 14001  # Japanese TF, home port 246
GUAM_INVASION = 14020  # Japanese TF whose home port is Guam, an Allied base
DESTROYERS = 14402  # Allied TF with four ships
LEXINGTON = 3002  # arrived Allied ship in a port chain
ARMY_UNIT, OTHER_UNIT = 100, 102  # arrived Allied land units with different leaders
JAPANESE_UNIT = 6  # arrived, HQ 7
GROUP = 1  # arrived Allied air group
JAPANESE_LEADER = 1  # Abe, Heisuke
ALLIED_LEADER = 6652  # Reese F.
UNUSED_LEADER = 49999


def put(save, section, pos, fmt, value):
    struct.pack_into(fmt, save[section].data, pos, value)


def get(save, section, pos, fmt):
    return struct.unpack_from(fmt, save[section].data, pos)[0]


@unittest.skipUnless(os.path.exists(SAVE_015), "sample save missing")
class InconsistencyTests(unittest.TestCase):
    def setUp(self):
        self.save = SaveFile.load(SAVE_015)

    def issues(self, check):
        return check(self.save)

    @staticmethod
    def find(issues, kind, subject_id):
        return next((i for i in issues if i.subject_kind == kind and i.subject_id == subject_id), None)

    # ---- the sample save ----------------------------------------------

    def test_checks_are_unique_labels(self):
        self.assertEqual(len(inc.CHECKS), len(set(inc.CHECKS)))
        self.assertEqual(inc.CHECKS[0], "Leader commands several units")

    def test_sample_counts_per_check(self):
        counts = Counter(i.check for i in inc.find_issues(self.save))
        self.assertEqual(counts, {inc.CHECK_NO_LEADER: 5, inc.CHECK_HOME: 1})

    def test_sample_leader_commands_several(self):
        # 70 leaders command a ship and a TF, which is allowed.
        self.assertEqual(inc.leader_commands_several(self.save), [])

    def test_sample_unit_without_leader(self):
        issues = self.issues(inc.unit_without_leader)
        self.assertEqual(Counter(i.subject_kind for i in issues), {"air group": 3, "task force": 2})
        self.assertFalse(any(i.future for i in issues))
        self.assertTrue(all(i.side in ("Allied", "Japanese") for i in issues))
        self.assertTrue(all(i.detail == "Leader id is 0" for i in issues))

    def test_sample_without_leader_skips_land_unit_fragments(self):
        # A unit split over several ships leaves fragments (ids 10000 and up) with leader 0; the first record of a
        # name counts, the fragments do not.
        units = landunits.list_land_units(self.save)
        fragments = [u for u in units if u.arrived and u.id >= 10000
                     and get(self.save, LOCS, u.id * LOC_SIZE + 128, "<H") == 0]
        self.assertTrue(fragments)
        flagged = {i.subject_id for i in self.issues(inc.unit_without_leader) if i.subject_kind == "land unit"}
        self.assertFalse(flagged & {u.id for u in fragments})

    def test_sample_without_leader_skips_supply_task_forces(self):
        tfs = {i.subject_id for i in self.issues(inc.unit_without_leader) if i.subject_kind == "task force"}
        self.assertTrue(tfs)
        self.assertFalse(any(taskforces.TaskForce(self.save, t).mission in inc.LOGISTICS_MISSIONS for t in tfs))

    def test_sample_other_checks_find_nothing(self):
        for check in (inc.unit_leader_side, inc.land_unit_hq, inc.ship_in_missing_task_force, inc.broken_chains):
            self.assertEqual(check(self.save), [], check.__name__)

    def test_sample_home_port(self):
        issues = self.issues(inc.task_force_home_port)
        self.assertEqual(len(issues), 1)
        issue = issues[0]
        self.assertEqual((issue.subject_kind, issue.subject_id, issue.side), ("task force", GUAM_INVASION, "Japanese"))
        self.assertIn("Guam", issue.detail)
        self.assertFalse(issue.future)

    def test_find_issues_is_sorted_by_check_then_subject(self):
        issues = inc.find_issues(self.save)
        order = {c: k for k, c in enumerate(inc.CHECKS)}
        keys = [(order[i.check], i.subject.lower(), i.subject_id) for i in issues]
        self.assertEqual(keys, sorted(keys))

    # ---- corrupted copies ---------------------------------------------

    def test_leader_commands_two_land_units(self):
        leader = get(self.save, LOCS, ARMY_UNIT * LOC_SIZE + 128, "<H")
        put(self.save, LOCS, OTHER_UNIT * LOC_SIZE + 128, "<H", leader)
        issues = self.issues(inc.leader_commands_several)
        self.assertEqual(len(issues), 1)
        self.assertEqual((issues[0].subject_kind, issues[0].subject_id), ("leader", leader))
        self.assertIn("West Coast", issues[0].detail)
        self.assertIn("Pacific Fleet", issues[0].detail)
        self.assertEqual(issues[0].side, "Allied")
        self.assertFalse(issues[0].future)

    def test_leader_commands_two_ships_is_flagged(self):
        leader = get(self.save, SHIPS, LEXINGTON * SHIP_SIZE + 32, "<H")
        put(self.save, SHIPS, 3664 * SHIP_SIZE + 32, "<H", leader)
        self.assertEqual([i.subject_id for i in self.issues(inc.leader_commands_several)], [leader])

    def test_leader_with_delay_is_future(self):
        leader = get(self.save, LOCS, ARMY_UNIT * LOC_SIZE + 128, "<H")
        put(self.save, LOCS, OTHER_UNIT * LOC_SIZE + 128, "<H", leader)
        put(self.save, LEADERS, leader * 180 + 44, "<i", 5)
        self.assertTrue(self.issues(inc.leader_commands_several)[0].future)

    def test_land_unit_without_leader(self):
        put(self.save, LOCS, ARMY_UNIT * LOC_SIZE + 128, "<H", 0)
        issues = self.issues(inc.unit_without_leader)
        found = self.find(issues, "land unit", ARMY_UNIT)
        self.assertIsNotNone(found)
        self.assertEqual(found.subject, "West Coast")
        self.assertEqual(len(issues), 6)

    def test_air_group_ship_and_task_force_without_leader(self):
        put(self.save, GROUPS, GROUP * GROUP_SIZE + 32, "<h", 0)
        put(self.save, SHIPS, LEXINGTON * SHIP_SIZE + 32, "<H", 0)
        put(self.save, LOCS, DESTROYERS * LOC_SIZE + 128, "<H", 0)
        issues = self.issues(inc.unit_without_leader)
        for kind, unit_id in (("air group", GROUP), ("ship", LEXINGTON), ("task force", DESTROYERS)):
            self.assertIsNotNone(self.find(issues, kind, unit_id), kind)

    def test_ship_that_has_not_arrived_may_lack_a_leader(self):
        ship = next(r for r in shiprecords.list_ship_records(self.save) if not r.arrived)
        put(self.save, SHIPS, ship.id * SHIP_SIZE + 32, "<H", 0)
        self.assertIsNone(self.find(self.issues(inc.unit_without_leader), "ship", ship.id))

    def test_air_group_with_leader_of_the_other_side(self):
        put(self.save, GROUPS, GROUP * GROUP_SIZE + 32, "<h", JAPANESE_LEADER)
        found = self.find(self.issues(inc.unit_leader_side), "air group", GROUP)
        self.assertEqual(found.side, "Allied")
        self.assertIn("Japanese", found.detail)
        self.assertIn("Abe, Heisuke", found.detail)

    def test_ship_land_unit_and_task_force_with_leader_of_the_other_side(self):
        put(self.save, SHIPS, LEXINGTON * SHIP_SIZE + 32, "<H", JAPANESE_LEADER)
        put(self.save, LOCS, ARMY_UNIT * LOC_SIZE + 128, "<H", JAPANESE_LEADER)
        put(self.save, LOCS, DESTROYERS * LOC_SIZE + 128, "<H", JAPANESE_LEADER)
        put(self.save, LOCS, JAPANESE_UNIT * LOC_SIZE + 128, "<H", ALLIED_LEADER)
        issues = self.issues(inc.unit_leader_side)
        for kind, unit_id in (("ship", LEXINGTON), ("land unit", ARMY_UNIT), ("task force", DESTROYERS),
                              ("land unit", JAPANESE_UNIT)):
            self.assertIsNotNone(self.find(issues, kind, unit_id), kind)
        self.assertEqual(len(issues), 4)

    def test_unit_with_unused_leader_record(self):
        put(self.save, LOCS, ARMY_UNIT * LOC_SIZE + 128, "<H", UNUSED_LEADER)
        found = self.find(self.issues(inc.unit_leader_side), "land unit", ARMY_UNIT)
        self.assertIn("unused leader record", found.detail)

    def test_unit_not_arrived_with_foreign_leader_is_future(self):
        unit = next(u for u in landunits.list_land_units(self.save) if not u.arrived and u.side == "Allied")
        put(self.save, LOCS, unit.id * LOC_SIZE + 128, "<H", JAPANESE_LEADER)
        self.assertTrue(self.find(self.issues(inc.unit_leader_side), "land unit", unit.id).future)

    def test_land_unit_hq_that_is_not_an_hq(self):
        put(self.save, LOCS, JAPANESE_UNIT * LOC_SIZE + 122, "<h", PEARL)
        issues = self.issues(inc.land_unit_hq)
        self.assertEqual(len(issues), 1)
        self.assertEqual((issues[0].subject_id, issues[0].side), (JAPANESE_UNIT, "Japanese"))
        self.assertIn(str(PEARL), issues[0].detail)

    def test_land_unit_hq_outside_the_table(self):
        put(self.save, LOCS, JAPANESE_UNIT * LOC_SIZE + 122, "<h", -5)
        self.assertEqual([i.subject_id for i in self.issues(inc.land_unit_hq)], [JAPANESE_UNIT])

    def test_land_unit_without_hq_is_fine(self):
        put(self.save, LOCS, JAPANESE_UNIT * LOC_SIZE + 122, "<h", 0)
        self.assertEqual(self.issues(inc.land_unit_hq), [])

    def test_land_unit_not_arrived_with_placeholder_hq_is_fine(self):
        unit = next(u for u in landunits.list_land_units(self.save) if not u.arrived)
        put(self.save, LOCS, unit.id * LOC_SIZE + 122, "<h", PEARL)
        self.assertEqual(self.issues(inc.land_unit_hq), [])

    def test_ship_in_missing_task_force(self):
        put(self.save, SHIPS, LEXINGTON * SHIP_SIZE + 62, "<H", 14999)
        issues = self.issues(inc.ship_in_missing_task_force)
        self.assertEqual([(i.subject_kind, i.subject_id) for i in issues], [("ship", LEXINGTON)])
        self.assertIn("14999", issues[0].detail)
        self.assertEqual(issues[0].side, "Allied")
        self.assertFalse(issues[0].future)
        # The chain the ship sat in no longer agrees with it either.
        chains = self.issues(inc.broken_chains)
        self.assertEqual(len(chains), 1)
        self.assertIn(f"ship {LEXINGTON}", chains[0].detail)

    def test_port_chain_with_a_ship_in_another_task_force(self):
        ship = next(r.id for r in shiprecords.list_ship_records(self.save)
                    if taskforces._ship(self.save, r.id, shiprecords.TASK_FORCE_OFFSET) == 0
                    and taskforces._ship(self.save, r.id, shiprecords.BASE_OFFSET) == PEARL)
        put(self.save, SHIPS, ship * SHIP_SIZE + 62, "<H", DESTROYERS)
        issues = self.issues(inc.broken_chains)
        places = [i for i in issues if i.subject_kind == "place"]
        self.assertEqual([i.subject_id for i in places], [PEARL])
        self.assertEqual(places[0].subject, "Pearl Harbor")
        self.assertIn(f"ship {ship}", places[0].detail)

    def test_ship_in_non_task_force_location_record(self):
        put(self.save, SHIPS, LEXINGTON * SHIP_SIZE + 62, "<H", 5000)
        self.assertEqual([i.subject_id for i in self.issues(inc.ship_in_missing_task_force)], [LEXINGTON])

    def test_task_force_chain_with_wrong_count(self):
        put(self.save, LOCS, DESTROYERS * LOC_SIZE + 656, "<H", 9)
        issues = self.issues(inc.broken_chains)
        self.assertEqual(len(issues), 1)
        self.assertEqual((issues[0].subject_kind, issues[0].subject_id, issues[0].side),
                         ("task force", DESTROYERS, "Allied"))
        self.assertIn("count is 9", issues[0].detail)

    def test_home_port_not_a_place(self):
        put(self.save, TFS, (KIDO_BUTAI - 14000) * TF_SIZE + 54, "<H", 0xFFFF)
        found = self.find(self.issues(inc.task_force_home_port), "task force", KIDO_BUTAI)
        self.assertIn("not a base or town", found.detail)

    def test_home_port_of_the_enemy(self):
        put(self.save, TFS, (KIDO_BUTAI - 14000) * TF_SIZE + 54, "<H", PEARL)
        found = self.find(self.issues(inc.task_force_home_port), "task force", KIDO_BUTAI)
        self.assertIn("other side", found.detail)
        self.assertEqual(found.side, "Japanese")

    def test_find_issues_reports_every_corrupted_check(self):
        put(self.save, LOCS, ARMY_UNIT * LOC_SIZE + 128, "<H", get(self.save, LOCS, OTHER_UNIT * LOC_SIZE + 128, "<H"))
        put(self.save, GROUPS, GROUP * GROUP_SIZE + 32, "<h", JAPANESE_LEADER)
        put(self.save, LOCS, JAPANESE_UNIT * LOC_SIZE + 122, "<h", PEARL)
        put(self.save, SHIPS, LEXINGTON * SHIP_SIZE + 62, "<H", 14999)
        counts = Counter(i.check for i in inc.find_issues(self.save))
        for check in inc.CHECKS:
            self.assertTrue(counts[check], check)


if __name__ == "__main__":
    unittest.main()
