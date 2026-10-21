import os
import struct
import unittest

from witpae import factories, industry, landunits, lcuproduction as lp
from witpae.container import SaveFile

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
SAVE_015 = os.path.join(DATA_DIR, "going2_411210.pws")


class Section:
    def __init__(self, data):
        self.data = data


def fake_save(devices):
    """A save holding only a device table: {id: (name, type, load)}."""
    data = bytearray(factories.DEVICE_RECORD_SIZE * (max(devices) + 1))
    for device_id, (name, type_, load) in devices.items():
        start = device_id * factories.DEVICE_RECORD_SIZE
        data[start:start + len(name)] = name.encode("latin-1")
        data[start + lp.DEVICE_TYPE_OFFSET] = type_
        struct.pack_into("<h", data, start + lp.DEVICE_LOAD_OFFSET, load)
    return {factories.DEVICE_SECTION: Section(data)}


class FakeUnit:
    """The parts of LandUnit the report reads."""

    def __init__(self, uid, side="Japanese", days=0, arrived=True, slots=()):
        self.id, self.side, self._arrived = uid, side, arrived
        self._v = {lp.DAYS_OFFSET: days}
        for k, (device, count, toe_device, toe_count) in enumerate(slots):
            self._v[landunits.DEVICE_OFFSET + 2 * k] = device
            self._v[landunits.COUNT_OFFSET + 2 * k] = count
            self._v[landunits.TOE_DEVICE_OFFSET + 2 * k] = toe_device
            self._v[landunits.TOE_COUNT_OFFSET + 2 * k] = toe_count

    def _i16(self, pos):
        return self._v.get(pos, 0)

    @property
    def move_blocker(self):
        return "" if self._arrived else "not at a base or town (not arrived)"


DEVICES = {1: ("Rifle Squad", 23, 17), 2: ("Engineer Squad", 24, 6), 3: ("Gun", 19, 10), 4: ("Truck", 25, 15),
           5: ("Tank", 22, 20), 6: ("Old Gun", 19, 8)}


class CostTests(unittest.TestCase):
    def test_squad_costs_one_armament_point_per_squad(self):
        self.assertEqual(lp.cost(23, 17, 3), (3, 0, 51))
        self.assertEqual(lp.cost(24, 6, 2), (2, 0, 12))

    def test_weapon_costs_load_in_armament(self):
        self.assertEqual(lp.cost(19, 10, 3), (30, 0, 30))
        self.assertEqual(lp.cost(12, 3, 4), (12, 0, 12))

    def test_vehicle_costs_load_in_vehicle_points(self):
        self.assertEqual(lp.cost(25, 15, 2), (0, 30, 30))
        self.assertEqual(lp.cost(22, 20, 1), (0, 20, 20))

    def test_read_device(self):
        save = fake_save(DEVICES)
        self.assertEqual(lp.read_device(save, 4), (4, "Truck", 25, 15))
        self.assertIsNone(lp.read_device(save, 0))
        self.assertIsNone(lp.read_device(save, 99))


class LackTests(unittest.TestCase):
    def test_same_device(self):
        self.assertEqual(lp.lack(3, 7, 3, 10), 3)

    def test_empty_slot(self):
        self.assertEqual(lp.lack(0, 0, 3, 10), 10)

    def test_over_strength_is_never_negative(self):
        self.assertEqual(lp.lack(3, 12, 3, 10), 0)

    def test_different_device_counts_the_whole_toe(self):
        self.assertEqual(lp.lack(6, 10, 3, 10), 10)

    def test_no_toe_count(self):
        self.assertEqual(lp.lack(3, 0, 3, 0), 0)


class RowTests(unittest.TestCase):
    def setUp(self):
        self.save = fake_save(DEVICES)
        self.units = [
            FakeUnit(1, slots=[(1, 8, 1, 10), (3, 2, 3, 2), (6, 5, 3, 4)]),  # lacks 2 squads and 4 guns
            FakeUnit(2, days=10, arrived=False, slots=[(0, 0, 4, 3)]),  # 3 trucks in 10 days
            FakeUnit(3, days=40, arrived=False, slots=[(0, 0, 5, 1)]),
            FakeUnit(4, days=9999, arrived=False, slots=[(0, 0, 5, 9)]),
            FakeUnit(5, days=19999, arrived=False, slots=[(0, 0, 5, 9)]),
            FakeUnit(6, days=0, arrived=False, slots=[(0, 0, 5, 9)]),
            FakeUnit(7, side="Allied", days=3, arrived=False, slots=[(0, 0, 5, 2)]),
        ]

    def rows(self, window):
        return {r.unit.id: r for r in lp.unit_rows(self.save, "Japanese", window, self.units)}

    def test_statuses(self):
        rows = self.rows(None)
        self.assertEqual({i: r.status for i, r in rows.items()},
                         {1: lp.ACTIVE, 2: lp.REINFORCEMENT, 3: lp.REINFORCEMENT, 4: lp.NOT_SCHEDULED,
                          5: lp.NOT_SCHEDULED, 6: lp.NO_DATE})

    def test_window_filters_reinforcements_only(self):
        self.assertEqual(sorted(self.rows(30)), [1, 2, 4, 5, 6])
        self.assertEqual(sorted(self.rows(10)), [1, 2, 4, 5, 6])
        self.assertEqual(sorted(self.rows(9)), [1, 4, 5, 6])
        self.assertEqual(sorted(self.rows(None)), [1, 2, 3, 4, 5, 6])

    def test_active_unit_lack(self):
        r = self.rows(30)[1]
        self.assertEqual((r.toe, r.current), (16, 10))
        # 2 squads (1 point each) and 4 guns of load 10 (the old model in slot 3 counts as missing).
        self.assertEqual((r.armament, r.vehicle, r.manpower), (2 + 4 * 10, 0, 2 * 17 + 4 * 10))

    def test_reinforcement_needs_whole_toe(self):
        r = self.rows(30)[2]
        self.assertEqual((r.armament, r.vehicle, r.manpower, r.days), (0, 45, 45, 10))

    def test_sentinels_and_missing_dates_cost_nothing(self):
        for i in (4, 5, 6):
            r = self.rows(None)[i]
            self.assertEqual((r.armament, r.vehicle, r.manpower), (0, 0, 0))

    def test_device_rows(self):
        rows = {r.id: r for r in lp.device_rows(self.save, "Japanese", 30, self.units)}
        # Rifle squads: 10 in the TOE of the active unit, 8 present.
        self.assertEqual((rows[1].toe, rows[1].current, rows[1].lacking, rows[1].reinforcement), (10, 8, 2, 0))
        self.assertEqual((rows[1].armament, rows[1].manpower, rows[1].kind), (2, 34, "Armament"))
        # Gun: 2 + 4 in the TOE; the old model in the third slot does not count as present.
        self.assertEqual((rows[3].toe, rows[3].current, rows[3].lacking), (6, 2, 4))
        self.assertEqual((rows[4].reinforcement, rows[4].vehicle, rows[4].kind), (3, 45, "Vehicle"))
        self.assertNotIn(5, rows)  # only the unit due in 40 days wants tanks, outside the window
        self.assertEqual(rows[4].type_name, "Vehicle")

    def test_summary_without_production_for_allies(self):
        s = lp.summary_rows({}, [], [], "Allied")
        self.assertEqual([(x.pool, x.per_day, x.days) for x in s], [(None, None, None)] * 3)


@unittest.skipUnless(os.path.exists(SAVE_015), "sample save missing")
class SampleSaveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sf = SaveFile.load(SAVE_015)
        cls.places = industry.list_industry_places(cls.sf)

    def summary(self, window):
        rows = lp.unit_rows(self.sf, "Japanese", window)
        return rows, {s.kind: s for s in lp.summary_rows(self.sf, rows, self.places)}

    def test_japanese_lacks(self):
        _rows, s = self.summary(30)
        self.assertEqual([s[k].arrived for k in lp.POINTS], [44612, 37034, 328601])

    def test_japanese_reinforcements_in_30_days(self):
        rows, s = self.summary(30)
        self.assertEqual(sum(1 for r in rows if r.status == lp.REINFORCEMENT), 14)
        self.assertEqual([s[k].reinforcement for k in lp.POINTS], [1834, 0, 10331])

    def test_pools_and_production(self):
        _rows, s = self.summary(30)
        self.assertEqual([s[k].pool for k in lp.POINTS], [18387, 20, 27426])
        self.assertEqual((s["armament"].per_day, s["vehicle"].per_day), (620, 72))
        self.assertAlmostEqual(s["armament"].days, (44612 + 1834) / 620)

    def test_window_all_includes_every_scheduled_reinforcement(self):
        rows = lp.unit_rows(self.sf, "Japanese", None)
        self.assertGreater(sum(1 for r in rows if r.status == lp.REINFORCEMENT), 14)
        self.assertTrue(all(r.days not in lp.SENTINEL_DAYS for r in rows if r.status == lp.REINFORCEMENT))

    def test_devices(self):
        expected = {707: ("IJA Infantry Squad", 23, 17, 6), 252: ("Support", 23, 10, 104),
                    253: ("Motorized Support", 25, 15, 0), 721: ("7.7mm T99 AAMG", 12, 3, None)}
        for device_id, (name, type_, load, pool) in expected.items():
            d = lp.read_device(self.sf, device_id)
            self.assertEqual((d.name, d.type, d.load), (name, type_, load))
            if pool is not None:
                self.assertEqual(lp.pool_of(self.sf, device_id, "Japanese"), pool)

    def test_device_rows_total_matches_unit_rows(self):
        rows = lp.unit_rows(self.sf, "Japanese", 30)
        devices = lp.device_rows(self.sf, "Japanese", 30)
        for kind in lp.POINTS:
            self.assertEqual(sum(getattr(r, kind) for r in devices), sum(getattr(r, kind) for r in rows))


if __name__ == "__main__":
    unittest.main()
