import os
import struct
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

    def test_set_aircraft_model(self):
        # Slot 8 is a P-38G Lightning (id 332); id 2 is the Allied A-29A Hudson.
        factories.set_factory(self.la, 8, 20, 5, False, False, False)
        before = factories.get_factory(self.la, 8)
        factories.set_aircraft_model(self.la, 8, 2)
        after = factories.get_factory(self.la, 8)
        self.assertEqual((after.type, after.name, after.kind), (2002, "A-29A Hudson", "aircraft"))
        self.assertEqual((after.size, after.damage, after.production_on, after.repair_on, after.upgrade_on),
                         (before.size, before.damage, before.production_on, before.repair_on, before.upgrade_on))
        self.assertEqual(after.available, (42, 7))
        data = self.sf[bases.LOCATION_SECTION].data
        start = LA * bases.RECORD_SIZE
        self.assertEqual(struct.unpack_from("<h", data, start + factories.TYPE_OFFSET + 16)[0], 2002)
        self.assertEqual(struct.unpack_from("<h", data, start + factories.ORIGINAL_TYPE_OFFSET + 16)[0], 2002)
        again = self.roundtrip()
        f = factories.get_factory({b.id: b for b in bases.list_bases(again)}[LA], 8)
        self.assertEqual((f.type, f.size, f.damage, f.production_on, f.repair_on, f.upgrade_on),
                         (2002, 20, 5, False, False, False))
        old, new = self.rec(SaveFile.load(SAVE_015)), self.rec(again)
        changed = {i - start for i in range(len(old)) if old[i] != new[i]}
        # Type and original type (two bytes each), plus what the earlier set_factory call changed.
        self.assertEqual(changed, {136 + 16, 136 + 17, 336 + 16, 336 + 17, 216 + 16, 844 + 8, 870 + 8, 1073 + 8})

    def test_set_aircraft_model_refusals(self):
        before = self.rec(self.sf)
        for slot, aircraft_id in ((3, 2),        # Heavy Industry, not an aircraft factory
                                  (8, 603),      # Japanese A6M2 Zero for an Allied factory
                                  (8, 0),        # no such model
                                  (8, 999),      # unnamed record
                                  (8, 5000),
                                  (8, 332),      # already building it
                                  (8, True),
                                  (8, "2")):
            with self.assertRaises(ValueError, msg=(slot, aircraft_id)):
                factories.set_aircraft_model(self.la, slot, aircraft_id)
            self.assertEqual(self.rec(self.sf), before, (slot, aircraft_id))
        with self.assertRaises(ValueError):
            factories.set_aircraft_model(self.by_id[252], 10, 2)  # engine factory
        empty = next((b, k) for b in self.by_id.values() for k in range(20) if factories.get_factory(b, k) is None)
        with self.assertRaises(ValueError):
            factories.set_aircraft_model(empty[0], empty[1], 2)

    def test_set_switches_writes_only_the_two_bytes(self):
        before = self.rec(self.sf)
        factories.set_switches(self.la, 4, production_on=False)
        base = LA * bases.RECORD_SIZE
        after = self.rec(self.sf)
        changed = {i - base for i in range(len(before)) if after[i] != before[i]}
        self.assertEqual(changed, {844 + 4})
        factories.set_switches(self.la, 4, repair_on=False)
        f = factories.get_factory(self.la, 4)
        self.assertEqual((f.production_on, f.repair_on, f.size, f.damage), (False, False, 2500, 0))
        factories.set_switches(self.la, 4, True, True)
        self.assertEqual(self.rec(self.sf), before)
        factories.set_switches(self.la, 4)  # None, None changes nothing
        self.assertEqual(self.rec(self.sf), before)

    def test_set_switches_ignores_size_and_damage(self):
        data = self.sf[bases.LOCATION_SECTION].data
        struct.pack_into("<h", data, LA * bases.RECORD_SIZE + factories.SIZE_OFFSET + 2 * 8, 0)
        struct.pack_into("<h", data, LA * bases.RECORD_SIZE + factories.DAMAGE_OFFSET + 2 * 8, 8)
        factories.set_switches(self.la, 8, production_on=False, repair_on=False)
        f = factories.get_factory(self.la, 8)
        self.assertEqual((f.size, f.damage, f.production_on, f.repair_on), (0, 8, False, False))
        with self.assertRaises(ValueError):
            factories.set_factory(self.la, 8, 0, 8, True, True)  # the editor's own rule is unchanged

    def test_set_switches_refusals(self):
        before = self.rec(self.sf)
        for args in ((2, False),            # Oil: production cannot be switched off
                     (8, 1),                # not a bool
                     (8, None, "no"),
                     (20, True),
                     (-1, True)):
            with self.assertRaises(ValueError, msg=args):
                factories.set_switches(self.la, *args)
            self.assertEqual(self.rec(self.sf), before, args)
        factories.set_switches(self.la, 2, repair_on=False)  # repair on a locked type is fine
        empty = next((b, k) for b in self.by_id.values() for k in range(20) if factories.get_factory(b, k) is None)
        with self.assertRaises(ValueError):
            factories.set_switches(empty[0], empty[1], True)

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
