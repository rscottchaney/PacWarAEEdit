import os
import struct
import tempfile
import unittest

from witpae import airgroups, bases, combat, landunits, mapview
from witpae.container import SaveFile

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
SAVE_015 = os.path.join(DATA_DIR, "going2_411210.pws")
PEARL = 584
DASHES = "-" * 80

# Tiny stand-ins for the real art: the same 7 x 6 layout with odd sizes, so a wrong offset or a row padded to 4 bytes
# shows up. Column 6 is narrower and row 5 shorter, as in the real art.
WIDTHS = [5, 5, 5, 5, 5, 5, 3]
HEIGHTS = [4, 4, 4, 4, 4, 2]


def pixel(gx, gy):
    return (gx * 7 % 256, gy * 13 % 256, (gx + gy) % 256)


def bmp(width, height, colour_at, bpp=24, truncate=0):
    stride = (width * 3 + 3) // 4 * 4
    rows = []
    for gy in range(height - 1, -1, -1):  # bottom-up
        row = b"".join(bytes(reversed(colour_at(gx, gy))) for gx in range(width))  # BGR
        rows.append(row + bytes(stride - len(row)))
    body = b"".join(rows)
    head = b"BM" + struct.pack("<IHHI", 54 + len(body), 0, 0, 54)
    head += struct.pack("<IiiHHIIiiII", 40, width, height, 1, bpp, 0, len(body), 0, 0, 0, 0)
    return head + body[:len(body) - truncate]


def write_art(folder, prefix="WPEH", **bad):
    """The 42 synthetic tiles of one style; bad maps a tile number to bmp() arguments to damage that tile."""
    x0s = [sum(WIDTHS[:c]) for c in range(7)]
    y0s = [sum(HEIGHTS[:r]) for r in range(6)]
    for n in range(42):
        col, row = n % 7, n // 7
        width, height = WIDTHS[col], HEIGHTS[row]
        kwargs = bad.get(f"t{n}", {})
        width, height = kwargs.pop("size", (width, height))
        with open(os.path.join(folder, f"{prefix}{n:02d}.bmp"), "wb") as f:
            f.write(bmp(width, height, lambda gx, gy: pixel(x0s[col] + gx, y0s[row] + gy), **kwargs))


def read_ppm(data):
    magic, size, depth, body = data.split(b"\n", 3)
    width, height = map(int, size.split())
    assert magic == b"P6" and depth == b"255" and len(body) == width * height * 3
    return width, height, body


class HexTests(unittest.TestCase):
    def test_known_points(self):
        # Pearl Harbor (180,107) lands on Oahu; odd rows are shifted half a hex to the right.
        self.assertEqual(mapview.hex_to_pixel(180, 107), (7575, 4048))
        self.assertEqual(mapview.hex_to_pixel(180, 106), (7554, 4010))
        self.assertEqual(mapview.hex_to_pixel(0, 0), (-6, -18))

    def test_round_trip(self):
        for y in range(0, 205):
            for x in range(0, 232, 7):
                self.assertEqual(mapview.pixel_to_hex(*mapview.hex_to_pixel(x, y)), (x, y))

    def test_pixel_near_centre(self):
        px, py = mapview.hex_to_pixel(77, 61)
        for dx, dy in ((-9, 0), (9, 0), (0, -8), (0, 8), (5, 5)):
            self.assertEqual(mapview.pixel_to_hex(px + dx, py + dy), (77, 61))

    def test_compass_to_tk(self):
        self.assertEqual(mapview.compass_to_tk(0, 90), (0, 90))  # north to east: Tk's 90 down to 0
        self.assertEqual(mapview.compass_to_tk(350, 10), (80, 20))
        self.assertEqual(mapview.compass_to_tk(180, 300), (150, 120))
        self.assertEqual(mapview.compass_to_tk(0, 0), (90, 360))  # callers draw an equal start and end as a circle


class ArtTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.folder = tmp.name

    def test_find_art(self):
        empty = os.path.join(self.folder, "empty")
        os.mkdir(empty)
        write_art(self.folder, "WPEH")
        self.assertEqual(mapview.find_art([None, empty, self.folder], "Hexes"), self.folder)
        self.assertIsNone(mapview.find_art([empty, self.folder], "No hexes"))
        os.remove(os.path.join(self.folder, "WPEH41.bmp"))
        self.assertIsNone(mapview.find_art([self.folder], "Hexes"))

    def test_map_size_reads_the_headers(self):
        write_art(self.folder)
        self.assertEqual(mapview.map_size(self.folder, "Hexes"), (sum(WIDTHS), sum(HEIGHTS)))

    def test_render_matches_the_source_pixels(self):
        write_art(self.folder)
        full_w, full_h = sum(WIDTHS), sum(HEIGHTS)
        for step in (1, 2, 3, 7):
            width, height, ppm = mapview.render(self.folder, "Hexes", step)
            self.assertEqual((width, height), (-(-full_w // step), -(-full_h // step)))
            _w, _h, body = read_ppm(ppm)
            for oy in range(height):
                for ox in range(width):
                    pos = (oy * width + ox) * 3
                    self.assertEqual(tuple(body[pos:pos + 3]), pixel(ox * step, oy * step), (step, ox, oy))

    def test_render_styles_are_separate(self):
        write_art(self.folder, "WPEN")
        with self.assertRaises(ValueError):
            mapview.render(self.folder, "Hexes", 2)
        self.assertEqual(mapview.render(self.folder, "No hexes", 2)[:2], (-(-sum(WIDTHS) // 2), -(-sum(HEIGHTS) // 2)))

    def test_bad_arguments(self):
        write_art(self.folder)
        for step in (0, -2, 1.5, True):
            with self.assertRaises(ValueError):
                mapview.render(self.folder, "Hexes", step)
        with self.assertRaises(ValueError):
            mapview.render(self.folder, "Sepia", 2)

    def test_bad_tiles(self):
        cases = {
            "not 24-bit": {"t3": {"bpp": 8}},
            "truncated": {"t10": {"truncate": 9}},
            "wrong size": {"t20": {"size": (6, 4)}},
        }
        for label, bad in cases.items():
            with self.subTest(label):
                write_art(self.folder, **bad)
                with self.assertRaises(ValueError):
                    mapview.render(self.folder, "Hexes", 2)
        write_art(self.folder)
        with open(os.path.join(self.folder, "WPEH05.bmp"), "wb") as f:
            f.write(b"not a bitmap")
        with self.assertRaisesRegex(ValueError, "WPEH05"):
            mapview.render(self.folder, "Hexes", 2)
        os.remove(os.path.join(self.folder, "WPEH05.bmp"))
        with self.assertRaisesRegex(ValueError, "WPEH05"):
            mapview.render(self.folder, "Hexes", 2)


@unittest.skipUnless(os.path.exists(SAVE_015), "sample save missing")
class OverlayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.save = SaveFile.load(SAVE_015)

    def test_locations(self):
        marks = mapview.location_marks(self.save)
        pearl = next(m for m in marks if m.id == PEARL)
        self.assertEqual((pearl.name, pearl.side, pearl.x, pearl.y, pearl.kind), ("Pearl Harbor", "Allied", 180, 107, "Base"))
        self.assertEqual(mapview.hex_to_pixel(pearl.x, pearl.y), (7575, 4048))
        self.assertTrue(all(m.kind == "Base" for m in marks))
        with_towns = mapview.location_marks(self.save, include_towns=True)
        self.assertGreater(len(with_towns), len(marks))
        self.assertEqual({m.kind for m in with_towns}, {"Base", "Town"})
        allied = mapview.location_marks(self.save, side="Allied")
        japanese = mapview.location_marks(self.save, side="Japanese")
        self.assertEqual({m.side for m in allied}, {"Allied"})
        self.assertEqual({m.side for m in japanese}, {"Japanese"})
        self.assertGreaterEqual(len(allied) + len(japanese), 1)

    def test_location_region_filter(self):
        from witpae import regions
        region_id, _name = regions.default_regions().region_of(PEARL)
        marks = mapview.location_marks(self.save, include_towns=True, region=region_id)
        self.assertIn(PEARL, [m.id for m in marks])
        self.assertTrue(all(regions.default_regions().region_of(m.id)[0] == region_id for m in marks))
        self.assertLess(len(marks), len(mapview.location_marks(self.save, include_towns=True)))

    def test_search_arcs(self):
        naval = mapview.search_arcs(self.save, "Naval")
        asw = mapview.search_arcs(self.save, "ASW")
        self.assertGreater(len(naval), 0)
        self.assertGreater(len(asw), 0)
        self.assertTrue(all(a.radius > 0 and a.kind == "Naval" for a in naval))
        defined = mapview.search_arcs(self.save, "Naval", "Defined")
        random = mapview.search_arcs(self.save, "Naval", "Random")
        self.assertGreater(len(defined), 0)
        self.assertEqual(len(defined) + len(random), len(naval))
        self.assertTrue(all(not a.full and a.start != a.end for a in defined))
        self.assertTrue(all(a.full and a.start == a.end for a in random))
        # The groups on Oahu search from Pearl Harbor's hex, limited by range and the aircraft's radius.
        oahu = [a for a in naval if (a.x, a.y) == (180, 107)]
        self.assertTrue(oahu)
        by_id = {g.id: g for g in airgroups.list_airgroups(self.save)}
        for a in oahu:
            self.assertGreater(by_id[a.group_id].get("search"), 0)
        self.assertEqual({a.side for a in mapview.search_arcs(self.save, "Naval", side="Japanese")}, {"Japanese"})
        with self.assertRaises(ValueError):
            mapview.search_arcs(self.save, "Naval", "Sometimes")

    def test_search_arc_radius_rule(self):
        by_id = {g.id: g for g in airgroups.list_airgroups(self.save)}
        arc = next(a for a in mapview.search_arcs(self.save, "Naval") if by_id[a.group_id].get("range"))
        group = by_id[arc.group_id]
        from witpae import aircraft
        normal = aircraft.Aircraft(self.save, group.aircraft_id, "").get("normal_radius_hex")
        self.assertEqual(arc.radius, min(group.get("range"), normal))
        setting = group.get("range")
        group.set("range", 0)  # in memory only; a range setting of 0 means the aircraft's normal radius
        try:
            again = next(a for a in mapview.search_arcs(self.save, "Naval") if a.group_id == arc.group_id)
        finally:
            group.set("range", setting)
        self.assertEqual(again.radius, normal)

    def test_groups_aboard_ships_use_the_task_force_hex(self):
        aboard = [g for g in airgroups.list_airgroups(self.save) if g.location_id >= airgroups.SHIP_LOCATION_BASE]
        placed = [(g, mapview.group_hex(self.save, g)) for g in aboard]
        self.assertTrue(any(pos is not None for _g, pos in placed))
        tf_hexes = {(t.x, t.y) for t in mapview.task_force_marks(self.save)}
        port_hexes = {(b.x, b.y) for b in mapview.location_marks(self.save, include_towns=True)}
        for _g, pos in placed:
            if pos is not None:
                self.assertIn(pos, tf_hexes | port_hexes)

    def test_task_forces(self):
        tfs = mapview.task_force_marks(self.save)
        self.assertGreater(len(tfs), 0)
        self.assertTrue(all(isinstance(t.x, int) and 0 <= t.x < 400 and 0 <= t.y < 300 for t in tfs))
        with_dest = [t for t in tfs if t.dest_x is not None]
        self.assertTrue(with_dest)
        for t in with_dest:
            self.assertEqual(bases.place_hex(self.save, t.dest_id), (t.dest_x, t.dest_y))
        self.assertTrue(all(t.dest_y is None for t in tfs if t.dest_x is None))
        self.assertEqual({t.side for t in mapview.task_force_marks(self.save, "Japanese")}, {"Japanese"})
        self.assertEqual(len(mapview.task_force_marks(self.save, "Allied"))
                         + len(mapview.task_force_marks(self.save, "Japanese")), len(tfs))

    def test_combat_marks_and_hex_index(self):
        report = [
            "AFTER ACTION REPORTS FOR Dec 10, 41", DASHES,
            "Morning Air attack on TF, near Legaspi at 82,82", " ", "Weather in hex: Clear sky", " ",
            DASHES, "ASW attack near Pearl Harbor at 180,107", " ", "Weather in hex: Clear sky", " ",
            DASHES, "Ground combat at Nowhere", " ", "Weather in hex: Clear sky", " "]
        actions = combat.parse_report(411210, report)
        self.assertEqual(len(actions), 3)
        self.assertEqual([a.x for a in actions], [82, 180, None])
        marks = mapview.combat_marks(actions)
        self.assertEqual([(m.x, m.y) for m in marks], [(82, 82), (180, 107)])  # the one without a hex is skipped
        self.assertEqual([m.kind for m in mapview.combat_marks(actions, "ASW")], ["ASW"])
        self.assertEqual(mapview.combat_marks(actions, "Submarine"), [])
        self.assertEqual(len(mapview.combat_marks(actions, "All")), 2)
        index = mapview.hex_index(self.save, actions)
        here = index[(180, 107)]
        self.assertIn("Pearl Harbor", [m.name for m in here["Places"]])
        self.assertEqual([m.kind for m in here["Combat"]], ["ASW"])
        self.assertTrue(here["Air groups searching"])
        self.assertTrue(set(here) <= set(mapview.INDEX_CATEGORIES))
        self.assertIn("Land units", here)
        self.assertIn("Support", here)
        self.assertEqual(mapview.INDEX_CATEGORIES[:4], ("Places", "Land units", "Support", "Task forces"))
        self.assertEqual({m.side for m in here["Support"]}, {"Allied"})

    def test_support_bar(self):
        self.assertEqual(mapview.support_bar(0), 0)
        self.assertAlmostEqual(mapview.support_bar(15), 0.2554, places=3)  # 1/4 hex
        self.assertAlmostEqual(mapview.support_bar(60), 0.5108, places=3)  # 1/2 hex
        self.assertAlmostEqual(mapview.support_bar(230), 1.0)
        self.assertAlmostEqual(mapview.support_bar(500), 1.4745, places=3)  # about 1.5 hexes
        self.assertEqual(mapview.support_bar(10000), 1.5)
        self.assertEqual(mapview.support_bar(-230), mapview.support_bar(230))
        self.assertEqual(mapview.support_bar(-10000), 1.5)

    def test_unit_support(self):
        units = mapview.unit_support(self.save)
        self.assertTrue(units)
        self.assertTrue(all((u.x, u.y) != (0, 0) for u in units))
        arrived = {u.id for u in landunits.list_land_units(self.save) if u.arrived}
        self.assertLessEqual({u.id for u in units}, arrived)
        self.assertEqual(len(units), 1939)  # of 2202 arrived units, 263 are at (0,0)
        for side in ("Allied", "Japanese"):
            self.assertEqual({u.side for u in mapview.unit_support(self.save, side)}, {side})
        by_side = [mapview.unit_support(self.save, side) for side in ("Allied", "Japanese")]
        self.assertEqual(sum(map(len, by_side)), len(units))
        # A field unit at location 0 still counts, in the hex of its own record.
        div = next(u for u in units if u.name == "37th Div" and u.side == "Japanese")
        self.assertEqual((div.x, div.y, div.support, div.needed), (90, 40, 375, 500))
        record = next(u for u in landunits.list_land_units(self.save) if u.id == div.id)
        self.assertEqual(record.location_id, 0)

    def test_support_marks(self):
        marks = mapview.support_marks(self.save)
        self.assertEqual(len(marks), 664)
        self.assertEqual(sum(m.support < m.needed for m in marks), 359)
        by_key = {(m.side, m.x, m.y): m for m in marks}
        pearl = by_key[("Allied", 180, 107)]
        self.assertEqual((pearl.support, pearl.needed, len(pearl.units)), (1985, 1532, 21))
        japan = by_key[("Japanese", 92, 40)]
        self.assertEqual((japan.support, japan.needed, len(japan.units)), (1864, 2438, 11))
        self.assertEqual(marks, sorted(marks, key=lambda m: (m.x, m.y, m.side)))
        self.assertTrue(all(m.support or m.needed for m in marks))
        for m in marks:
            self.assertEqual((m.support, m.needed), (sum(u.support for u in m.units), sum(u.needed for u in m.units)))
        allied = mapview.support_marks(self.save, "Allied")
        self.assertTrue(allied)
        self.assertEqual({m.side for m in allied}, {"Allied"})
        self.assertEqual({m.side for m in mapview.support_marks(self.save, "Japanese")}, {"Japanese"})


if __name__ == "__main__":
    unittest.main()
