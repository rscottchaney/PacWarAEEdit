import os
import tempfile
import unittest

from witpae import regions


class RegionFileTests(unittest.TestCase):
    def write(self, text):
        fd, path = tempfile.mkstemp(suffix=".txt")
        self.addCleanup(os.remove, path)
        with os.fdopen(fd, "wb") as fh:
            fh.write(text.encode("latin-1"))
        return path

    def test_bundled_file(self):
        rm = regions.load_regions()
        self.assertEqual(len(rm), 1153)
        # Ids run to 65 but the file only uses 62 of them.
        self.assertEqual(len(rm.regions()), 62)
        self.assertEqual(rm.regions()[0], (1, "Japan"))
        self.assertEqual(rm.regions()[-1], (65, "Africa"))
        self.assertEqual(rm.region_of(506), (17, "Continental US"))
        self.assertIs(regions.default_regions(), regions.default_regions())

    def test_repeated_region_name_kept_by_id(self):
        found = regions.load_regions().regions()
        self.assertEqual([i for i, name in found if name == "Line Islands"], [20, 36])

    def test_unknown_location_is_unassigned(self):
        rm = regions.load_regions()
        self.assertEqual(rm.region_of(1601), regions.UNASSIGNED)  # Truscott is not in the file
        self.assertEqual(regions.UNASSIGNED[1], "Unassigned")

    def test_line_endings(self):
        lines = ["1\tAlpha\t7\tNorth", "", "2\tBeta\t8\tSouth"]
        results = []
        for sep in ("\r", "\n", "\r\n"):
            rm = regions.load_regions(self.write(sep.join(lines) + sep))
            results.append((len(rm), rm.region_of(1), rm.region_of(2), rm.regions()))
        self.assertEqual(results[0], (2, (7, "North"), (8, "South"), [(7, "North"), (8, "South")]))
        self.assertEqual(results[0], results[1])
        self.assertEqual(results[0], results[2])

    def test_malformed_lines_name_the_line_number(self):
        for text, number in (("1\tA\t7\tN\r2\tB\t8\r", 2), ("1\tA\t7\tN\rx\tB\t8\tS\r", 2),
                             ("1\tA\t7\tN\r\r2\tB\tq\tS\r", 3), ("1\tA\t7\tN\t9\r", 1)):
            with self.assertRaises(ValueError) as ctx:
                regions.load_regions(self.write(text))
            self.assertIn(f"line {number}", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
