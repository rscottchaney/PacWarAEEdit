import os
import struct
import tempfile
import unittest

from witpae import pilotpool
from witpae.container import SaveFile, SaveFormatError

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
SAVE_015 = os.path.join(DATA_DIR, "going2_411210.pws")


@unittest.skipUnless(os.path.exists(SAVE_015), "sample save missing")
class PilotPoolTests(unittest.TestCase):
    def setUp(self):
        self.sf = SaveFile.load(SAVE_015)
        self.pools = {p.nation_id: p for p in pilotpool.list_pools(self.sf)}

    def roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "out.pws")
            self.sf.save(path)
            return SaveFile.load(path)

    def test_values_in_sample_save(self):
        self.assertEqual(sorted(self.pools), list(range(1, 19)))
        ija, usn = self.pools[1], self.pools[4]
        self.assertEqual((ija.label, ija.side, ija.get("pool"), ija.get("experience"), ija.get("rate")),
                         ("IJA", "Japanese", 2173, 35, 195))
        self.assertEqual(ija.counts, [204, 197, 202, 189, 179, 192, 191, 188, 188, 192, 183, 200])
        self.assertEqual(ija.experiences, [0, 4, 1, 11, 13, 14, 20, 21, 26, 25, 30, 33])
        self.assertEqual(ija.in_training, sum(ija.counts))
        self.assertEqual((usn.label, usn.side, usn.get("pool"), usn.get("experience"), usn.get("rate")),
                         ("USN", "Allied", 6770, 40, 600))
        self.assertEqual(usn.counts, [606, 558, 586, 614, 636, 582, 592, 587, 624, 595, 625, 618])
        self.assertEqual(usn.experiences, [0, 4, 9, 9, 11, 14, 23, 23, 25, 28, 34, 33])
        self.assertEqual((self.pools[18].label, self.pools[18].get("pool"), self.pools[18].get("rate")),
                         ("Canada", 230, 20))
        self.assertEqual((self.pools[6].label, self.pools[6].get("pool"), self.pools[6].get("rate")),
                         ("6", 1270, 115))
        self.assertEqual(self.pools[10].get("pool"), 0)
        self.assertFalse(usn.is_empty)

    def test_edit_roundtrip_changes_only_the_edited_bytes(self):
        old = bytes(SaveFile.load(SAVE_015)[pilotpool.SECTION].data)
        usn = self.pools[4]
        usn.set_many({"pool": 7000, "experience": 41, "rate": 650, "count3": 700, "exp11": 50})
        again = self.roundtrip()
        new = bytes(again[pilotpool.SECTION].data)
        usn = {p.nation_id: p for p in pilotpool.list_pools(again)}[4]
        self.assertEqual((usn.get("pool"), usn.get("experience"), usn.get("rate")), (7000, 41, 650))
        self.assertEqual((usn.counts[3], usn.experiences[11]), (700, 50))
        base = pilotpool.TRAINING_BASE + pilotpool.TRAINING_STRIDE * 3
        expected = bytearray(old)
        struct.pack_into("<h", expected, pilotpool.POOL_BASE + 6, 7000)
        struct.pack_into("<h", expected, pilotpool.EXPERIENCE_BASE + 64, 41)
        struct.pack_into("<h", expected, pilotpool.RATE_BASE + 64, 650)
        struct.pack_into("<h", expected, base + 6, 700)
        expected[base + pilotpool.TRAINING_EXPERIENCE_OFFSET + 11] = 50
        self.assertEqual(new, bytes(expected))

    def test_validation_writes_nothing(self):
        before = bytes(self.sf[pilotpool.SECTION].data)
        usn = self.pools[4]
        bad = [("pool", -1), ("pool", 32768), ("experience", 100), ("rate", True), ("count0", "5"),
               ("exp0", -1), ("exp5", 100), ("count11", 1.5), ("count12", 1), ("nope", 1)]
        for name, value in bad:
            with self.assertRaises(ValueError, msg=(name, value)):
                usn.set(name, value)
        with self.assertRaises(ValueError):
            usn.set_many({"pool": 10, "rate": -5})
        self.assertEqual(bytes(self.sf[pilotpool.SECTION].data), before)

    def test_missing_or_short_section_raises(self):
        short = bytes(self.sf[pilotpool.SECTION].data)
        del self.sf[pilotpool.SECTION].data[pilotpool.SECTION_END - 1:]
        with self.assertRaises(SaveFormatError):
            pilotpool.list_pools(self.sf)
        self.sf[pilotpool.SECTION].data[:] = short
        self.assertEqual(len(pilotpool.list_pools(self.sf)), 18)
        self.sf._by_id.pop(pilotpool.SECTION)
        with self.assertRaises(SaveFormatError):
            pilotpool.list_pools(self.sf)


if __name__ == "__main__":
    unittest.main()
