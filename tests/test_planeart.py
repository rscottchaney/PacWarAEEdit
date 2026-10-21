import os
import struct
import tempfile
import unittest
from unittest import mock

from witpae import planeart

ART = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "ART")
REAL = os.path.join(ART, "J_PlaneSide.bmp")

W, H = 6, 4  # 18 data bytes per row, padded to 20


def pixel(x, y):
    return (x * 10 + 1, y * 10 + 2, 3)


def make_bmp(path, width=W, height=H, bpp=24, compression=0, signature=b"BM"):
    stride = (width * 3 + 3) // 4 * 4
    rows = []
    for y in range(height - 1, -1, -1):  # bottom-up
        row = b"".join(bytes(reversed(pixel(x, y))) for x in range(width))  # BGR
        rows.append(row + b"\xAA" * (stride - len(row)))
    body = b"".join(rows)
    head = signature + struct.pack("<IHHI", 54 + len(body), 0, 0, 54)
    head += struct.pack("<IiiHHIIiiII", 40, width, height, 1, bpp, compression, len(body), 0, 0, 0, 0)
    with open(path, "wb") as f:
        f.write(head + body)


class SyntheticSheetTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "J_PlaneSide.bmp")
        make_bmp(self.path)
        # 2 x 2 tiles, 3 per row: the 6 x 4 sheet holds 6 tiles.
        for name, value in (("TILE_W", 2), ("TILE_H", 2), ("TILES_PER_ROW", 3)):
            patcher = mock.patch.object(planeart, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        planeart._cache.clear()
        self.addCleanup(planeart._cache.clear)

    def test_tile_is_cut_from_the_right_place_as_rgb(self):
        for n in range(6):
            x0, y0 = (n % 3) * 2, (n // 3) * 2
            rows = planeart.read_tile(self.path, n)
            expected = [b"".join(bytes(pixel(x, y)) for x in range(x0, x0 + 2)) for y in range(y0, y0 + 2)]
            self.assertEqual(rows, expected, n)

    def test_tiles_outside_the_sheet(self):
        for n in (-1, 6, 100):
            with self.assertRaises(ValueError, msg=n):
                planeart.read_tile(self.path, n)

    def test_sheet_size(self):
        self.assertEqual(planeart.sheet_size(self.path), (W, H))

    def test_png_is_valid(self):
        data = planeart.tile_png(self.path, 4)
        self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
        length, kind, width, height, depth, color = struct.unpack(">I4sIIBB", data[8:26])
        self.assertEqual((length, kind, width, height, depth, color), (13, b"IHDR", 2, 2, 8, 2))
        self.assertTrue(data.endswith(b"IEND\xaeB`\x82"))
        self.assertIs(planeart.tile_png(self.path, 4), data)  # cached

    def test_png_pixels_round_trip(self):
        import zlib
        data = planeart.tile_png(self.path, 1)
        pos, idat = 8, b""
        while pos < len(data):
            size, kind = struct.unpack(">I4s", data[pos:pos + 8])
            if kind == b"IDAT":
                idat += data[pos + 8:pos + 8 + size]
            pos += 12 + size
        raw = zlib.decompress(idat)
        rows = [raw[i * 7 + 1:(i + 1) * 7] for i in range(2)]
        self.assertEqual(rows, planeart.read_tile(self.path, 1))
        self.assertTrue(all(raw[i * 7] == 0 for i in range(2)))

    def test_bad_headers(self):
        for kwargs in ({"signature": b"XX"}, {"bpp": 8}, {"bpp": 32}, {"compression": 1}):
            bad = os.path.join(self.tmp.name, "bad.bmp")
            make_bmp(bad, **kwargs)
            with self.assertRaises(ValueError, msg=kwargs):
                planeart.read_tile(bad, 0)
        short = os.path.join(self.tmp.name, "short.bmp")
        with open(short, "wb") as f:
            f.write(b"BM")
        with self.assertRaises(ValueError):
            planeart.read_tile(short, 0)

    def test_truncated_file(self):
        with open(self.path, "r+b") as f:
            f.truncate(60)
        with self.assertRaises(ValueError):
            planeart.read_tile(self.path, 0)

    def test_art_folder_search_order(self):
        first = os.path.join(self.tmp.name, "first")
        second = os.path.join(self.tmp.name, "second")
        os.makedirs(first)
        os.makedirs(second)
        missing = os.path.join(self.tmp.name, "missing")
        self.assertIsNone(planeart.find_sheet([first, second, missing], 0))
        with self.assertRaises(ValueError):
            planeart.plane_png([first, second], 0, 0)
        make_bmp(os.path.join(second, "J_PlaneSide.bmp"))
        self.assertEqual(planeart.find_sheet([missing, first, second], 0), os.path.join(second, "J_PlaneSide.bmp"))
        make_bmp(os.path.join(first, "J_PlaneSide.bmp"))
        self.assertEqual(planeart.find_sheet([first, second], 0), os.path.join(first, "J_PlaneSide.bmp"))
        self.assertIsNone(planeart.find_sheet([first, second], 1))  # no Allied sheet
        self.assertIsNone(planeart.find_sheet([first], 7))
        self.assertTrue(planeart.plane_png([first], 0, 2).startswith(b"\x89PNG"))


@unittest.skipUnless(os.path.exists(REAL), "game ART folder missing")
class RealArtTests(unittest.TestCase):
    def test_sheet_sizes(self):
        self.assertEqual(planeart.sheet_size(REAL), (600, 3900))
        self.assertEqual(planeart.sheet_size(os.path.join(ART, "A_PlaneSide.bmp")), (600, 7504))

    def test_tiles_of_known_models_can_be_read(self):
        # (side, bitmap): A6M2 Zero, Ki-21-Ic Sally, P-38G, F6F-5, A-29A Hudson
        for side, bitmap in ((0, 4), (0, 147), (1, 333), (1, 439), (1, 1)):
            path = planeart.find_sheet([ART], side)
            rows = planeart.read_tile(path, bitmap)
            self.assertEqual((len(rows), len(rows[0])), (60, 450), (side, bitmap))
            png = planeart.plane_png([ART], side, bitmap)
            self.assertEqual(struct.unpack(">II", png[16:24]), (150, 60))

    def test_tile_past_the_end(self):
        with self.assertRaises(ValueError):
            planeart.read_tile(REAL, 3900 // 60 * 4)


if __name__ == "__main__":
    unittest.main()
