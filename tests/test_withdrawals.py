import datetime
import os
import struct
import unittest

from witpae import landunits, withdrawals as wd
from witpae.container import SaveFile

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
SAVE_015 = os.path.join(DATA_DIR, "going2_411210.pws")  # game date 10 Dec 1941


class ParseTests(unittest.TestCase):
    def test_yymmdd(self):
        self.assertEqual(wd.parse_yymmdd(411219), datetime.date(1941, 12, 19))
        self.assertEqual(wd.parse_yymmdd(450101), datetime.date(1945, 1, 1))

    def test_no_date(self):
        self.assertIsNone(wd.parse_yymmdd(0))
        self.assertIsNone(wd.parse_yymmdd(9999))
        self.assertIsNone(wd.parse_yymmdd(421301))

    def test_invalid_day_is_clamped_to_the_end_of_the_month(self):
        self.assertEqual(wd.parse_yymmdd(440631), datetime.date(1944, 6, 30))
        self.assertEqual(wd.parse_yymmdd(420230), datetime.date(1942, 2, 28))
        self.assertEqual(wd.parse_yymmdd(440230), datetime.date(1944, 2, 29))

    def test_status_boundaries(self):
        self.assertEqual(wd.status(-1, 30), wd.OVERDUE)
        self.assertEqual(wd.status(0, 30), wd.DUE)
        self.assertEqual(wd.status(30, 30), wd.DUE)
        self.assertEqual(wd.status(31, 30), wd.SCHEDULED)


@unittest.skipUnless(os.path.exists(SAVE_015), "sample save missing")
class WithdrawalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.save = SaveFile.load(SAVE_015)
        cls.rows = wd.withdrawal_rows(cls.save)
        cls.by_key = {(r.kind, r.id): r for r in cls.rows}

    def test_counts(self):
        self.assertEqual(len(self.rows), 978)
        self.assertEqual(sum(r.kind == wd.LAND_UNIT for r in self.rows), 372)
        self.assertEqual(sum(r.kind == wd.AIR_GROUP for r in self.rows), 606)
        self.assertEqual(sum(r.arrived for r in self.rows), 365)

    def test_air_group_date(self):
        r = self.by_key[(wd.AIR_GROUP, 3212)]
        self.assertEqual(r.name, "No.100 Sqn RAF Det")
        self.assertEqual((r.side, r.location, r.arrived), ("Allied", "Kuantan", True))
        self.assertEqual(r.date, datetime.date(1941, 12, 19))
        self.assertEqual(r.days, 9)
        self.assertIsNone(r.returns)

    def test_air_group_return_date(self):
        r = self.by_key[(wd.AIR_GROUP, 3983)]
        self.assertEqual(r.date, datetime.date(1942, 1, 17))
        self.assertEqual(r.returns, datetime.date(1942, 5, 28))

    def test_air_group_not_arrived(self):
        r = self.by_key[(wd.AIR_GROUP, 4174)]
        self.assertEqual((r.arrived, r.location), (False, wd.NOT_ARRIVED))
        self.assertEqual(r.date, datetime.date(1942, 3, 15))

    def test_land_unit_days_become_a_date(self):
        r = self.by_key[(wd.LAND_UNIT, 5601)]
        self.assertEqual(r.name, "56th Cst Art Rgt")
        self.assertEqual((r.side, r.location, r.arrived), ("Allied", "San Francisco", True))
        self.assertEqual(r.days, 81)
        self.assertEqual(r.date, datetime.date(1941, 12, 10) + datetime.timedelta(days=81))
        self.assertEqual(r.date, datetime.date(1942, 3, 1))
        self.assertIsNone(r.returns)

    def test_land_unit_not_arrived(self):
        r = self.by_key[(wd.LAND_UNIT, 7841)]
        self.assertEqual(r.date, datetime.date(1941, 12, 21))
        self.assertEqual((r.days, r.arrived, r.location), (11, False, wd.NOT_ARRIVED))

    def test_unscheduled_and_placeholder_land_units_are_skipped(self):
        units = {u.id: u for u in landunits.list_land_units(self.save)}
        # id 2 holds 0 (not scheduled); id 7959 holds 10002, a placeholder.
        self.assertEqual(struct.unpack_from("<i", units[2]._data, units[2]._offset + wd.WITHDRAW_DAYS_OFFSET)[0], 0)
        self.assertGreaterEqual(
            struct.unpack_from("<i", units[7959]._data, units[7959]._offset + wd.WITHDRAW_DAYS_OFFSET)[0],
            wd.PLACEHOLDER_DAYS)
        self.assertNotIn((wd.LAND_UNIT, 2), self.by_key)
        self.assertNotIn((wd.LAND_UNIT, 7959), self.by_key)
        # Every listed land unit has a countdown between 1 and the placeholder.
        for r in self.rows:
            if r.kind == wd.LAND_UNIT:
                self.assertTrue(0 < r.days < wd.PLACEHOLDER_DAYS)

    def test_sort_order(self):
        keys = [(r.days, r.kind, r.name.lower(), r.id) for r in self.rows]
        self.assertEqual(keys, sorted(keys))
        self.assertEqual((self.rows[0].kind, self.rows[0].id), (wd.AIR_GROUP, 3212))

    def test_rows_are_in_date_order_and_days_match_the_date(self):
        dates = [r.date for r in self.rows]
        self.assertEqual(dates, sorted(dates))
        for r in self.rows:
            self.assertEqual((r.date - datetime.date(1941, 12, 10)).days, r.days)


if __name__ == "__main__":
    unittest.main()
