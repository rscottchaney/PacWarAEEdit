import os
import tempfile
import unittest

from witpae import bases, factories
from witpae.container import SaveFile

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
SAVE_015 = os.path.join(DATA_DIR, "going2_411210.pws")
LA = 506


@unittest.skipUnless(os.path.exists(SAVE_015), "sample save missing")
class FactoryTests(unittest.TestCase):
    def setUp(self):
        self.sf = SaveFile.load(SAVE_015)
        self.by_id = {b.id: b for b in bases.list_bases(self.sf)}
        self.la = self.by_id[LA]
        self.rec = lambda sf: bytes(sf[bases.LOCATION_SECTION].data)

    def roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "out.pws")
            self.sf.save(path)
            return SaveFile.load(path)

    def test_los_angeles_factories(self):
        fl = factories.list_factories(self.la)
        self.assertEqual(len(fl), 20)
        self.assertEqual([(f.name, f.size) for f in fl[:7]],
                         [("Manpower", 36), ("Resources", 200), ("Oil", 2000), ("Heavy Industry", 860),
                          ("Refinery", 2500), ("Light Industry", 1280), ("Repair Shipyard", 90)])
        self.assertTrue(all(f.kind == "industry" for f in fl[:7]))
        self.assertEqual([(f.name, f.size, f.kind) for f in fl[7:9]],
                         [("SBD-3 Dauntless", 21, "aircraft"), ("P-38G Lightning", 20, "aircraft")])
        for f in fl:
            self.assertEqual(f.damage, 0)
            self.assertTrue(f.production_on and f.repair_on)

    def test_aircraft_available_date(self):
        fl = factories.list_factories(self.la)
        # Dates as shown on the game's aircraft assembly screen, e.g. "P-38G Lightning (42/10)".
        self.assertEqual([(f.name, f.available) for f in fl[7:10]],
                         [("SBD-3 Dauntless", (41, 12)), ("P-38G Lightning", (42, 10)),
                          ("P-38H Lightning", (43, 2))])
        self.assertIsNone(fl[0].available)

    def test_upgrade_switch(self):
        start = LA * bases.RECORD_SIZE + factories.KEEP_OFFSET
        data = self.sf[bases.LOCATION_SECTION].data
        factories.set_factory(self.la, 8, 20, 0, True, True, False)
        self.assertEqual(data[start + 8], 1)  # Keep
        factories.set_factory(self.la, 8, 20, 0, True, True)
        self.assertEqual(data[start + 8], 1)  # None leaves it alone
        factories.set_factory(self.la, 8, 20, 0, True, True, True)
        self.assertEqual(data[start + 8], 0)  # Upgd
        before = self.rec(self.sf)
        for upgrade in (False, 1):
            with self.assertRaises(ValueError, msg=upgrade):
                factories.set_factory(self.la, 3, 860, 0, True, True, upgrade)  # Heavy Industry
        self.assertEqual(self.rec(self.sf), before)

    def test_engine_kind(self):
        fl = {f.type: f for f in factories.list_factories(self.by_id[252])}
        self.assertEqual(fl[1932].name, "Nakajima Ha-35")
        self.assertEqual(fl[1932].kind, "engine")

    def test_edit_roundtrip(self):
        factories.set_factory(self.la, 4, 2000, 300, False, False)
        again = self.roundtrip()
        f = factories.get_factory({b.id: b for b in bases.list_bases(again)}[LA], 4)
        self.assertEqual((f.name, f.size, f.damage, f.production_on, f.repair_on),
                         ("Refinery", 2000, 300, False, False))
        old, new = self.rec(SaveFile.load(SAVE_015)), self.rec(again)
        base = LA * bases.RECORD_SIZE
        changed = {i - base for i in range(len(old)) if old[i] != new[i]}
        self.assertEqual(changed, {176 + 8, 176 + 9, 216 + 8, 216 + 9, 844 + 4, 870 + 4})
        self.assertEqual(new[base + 844 + 4], 1)
        self.assertEqual(new[base + 870 + 4], 1)
        self.assertEqual(new[base + 1073 + 4], old[base + 1073 + 4])

    def test_validation_changes_nothing(self):
        before = self.rec(self.sf)
        bad = [(2, 2000, 0, False, True),     # production off on Oil
               (4, 100, 101, True, True),     # damage > size
               (4, -1, 0, True, True),
               (4, 30001, 0, True, True),
               (4, 100, -1, True, True),
               (4, 100, 0, 1, True),
               (4, 100, 0, True, "yes"),
               (4, True, 0, True, True),
               (4, "5", 0, True, True),
               (20, 1, 0, True, True),
               (-1, 1, 0, True, True)]
        for args in bad:
            with self.assertRaises(ValueError, msg=args):
                factories.set_factory(self.la, *args)
            self.assertEqual(self.rec(self.sf), before, args)

    def test_empty_slot_rejected(self):
        empty = next((b, k) for b in self.by_id.values() for k in range(20)
                     if factories.get_factory(b, k) is None)
        with self.assertRaises(ValueError):
            factories.set_factory(empty[0], empty[1], 1, 0, True, True)

    def test_production_back_on_allowed_for_locked(self):
        factories.set_factory(self.la, 2, 2000, 0, True, False)
        self.assertFalse(factories.get_factory(self.la, 2).repair_on)

    def test_locked_slot_already_off_stays_editable(self):
        data = self.sf[bases.LOCATION_SECTION].data
        data[506 * bases.RECORD_SIZE + factories.PRODUCTION_OFF_OFFSET + 2] = 1
        factories.set_factory(self.la, 2, 1500, 0, False, True)
        self.assertEqual(factories.get_factory(self.la, 2).size, 1500)


if __name__ == "__main__":
    unittest.main()
