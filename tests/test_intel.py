import os
import tempfile
import unittest

from witpae import history, intel
from witpae.container import SaveFile

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
SAVE_015 = os.path.join(DATA_DIR, "going2_411210.pws")

SIGINT = [
    "SIG INT REPORT FOR Dec 10, 41",
    "",
    "Radio transmissions detected at Matsue (107,57).",
    "Radio transmissions detected at 70,75.",
    "Heavy Volume of Radio transmissions detected at 89,96.",
    "9th Tank Regiment is located at Yenki(110,44).",
    "3rd Ind.AA Gun Co  is located at Nagaoka(114,58).",
    "2/54th Division is loaded on a Japanese CM moving to Bangkok.",
    "2/56th Engineer Regiment is loaded on a Aden Cargo class xAK moving to Patani.",
    "a To'su Cargo class xAKL is moving to Kota Bharu (51,75).",
    "4th Fleet is planning for an attack on Wake Island.",
    "1517 men are based at Toyama (112,57).",
    "12 aircraft are based at Hankow (85,50).",
    "Something the game may add one day.",
]
OPS = [
    "OPERATIONAL REPORT FOR Dec 10, 41",
    "",
    "Sighting report: 10 Japanese ships at 82,82 near Legaspi , Speed 9 , Moving West ",
    "Coastwatcher Report: 3 ships in port at Pakhoi",
    "Coastwatcher Report: harbor at Hong Kong is reported empty",
    "CA Houston snooped by Japanese Torpedo Bomber at 79,84 near Iloilo",
    "E7K2 Alf reports object near surface at 83, 69 near Itbayat Island",
    "C5M2 Babs sighted over Laoag",
    "Japanese Fighter Bomber sighted over 41st PA Infantry Division",
    "SS S-37 assigned to offensive patrol 88, 63 - 87, 66 off Ishigaki",
    "SS S-23 transfers to Pearl Harbor",
    "1LT Brown, B.S. of 35th PG/34th PS is credited with kill number 2",
    "LTJG Jordan O. of VJ-10 Det A is KILLED",
    "Search SOC-1 Seagull destroyed by CAP at (80,73)",
    "Beaufort V (PR) takes recon photos of Singora",
    "Nth Sentai at Takao takes Ki-43b Oscar replacements",
    "xAK Ewa arrives at Balboa",
    "Nth RGC Division - some devices have been upgraded at Wuhu",
    "Device(s) upgraded in 13th RAAF Base Force supplied from Cairns",
    "Takao expands fortifications to size 3",
    "Task Force 223 formed at Colombo for Auto Supply to Tacloban",
    "Task Force 141 has merged with TF 140 at 130 , 57",
    "Japanese forces CAPTURE Vigan !!!",
    "PT-5 is reported to have been sunk near Pearl Harbor on Dec 07, 41",
    "Zedong L. now available for reassignment",
]


def write(folder, name, lines, newline="\r\n", encoding="latin-1"):
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, name), "wb") as f:
        f.write(newline.join(lines).encode(encoding) + newline.encode())


def line_of(lines, kind, fragment):
    return next(l for l in lines if l.kind == kind and fragment in l.text)


class ParseTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.folder = tmp.name
        write(self.folder, "asigint_411210.txt", SIGINT)
        write(self.folder, "aoperationsreport_411210.txt", OPS)
        self.reports = intel.load_reports(self.folder)

    def test_sigint_kinds(self):
        lines = self.reports["sigint"]
        self.assertEqual(len(lines), len(SIGINT) - 2)
        kinds = {l.kind for l in lines}
        self.assertEqual(kinds, {"Radio", "Heavy radio", "Unit located", "Loaded on ship", "Moving",
                                 "Planning attack", "Troop count", "Aircraft count", "Other"})
        self.assertTrue(all(l.side == "Allied" and l.date == 411210 for l in lines))
        radio = line_of(lines, "Radio", "Matsue")
        self.assertEqual((radio.place, radio.x, radio.y, radio.unit), ("Matsue", 107, 57, ""))
        bare = line_of(lines, "Radio", "70,75")
        self.assertEqual((bare.place, bare.x, bare.y), ("", 70, 75))
        heavy = line_of(lines, "Heavy radio", "89,96")
        self.assertEqual((heavy.place, heavy.x, heavy.y), ("", 89, 96))
        unit = line_of(lines, "Unit located", "Yenki")
        self.assertEqual((unit.unit, unit.place, unit.x, unit.y), ("9th Tank Regiment", "Yenki", 110, 44))
        self.assertEqual(line_of(lines, "Unit located", "Nagaoka").unit, "3rd Ind.AA Gun Co")
        loaded = line_of(lines, "Loaded on ship", "Bangkok")
        self.assertEqual((loaded.unit, loaded.detail, loaded.place, loaded.x), ("2/54th Division", "a Japanese CM",
                                                                               "Bangkok", None))
        self.assertEqual(line_of(lines, "Loaded on ship", "Patani").detail, "a Aden Cargo class xAK")
        moving = line_of(lines, "Moving", "To'su")
        self.assertEqual((moving.unit, moving.place, moving.x, moving.y), ("To'su Cargo class xAKL", "Kota Bharu",
                                                                           51, 75))
        plan = line_of(lines, "Planning attack", "Wake")
        self.assertEqual((plan.unit, plan.place), ("4th Fleet", "Wake Island"))
        troops = line_of(lines, "Troop count", "Toyama")
        self.assertEqual((troops.detail, troops.place, troops.x, troops.y), ("1,517 men", "Toyama", 112, 57))
        self.assertEqual(line_of(lines, "Aircraft count", "Hankow").detail, "12 aircraft")
        other = line_of(lines, "Other", "game may add")
        self.assertEqual((other.place, other.x, other.unit, other.detail), ("", None, "", ""))
        self.assertEqual(other.text, "Something the game may add one day.")

    def test_operations_categories(self):
        lines = self.reports["ops"]
        self.assertEqual(len(lines), len(OPS) - 2)
        expected = {
            "Sighting report: 10": "Sighting", "Pakhoi": "Sighting", "Hong Kong is reported": "Sighting",
            "snooped": "Sighting", "object near surface": "Sighting", "sighted over Laoag": "Sighting",
            "41st PA": "Sighting", "S-37": "Submarine", "S-23": "Submarine", "credited": "Pilot",
            "KILLED": "Pilot", "destroyed by CAP": "Air", "recon photos": "Air", "replacements": "Air",
            "Balboa": "Arrival", "Wuhu": "Upgrade", "Cairns": "Upgrade", "fortifications": "Base",
            "formed at Colombo": "Task force", "merged": "Task force", "CAPTURE": "Capture", "sunk": "Ship",
            "Zedong": "Other"}
        for fragment, kind in expected.items():
            self.assertEqual(next(l for l in lines if fragment in l.text).kind, kind, fragment)
        self.assertEqual({l.kind for l in lines}, set(intel.OPS_KINDS))

    def test_operations_fields(self):
        lines = self.reports["ops"]
        sighting = next(l for l in lines if "Legaspi" in l.text)
        self.assertEqual((sighting.place, sighting.x, sighting.y), ("Legaspi", 82, 82))
        self.assertEqual(next(l for l in lines if "Hong Kong is" in l.text).place, "Hong Kong")
        wake = next(l for l in lines if "object near" in l.text)
        self.assertEqual((wake.place, wake.x, wake.y, wake.unit), ("Itbayat Island", 83, 69, "E7K2 Alf"))
        paren = next(l for l in lines if "destroyed by CAP" in l.text)
        self.assertEqual((paren.x, paren.y), (80, 73))
        merged = next(l for l in lines if "merged" in l.text)
        self.assertEqual((merged.x, merged.y), (130, 57))
        patrol = next(l for l in lines if "S-37" in l.text)
        self.assertEqual((patrol.unit, patrol.place, patrol.x, patrol.detail),
                         ("SS S-37", "Ishigaki", None, "offensive patrol 88, 63 - 87, 66"))
        self.assertEqual(next(l for l in lines if "Singora" in l.text).place, "Singora")
        arrives = next(l for l in lines if "Balboa" in l.text)
        self.assertEqual((arrives.unit, arrives.place), ("xAK Ewa", "Balboa"))
        repl = next(l for l in lines if "replacements" in l.text)
        self.assertEqual((repl.unit, repl.place, repl.detail), ("Nth Sentai", "Takao", "Ki-43b Oscar"))
        self.assertEqual(next(l for l in lines if "fortifications" in l.text).place, "Takao")
        self.assertEqual(next(l for l in lines if "sunk" in l.text).place, "Pearl Harbor")
        self.assertEqual(next(l for l in lines if "CAPTURE" in l.text).place, "Vigan")
        # A land unit is not a place.
        land = next(l for l in lines if "41st PA" in l.text)
        self.assertEqual((land.place, land.unit, land.detail),
                         ("", "Japanese Fighter Bomber", "over 41st PA Infantry Division"))

    def test_no_line_dropped(self):
        for key, source in (("sigint", SIGINT), ("ops", OPS)):
            self.assertEqual([l.text for l in self.reports[key]], [t.rstrip() for t in source[2:] if t])


class FileTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.folder = tmp.name

    def test_missing_folder_and_no_files(self):
        empty = {"sigint": [], "ops": []}
        self.assertEqual(intel.load_reports(os.path.join(self.folder, "nope")), empty)
        self.assertEqual(intel.load_reports(self.folder), empty)
        write(self.folder, "notes.txt", ["Radio transmissions detected at 1,2."])
        self.assertEqual(intel.load_reports(self.folder), empty)

    def test_header_date_and_file_name_fallback(self):
        self.assertEqual(intel.header_date("SIG INT REPORT FOR Dec 10, 41"), 411210)
        self.assertEqual(intel.header_date("OPERATIONAL REPORT FOR Mar 1, 1942"), 420301)
        self.assertIsNone(intel.header_date("Radio transmissions detected at 1,2."))
        self.assertIsNone(intel.header_date("REPORT FOR Foo 10, 41"))
        # The header wins over the file name; a file without a header uses the name and keeps its first line.
        write(self.folder, "asigint_411211.txt", ["SIG INT REPORT FOR Dec 10, 41", "Radio transmissions detected at 1,2."])
        write(self.folder, "jsigint_411212.txt", ["Radio transmissions detected at 3,4.", "Radio transmissions detected at 5,6."])
        lines = intel.load_reports(self.folder)["sigint"]
        self.assertEqual([(l.side, l.date, l.x) for l in lines], [("Allied", 411210, 1), ("Japanese", 411212, 3),
                                                                  ("Japanese", 411212, 5)])

    def test_undated_file_dedupe(self):
        radio = "Radio transmissions detected at {},{}."
        write(self.folder, "asigint_411209.txt", ["SIG INT REPORT FOR Dec 9, 41", radio.format(1, 1)])
        write(self.folder, "asigint_411210.txt", ["SIG INT REPORT FOR Dec 10, 41", radio.format(2, 2)])
        write(self.folder, "asigint.txt", ["SIG INT REPORT FOR Dec 10, 41", radio.format(2, 2)])
        write(self.folder, "jsigint.txt", ["SIG INT REPORT FOR Dec 11, 41", radio.format(3, 3)])
        write(self.folder, "aoperationsreport.txt", ["OPERATIONAL REPORT FOR Dec 11, 41", "X arrives at Y"])
        reports = intel.load_reports(self.folder)
        self.assertEqual([(l.side, l.date, l.x) for l in reports["sigint"]],
                         [("Allied", 411209, 1), ("Allied", 411210, 2), ("Japanese", 411211, 3)])
        self.assertEqual([(l.side, l.date) for l in reports["ops"]], [("Allied", 411211)])

    def test_line_endings_encoding_and_trailing_spaces(self):
        for newline in ("\r\n", "\n", "\r"):
            with self.subTest(newline=repr(newline)):
                folder = os.path.join(self.folder, f"nl{ord(newline[0])}{len(newline)}")
                write(folder, "jsigint_411210.txt", ["SIG INT REPORT FOR Dec 10, 41", "", "Radio transmissions detected at 1,2.  ",
                                                      "Oboe Mar\xfa is located at Bikin (3,4)."], newline)
                lines = intel.load_reports(folder)["sigint"]
                self.assertEqual([l.text for l in lines], ["Radio transmissions detected at 1,2.",
                                                           "Oboe Mar\xfa is located at Bikin (3,4)."])
                self.assertEqual(lines[1].unit, "Oboe Mar\xfa")

    def test_autosave_uses_parent_folder(self):
        auto = os.path.join(self.folder, "autosave")
        os.makedirs(auto)
        self.assertEqual(intel.intel_folder(os.path.join(auto, "w.pws")), os.path.abspath(self.folder))
        self.assertEqual(intel.intel_folder(os.path.join(self.folder, "w.pws")), os.path.abspath(self.folder))
        self.assertEqual(intel.intel_folder(os.path.join(auto, "w.pws")),
                         history.save_folder(os.path.join(auto, "w.pws")))

    def test_files_are_not_written(self):
        write(self.folder, "asigint_411210.txt", SIGINT)
        path = os.path.join(self.folder, "asigint_411210.txt")

        def state():
            with open(path, "rb") as f:
                return f.read(), os.stat(path).st_mtime_ns

        before = state()
        intel.load_reports(self.folder)
        self.assertEqual(state(), before)
        self.assertEqual(os.listdir(self.folder), ["asigint_411210.txt"])


def make_line(date, kind, place="", x=None, y=None, unit="", side="Allied"):
    return intel.IntelLine(date, side, kind, place, x, y, unit, "", f"{kind} {place} {unit}")


class TurnsTests(unittest.TestCase):
    def test_recent(self):
        lines = [make_line(d, "Radio") for d in (411207, 411208, 411208, 411209, 411210)]
        self.assertEqual(len(intel.recent(lines, 1)), 1)
        self.assertEqual({l.date for l in intel.recent(lines, 3)}, {411208, 411209, 411210})
        self.assertEqual(len(intel.recent(lines, 3)), 4)
        self.assertEqual(len(intel.recent(lines, 7)), 5)
        self.assertEqual(len(intel.recent(lines, None)), 5)
        self.assertEqual(intel.recent([], 1), [])
        self.assertEqual(list(intel.TURN_CHOICES), ["Latest", "Last 3", "Last 7", "All"])


class ByPlaceTests(unittest.TestCase):
    def test_aggregation_without_a_save(self):
        lines = [
            make_line(411208, "Radio", "Patani", 51, 73),
            make_line(411209, "Heavy radio", "", 51, 73),
            make_line(411210, "Unit located", "Patani", 51, 73, "42nd Infantry Regiment"),
            make_line(411210, "Unit located", "Patani", 51, 73, "1/148th Infantry Regiment"),
            make_line(411210, "Planning attack", "Patani", None, None, "4th Fleet"),  # borrows the hex of the name
            make_line(411210, "Radio", "", 70, 75),
            make_line(411210, "Other"),  # no place: not grouped
        ]
        rows = intel.by_place(lines)
        self.assertEqual([r.total for r in rows], [5, 1])
        patani = rows[0]
        self.assertEqual((patani.place, patani.x, patani.y, patani.place_id), ("Patani", 51, 73, None))
        self.assertEqual(patani.counts, {"Radio": 1, "Heavy radio": 1, "Unit located": 2, "Planning attack": 1})
        self.assertEqual((patani.first, patani.last), (411208, 411210))
        self.assertEqual(patani.units, "1/148th Infantry Regiment, 42nd Infantry Regiment, 4th Fleet")
        bare = rows[1]
        self.assertEqual((bare.place, bare.x, bare.y), ("", 70, 75))

    def test_units_truncated(self):
        lines = [make_line(411210, "Unit located", "Patani", 51, 73, f"{n}th Division") for n in range(1, 8)]
        row = intel.by_place(lines)[0]
        self.assertTrue(row.units.endswith("(+3 more)"))
        self.assertEqual(row.units.count(","), intel.USED_BY_NAMES - 1)
        self.assertEqual(row.total, 7)


@unittest.skipUnless(os.path.exists(SAVE_015), "sample save missing")
class PlaceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.save = SaveFile.load(SAVE_015)
        cls.index = intel.PlaceIndex(cls.save)

    def test_resolution_by_hex_and_name(self):
        pearl = self.index.find(180, 107, "")
        self.assertEqual(self.index.name(pearl), "Pearl Harbor")
        self.assertEqual(self.index.hex(pearl), (180, 107))
        self.assertEqual(self.index.find(None, None, "PEARL harbor"), pearl)
        # The hex wins over a wrong name; an unknown hex falls back to the name.
        self.assertEqual(self.index.find(180, 107, "Nowhere"), pearl)
        self.assertEqual(self.index.find(1, 1, "Pearl Harbor"), pearl)
        self.assertIsNone(self.index.find(1, 1, "Nowhere"))
        self.assertIsNone(self.index.find(None, None, ""))
        self.assertIsNone(self.index.find(None, None, "Pearl"))  # exact names only

    def test_resolve_lines_and_by_place(self):
        pearl = self.index.find(180, 107, "")
        lines = [make_line(411210, "Radio", "", 180, 107),
                 make_line(411210, "Planning attack", "Pearl Harbor", None, None, "4th Fleet"),
                 make_line(411210, "Radio", "Nowhere", 1, 1)]
        rows = intel.resolve_lines(lines, self.index)
        self.assertEqual([(r.place_id, r.place) for r in rows], [(pearl, "Pearl Harbor"), (pearl, "Pearl Harbor"),
                                                                 (None, "Nowhere")])
        self.assertEqual([r.place_id for r in intel.resolve_lines(lines)], [None, None, None])
        grouped = intel.by_place(lines, self.index)
        self.assertEqual([(r.place, r.place_id, r.total, r.x, r.y) for r in grouped],
                         [("Pearl Harbor", pearl, 2, 180, 107), ("Nowhere", None, 1, 1, 1)])


if __name__ == "__main__":
    unittest.main()
