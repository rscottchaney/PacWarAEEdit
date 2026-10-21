import datetime
import os
import unittest

from witpae import industry, shipproduction as sp, ships
from witpae.container import SaveFile

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
SAVE_015 = os.path.join(DATA_DIR, "going2_411210.pws")


class FakeClass:
    name = "Test"

    def __init__(self, durability, type_label="DD"):
        self.type = type_label
        self._durability = durability

    def get(self, name):
        assert name == "durability"
        return self._durability


class FakeRecord:
    def __init__(self, delay):
        self.days_to_arrival = delay


class StatusTests(unittest.TestCase):
    def test_thresholds(self):
        d = 10
        self.assertEqual(sp.status_of(d, 1), sp.BUILDING)
        self.assertEqual(sp.status_of(d, 10 * d), sp.BUILDING)
        self.assertEqual(sp.status_of(d, 10 * d + 1), sp.CAN_ACCELERATE)
        self.assertEqual(sp.status_of(d, 30 * d), sp.CAN_ACCELERATE)
        self.assertEqual(sp.status_of(d, 30 * d + 1), sp.BLUEPRINT)

    def row(self, durability, delay, today=(10, 12, 1941)):
        return sp.make_row(FakeRecord(delay), FakeClass(durability), 12, today)

    def test_building_row(self):
        r = self.row(10, 100)
        self.assertEqual((r.status, r.starts_in, r.per_day, r.to_finish, r.accel_per_day),
                         (sp.BUILDING, 0, 10, 1000, 30))
        self.assertEqual(r.arrival, datetime.date(1942, 3, 20))

    def test_building_with_short_delay_finishes_sooner(self):
        r = self.row(10, 40)
        self.assertEqual((r.per_day, r.to_finish), (10, 400))

    def test_can_accelerate_row(self):
        for delay, starts_in in ((101, 1), (300, 200)):
            r = self.row(10, delay)
            self.assertEqual((r.status, r.starts_in, r.per_day, r.to_finish, r.accel_per_day),
                             (sp.CAN_ACCELERATE, starts_in, 0, 1000, 10))

    def test_blueprint_row(self):
        r = self.row(10, 301)
        self.assertEqual((r.status, r.starts_in, r.per_day, r.to_finish, r.accel_per_day),
                         (sp.BLUEPRINT, 201, 0, 1000, None))

    def test_unreadable_date_or_overflow_gives_no_arrival(self):
        self.assertIsNone(self.row(10, 100, today=None).arrival)
        self.assertIsNone(self.row(10, 4_000_000_000).arrival)

    def test_midget_sub_uses_no_points(self):
        for delay in (1, 301, 19999):
            r = sp.make_row(FakeRecord(delay), FakeClass(12, "SSX"), 28, (10, 12, 1941))
            self.assertEqual((r.status, r.yard, r.starts_in, r.per_day, r.to_finish, r.accel_per_day),
                             (sp.MIDGET, sp.NAVAL, 0, 0, 0, None))
        self.assertIn(sp.MIDGET, sp.STATUSES)
        self.assertNotIn(sp.MIDGET, sp.COUNTED)

    def test_yard_types(self):
        self.assertEqual(sp.yard_of(12), sp.NAVAL)  # DD
        self.assertEqual(sp.yard_of(2), sp.NAVAL)  # CV
        self.assertEqual(sp.yard_of(4), sp.MERCHANT)  # CVE
        self.assertEqual(sp.yard_of(56), sp.MERCHANT)  # AK
        self.assertEqual(sp.yard_of(11), sp.MERCHANT)  # CS
        self.assertEqual(len(sp.NAVAL_TYPES), 31)


@unittest.skipUnless(os.path.exists(SAVE_015), "sample save missing")
class SampleSaveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.save = SaveFile.load(SAVE_015)
        cls.rows = sp.production_rows(cls.save)
        cls.by_id = {r.ship.id: r for r in cls.rows}
        cls.summary = {s.yard: s for s in sp.summary_rows(cls.save, cls.rows, industry.list_industry_places(cls.save))}

    def test_only_unarrived_japanese(self):
        self.assertEqual(len(self.rows), 2041)
        self.assertTrue(all(r.ship.side == "Japanese" and r.delay > 0 for r in self.rows))

    def test_examples(self):
        junyo, unryu, shimane = self.by_id[7], self.by_id[11], self.by_id[30]
        self.assertEqual((junyo.ship.name, junyo.type, junyo.durability, junyo.delay, junyo.status, junyo.yard),
                         ("Junyo", "CV", 84, 144, sp.BUILDING, sp.NAVAL))
        self.assertEqual((junyo.per_day, junyo.accel_per_day), (84, 252))
        self.assertEqual((unryu.ship.name, unryu.durability, unryu.delay, unryu.status),
                         ("Unryu", 61, 970, sp.CAN_ACCELERATE))
        self.assertEqual((shimane.ship.name, shimane.type, shimane.durability, shimane.delay, shimane.status,
                          shimane.yard), ("Shimane Maru", "CVE", 27, 1163, sp.BLUEPRINT, sp.MERCHANT))

    def test_counts(self):
        self.assertEqual([(s.building, s.can_accelerate, s.blueprint) for s in self.summary.values()],
                         [(24, 83, 792), (21, 77, 958)])

    def test_midget_subs(self):
        midgets = [r for r in self.rows if r.status == sp.MIDGET]
        self.assertEqual(len(midgets), 86)
        self.assertEqual(sorted({r.delay for r in midgets}), [1, 19999])
        self.assertEqual(sum(1 for r in midgets if r.delay == 1), 83)
        self.assertEqual(sum(r.per_day for r in midgets), 0)

    def test_summary(self):
        naval, merchant = self.summary[sp.NAVAL], self.summary[sp.MERCHANT]
        self.assertEqual((naval.size, naval.hi_per_day, naval.pool, naval.needed, naval.net),
                         (1384, 4152, 1, 1385, -1))
        self.assertEqual((merchant.size, merchant.hi_per_day, merchant.pool, merchant.needed, merchant.net),
                         (807, 2421, 1113, 436, 371))

    def test_pool_unreadable(self):
        sf = SaveFile.load(SAVE_015)
        del sf[industry.POOL_SECTION].data[industry.POOL_BASE:]
        summary = sp.summary_rows(sf, self.rows, industry.list_industry_places(sf))
        self.assertEqual([s.pool for s in summary], [None, None])


if __name__ == "__main__":
    unittest.main()
