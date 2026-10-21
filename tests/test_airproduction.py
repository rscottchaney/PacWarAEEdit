import os
import struct
import unittest
from unittest import mock

from witpae import airgroups, airproduction, bases, industry
from witpae.container import SaveFile

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
SAVE_015 = os.path.join(DATA_DIR, "going2_411210.pws")

# Model ids in the sample save: 603 A6M2 Zero (Japanese, 1 x Ha-35), 746 Ki-21-Ic Sally (Japanese, 2 x Ha-5),
# 2 A-29A Hudson (Allied, 2 generic engines), 332 P-38G Lightning (Allied, 2 engines, available 10/42).
ZERO, SALLY, HUDSON, P38G = 603, 746, 2, 332


@unittest.skipUnless(os.path.exists(SAVE_015), "sample save missing")
class AirProductionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.save = SaveFile.load(SAVE_015)
        cls.places = industry.list_industry_places(cls.save)
        cls.entries = airproduction.plant_entries(cls.places)
        cls.rows = {r.id: r for r in airproduction.air_rows(cls.save, cls.entries)}
        cls.engines = {r.id: r for r in airproduction.engine_rows(cls.save, cls.entries)}

    def test_allied_totals(self):
        allied = [r for r in self.rows.values() if r.side == "Allied"]
        self.assertEqual(sum(r.factories for r in allied), 33)
        self.assertEqual(sum(r.size + r.research for r in allied), 856)
        # The game date is 10 Dec 1941: only six of the factories build a model that is already available.
        self.assertEqual(sum(r.size for r in allied), 60)
        self.assertEqual(sum(r.research for r in allied), 796)
        self.assertAlmostEqual(sum(r.planes_day for r in allied), 60 / 30)
        self.assertAlmostEqual(sum(r.hi_day for r in allied), 67.8)
        self.assertTrue(all(r.engines_day is None for r in allied))

    def test_allied_totals_when_every_model_is_available(self):
        sf = SaveFile.load(SAVE_015)
        sf[industry.reports.DATE_SECTION].data[industry.reports.YEAR_OFFSET] = 46
        rows = [r for r in airproduction.air_rows(sf, airproduction.plant_entries(
            industry.list_industry_places(sf))) if r.side == "Allied"]
        self.assertEqual((sum(r.factories for r in rows), sum(r.size for r in rows), sum(r.research for r in rows)),
                         (33, 856, 0))
        self.assertAlmostEqual(sum(r.planes_day for r in rows), 856 / 30)
        self.assertEqual(round(sum(r.hi_day for r in rows), 1), 1096.2)

    def test_rows(self):
        zero = self.rows[ZERO]
        self.assertEqual((zero.name, zero.side, zero.engines, zero.factories, zero.size), (
            "A6M2 Zero", "Japanese", "1 x Nakajima Ha-35", 1, 56))
        self.assertAlmostEqual(zero.planes_day, 56 / 30)
        self.assertAlmostEqual(zero.hi_day, 56 / 30 * 18)
        self.assertAlmostEqual(zero.engines_day, 56 / 30)
        self.assertEqual(self.rows[SALLY].engines, "2 x Nakajima Ha-5")
        self.assertEqual(self.rows[HUDSON].engines, "2 engines")
        p38 = self.rows[P38G]
        # Researching (available 10/42): counted under Research only, nothing built or used yet.
        self.assertEqual((p38.size, p38.research, p38.available, p38.planes_day, p38.hi_day),
                         (0, 20, "10/42 to 5/43", 0, 0))

    def test_groups_match_the_records(self):
        data = self.save[airgroups.GROUP_SECTION].data
        for model in (ZERO, SALLY, HUDSON):
            groups = shortfall = 0
            planes = 0
            days = []
            for g in airgroups.list_airgroups(self.save):
                start = g.id * airgroups.GROUP_RECORD_SIZE
                if struct.unpack_from("<h", data, start + 30)[0] != model:
                    continue
                if struct.unpack_from("<h", data, start + 40)[0] != 0:
                    groups += 1
                    planes += data[start + 210]
                    shortfall += max(0, data[start + 245] - data[start + 210])
                else:
                    days.append(struct.unpack_from("<h", data, start + 220)[0])
            row = self.rows[model]
            self.assertEqual((row.groups, row.in_groups, row.short, row.next_group),
                             (groups, planes, shortfall, min(days) if days else None), model)
        self.assertGreater(self.rows[ZERO].groups, 0)
        self.assertGreater(self.rows[ZERO].short, 0)
        self.assertIsNotNone(self.rows[ZERO].next_group)

    def test_active_models(self):
        for r in self.rows.values():
            if r.factories or r.pool:
                self.assertTrue(r.active, r.name)
        self.assertTrue(self.rows[ZERO].active)
        self.assertTrue(any(not r.active for r in self.rows.values()))

    def test_engine_rows(self):
        self.assertEqual({d: self.engines[d].pool for d in (239, 242, 243, 244, 237)},
                         {239: 332, 242: 245, 243: 43, 244: 119, 237: 0})
        self.assertEqual((self.engines[1932].name, self.engines[1932].size, self.engines[1932].factories),
                         ("Nakajima Ha-35", 180, 1))
        self.assertEqual(self.engines[237].size, 125)
        self.assertEqual(self.engines[244].size, 65)
        ha35 = self.engines[1932]
        models = [a for a in airproduction.aircraft.list_aircraft(self.save) if a.side_id == 0 and a.engine_id == 1932]
        needed = sum(f.size * m.engine_count for e in self.entries for f in [e.factory]
                     for m in models if f.type == 2000 + m.id and f.production_on
                     and not industry.is_researching(self.save, f) and e.place.base.side_id == 0)
        self.assertEqual((ha35.needed, ha35.net), (needed, 180 - needed))
        self.assertGreater(needed, 0)
        self.assertAlmostEqual(ha35.hi_day, 180 / 30 * 18)
        self.assertIn("A6M2 Zero", ha35.used_by)
        self.assertIn("more)", ha35.used_by)  # many models: the list is truncated
        # Only Japanese engines: the generic Allied engine device is not listed.
        self.assertNotIn(1852, self.engines)

    def test_model_entries(self):
        entries = airproduction.model_entries(self.entries, ZERO)
        self.assertEqual([(e.place.id, e.factory.slot, e.factory.size) for e in entries], [(236, 6, 56)])

    def test_set_switches_only_changes_that_model(self):
        sf = SaveFile.load(SAVE_015)
        places = industry.list_industry_places(sf)
        entries = airproduction.plant_entries(places)
        before = {(e.place.id, e.factory.slot): e.factory for e in entries}
        # 674 G4M2 Betty has two Okayama factories with size 0 and damage above 0; they switch too.
        target = next(r for r in airproduction.air_rows(sf, entries) if r.id == 674)
        self.assertTrue(any(e.factory.damage > e.factory.size for e in airproduction.model_entries(entries, 674)))
        changed, unchanged, failed = airproduction.set_switches(entries, target.id, production=False)
        self.assertEqual((len(changed), unchanged, failed), (target.factories, 0, []))
        after = {(e.place.id, e.factory.slot): e.factory for e in airproduction.plant_entries(places)}
        for key, f in before.items():
            g = after[key]
            if f.type == 2000 + target.id:
                self.assertFalse(g.production_on)
                self.assertEqual(g._replace(production_on=True), f)
            else:
                self.assertEqual(g, f, key)
        again = airproduction.set_switches(airproduction.plant_entries(places), target.id, production=False)
        self.assertEqual((again[0], again[1]), ([], target.factories))
        # Repair is independent of production.
        changed, _same, _failed = airproduction.set_switches(airproduction.plant_entries(places), target.id,
                                                             repair=False)
        self.assertEqual(len(changed), target.factories)
        row = next(r for r in airproduction.air_rows(sf, airproduction.plant_entries(places)) if r.id == target.id)
        self.assertEqual(row.size, 0)
        self.assertEqual(row.production_off, target.size + target.production_off)
        self.assertEqual(row.research, target.research)
        self.assertEqual(row.repair_off, target.size + target.research + target.production_off)

    def test_set_switches_reports_refused_factories(self):
        sf = SaveFile.load(SAVE_015)
        entries = airproduction.plant_entries(industry.list_industry_places(sf))
        with mock.patch.object(airproduction.factories, "set_switches", side_effect=ValueError("no")):
            changed, unchanged, failed = airproduction.set_switches(entries, ZERO, production=False)
        self.assertEqual((changed, unchanged, [msg for _e, msg in failed]), ([], 0, ["no"]))


if __name__ == "__main__":
    unittest.main()
