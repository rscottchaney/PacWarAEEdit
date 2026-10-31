import os
import tempfile
import unittest

from witpae import airgroups, leaders
from witpae.container import SaveFile

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
SAVE_015 = os.path.join(DATA_DIR, "going2_411210.pws")
SIZE = airgroups.LEADER_RECORD_SIZE
TOP_CARRIER_TF = (7816, "Towers, John Henry")


class LabelTests(unittest.TestCase):
    def test_rank_labels(self):
        self.assertEqual([leaders.rank_label(c) for c in (0, 8, 9, 10, 19, 22, 23, 31, 32, 37, 39, 42, 43, 53)],
                         ["WO", "LGEN", "GEN", "PO2", "CPT", "ADM", "ENS", "ADM", "FO", "LTC", "BGEN", "GEN", "WO",
                          "ACM"])
        self.assertEqual(len(leaders.RANKS), 54)
        self.assertEqual((leaders.rank_label(54), leaders.rank_label(200)), ("Rank 54", "Rank 200"))

    def test_branch_labels(self):
        branches = {0: "Army", 9: "Army", 10: "Navy", 31: "Navy", 32: "Army", 42: "Army", 43: "Air", 53: "Air",
                    54: "?", 255: "?"}
        for code, branch in branches.items():
            self.assertEqual(leaders.branch_label(code), branch, code)

    def test_type_labels(self):
        self.assertEqual([leaders.type_label(c) for c in range(7)],
                         ["None", "Headquarters", "Large Ground Unit", "Small Ground Unit", "Task Force", "Ship",
                          "Air Group"])
        self.assertEqual(leaders.type_label(7), "Type 7")

    def test_side(self):
        self.assertEqual([leaders.side_of(n) for n in (1, 2, 4, 5, 9)],
                         ["Japanese", "Japanese", "Allied", "Allied", "Allied"])

    def test_weighted_rating(self):
        row = leaders.LeaderRow(1, "x", "Allied", 4, "US", 8, "LGEN", "Army", 2, "Large Ground Unit",
                                10, 20, 30, 40, 50, 60, 70, 0, 0, "", 0, "", 0, "")
        self.assertEqual(leaders.weighted_rating(row, {}), 0)
        self.assertEqual(leaders.weighted_rating(row, {"air": 2, "aggression": -1}), 2 * 40 - 70)
        self.assertEqual(leaders.weighted_rating(row, {"leadership": 5, "naval": -5, "bogus": 9}), 50 - 150)

    def test_presets_are_valid(self):
        self.assertEqual(len(leaders.PRESETS), 10)
        types = set(leaders.TYPES.values()) | {"All"}
        for name, (weights, type_text, branch) in leaders.PRESETS.items():
            self.assertTrue(set(weights) <= set(leaders.RATING_NAMES), name)
            self.assertTrue(all(leaders.WEIGHT_MIN <= v <= leaders.WEIGHT_MAX for v in weights.values()), name)
            self.assertIn(type_text, types, name)
            self.assertIn(branch, leaders.BRANCHES + ("All",), name)


@unittest.skipUnless(os.path.exists(SAVE_015), "sample save missing")
class LeaderTests(unittest.TestCase):
    def setUp(self):
        self.sf = SaveFile.load(SAVE_015)
        self.assigned = leaders.assignments(self.sf)
        self.rows = {r.id: r for r in leaders.list_leaders(self.sf, self.assigned)}

    def roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "out.pws")
            self.sf.save(path)
            return SaveFile.load(path)

    def test_list(self):
        self.assertEqual(len(self.rows), 27732)
        self.assertEqual(list(self.rows), sorted(self.rows))
        self.assertEqual(len(leaders.list_leaders(self.sf)), 27732)  # assignments are built when not given

    def test_leader_record(self):
        r = self.rows[1]
        self.assertEqual((r.name, r.side, r.nation_id, r.nation), ("Abe, Heisuke", "Japanese", 1, "IJA"))
        self.assertEqual((r.rank_code, r.rank, r.branch, r.type_code, r.type), (8, "LGEN", "Army", 2,
                                                                               "Large Ground Unit"))
        self.assertEqual((r.leadership, r.inspiration, r.naval, r.air, r.land, r.admin, r.aggression),
                         (63, 66, 35, 44, 66, 46, 74))
        self.assertEqual((r.political, r.delay, r.kind, r.commands), (7, 22, "", ""))

    def test_preset_top_leader(self):
        weights, type_text, branch = leaders.PRESETS["Carrier TF"]
        shown = leaders.filter_leaders(self.rows.values(), "All", branch, type_text)
        ranked = sorted(shown, key=lambda r: (-leaders.weighted_rating(r, weights), r.id))
        self.assertEqual((ranked[0].id, ranked[0].name), TOP_CARRIER_TF)
        self.assertGreater(leaders.weighted_rating(ranked[0], weights), leaders.weighted_rating(ranked[1], weights))

    def test_types_and_branches_counted(self):
        counts = {}
        for r in self.rows.values():
            counts[r.type] = counts.get(r.type, 0) + 1
        self.assertEqual(counts, {"Ship": 17293, "Air Group": 4488, "Small Ground Unit": 3479,
                                  "Large Ground Unit": 1492, "Headquarters": 584, "Task Force": 396})
        self.assertEqual({r.branch for r in self.rows.values()}, {"Army", "Navy", "Air"})
        self.assertEqual(sum(1 for r in self.rows.values() if r.delay == 0), 15210)

    def test_air_group_leader(self):
        r = self.rows[27701]
        self.assertEqual((r.name, r.side, r.nation, r.rank, r.branch, r.type), ("Dionne E.", "Allied", "USA", "LTC",
                                                                               "Army", "Air Group"))
        self.assertEqual((r.kind, r.unit_id, r.unit, r.extra, r.commands), ("Air group", 4205, "19th TS", 0,
                                                                          "19th TS"))
        self.assertEqual(self.assigned[27701], [("Air group", 4205, "19th TS")])

    def test_ship_captain(self):
        r = self.rows[1478]
        self.assertEqual((r.name, r.side, r.type, r.kind, r.unit_id, r.unit),
                         ("Adachi, I.", "Japanese", "Ship", "Ship", 1549, "Havana Maru"))

    def test_task_force_leader(self):
        r = self.rows[1467]
        self.assertEqual((r.name, r.kind, r.unit_id, r.unit), ("Imoto, Masayuki", "TF", 14070, "TF 14070"))

    def test_lcu_and_hq_leader(self):
        r = self.rows[9]
        self.assertEqual((r.name, r.kind, r.unit_id, r.unit, r.type), ("Akashiba, Yaezo", "LCU", 3788, "25th Div",
                                                                       "Large Ground Unit"))
        hq = self.rows[5]
        self.assertEqual((hq.kind, hq.unit_id, hq.unit), ("LCU", 71, "18th Army"))

    def test_unassigned_and_multiple(self):
        self.assertEqual(self.rows[1].commands, "")
        self.assertEqual(sum(1 for r in self.rows.values() if not r.kind), 12123)
        multi = [r for r in self.rows.values() if r.extra]
        self.assertEqual(len(multi), 70)
        r = self.rows[2025]
        self.assertEqual((r.unit, r.extra, r.commands), ("Nittai Maru", 1, "Nittai Maru +1"))
        self.assertEqual(len(self.assigned[2025]), 2)

    def test_unused_unit_records_are_ignored(self):
        # An air group with no name is an unused record, so its leader field does not count.
        g = next(g for g in airgroups.list_airgroups(self.sf) if g.leader_id > 0)
        data = self.sf[airgroups.GROUP_SECTION].data
        start = g.id * airgroups.GROUP_RECORD_SIZE
        before = leaders.assignments(self.sf)
        data[start:start + 24] = bytes(24)
        after = leaders.assignments(self.sf)
        lost = [k for k, v in before.items() if len(v) != len(after.get(k, []))]
        self.assertEqual(lost, [g.leader_id])

    def test_filters(self):
        rows = list(self.rows.values())
        japanese = leaders.filter_leaders(rows, side="Japanese")
        allied = leaders.filter_leaders(rows, side="Allied")
        self.assertEqual((len(japanese), len(allied)), (9410, 18322))
        self.assertTrue(all(r.nation in ("IJA", "IJN") for r in japanese))
        by_branch = {b: leaders.filter_leaders(rows, branch=b) for b in leaders.BRANCHES}
        self.assertEqual({b: len(v) for b, v in by_branch.items()}, {"Army": 6266, "Navy": 20593, "Air": 873})
        self.assertTrue(all(r.rank_code in range(32, 43) or r.rank_code < 10 for r in by_branch["Army"]))
        self.assertEqual(len(leaders.filter_leaders(rows, type_text="Task Force")), 396)
        self.assertEqual(len(leaders.filter_leaders(rows, type_text="Air Group", side="Allied", branch="Army")),
                         len([r for r in rows if r.type == "Air Group" and r.side == "Allied"
                              and r.branch == "Army"]))
        self.assertEqual(len(leaders.filter_leaders(rows, assigned="Unassigned")), 12123)
        self.assertEqual(len(leaders.filter_leaders(rows, assigned="Assigned")), 27732 - 12123)
        self.assertIn(27701, [r.id for r in leaders.filter_leaders(rows, needle="dionne")])
        self.assertEqual([r.id for r in leaders.filter_leaders(rows, needle=" HAVANA maru ")], [1478])

    def test_rating_edit_roundtrip(self):
        leader = airgroups.get_leader(self.sf, 1)
        self.assertEqual(leader.rank_code, 8)
        leader.set_many({"leadership": 90, "aggression": 5})
        other = self.roundtrip()
        row = next(r for r in leaders.list_leaders(other) if r.id == 1)
        self.assertEqual((row.leadership, row.aggression, row.inspiration), (90, 5, 66))
        old = bytes(SaveFile.load(SAVE_015)[airgroups.LEADER_SECTION].data[SIZE:2 * SIZE])
        new = bytes(other[airgroups.LEADER_SECTION].data[SIZE:2 * SIZE])
        self.assertEqual([i for i in range(SIZE) if old[i] != new[i]], [26, 32])
        # make_row reads the current bytes, so the edit is visible without reloading
        self.assertEqual(leaders.make_row(self.sf, 1, "Abe, Heisuke").leadership, 90)

    def test_validation_refuses_out_of_range(self):
        leader = airgroups.get_leader(self.sf, 1)
        for bad in (100, -1, "5", True):
            with self.assertRaises(ValueError, msg=bad):
                leader.set("leadership", bad)
        with self.assertRaises(ValueError):
            leader.set_many({"air": 50, "land": 100})
        self.assertEqual((leader.get("air"), leader.get("land"), leader.get("leadership")), (44, 66, 63))
        self.assertEqual(self.rows[1].leadership, 63)


if __name__ == "__main__":
    unittest.main()
