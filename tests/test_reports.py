import os
import unittest

from witpae import bases, reports, shiprecords, ships
from witpae.container import SaveFile, SaveFormatError

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
SAVE_015 = os.path.join(DATA_DIR, "going2_411210.pws")


class SpoilageLimitTests(unittest.TestCase):
    def test_limits(self):
        self.assertEqual(reports.spoilage_limits(0, 0), (5000, 1000))
        self.assertEqual(reports.spoilage_limits(1, 0), (8000, 3000))
        self.assertEqual(reports.spoilage_limits(0, 1), (8000, 3000))
        self.assertEqual(reports.spoilage_limits(4, 5), (248000, 163000))

    def test_no_limit_from_ten(self):
        self.assertIsNone(reports.spoilage_limits(5, 5))
        self.assertIsNone(reports.spoilage_limits(10, 10))
        self.assertIsNone(reports.spoilage_limits(10, 0))


@unittest.skipUnless(os.path.exists(SAVE_015), "sample save missing")
class ReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pristine = SaveFile.load(SAVE_015)

    def setUp(self):
        self.sf = SaveFile.load(SAVE_015)
        self.base_list = bases.list_bases(self.sf, include_towns=True)
        self.classes = {c.id: c for c in ships.list_ships(self.sf)}

    def test_game_date(self):
        self.assertEqual(reports.game_date(self.sf), (10, 12, 1941))

    def test_game_date_missing_or_truncated_section(self):
        del self.sf[reports.DATE_SECTION].data[reports.YEAR_OFFSET:]
        with self.assertRaises(SaveFormatError):
            reports.game_date(self.sf)
        no_date = SaveFile([s for s in self.sf.sections if s.sid != reports.DATE_SECTION])
        with self.assertRaises(SaveFormatError):
            reports.game_date(no_date)

    def test_spoilage_rows_really_exceed(self):
        rows = reports.spoilage_rows(self.base_list)
        self.assertTrue(rows)
        for r in rows:
            b = r.base
            self.assertLess(b.get("port") + b.get("airfield"), 10)
            self.assertEqual(r.size, b.get("port") + b.get("airfield"))
            self.assertEqual((r.supply_limit, r.fuel_limit), reports.spoilage_limits(b.get("port"), b.get("airfield")))
            self.assertEqual(r.supply_over, max(b.get("supply") - r.supply_limit, 0))
            self.assertEqual(r.fuel_over, max(b.get("fuel") - r.fuel_limit, 0))
            self.assertGreater(r.total_over, 0)
            self.assertEqual(r.total_over, r.supply_over + r.fuel_over)

    def test_spoilage_known_cases(self):
        by_id = {r.base.id: r for r in reports.spoilage_rows(self.base_list)}
        # Miri: size 4, fuel limit 33000, fuel 40238.
        self.assertEqual(by_id[731].fuel_over, 7238)
        self.assertEqual(by_id[731].supply_over, 0)
        # Changchun: size 1, supply 8176 over the 8000 limit.
        self.assertEqual((by_id[336].supply_limit, by_id[336].supply_over, by_id[336].fuel_over), (8000, 176, 0))
        # Pearl Harbor has size 17: no limit, never listed.
        self.assertNotIn(584, by_id)

    def test_spoilage_negative_case(self):
        by_id = {r.base.id for r in reports.spoilage_rows(self.base_list)}
        # Asahikawa is under both limits.
        b = next(b for b in self.base_list if b.id == 224)
        limits = reports.spoilage_limits(b.get("port"), b.get("airfield"))
        self.assertLessEqual(b.get("supply"), limits[0])
        self.assertLessEqual(b.get("fuel"), limits[1])
        self.assertNotIn(224, by_id)

    def test_upgrade_links(self):
        self.assertEqual(self.classes[674].upgrade_id, 675)
        self.assertIsNone(self.classes[679].upgrade_id)
        self.assertEqual(self.classes[337].upgrade_id, 338)
        self.assertEqual(self.classes[338].date, (1, 42))
        self.assertEqual(self.classes[2388].upgrade_id, 2389)
        self.assertEqual(self.classes[2389].date, (6, 42))
        self.assertEqual(reports.upgrade_target(self.classes[337], self.classes).id, 338)
        self.assertIsNone(reports.upgrade_target(self.classes[679], self.classes))

    def test_upgrade_to_unused_class_is_none(self):
        data = self.sf[ships.SHIP_SECTION].data
        data[337 * ships.RECORD_SIZE + ships.UPGRADE_OFFSET:337 * ships.RECORD_SIZE + ships.UPGRADE_OFFSET + 2] = (4999).to_bytes(2, "little")
        classes = {c.id: c for c in ships.list_ships(self.sf)}
        self.assertNotIn(4999, classes)
        self.assertIsNone(reports.upgrade_target(classes[337], classes))

    def test_upgrade_rows(self):
        rows = reports.upgrade_rows(self.sf)
        records = shiprecords.list_ship_records(self.sf)
        maryland = [r for r in rows if r.current.id == 337]
        self.assertTrue(maryland)
        for r in maryland:
            self.assertEqual((r.target.id, r.month, r.year, r.months), (338, 1, 42, 1))
        self.assertTrue(all(r.months == 1 for r in rows if r.ship.name == "Maryland"))
        kanawha = [r for r in rows if r.current.id == 2388]
        self.assertTrue(all(r.months == 6 for r in kanawha))
        by_ship = {r.ship.id for r in rows}
        for rec in records:
            if rec.class_id == 679:
                self.assertNotIn(rec.id, by_ship)

    def test_upgrade_rows_skip_unarrived_ships(self):
        rows = reports.upgrade_rows(self.sf)
        self.assertTrue(all(r.ship.days_to_arrival == 0 for r in rows))
        # Tactician (4918) arrives later; its class 217 still has an upgrade link.
        tactician = {rec.id: rec for rec in shiprecords.list_ship_records(self.sf)}[4918]
        self.assertGreater(tactician.days_to_arrival, 0)
        classes = {c.id: c for c in ships.list_ships(self.sf)}
        self.assertIsNotNone(reports.upgrade_target(classes[tactician.class_id], classes))
        self.assertNotIn(4918, {r.ship.id for r in rows})

    def test_upgrade_type_change(self):
        for r in reports.upgrade_rows(self.sf):
            if r.current.type == r.target.type:
                self.assertEqual(r.type_change, "")
            else:
                self.assertEqual(r.type_change, f"{r.current.type} -> {r.target.type}")


if __name__ == "__main__":
    unittest.main()
