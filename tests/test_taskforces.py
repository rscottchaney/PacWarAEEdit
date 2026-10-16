import os
import struct
import tempfile
import unittest

from witpae import bases, shiprecords, taskforces
from witpae.container import SaveFile

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
SAVE_015 = os.path.join(DATA_DIR, "going2_411210.pws")
SHIPS, LOCS, TFS = 0x08, 0x13, 0x46
SHIP_SIZE, LOC_SIZE, TF_SIZE = 464, 1172, 556
BASE, TASK_FORCE, NEXT, PREV, COUNT, LAST, FLAG = 60, 62, 64, 66, 656, 818, 44
PEARL = 584
MINESWEEPERS, PATROL, YMS = 14409, 14416, 14417
SOUTHARD, DORSEY, LONG, ELLIOT, ZANE = 4315, 4324, 4326, 4342, 4319
LONE_SHIP = 3684  # only ship of Pearl Harbor Patrol
FAR_TF = 14001  # not at Pearl Harbor
DESTROYERS = 14402  # Alden, Edsall (damaged), John D. Edwards, Whipple; all at 345 of 385 fuel
DESTROYER_SHIPS = [3664, 3668, 3669, 3680]
EDSALL = 3668
MS_FLAG = (TFS, (MINESWEEPERS - 14000) * TF_SIZE + FLAG)


def u16(save, section, pos):
    return struct.unpack_from("<H", save[section].data, pos)[0]


def snapshot(save):
    return {s.sid: bytes(s.data) for s in save.sections}


def changes(save, before):
    """Set of (section, even offset) whose u16 differs from the snapshot."""
    out = set()
    for s in save.sections:
        old, new = before[s.sid], bytes(s.data)
        assert len(old) == len(new)
        if old != new:
            out |= {(s.sid, i & ~1) for i in range(len(old)) if old[i] != new[i]}
    return out


def ship_at(sid, off):
    return (SHIPS, sid * SHIP_SIZE + off)


def loc_at(lid, off):
    return (LOCS, lid * LOC_SIZE + off)


@unittest.skipUnless(os.path.exists(SAVE_015), "sample save missing")
class TaskForceTests(unittest.TestCase):
    def setUp(self):
        self.sf = SaveFile.load(SAVE_015)

    def g(self, where):
        return u16(self.sf, *where)

    def roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "out.pws")
            self.sf.save(path)
            return SaveFile.load(path)

    def assert_consistent(self, save):
        """Walk every TF and port: links, counts, last ship, membership, flagship."""
        for tf in taskforces.list_task_forces(save):
            ships = tf.ships  # raises on a broken chain
            self.assertIn(tf.flagship, ships, tf.id)
        for p in bases.list_places(save):
            taskforces.chain(save, p.id)
        # Every ship with a TF or base is in the chain it names.
        for i in range(20000):
            if not save[SHIPS].data[i * SHIP_SIZE]:
                continue
            owner = u16(save, SHIPS, i * SHIP_SIZE + TASK_FORCE) or u16(save, SHIPS, i * SHIP_SIZE + BASE)
            if owner:
                self.assertIn(i, taskforces.chain(save, owner), i)

    def assert_refused(self, ship, dest, pattern):
        before = snapshot(self.sf)
        with self.assertRaisesRegex(ValueError, pattern):
            taskforces.move_ship(self.sf, ship, dest)
        self.assertEqual(snapshot(self.sf), before)

    def test_anchors(self):
        tf = taskforces.TaskForce(self.sf, MINESWEEPERS)
        self.assertEqual(tf.name, "USN minesweepers")
        self.assertEqual(tf.ships, [SOUTHARD, DORSEY, LONG, ELLIOT])
        self.assertEqual(tf.flagship, ELLIOT)
        self.assertEqual(tf.hex, bases.place_hex(self.sf, PEARL))
        self.assertEqual(tf.side, "Allied")
        self.assertEqual(taskforces.TaskForce(self.sf, PATROL).name, "Pearl Harbor Patrol")
        self.assertEqual(taskforces.TaskForce(self.sf, PATROL).ships, [LONE_SHIP])

    def test_save_is_consistent(self):
        self.assert_consistent(self.sf)
        self.assertEqual(len(taskforces.list_task_forces(self.sf)), 236)

    def test_move_tf_to_port_like_game(self):
        old_last = self.g(loc_at(PEARL, LAST))
        pearl_count = self.g(loc_at(PEARL, COUNT))
        before = snapshot(self.sf)
        taskforces.move_ship(self.sf, ELLIOT, PEARL)
        self.assertEqual(self.g(ship_at(LONG, NEXT)), 0)
        self.assertEqual(self.g(ship_at(ELLIOT, PREV)), old_last)
        self.assertEqual(self.g(ship_at(old_last, NEXT)), ELLIOT)
        self.assertEqual(self.g(ship_at(ELLIOT, NEXT)), 0)
        self.assertEqual((self.g(ship_at(ELLIOT, BASE)), self.g(ship_at(ELLIOT, TASK_FORCE))), (PEARL, 0))
        self.assertEqual((self.g(loc_at(MINESWEEPERS, COUNT)), self.g(loc_at(MINESWEEPERS, LAST))), (3, LONG))
        self.assertEqual((self.g(loc_at(PEARL, COUNT)), self.g(loc_at(PEARL, LAST))), (pearl_count + 1, ELLIOT))
        self.assertEqual(self.g(MS_FLAG), LONG)
        self.assertEqual(changes(self.sf, before), {
            ship_at(LONG, NEXT), ship_at(ELLIOT, BASE), ship_at(ELLIOT, TASK_FORCE), ship_at(ELLIOT, PREV),
            ship_at(old_last, NEXT), loc_at(MINESWEEPERS, COUNT), loc_at(MINESWEEPERS, LAST),
            loc_at(PEARL, COUNT), loc_at(PEARL, LAST), MS_FLAG})
        self.assert_consistent(self.sf)
        other = self.roundtrip()
        self.assert_consistent(other)
        for sid in (SHIPS, LOCS, TFS):
            self.assertEqual(bytes(other[sid].data), bytes(self.sf[sid].data))
        self.assertEqual(taskforces.TaskForce(other, MINESWEEPERS).ships, [SOUTHARD, DORSEY, LONG])
        self.assertEqual(shiprecords.list_ship_records(other)[0].id, shiprecords.list_ship_records(self.sf)[0].id)

    def test_move_port_to_tf_like_game(self):
        self.assertEqual((self.g(ship_at(ZANE, BASE)), self.g(ship_at(ZANE, TASK_FORCE))), (PEARL, 0))
        prev, nxt = self.g(ship_at(ZANE, PREV)), self.g(ship_at(ZANE, NEXT))
        self.assertTrue(prev and nxt)
        pearl_count = self.g(loc_at(PEARL, COUNT))
        pearl_last = self.g(loc_at(PEARL, LAST))
        before = snapshot(self.sf)
        taskforces.move_ship(self.sf, ZANE, MINESWEEPERS)
        self.assertEqual(taskforces.TaskForce(self.sf, MINESWEEPERS).ships, [SOUTHARD, ZANE, DORSEY, LONG, ELLIOT])
        self.assertEqual((self.g(ship_at(ZANE, PREV)), self.g(ship_at(ZANE, NEXT))), (SOUTHARD, DORSEY))
        self.assertEqual((self.g(ship_at(prev, NEXT)), self.g(ship_at(nxt, PREV))), (nxt, prev))
        self.assertEqual((self.g(ship_at(ZANE, BASE)), self.g(ship_at(ZANE, TASK_FORCE))), (0, MINESWEEPERS))
        self.assertEqual((self.g(loc_at(PEARL, COUNT)), self.g(loc_at(MINESWEEPERS, COUNT))), (pearl_count - 1, 5))
        self.assertEqual(self.g(loc_at(PEARL, LAST)), pearl_last)
        self.assertEqual(self.g(loc_at(MINESWEEPERS, LAST)), ELLIOT)
        self.assertEqual(taskforces.TaskForce(self.sf, MINESWEEPERS).flagship, ELLIOT)
        self.assertEqual(changes(self.sf, before), {
            ship_at(prev, NEXT), ship_at(nxt, PREV), ship_at(ZANE, BASE), ship_at(ZANE, TASK_FORCE),
            ship_at(ZANE, NEXT), ship_at(ZANE, PREV), ship_at(SOUTHARD, NEXT), ship_at(DORSEY, PREV),
            loc_at(PEARL, COUNT), loc_at(MINESWEEPERS, COUNT)})
        self.assert_consistent(self.sf)
        self.assert_consistent(self.roundtrip())

    def test_move_last_of_port_chain_updates_last(self):
        last = taskforces.chain(self.sf, PEARL)[-1]
        self.assertEqual(self.g(loc_at(PEARL, LAST)), last)
        taskforces.move_ship(self.sf, last, MINESWEEPERS)
        self.assertNotEqual(self.g(loc_at(PEARL, LAST)), last)
        self.assertIn(last, taskforces.TaskForce(self.sf, MINESWEEPERS).ships)
        self.assert_consistent(self.sf)

    def test_move_tf_to_tf_same_hex(self):
        yms = taskforces.TaskForce(self.sf, YMS)
        ships, flagship = yms.ships, yms.flagship
        before = snapshot(self.sf)
        taskforces.move_ship(self.sf, SOUTHARD, YMS)  # head of its chain
        self.assertEqual(taskforces.TaskForce(self.sf, MINESWEEPERS).ships, [DORSEY, LONG, ELLIOT])
        self.assertEqual(taskforces.TaskForce(self.sf, YMS).ships, [s for s in ships if s < SOUTHARD] + [SOUTHARD] + [s for s in ships if s > SOUTHARD])
        self.assertEqual((self.g(ship_at(SOUTHARD, TASK_FORCE)), self.g(ship_at(SOUTHARD, BASE))), (YMS, 0))
        self.assertEqual(taskforces.TaskForce(self.sf, YMS).flagship, flagship)
        self.assertEqual(taskforces.TaskForce(self.sf, MINESWEEPERS).flagship, ELLIOT)
        self.assertEqual(changes(self.sf, before) & {(TFS, o) for o in range(len(before[TFS]))}, set())
        self.assert_consistent(self.sf)
        # Moving the flagship out makes the new last ship the flagship.
        taskforces.move_ship(self.sf, ELLIOT, YMS)
        self.assertEqual(taskforces.TaskForce(self.sf, MINESWEEPERS).flagship, LONG)
        self.assertEqual(taskforces.TaskForce(self.sf, YMS).flagship, flagship)
        self.assert_consistent(self.sf)
        self.assert_consistent(self.roundtrip())

    def test_move_into_one_ship_tf(self):
        taskforces.move_ship(self.sf, ELLIOT, PATROL)
        self.assertEqual(taskforces.TaskForce(self.sf, PATROL).ships, [ELLIOT, LONE_SHIP] if ELLIOT < LONE_SHIP
                         else [LONE_SHIP, ELLIOT])
        self.assert_consistent(self.sf)

    def test_destinations(self):
        out = taskforces.destinations(self.sf, ELLIOT)
        hexxy = bases.place_hex(self.sf, PEARL)
        expected = {t.id for t in taskforces.list_task_forces(self.sf)
                    if t.hex == hexxy and t.side == "Allied" and t.id != MINESWEEPERS}
        self.assertEqual({d.id for d in out if d.kind == "tf"}, expected)
        self.assertIn(PATROL, expected)
        self.assertEqual([d for d in out if d.kind == "port"], [
            taskforces.Destination(PEARL, "Pearl Harbor (port)", "port")])
        self.assertEqual({d.id: d.label for d in out}[PATROL], "TF 14416 Pearl Harbor Patrol (1 ships)")
        for d in out:  # every offer is movable, and the original is left alone
            copy = SaveFile.from_bytes(self.sf.to_bytes())
            taskforces.move_ship(copy, ELLIOT, d.id)
            self.assert_consistent(copy)
        # A docked ship can join the TFs but not another port.
        docked = taskforces.destinations(self.sf, ZANE)
        self.assertIn(MINESWEEPERS, {d.id for d in docked})
        self.assertEqual([d for d in docked if d.kind == "port"], [])

    def test_no_destinations(self):
        self.assertEqual(taskforces.destinations(self.sf, LONE_SHIP), [])  # last ship of its TF
        self.assertEqual(taskforces.destinations(self.sf, 0), [])
        self.assertEqual(taskforces.destinations(self.sf, 19999), [])

    def test_refuse_last_ship_of_tf(self):
        self.assert_refused(LONE_SHIP, PEARL, "last ship")
        self.assert_refused(LONE_SHIP, MINESWEEPERS, "last ship")

    def test_refuse_different_hex(self):
        self.assertNotEqual(taskforces.TaskForce(self.sf, FAR_TF).hex, bases.place_hex(self.sf, PEARL))
        self.assert_refused(ELLIOT, FAR_TF, "same hex")
        other_port = next(p.id for p in bases.list_places(self.sf)
                          if (p.x, p.y) != bases.place_hex(self.sf, PEARL) and p.side_id == 1)
        self.assert_refused(ELLIOT, other_port, "same hex")
        self.assert_refused(ZANE, FAR_TF, "same hex")

    def test_refuse_other_side(self):
        self.sf[SHIPS].data[ELLIOT * SHIP_SIZE + shiprecords.NATION_OFFSET] = 1  # IJN
        self.assertEqual(taskforces.ship_side(self.sf, ELLIOT), "Japanese")
        self.assert_refused(ELLIOT, PEARL, "other side")
        self.assert_refused(ELLIOT, YMS, "other side")
        self.assertEqual(taskforces.destinations(self.sf, ELLIOT), [])

    def test_refuse_enemy_port(self):
        enemy = next(p for p in bases.list_places(self.sf) if p.side_id == 0)
        # Put the Allied TF on a Japanese place's hex so only the side check can refuse.
        struct.pack_into("<2h", self.sf[LOCS].data, MINESWEEPERS * LOC_SIZE + bases.X_OFFSET, enemy.x, enemy.y)
        self.assert_refused(ELLIOT, enemy.id, "other side")

    def test_refuse_at_sea_alone(self):
        pos = ELLIOT * SHIP_SIZE + TASK_FORCE
        self.sf[SHIPS].data[pos:pos + 2] = bytes(2)
        self.assert_refused(ELLIOT, PEARL, "at sea")
        self.assertEqual(taskforces.destinations(self.sf, ELLIOT), [])

    def test_refuse_not_arrived(self):
        data = self.sf[SHIPS].data
        ship = next(i for i in range(20000) if data[i * SHIP_SIZE]
                    and struct.unpack_from("<I", data, i * SHIP_SIZE + shiprecords.ARRIVAL_OFFSET)[0])
        self.assert_refused(ship, PEARL, "not arrived")
        self.assertEqual(taskforces.destinations(self.sf, ship), [])
        struct.pack_into("<I", data, ELLIOT * SHIP_SIZE + shiprecords.ARRIVAL_OFFSET, 3)
        self.assert_refused(ELLIOT, PEARL, "not arrived")

    def test_refuse_same_chain_and_port_to_port(self):
        self.assert_refused(ELLIOT, MINESWEEPERS, "already")
        self.assert_refused(ZANE, PEARL, "already")
        other_port = next(p.id for p in bases.list_places(self.sf) if p.id != PEARL)
        self.assert_refused(ZANE, other_port, "port to another")

    def test_refuse_bad_ids(self):
        self.assert_refused(19999, PEARL, "not a ship")
        self.assert_refused(True, PEARL, "not a ship")
        self.assert_refused(ELLIOT, 13999, "not a task force")
        self.assert_refused(ELLIOT, "584", "not a destination")
        self.assert_refused(ELLIOT, 0, "not a task force")

    def test_refuse_broken_chains(self):
        data, locs = self.sf[SHIPS].data, self.sf[LOCS].data

        def poke(section_data, pos, value):
            old = struct.unpack_from("<H", section_data, pos)[0]
            struct.pack_into("<H", section_data, pos, value)
            return old

        # Link broken inside the source TF.
        old = poke(data, DORSEY * SHIP_SIZE + NEXT, 0)
        self.assert_refused(ELLIOT, PEARL, "broken")
        poke(data, DORSEY * SHIP_SIZE + NEXT, old)
        # Count disagrees with the walked destination chain.
        pos = PEARL * LOC_SIZE + COUNT
        old = poke(locs, pos, self.g(loc_at(PEARL, COUNT)) + 1)
        self.assert_refused(ELLIOT, PEARL, "ships but its count")
        poke(locs, pos, old)
        # Last ship is not the end of the destination chain.
        port = taskforces.chain(self.sf, PEARL)
        poke(locs, PEARL * LOC_SIZE + LAST, port[-2])
        self.assert_refused(ELLIOT, PEARL, "broken")
        poke(locs, PEARL * LOC_SIZE + LAST, port[-1])
        # Flagship is not a member of the source TF.
        old = poke(self.sf[TFS].data, MS_FLAG[1], 4)
        self.assert_refused(ELLIOT, PEARL, "flagship")
        poke(self.sf[TFS].data, MS_FLAG[1], old)
        # A ship in a chain that does not record it.
        poke(data, LONG * SHIP_SIZE + TASK_FORCE, YMS)
        self.assert_refused(ELLIOT, PEARL, "not recorded")
        poke(data, LONG * SHIP_SIZE + TASK_FORCE, MINESWEEPERS)
        taskforces.move_ship(self.sf, ELLIOT, PEARL)  # every repair restored a valid save

    # ---- flagship ------------------------------------------------------

    def test_set_flagship(self):
        self.assertEqual(self.g(MS_FLAG), ELLIOT)
        before = snapshot(self.sf)
        taskforces.set_flagship(self.sf, MINESWEEPERS, LONG)
        self.assertEqual(taskforces.TaskForce(self.sf, MINESWEEPERS).flagship, LONG)
        self.assertEqual(changes(self.sf, before), {MS_FLAG})
        for section in (SHIPS, LOCS, TFS):
            old, new = before[section], bytes(self.sf[section].data)
            diff = [i for i in range(len(old)) if old[i] != new[i]]
            if section == TFS:
                self.assertEqual(diff, [MS_FLAG[1]])  # low byte of 4342 -> 4326 only
            else:
                self.assertEqual(diff, [])
        self.assert_consistent(self.sf)
        other = self.roundtrip()
        self.assertEqual(taskforces.TaskForce(other, MINESWEEPERS).flagship, LONG)
        # Setting the current flagship again writes nothing.
        again = snapshot(self.sf)
        taskforces.set_flagship(self.sf, MINESWEEPERS, LONG)
        self.assertEqual(snapshot(self.sf), again)

    def test_set_flagship_refused(self):
        before = snapshot(self.sf)
        cases = [(MINESWEEPERS, ZANE), (MINESWEEPERS, 0), (MINESWEEPERS, 19999), (MINESWEEPERS, True),
                 (MINESWEEPERS, "4326"), (PEARL, LONG), (13999, LONG), (True, LONG), ("14409", LONG)]
        for tf_id, ship_id in cases:
            with self.assertRaises(ValueError, msg=(tf_id, ship_id)):
                taskforces.set_flagship(self.sf, tf_id, ship_id)
        self.assertEqual(snapshot(self.sf), before)
        # A TF whose chain is inconsistent is refused too.
        struct.pack_into("<H", self.sf[SHIPS].data, DORSEY * SHIP_SIZE + NEXT, 0)
        before = snapshot(self.sf)
        with self.assertRaisesRegex(ValueError, "broken"):
            taskforces.set_flagship(self.sf, MINESWEEPERS, LONG)
        self.assertEqual(snapshot(self.sf), before)

    # ---- repair / refuel -----------------------------------------------

    def ship_values(self, ids):
        return {i: {n: shiprecords.ShipRecord(self.sf, i, "x").get(n) for n in ("fuel", *shiprecords.DAMAGE_FIELDS)}
                for i in ids}

    def test_repair_task_force(self):
        # Edsall is the only damaged ship of the destroyer TF (system 1, engine 1).
        self.assertEqual(taskforces.TaskForce(self.sf, DESTROYERS).ships, DESTROYER_SHIPS)
        self.assertEqual(self.ship_values([EDSALL])[EDSALL]["sys_dmg"], 1)
        before = snapshot(self.sf)
        self.assertEqual(taskforces.repair_task_force(self.sf, DESTROYERS), [EDSALL])
        self.assertEqual(changes(self.sf, before), {ship_at(EDSALL, 332), ship_at(EDSALL, 334)})  # sys and eng u8s
        self.assertEqual(sum(self.ship_values([EDSALL])[EDSALL][n] for n in shiprecords.DAMAGE_FIELDS), 0)
        again = snapshot(self.sf)
        self.assertEqual(taskforces.repair_task_force(self.sf, DESTROYERS), [])
        self.assertEqual(snapshot(self.sf), again)
        # The minesweepers have one damaged ship (Dorsey) and nothing else changes.
        before = snapshot(self.sf)
        self.assertEqual(taskforces.repair_task_force(self.sf, MINESWEEPERS), [DORSEY])
        self.assertEqual({o for s, o in changes(self.sf, before)}, {DORSEY * SHIP_SIZE + 332})
        self.assert_consistent(self.sf)

    def test_refuel_task_force(self):
        for s in DESTROYER_SHIPS:
            self.assertEqual(self.ship_values([s])[s]["fuel"], 345)
            self.assertEqual(shiprecords.ShipRecord(self.sf, s, "x").max_fuel, 385)
        # One ship above its class fuel is never lowered.
        shiprecords.ShipRecord(self.sf, DESTROYER_SHIPS[0], "x").set("fuel", 400)
        before = snapshot(self.sf)
        self.assertEqual(taskforces.refuel_task_force(self.sf, DESTROYERS), DESTROYER_SHIPS[1:])
        self.assertEqual([self.ship_values([s])[s]["fuel"] for s in DESTROYER_SHIPS], [400, 385, 385, 385])
        self.assertEqual(changes(self.sf, before), {ship_at(s, 56) for s in DESTROYER_SHIPS[1:]})  # fuel u16
        again = snapshot(self.sf)
        self.assertEqual(taskforces.refuel_task_force(self.sf, DESTROYERS), [])
        self.assertEqual(snapshot(self.sf), again)
        # Ships already full are untouched.
        self.assertEqual(taskforces.refuel_task_force(self.sf, MINESWEEPERS), [])
        self.assertEqual(snapshot(self.sf), again)

    def test_quick_edits_refused_for_bad_tf(self):
        before = snapshot(self.sf)
        for fn in (taskforces.repair_task_force, taskforces.refuel_task_force):
            for bad in (PEARL, 13999, True, "14402"):
                with self.assertRaises(ValueError):
                    fn(self.sf, bad)
            struct.pack_into("<H", self.sf[LOCS].data, DESTROYERS * LOC_SIZE + COUNT, 9)
            with self.assertRaisesRegex(ValueError, "count"):
                fn(self.sf, DESTROYERS)
            struct.pack_into("<H", self.sf[LOCS].data, DESTROYERS * LOC_SIZE + COUNT, 4)
        self.assertEqual(snapshot(self.sf), before)


if __name__ == "__main__":
    unittest.main()
