import os
import struct
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

    def test_supply_cap_and_garrison(self):
        by_name = {b.name: b for b in self.by_id.values()}
        # Bassein (supply cap 500 on the game screen) is a town record here, not a base.
        self.assertEqual(by_name["Akyab"].get("supply_cap"), 100)
        self.assertEqual(by_name["Bangkok"].get("supply_cap"), 1000)
        colombo = by_name["Colombo"]
        self.assertEqual(colombo.get("garrison_allied"), 40)
        self.assertEqual(colombo.get("garrison_japanese"), 80)
        self.assertFalse(bases.FIELD_BY_NAME["garrison_japanese"].verified)

    def test_supply_cap_and_garrison_edit(self):
        section = self.sf[bases.LOCATION_SECTION]
        before = bytes(section.data)
        b = self.by_id[688]
        b.set_many({"supply_cap": 700, "garrison_allied": 41, "garrison_japanese": 300})
        after = bytes(self.roundtrip()[bases.LOCATION_SECTION].data)
        changed = {i - 688 * bases.RECORD_SIZE for i in range(len(before)) if before[i] != after[i]}
        # 0 -> 700 and 80 -> 300 touch both bytes; 40 -> 41 only the low one.
        self.assertEqual(changed, {1116, 1117, 978, 902, 903})
        for bad in ({"supply_cap": 65536}, {"garrison_allied": -1}, {"garrison_japanese": 70000},
                    {"garrison_allied": 5, "supply_cap": "9"}):
            with self.assertRaises(ValueError, msg=str(bad)):
                b.set_many(bad)
        self.assertEqual(bytes(section.data), bytes(self.sf[bases.LOCATION_SECTION].data))
        self.assertEqual(b.get("garrison_allied"), 41)

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

    def test_building_matches_game(self):
        # Los Angeles: port expanding and forts building, airfield above its max so off.
        self.assertEqual(self.by_id[506].get_building(), {"port": True, "airfield": False, "forts": True})

    def test_building_off_and_on_like_game(self):
        b = self.by_id[506]
        data = self.sf[bases.LOCATION_SECTION].data
        pos = 506 * bases.RECORD_SIZE
        b.set_building({"port": False})
        self.assertEqual(struct.unpack_from("<hh", data, pos + 424)[0], 0)
        self.assertEqual(struct.unpack_from("<h", data, pos + 866)[0], 8)  # copy kept
        b.set_building({"port": True})
        again = {x.id: x for x in bases.list_bases(self.roundtrip())}[506]
        self.assertEqual(again.get_building(), {"port": True, "airfield": False, "forts": True})
        self.assertEqual(bytes(self.roundtrip()[bases.LOCATION_SECTION].data), bytes(self.pristine[bases.LOCATION_SECTION].data))

    def test_building_on_with_empty_copy(self):
        b = self.by_id[506]
        b.set_building({"airfield": True})
        self.assertEqual(struct.unpack_from("<h", self.sf[bases.LOCATION_SECTION].data, 506 * bases.RECORD_SIZE + 428)[0], 1)

    def test_building_validation(self):
        before = bytes(self.sf[bases.LOCATION_SECTION].data)
        for flags in [{"nope": True}, {"port": 1}, {"port": False, "forts": "no"}]:
            with self.assertRaises(ValueError, msg=flags):
                self.by_id[506].set_building(flags)
        self.assertEqual(bytes(self.sf[bases.LOCATION_SECTION].data), before)

    def test_stockpile_default_off(self):
        self.assertEqual(self.by_id[506].get_stockpile(),
                         {"supply": False, "fuel": False, "resources": False, "oil": False})

    def test_stockpile_roundtrip(self):
        self.by_id[506].set_stockpile({"supply": True, "oil": True})
        b2 = {x.id: x for x in bases.list_bases(self.roundtrip())}[506]
        self.assertEqual(b2.get_stockpile(),
                         {"supply": True, "fuel": False, "resources": False, "oil": True})
        data = self.roundtrip()[bases.LOCATION_SECTION].data
        self.assertEqual(data[506 * bases.RECORD_SIZE + bases.STOCKPILE_OFFSET], 0x09)

    def test_stockpile_preserves_upper_bits(self):
        pos = 506 * bases.RECORD_SIZE + bases.STOCKPILE_OFFSET
        data = self.sf[bases.LOCATION_SECTION].data
        data[pos] = 0xF0
        b = self.by_id[506]
        b.set_stockpile({"fuel": True, "resources": True})
        self.assertEqual(data[pos], 0xF6)
        b.set_stockpile({"fuel": False, "resources": False})
        self.assertEqual(data[pos], 0xF0)

    def test_stockpile_validation(self):
        pos = 506 * bases.RECORD_SIZE + bases.STOCKPILE_OFFSET
        data = self.sf[bases.LOCATION_SECTION].data
        b = self.by_id[506]
        for flags in [{"nope": True}, {"supply": 1}, {"supply": True, "oil": "yes"},
                      {"supply": True, "nope": False}]:
            with self.assertRaises(ValueError, msg=flags):
                b.set_stockpile(flags)
            self.assertEqual(data[pos], 0, flags)

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

    def test_list_places_includes_bases_and_towns(self):
        places = {p.id: p for p in bases.list_places(self.sf)}
        self.assertEqual(len(bases.list_bases(self.sf)), 781)
        self.assertTrue(set(self.by_id) <= set(places))
        self.assertEqual(places[584], bases.Place(584, "Pearl Harbor", 1, 180, 107))
        self.assertEqual((places[581].name, places[581].x, places[581].y), ("Midway Island", 158, 91))
        self.assertEqual(places[1091].name, "Chungking")
        self.assertNotIn(1091, self.by_id)
        self.assertGreater(len(places), len(self.by_id))
        self.assertTrue(bases.is_place(self.sf, 1091))
        self.assertFalse(bases.is_place(self.sf, 5560))
        self.assertFalse(bases.is_place(self.sf, bases.RECORD_COUNT))

    def test_include_towns(self):
        self.assertEqual(len(bases.list_bases(self.sf)), 781)
        everything = bases.list_bases(self.sf, include_towns=True)
        self.assertEqual(len(everything), 781 + 271)
        ids = [b.id for b in everything]
        self.assertEqual(ids, sorted(ids))
        towns = [b for b in everything if b.id not in self.by_id]
        self.assertEqual(len(towns), 271)
        self.assertTrue(all(b.kind == "Town" for b in towns))
        self.assertTrue(all(b.kind == "Base" for b in self.by_id.values()))

    def town(self, sf=None):
        sf = sf or self.sf
        return {b.id: b for b in bases.list_bases(sf, include_towns=True)}[696]

    def test_town_edit_roundtrip(self):
        t = self.town()
        self.assertEqual((t.name, t.kind, t.get("supply_cap")), ("Bassein", "Town", 500))
        t.set_many({"supply_cap": 700, "supply": 1234, "airfield": 3})
        again = self.town(self.roundtrip())
        self.assertEqual((again.get("supply_cap"), again.get("supply"), again.get("airfield")), (700, 1234, 3))

    def test_town_port_is_read_only(self):
        t = self.town()
        before = bytes(self.sf[bases.LOCATION_SECTION].data)
        for name in bases.TOWN_READONLY_FIELDS:
            with self.assertRaises(ValueError):
                t.set(name, 1)
            with self.assertRaises(ValueError):
                t.set_many({"supply": 5, name: 1})
        for flags in ({"port": True}, {"port": False}, {"airfield": False, "port": True}):
            with self.assertRaises(ValueError):
                t.set_building(flags)
        self.assertEqual(bytes(self.sf[bases.LOCATION_SECTION].data), before)

    def test_base_still_accepts_port_edits(self):
        b = self.by_id[584]
        b.set_many({"port": 3, "port_max": 4, "port_damage": 5})
        b.set_building({"port": False})
        self.assertEqual((b.get("port"), b.get("port_max"), b.get("port_damage")), (3, 4, 5))
        self.assertFalse(b.get_building()["port"])


if __name__ == "__main__":
    unittest.main()
