import os
import struct
import unittest

from witpae import airgroups, factories, losses, shiprecords
from witpae.container import SaveFile

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
SAVE_015 = os.path.join(DATA_DIR, "going2_411210.pws")


class Section:
    def __init__(self, data):
        self.data = data


def fake_devices(devices):
    """A save holding only a device table: {id: name}."""
    data = bytearray(factories.DEVICE_RECORD_SIZE * (max(devices) + 1))
    for device_id, name in devices.items():
        start = device_id * factories.DEVICE_RECORD_SIZE
        data[start:start + len(name)] = name.encode("latin-1")
    return {factories.DEVICE_SECTION: Section(data)}


class CauseTests(unittest.TestCase):
    def setUp(self):
        self.save = fake_devices({101: "18in Type 91 Torpedo", 209: "800 kg AP Bomb"})

    def test_device_causes(self):
        self.assertEqual(losses.cause_text(self.save, 101), "18in Type 91 Torpedo")
        self.assertEqual(losses.cause_text(self.save, 209), "800 kg AP Bomb")

    def test_other_causes(self):
        self.assertEqual(losses.cause_text(self.save, 2000), "Destroyed while building")
        self.assertEqual(losses.cause_text(self.save, 2005), "Foundered")
        self.assertEqual(losses.cause_text(self.save, 2010), "Hit obstruction")
        self.assertEqual(losses.cause_text(self.save, 2012), "Kamikaze")
        self.assertEqual([losses.CAUSES[c] for c in (2001, 2002, 2003, 2004, 2006, 2007, 2008, 2009, 2011)],
                         ["Cancelled", "Written off", "Internal explosion", "Grounding", "Marine casualty",
                          "Abandoned", "Accident", "Operational casualty", "Collision"])

    def test_unknown_codes(self):
        self.assertEqual(losses.cause_text(self.save, 2013), "Unknown (#2013)")
        self.assertEqual(losses.cause_text(self.save, 65535), "Unknown (#65535)")
        self.assertEqual(losses.cause_text(self.save, 0), "Unknown (#0)")
        self.assertEqual(losses.cause_text(self.save, 150), "Unknown (#150)")  # unnamed device
        self.assertEqual(losses.cause_text(self.save, 1999), "Unknown (#1999)")  # outside the device table


@unittest.skipUnless(os.path.exists(SAVE_015), "sample save missing")
class SunkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sf = SaveFile.load(SAVE_015)
        cls.rows = {r.id: r for r in losses.sunk_ships(cls.sf)}

    def test_count_and_ids(self):
        self.assertEqual(len(self.rows), 14)
        for ship_id in (3152, 3168, 3188, 10037):
            self.assertIn(ship_id, self.rows)

    def test_tennessee_sunk_at_base(self):
        r = self.rows[3152]
        self.assertEqual((r.name, r.side, r.date, r.cause, r.location, r.scuttled),
                         ("Tennessee", "Allied", 411207, "800 kg AP Bomb", "Pearl Harbor", False))
        self.assertEqual((r.nation, r.type), ("USN", "BB"))
        self.assertEqual(airgroups.format_day_date(r.date), "7 Dec 1941")

    def test_prince_of_wales_sunk_at_sea_hex(self):
        r = self.rows[3168]
        self.assertEqual((r.cause, r.location, r.date), ("18in Type 91 Torpedo", "52,82 near Mersing", 411207))
        self.assertEqual(r.class_name, "King George V")

    def test_indianapolis(self):
        r = self.rows[3188]
        self.assertEqual((r.date, r.location), (411208, "174,107 near Niihau"))

    def test_japanese_causes(self):
        self.assertEqual(self.rows[10037].side, "Japanese")
        self.assertEqual((self.rows[10037].cause, self.rows[10037].location), ("Hit obstruction", "Pearl Harbor"))
        self.assertEqual(self.rows[10042].cause, "Foundered")
        self.assertEqual(self.rows[4369].cause, "250 kg GP Bomb")
        self.assertEqual(self.rows[4369].location, "Davao")

    def test_summary_totals(self):
        s = {r.side: r for r in losses.summary_rows(list(self.rows.values()), [])}
        self.assertEqual((s["Allied"].ships, s["Japanese"].ships), (11, 3))
        self.assertEqual(sum(1 for r in self.rows.values() if r.side == "Japanese"), 3)

    def test_unused_records_are_skipped(self):
        sf = SaveFile.load(SAVE_015)
        data = sf[shiprecords.SHIP_SECTION].data
        unused = next(i for i in range(shiprecords.SHIP_RECORD_COUNT)
                      if not any(data[i * shiprecords.SHIP_RECORD_SIZE:i * shiprecords.SHIP_RECORD_SIZE + 24]))
        struct.pack_into("<i", data, unused * shiprecords.SHIP_RECORD_SIZE + shiprecords.ARRIVAL_OFFSET,
                         losses.SUNK)
        self.assertNotIn(unused, {r.id for r in losses.sunk_ships(sf)})

    def test_arrived_ships_are_not_listed(self):
        self.assertTrue(all(r.id not in self.rows for r in shiprecords.list_ship_records(self.sf)
                            if r.days_to_arrival != losses.SUNK))

    def test_bad_data_degrades(self):
        sf = SaveFile.load(SAVE_015)
        data = sf[shiprecords.SHIP_SECTION].data
        base = 3152 * shiprecords.SHIP_RECORD_SIZE
        struct.pack_into("<H", data, base + shiprecords.CLASS_OFFSET, 65535)
        struct.pack_into("<H", data, base + losses.CAUSE_OFFSET, 3000)
        struct.pack_into("<H", data, base + losses.LOCATION_OFFSET, 65000)
        data[base + losses.SCUTTLED_OFFSET] = 1
        r = {r.id: r for r in losses.sunk_ships(sf)}[3152]
        self.assertEqual((r.class_name, r.type, r.cause, r.location, r.scuttled),
                         ("#65535", "?", "Unknown (#3000)", "#65000", True))
        struct.pack_into("<H", data, base + losses.LOCATION_OFFSET, 0)
        self.assertEqual({r.id: r for r in losses.sunk_ships(sf)}[3152].location, "unknown")


@unittest.skipUnless(os.path.exists(SAVE_015), "sample save missing")
class AircraftLossTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sf = SaveFile.load(SAVE_015)
        cls.rows = {r.id: r for r in losses.aircraft_losses(cls.sf)}

    def test_ground_losses_only(self):
        r = self.rows[284]
        self.assertEqual((r.name, r.side), ("B-17D Fortress", "Allied"))
        self.assertEqual((r.turn_total, r.air, r.ground, r.flak, r.ops, r.total), (0, 0, 9, 0, 0, 9))
        self.assertEqual(self.rows[466].ground, 26)

    def test_turn_and_total(self):
        r = self.rows[342]
        self.assertEqual((r.turn_air, r.turn_ground, r.turn_flak, r.turn_ops, r.turn_total), (19, 0, 0, 2, 21))
        self.assertEqual((r.air, r.ground, r.flak, r.ops, r.total), (19, 16, 0, 2, 37))
        z = self.rows[603]
        self.assertEqual((z.side, z.turn_air, z.turn_ops, z.air, z.flak, z.ops), ("Japanese", 2, 1, 4, 9, 2))
        self.assertEqual((self.rows[644].flak, self.rows[644].ops), (6, 3))

    def test_models_without_losses_are_excluded(self):
        for r in self.rows.values():
            self.assertTrue(r.turn_total or r.total)
        from witpae import aircraft
        self.assertGreater(len(aircraft.list_aircraft(self.sf)), len(self.rows))

    def test_summary(self):
        s = {r.side: r for r in losses.summary_rows([], list(self.rows.values()))}
        for side in ("Allied", "Japanese"):
            mine = [r for r in self.rows.values() if r.side == side]
            self.assertEqual(s[side].total, sum(r.total for r in mine))
            self.assertEqual(s[side].turn_total, sum(r.turn_total for r in mine))
            self.assertEqual(s[side].total, s[side].air + s[side].ground + s[side].flak + s[side].ops)
        self.assertEqual(s["Allied"].ground, sum(r.ground for r in self.rows.values() if r.side == "Allied"))
        self.assertEqual(s["Allied"].ships, 0)


class LocationTests(unittest.TestCase):
    @unittest.skipUnless(os.path.exists(SAVE_015), "sample save missing")
    def test_base_and_hex_text(self):
        sf = SaveFile.load(SAVE_015)
        self.assertEqual(losses.location_text(sf, 0, 0, 584), "Pearl Harbor")
        self.assertEqual(losses.location_text(sf, 52, 82, 584), "52,82 near Pearl Harbor")
        self.assertEqual(losses.location_text(sf, 0, 0, 0), "unknown")
        self.assertEqual(losses.location_text(sf, 5, 6, 0), "5,6 near unknown")


if __name__ == "__main__":
    unittest.main()
