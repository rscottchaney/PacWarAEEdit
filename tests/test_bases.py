import os
import tempfile
import unittest

from witpae import bases
from witpae.container import SaveFile

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
SAVE_015 = os.path.join(DATA_DIR, "going2_411210.pws")


@unittest.skipUnless(os.path.exists(SAVE_015), "sample save missing")
class BaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pristine = SaveFile.load(SAVE_015)

    def setUp(self):
        self.sf = SaveFile.load(SAVE_015)
        self.by_id = {b.id: b for b in bases.list_bases(self.sf)}

    def roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "out.pws")
            self.sf.save(path)
            return SaveFile.load(path)

    def test_names(self):
        self.assertEqual(self.by_id[584].name, "Pearl Harbor")
        self.assertEqual(self.by_id[631].name, "Manila")
        self.assertEqual(self.by_id[252].name, "Tokyo")

    def test_count(self):
        self.assertEqual(len(self.by_id), 781)

    def test_pearl_harbor(self):
        b = self.by_id[584]
        self.assertEqual(b.get("supply"), 982531)
        self.assertEqual(b.get("fuel"), 908984)
        self.assertEqual(b.get("port"), 7)
        self.assertEqual(b.get("airfield"), 10)
        self.assertEqual(b.get("port_max"), 5)
        self.assertEqual(b.get("airfield_max"), 7)
        self.assertEqual(b.get("fuel_requested"), 14935)
        self.assertEqual(b.get("supply_required"), 7053)
        self.assertEqual(b.get("runway_damage"), 10)
        self.assertEqual(b.get("service_damage"), 40)
        self.assertEqual(b.get("ships_in_port"), 111)
        self.assertEqual(b.get("aircraft"), 256)
        self.assertEqual((b.x, b.y), (180, 107))
        self.assertEqual(b.side, "Allied")

    def test_max_sizes_match_game(self):
        # (port max, airfield max) as read off the in-game base screen.
        expected = {"Los Angeles": (9, 7), "Manila": (6, 7), "Lunga": (1, 5), "Rabaul": (4, 6)}
        by_name = {b.name: b for b in self.by_id.values()}
        for name, maxes in expected.items():
            b = by_name[name]
            self.assertEqual((b.get("port_max"), b.get("airfield_max")), maxes, name)

    def test_los_angeles_matches_screenshot(self):
        b = self.by_id[506]
        self.assertEqual(b.name, "Los Angeles")
        expected = {"supply_required": 20836, "fuel_requested": 15654, "aviation_support": 302,
                    "value_japan": 100, "value_allies": 1, "ships_in_port": 26, "aircraft": 19,
                    "port": 8, "port_max": 9, "airfield": 10, "airfield_max": 7, "forts": 0}
        for name, value in expected.items():
            self.assertEqual(b.get(name), value, name)

    def test_singapore_matches_screenshot(self):
        b = self.by_id[722]
        self.assertEqual(b.name, "Singapore")
        expected = {"port_damage": 17, "runway_damage": 0, "service_damage": 0, "aviation_support": 104,
                    "supply_required": 3417, "fuel_requested": 10644, "value_japan": 20, "value_allies": 90}
        for name, value in expected.items():
            self.assertEqual(b.get(name), value, name)

    def test_tokyo_side(self):
        self.assertEqual(self.by_id[252].side, "Japanese")

    def test_validation(self):
        b = self.by_id[584]
        for name, value in [("supply", -1), ("supply", 100000000), ("port", 11),
                            ("forts", 10), ("airfield", "5"), ("aircraft", 1), ("supply_required", 1),
                            ("ships_in_port", 1), ("nope", 1)]:
            with self.assertRaises(ValueError, msg=(name, value)):
                b.set(name, value)
        self.assertEqual(b.get("supply"), 982531)

    def test_set_many_is_atomic(self):
        b = self.by_id[584]
        with self.assertRaises(ValueError):
            b.set_many({"supply": 5, "port": 99})
        self.assertEqual(b.get("supply"), 982531)

    def test_edit_roundtrip(self):
        self.by_id[584].set_many({"supply": 123, "fuel": 99999999, "port": 0, "forts": 9, "oil": 7})
        again = self.roundtrip()
        b2 = {x.id: x for x in bases.list_bases(again)}[584]
        self.assertEqual([b2.get(n) for n in ("supply", "fuel", "port", "forts", "oil")],
                         [123, 99999999, 0, 9, 7])
        self.assertEqual(b2.get("airfield"), 10)
        for s in self.pristine.sections:
            if s.sid != bases.LOCATION_SECTION:
                self.assertEqual(bytes(again[s.sid].data), bytes(s.data), hex(s.sid))
        old = bytes(self.pristine[bases.LOCATION_SECTION].data)
        new = bytes(again[bases.LOCATION_SECTION].data)
        lo, hi = 584 * bases.RECORD_SIZE, 585 * bases.RECORD_SIZE
        self.assertEqual(old[:lo], new[:lo])
        self.assertEqual(old[hi:], new[hi:])

    def test_untouched_identical(self):
        with open(SAVE_015, "rb") as fh:
            self.assertEqual(self.sf.to_bytes(), fh.read())

    def test_title_roundtrip(self):
        bases.set_title(self.sf, "My edited save")
        again = self.roundtrip()
        self.assertEqual(again.description, "My edited save")
        old = bytes(self.pristine[bases.TITLE_SECTION].data)
        self.assertEqual(bytes(again[bases.TITLE_SECTION].data)[1000:], old[1000:])

    def test_title_validation(self):
        with self.assertRaises(ValueError):
            bases.set_title(self.sf, "x" * 1000)
        with self.assertRaises(ValueError):
            bases.set_title(self.sf, "€")
        bases.set_title(self.sf, "x" * 999)


if __name__ == "__main__":
    unittest.main()
