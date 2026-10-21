import os
import struct
import unittest

from witpae import aircraft, bases, losses, victory
from witpae.container import SaveFile, SaveFormatError

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
SAVE_015 = os.path.join(DATA_DIR, "going2_411210.pws")
PEARL, BATAAN = 584, 621  # both Allied-held in the sample save


class HelperTests(unittest.TestCase):
    def test_victory_level_boundaries(self):
        self.assertEqual(victory.victory_level(175, 100), "Allied Decisive Victory")
        self.assertEqual(victory.victory_level(174, 100), "Allied Marginal Victory")
        self.assertEqual(victory.victory_level(100, 175), "Japanese Decisive Victory")
        self.assertEqual(victory.victory_level(125, 100), "Allied Marginal Victory")
        self.assertEqual(victory.victory_level(124, 100), "Draw")
        self.assertEqual(victory.victory_level(100, 125), "Japanese Marginal Victory")
        self.assertEqual(victory.victory_level(100, 124), "Draw")

    def test_victory_level_ties_and_zeros(self):
        self.assertEqual(victory.victory_level(100, 100), "Draw")
        self.assertEqual(victory.victory_level(0, 0), "Draw")
        self.assertEqual(victory.victory_level(5, 0), "Allied Decisive Victory")
        self.assertEqual(victory.victory_level(0, 5), "Japanese Decisive Victory")

    def test_ratio_text(self):
        self.assertEqual(victory.ratio_text(11303, 2165), "Allied 5.22 : 1")
        self.assertEqual(victory.ratio_text(100, 300), "Japanese 3.00 : 1")
        self.assertEqual(victory.ratio_text(7, 7), "Even 1.00 : 1")
        self.assertEqual(victory.ratio_text(0, 0), "Even 0 : 0")
        self.assertEqual(victory.ratio_text(0, 9), "Japanese 9 : 0")

    def test_automatic_threshold(self):
        self.assertEqual([victory.automatic_threshold(y) for y in (1941, 1942, 1943, 1944, 1945, 1946)],
                         [None, None, 4, 3, 2, 2])

    def test_automatic_text(self):
        self.assertEqual(victory.automatic_text(1943), "Automatic victory at 4:1 from 1943 (after 365 days played)")
        self.assertEqual(victory.automatic_text(1945), "Automatic victory at 2:1 from 1945 (after 365 days played)")
        self.assertEqual(victory.automatic_text(1941), "No automatic victory before 1943")

    def test_scored_value(self):
        self.assertEqual(victory.place_value(3, 7, 8), 69)
        self.assertEqual(victory.scored_value(69, 30, 100), 33)  # the manual's Rabaul example
        self.assertEqual(victory.scored_value(69, 0, 100), 17)  # 25% floor
        self.assertEqual(victory.scored_value(69, 500, 100), 69)  # supply above the requirement
        self.assertEqual(victory.scored_value(69, 0, 0), 69)  # nothing required
        self.assertEqual(victory.scored_value(69, -5, 100), 17)


@unittest.skipUnless(os.path.exists(SAVE_015), "sample save missing")
class VictoryTests(unittest.TestCase):
    def setUp(self):
        self.sf = SaveFile.load(SAVE_015)

    def poke_base(self, loc_id, **values):
        base = bases.Base(self.sf, loc_id, "")
        for name, value in values.items():
            f = bases.FIELD_BY_NAME[name]
            struct.pack_into("<" + f.fmt, self.sf[bases.LOCATION_SECTION].data, base._offset + f.offset, value)

    def row(self, loc_id):
        return {r.id: r for r in victory.base_rows(self.sf)}[loc_id]

    def by_side(self):
        return {s.side: s for s in victory.scores(self.sf)}

    def set_totals(self, totals):
        """Make these aircraft ids the only ones with losses: {id: total air losses}."""
        for a in aircraft.list_aircraft(self.sf):
            values = [0] * 8
            if a.id in totals:
                values[4] = totals[a.id]
            struct.pack_into("<8i", a._data, a._offset + losses.LOSS_OFFSET, *values)

    def models(self, side_id, heavy):
        return [a.id for a in aircraft.list_aircraft(self.sf)
                if a.side_id == side_id and a.engine_count > 0 and (a.engine_count >= 4) == heavy]

    # ---- the sample save -------------------------------------------------------

    def test_scores_of_the_sample(self):
        allied, japanese = victory.scores(self.sf)
        self.assertEqual((allied.side, japanese.side), ("Allied", "Japanese"))
        self.assertEqual((japanese.score, allied.score), (2165, 11303))
        self.assertEqual((japanese.political_points, allied.political_points), (650, 250))
        # Ground losses (Japan 32, Allies 871 twelfths) score for the other side.
        self.assertEqual((japanese.ground_points, allied.ground_points), (72, 2))

    def test_other_is_what_the_parts_leave_out(self):
        for s in victory.scores(self.sf):
            self.assertEqual(s.other, s.score - s.base_points - s.aircraft_points - s.ground_points)

    def test_ships_sunk_count_the_enemy_ships(self):
        sunk = losses.sunk_ships(self.sf)
        by = self.by_side()
        self.assertEqual(by["Allied"].ships_sunk, sum(1 for r in sunk if r.side == "Japanese"))
        self.assertEqual(by["Japanese"].ships_sunk, sum(1 for r in sunk if r.side == "Allied"))

    def test_base_points_sum_the_owned_rows(self):
        rows = victory.base_rows(self.sf)
        by = self.by_side()
        for side in ("Allied", "Japanese"):
            owned = [r for r in rows if r.side == side and r.full > 0]
            self.assertEqual((by[side].bases, by[side].base_points), (len(owned), sum(r.scored for r in owned)))

    def test_status_lines(self):
        level, automatic = victory.status_lines(self.sf)
        self.assertEqual(level, "Allied Decisive Victory (Allied 5.22 : 1)")
        self.assertEqual(automatic, "No automatic victory before 1943")

    # ---- bases -------------------------------------------------------------------

    def test_base_rows_keep_only_places_with_a_value(self):
        rows = victory.base_rows(self.sf)
        self.assertTrue(rows)
        self.assertTrue(all(r.value_japan or r.value_allies for r in rows))
        self.assertEqual(rows, sorted(rows, key=lambda r: (-r.scored, r.name)))
        self.poke_base(PEARL, value_japan=0, value_allies=0)
        self.assertNotIn(PEARL, {r.id for r in victory.base_rows(self.sf)})
        self.poke_base(PEARL, value_japan=0, value_allies=2)
        self.assertIn(PEARL, {r.id for r in victory.base_rows(self.sf)})

    def test_supply_rule(self):
        self.poke_base(PEARL, value_japan=1, value_allies=3, port=7, airfield=8, supply=30, supply_required=100)
        r = self.row(PEARL)
        self.assertEqual((r.side, r.full, r.scored, r.supply_pct, r.to_allies, r.to_japan),
                         ("Allied", 69, 33, 30, 69, 23))
        self.poke_base(PEARL, supply=0)
        self.assertEqual((self.row(PEARL).scored, self.row(PEARL).supply_pct), (17, 0))
        self.poke_base(PEARL, supply_required=0)
        self.assertEqual((self.row(PEARL).scored, self.row(PEARL).supply_pct), (69, 100))

    def test_supply_pct_is_capped(self):
        self.poke_base(PEARL, value_allies=3, supply=5000, supply_required=100)
        r = self.row(PEARL)
        self.assertEqual((r.supply_pct, r.scored), (100, r.full))

    def test_region_is_filled(self):
        self.assertEqual(self.row(BATAAN).region, "Luzon")

    # ---- aircraft ----------------------------------------------------------------

    def test_heavy_bombers_count_double(self):
        heavy, light = self.models(0, True), self.models(0, False)
        self.assertTrue(heavy and light)
        self.set_totals({light[0]: 5})
        allied = self.by_side()["Allied"]
        self.assertEqual((allied.aircraft, allied.aircraft_points), (5, 5))
        self.set_totals({light[0]: 5, heavy[0]: 10})
        by = self.by_side()
        self.assertEqual((by["Allied"].aircraft, by["Allied"].aircraft_points), (15, 25))
        self.assertEqual((by["Japanese"].aircraft, by["Japanese"].aircraft_points), (0, 0))

    def test_missing_scenario_section(self):
        del self.sf._by_id[victory.SECTION]
        with self.assertRaises(SaveFormatError):
            victory.scores(self.sf)


if __name__ == "__main__":
    unittest.main()
