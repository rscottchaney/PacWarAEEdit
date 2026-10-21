import os
import struct
import unittest

from witpae import bases, shiprecords, shiprepair
from witpae.container import SaveFile

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
SAVE_015 = os.path.join(DATA_DIR, "going2_411210.pws")
TATSUTA, YUBARI, USHIO, AMAGISAN = 125, 126, 240, 1228
WAKE, KAGOSHIMA, MIDWAY, PEARL, SOERABAJA = 611, 229, 581, 584, 1160
JAVA = 3231


class LabelTests(unittest.TestCase):
    def test_priority_codes(self):
        self.assertEqual([shiprepair.priority_text(c) for c in range(4)], ["Low", "Normal", "High", "Critical"])
        self.assertEqual(shiprepair.priority_text(4), "Unknown (4)")
        self.assertEqual(shiprepair.priority_text(255), "Unknown (255)")

    def test_mode_codes(self):
        self.assertEqual([shiprepair.mode_text(c) for c in range(4)],
                         ["Readiness", "Pierside", "Repair ship", "Shipyard"])
        self.assertEqual(shiprepair.mode_text(4), "Unknown (4)")
        self.assertEqual(shiprepair.mode_text(200), "Unknown (200)")


class MinimumTests(unittest.TestCase):
    def test_min_port(self):
        self.assertEqual(shiprepair.min_port(0), 0)
        self.assertEqual(shiprepair.min_port(1), 1)
        self.assertEqual(shiprepair.min_port(6000), 1)
        self.assertEqual(shiprepair.min_port(6001), 2)
        self.assertEqual(shiprepair.min_port(38200), 6)
        self.assertEqual(shiprepair.min_port(84000), 10)
        self.assertEqual(shiprepair.min_port(84001), shiprepair.NO_PORT)
        self.assertEqual(shiprepair.min_port(100000), shiprepair.NO_PORT)

    def test_min_yard(self):
        self.assertEqual(shiprepair.min_yard(0), 0)
        self.assertEqual(shiprepair.min_yard(1), 1)
        self.assertEqual(shiprepair.min_yard(1000), 1)
        self.assertEqual(shiprepair.min_yard(1001), 2)
        self.assertEqual(shiprepair.min_yard(6000), 6)
        self.assertEqual(shiprepair.min_yard(38200), 39)
        self.assertEqual(shiprepair.min_yard(84001), 85)


@unittest.skipUnless(os.path.exists(SAVE_015), "sample save missing")
class DamagedShipTests(unittest.TestCase):
    def setUp(self):
        self.sf = SaveFile.load(SAVE_015)

    def record(self, ship_id):
        return {r.id: r for r in shiprecords.list_ship_records(self.sf)}[ship_id]

    def poke(self, ship_id, offset, value, fmt="B"):
        rec = self.record(ship_id)
        struct.pack_into("<" + fmt, rec._data, rec._offset + offset, value)

    def rows(self):
        return {r.id: r for r in shiprepair.damaged_ships(self.sf)}

    def test_count_and_example_ships(self):
        rows = self.rows()
        self.assertEqual(len(rows), 105)
        u = rows[USHIO]
        self.assertEqual((u.fires, u.system, u.flotation, u.major_flotation, u.engine, u.major_engine),
                         (0, 15, 6, 5, 3, 0))
        self.assertEqual((u.name, u.side, u.nation, u.type, u.class_name, u.tons, u.weapons, u.weapon_text),
                         ("Ushio", "Japanese", "IJN", "DD", "Fubuki(II)", 2090, 0, ""))
        self.assertEqual((u.priority, u.mode, u.delay, u.min_port, u.min_yard), ("Normal", "Readiness", 0, 1, 3))
        y = rows[YUBARI]
        self.assertEqual((y.fires, y.system), (9, 14))
        self.assertEqual(rows[AMAGISAN].delay, 2)
        self.assertEqual((rows[AMAGISAN].tons, rows[AMAGISAN].min_port, rows[AMAGISAN].min_yard), (6825, 2, 7))

    def test_weapon_damage_text(self):
        t = self.rows()[TATSUTA]
        self.assertEqual((t.weapons, t.weapon_text), (2, "2x 25mm Type 96 AA Gun"))
        self.assertEqual((t.fires, t.flotation), (2, 1))
        # A second damaged slot is appended in slot order.
        self.poke(TATSUTA, shiprepair.WEAPON_DAMAGE_OFFSET + 0, 1)
        device = self.record(TATSUTA).get_weapon(0)["name"]
        t = self.rows()[TATSUTA]
        self.assertEqual(t.weapons, 3)
        self.assertEqual(t.weapon_text, f"1x {device}; 2x 25mm Type 96 AA Gun")

    def test_unnamed_device(self):
        self.poke(TATSUTA, shiprecords.DEVICE_OFFSET + 2 * 4, 19999, "H")
        self.assertEqual(self.rows()[TATSUTA].weapon_text, "2x #19999")

    def test_weapon_damage_alone_lists_the_ship(self):
        for off in range(331, 337):
            self.poke(TATSUTA, off, 0)
        t = self.rows()[TATSUTA]
        self.assertEqual((t.fires, t.flotation, t.weapons), (0, 0, 2))

    def test_undamaged_ship_excluded(self):
        for off in range(331, 337):
            self.poke(AMAGISAN, off, 0)
        self.assertNotIn(AMAGISAN, self.rows())
        self.assertEqual(len(self.rows()), 104)

    def test_unarrived_and_sunk_excluded(self):
        self.poke(AMAGISAN, shiprecords.ARRIVAL_OFFSET, 5, "I")
        self.poke(USHIO, shiprecords.ARRIVAL_OFFSET, 19999, "I")
        rows = self.rows()
        self.assertNotIn(AMAGISAN, rows)
        self.assertNotIn(USHIO, rows)
        self.assertEqual(len(rows), 103)

    def test_labels_and_unknown_codes(self):
        self.poke(AMAGISAN, shiprepair.PRIORITY_OFFSET, 3)
        self.poke(AMAGISAN, shiprepair.MODE_OFFSET, 3)
        self.poke(USHIO, shiprepair.PRIORITY_OFFSET, 9)
        self.poke(USHIO, shiprepair.MODE_OFFSET, 7)
        rows = self.rows()
        self.assertEqual((rows[AMAGISAN].priority, rows[AMAGISAN].mode), ("Critical", "Shipyard"))
        self.assertEqual((rows[USHIO].priority, rows[USHIO].mode), ("Unknown (9)", "Unknown (7)"))

    def test_unknown_class(self):
        self.poke(AMAGISAN, shiprecords.CLASS_OFFSET, 65535, "H")
        r = self.rows()[AMAGISAN]
        self.assertEqual((r.class_name, r.type, r.tons, r.min_port, r.min_yard), ("#65535", "?", 0, 0, 0))

    def test_location_docked(self):
        r = self.rows()[AMAGISAN]
        self.assertEqual((r.location, r.port_id), ("Kagoshima", KAGOSHIMA))

    def test_location_task_force_in_port(self):
        r = self.rows()[JAVA]
        self.assertEqual((r.location, r.port_id), ("TF 14413 at Soerabaja", SOERABAJA))

    def test_task_force_in_enemy_base_hex_is_at_sea(self):
        # Tatsuta (Japanese) is in the hex of Wake Island, an Allied base.
        r = self.rows()[TATSUTA]
        self.assertEqual((r.location, r.port_id), ("TF 14016 at sea 136,98", None))

    def test_location_task_force_at_sea(self):
        r = self.rows()[USHIO]
        self.assertEqual((r.location, r.port_id), ("TF 14141 at sea 143,56", None))

    def test_location_unknown_base(self):
        self.poke(AMAGISAN, shiprecords.BASE_OFFSET, 17999, "H")
        r = self.rows()[AMAGISAN]
        self.assertEqual((r.location, r.port_id), ("#17999", None))

    def test_location_unknown_task_force(self):
        self.poke(USHIO, shiprecords.TASK_FORCE_OFFSET, 3, "H")
        r = self.rows()[USHIO]
        self.assertEqual((r.location, r.port_id), ("TF 3 at sea", None))

    def test_ports_only_with_damaged_ships(self):
        rows = shiprepair.damaged_ships(self.sf)
        ports = shiprepair.repair_ports(self.sf, rows)
        ids = [p.id for p in ports]
        self.assertEqual(ids, sorted(set(r.port_id for r in rows if r.port_id is not None)))
        self.assertEqual(sum(p.ships for p in ports), sum(1 for r in rows if r.port_id is not None))
        self.assertEqual(shiprepair.repair_ports(self.sf, []), [])

    def test_port_aggregation(self):
        rows = shiprepair.damaged_ships(self.sf)
        ports = {p.id: p for p in shiprepair.repair_ports(self.sf, rows)}
        self.assertNotIn(WAKE, ports)  # only an enemy TF is there
        s = ports[SOERABAJA]  # Java, Tromp, Evertsen and two more
        self.assertEqual((s.name, s.side, s.largest, s.yard_capacity), ("Soerabaja", "Allied", 60000, 8000))
        self.assertEqual((s.ships, s.tons, s.shipyard_tons, s.largest_tons, s.oversize), (5, 13113, 0, 6670, 0))
        k = ports[KAGOSHIMA]
        self.assertEqual((k.port_size, k.largest, k.total), (4, 24000, 48000))
        self.assertEqual((k.yard_size, k.yard_damage, k.yard_capacity, k.repair_points), (10, 0, 10000, 100))
        p = ports[PEARL]
        self.assertEqual((p.ships, p.yard_damage, p.largest, p.total), (22, 3, 60000, 104000))
        self.assertEqual(ports[722].port_damage, 17)  # Singapore

    def test_port_oversize_ships(self):
        # Midway: size 1 (6,000 t), no yard. Shrinking the port to size 0 makes its 1,700 t ship too big.
        ports = {p.id: p for p in shiprepair.repair_ports(self.sf, shiprepair.damaged_ships(self.sf))}
        self.assertEqual((ports[MIDWAY].largest, ports[MIDWAY].yard_capacity, ports[MIDWAY].oversize), (6000, 0, 0))
        base = bases.Base(self.sf, MIDWAY, "Midway Island")
        struct.pack_into("<h", self.sf[bases.LOCATION_SECTION].data, base._offset + 422, 0)
        ports = {p.id: p for p in shiprepair.repair_ports(self.sf, shiprepair.damaged_ships(self.sf))}
        self.assertEqual((ports[MIDWAY].largest, ports[MIDWAY].largest_tons, ports[MIDWAY].oversize), (0, 1700, 1))

    def test_shipyard_mode_tonnage(self):
        self.poke(JAVA, shiprepair.MODE_OFFSET, 3)
        rows = shiprepair.damaged_ships(self.sf)
        s = {p.id: p for p in shiprepair.repair_ports(self.sf, rows)}[SOERABAJA]
        self.assertEqual((s.tons, s.shipyard_tons), (13113, 6670))
        side = {x.side: x for x in shiprepair.summary_rows(rows)}
        self.assertEqual((side["Allied"].shipyard, side["Japanese"].shipyard), (1, 0))

    def test_summary_by_side(self):
        rows = shiprepair.damaged_ships(self.sf)
        side = {s.side: s for s in shiprepair.summary_rows(rows)}
        self.assertEqual(list(side), ["Allied", "Japanese"])
        self.assertEqual(tuple(side["Allied"])[1:], (69, 19, 50, 0, 554621))
        self.assertEqual(tuple(side["Japanese"])[1:], (36, 34, 2, 0, 101365))
        self.assertEqual(side["Allied"].ships + side["Japanese"].ships, len(rows))
        self.assertEqual([r.side for r in shiprepair.summary_rows([])], ["Allied", "Japanese"])
        self.assertEqual(tuple(shiprepair.summary_rows([])[0])[1:], (0, 0, 0, 0, 0))


if __name__ == "__main__":
    unittest.main()
