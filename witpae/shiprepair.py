"""Read-only report of the damaged ships and the ports that repair them.

Only arrived ships (days to arrival, i32 at 36, is 0) count. A ship is damaged when any of its six damage bytes
(fires 331, system 332, flotation 333, major flotation 334, engine 335, major engine 336) is above 0 or any weapon
slot has damaged mounts: the u8 at 270 + k is the number of damaged mounts in slot k (0 to 19), whose device is the
u16 at 70 + 2k. The repair priority is the u8 at 338 (0 Low, 1 Normal, 2 High, 3 Critical), the repair mode the u8 at
339 (0 Readiness, 1 Pierside, 2 Repair ship, 3 Shipyard) and the repair delay (days) the u16 at 342. The tonnage is
the displacement, u16 at 28 of the ship class (section 0x1B). A docked ship has a base (u16 at 60); a ship in a task
force (u16 at 62, base 0) is in port when the TF's hex equals the hex of a base of its own side, otherwise it
is at sea.
A port (section 0x13) has its size i16 at 422, max size at 420 and damage at 442; its repair shipyard is the factory
slot of type 524 (its size and damage). The yard repairs yard size x 10 points a day (manual 14.2.3.1) and holds
ships up to yard size x 1000 tons; the largest ship and the total tonnage a port can dock come from the manual's
table in 14.2 (PORT_LARGEST, PORT_TOTAL). The minimum port of a ship is the smallest size whose largest ship docked
reaches its tonnage, the minimum yard is its tonnage in thousands, rounded up. The offsets come from WiTPTracker's
reader facts and match the saves seen; they have not been compared with the game's own screens yet. Nothing here
writes to the save.
"""

import struct
from collections import namedtuple

from . import bases, factories, ships, shiprecords, taskforces
from .bases import LOCATION_SECTION, NAME_SIZE, RECORD_SIZE as LOCATION_RECORD_SIZE, decode_name
from .factories import DEVICE_RECORD_SIZE, DEVICE_SECTION, _plain_name

WEAPON_DAMAGE_OFFSET = 270  # u8 per slot: damaged mounts
PRIORITY_OFFSET = 338  # u8
MODE_OFFSET = 339  # u8
DELAY_OFFSET = 342  # u16, days
REPAIR_YARD = 524  # factory type of a repair shipyard
YARD_TONS = 1000  # capacity per yard size
YARD_POINTS = 10  # repair points a day per yard size
SIDES = ("Allied", "Japanese")
PRIORITIES = {0: "Low", 1: "Normal", 2: "High", 3: "Critical"}
MODES = {0: "Readiness", 1: "Pierside", 2: "Repair ship", 3: "Shipyard"}
SHIPYARD = MODES[3]
# Manual 14.2, indexed by port size 0 to 10.
PORT_LARGEST = (0, 6000, 9000, 12000, 24000, 36000, 48000, 60000, 72000, 78000, 84000)
PORT_TOTAL = (0, 6000, 12000, 24000, 48000, 60000, 84000, 104000, 128000, 172000, 196000)
NO_PORT = len(PORT_LARGEST)  # min port of a ship too big for any port (shown as "-")

ShipRepairRow = namedtuple("ShipRepairRow", "id name side nation type class_name tons location port_id fires "
                                            "system flotation major_flotation engine major_engine weapons "
                                            "weapon_text priority mode delay min_port min_yard")
PortRepairRow = namedtuple("PortRepairRow", "id name side port_size port_max port_damage largest total yard_size "
                                            "yard_damage yard_capacity repair_points ships tons shipyard_tons "
                                            "largest_tons oversize")
SideSummary = namedtuple("SideSummary", "side ships at_sea in_port shipyard tons")


def priority_text(code):
    return PRIORITIES.get(code) or f"Unknown ({code})"


def mode_text(code):
    return MODES.get(code) or f"Unknown ({code})"


def min_port(tons):
    """Smallest port size that can dock a ship of this tonnage, NO_PORT when none can."""
    for size, largest in enumerate(PORT_LARGEST):
        if largest >= tons:
            return size
    return NO_PORT


def min_yard(tons):
    """Smallest repair yard size (1000 tons each) that holds a ship of this tonnage."""
    return -(-tons // YARD_TONS) if tons > 0 else 0


def _tons(rec):
    start = rec._class_start()
    if start is None:
        return 0
    return struct.unpack_from("<H", rec._save[ships.SHIP_SECTION].data, start + ships.DISPLACEMENT_OFFSET)[0]


def _device_name(save, device_id):
    data = save[DEVICE_SECTION].data
    start = device_id * DEVICE_RECORD_SIZE
    if start + DEVICE_RECORD_SIZE > len(data):
        return f"#{device_id}"
    return _plain_name(data, start) or f"#{device_id}"


def weapon_damage(rec):
    """(damaged mount count, text like "2x <device>; 1x <device>") over the ship's 20 weapon slots."""
    parts, total = [], 0
    for k in range(shiprecords.SLOTS):
        damaged = rec._u8(WEAPON_DAMAGE_OFFSET + k)
        if damaged:
            total += damaged
            parts.append(f"{damaged}x {_device_name(rec._save, rec._u16(shiprecords.DEVICE_OFFSET + 2 * k))}")
    return total, "; ".join(parts)


def _port_hexes(save):
    """{hex: place id} of the places, a base (location type 1) winning over a town in the same hex."""
    out, ranks = {}, {}
    for b in bases.list_bases(save, include_towns=True):
        rank = b.kind != "Base"
        key = (b.x, b.y)
        if key not in out or rank < ranks[key]:
            out[key], ranks[key] = b.id, rank
    return out


def _place_name(save, loc):
    if not bases.is_place(save, loc):
        return f"#{loc}"
    start = loc * LOCATION_RECORD_SIZE
    return decode_name(save[LOCATION_SECTION].data[start:start + NAME_SIZE]) or f"#{loc}"


def _location(save, rec, hexes):
    """(text, port id or None) of a ship."""
    if rec.base_id:
        return rec.base_name, (rec.base_id if bases.is_place(save, rec.base_id) else None)
    tf = rec.task_force
    if not tf:
        return "at sea", None
    if not taskforces.is_task_force(save, tf):
        return f"TF {tf} at sea", None
    x, y = bases.place_hex(save, tf)
    port = hexes.get((x, y))
    # A TF in the hex of an enemy base (e.g. a bombardment off Wake) is not in port.
    if port is not None and bases.SIDES.get(bases.place_side_id(save, port)) != rec.side:
        port = None
    if port is None:
        return f"TF {tf} at sea {x},{y}", None
    return f"TF {tf} at {_place_name(save, port)}", port


def damaged_ships(save):
    """One ShipRepairRow per arrived ship with damage or damaged weapons, in id order."""
    hexes = _port_hexes(save)
    rows = []
    for rec in shiprecords.list_ship_records(save):
        if rec.days_to_arrival != 0:
            continue
        damage = [rec._u8(shiprecords.FIELD_BY_NAME[n].offset) for n in shiprecords.DAMAGE_FIELDS]
        weapons, weapon_text = weapon_damage(rec)
        if not any(damage) and not weapons:
            continue
        location, port = _location(save, rec, hexes)
        tons = _tons(rec)
        rows.append(ShipRepairRow(rec.id, rec.name, rec.side, rec.nation, rec.type or "?",
                                  rec.class_name or f"#{rec.class_id}", tons, location, port, *damage, weapons,
                                  weapon_text, priority_text(rec._u8(PRIORITY_OFFSET)),
                                  mode_text(rec._u8(MODE_OFFSET)), rec._u16(DELAY_OFFSET), min_port(tons),
                                  min_yard(tons)))
    return rows


def _table(values, size):
    return values[size] if 0 <= size < len(values) else 0


def repair_ports(save, rows):
    """One PortRepairRow per port holding at least one of the damaged ships, in id order."""
    by_port = {}
    for r in rows:
        if r.port_id is not None:
            by_port.setdefault(r.port_id, []).append(r)
    out = []
    for port_id in sorted(by_port):
        base = bases.Base(save, port_id, _place_name(save, port_id))
        yards = [f for f in factories.list_factories(base) if f.type == REPAIR_YARD]
        yard = max(yards, key=lambda f: f.size) if yards else None
        yard_size = yard.size if yard else 0
        size = base.get("port")
        largest = _table(PORT_LARGEST, size)
        capacity = yard_size * YARD_TONS
        here = by_port[port_id]
        out.append(PortRepairRow(
            port_id, base.name, base.side, size, base.get("port_max"), base.get("port_damage"), largest,
            _table(PORT_TOTAL, size), yard_size, yard.damage if yard else 0, capacity, yard_size * YARD_POINTS,
            len(here), sum(r.tons for r in here), sum(r.tons for r in here if r.mode == SHIPYARD),
            max(r.tons for r in here), sum(1 for r in here if r.tons > largest and r.tons > capacity)))
    return out


def summary_rows(rows):
    """One SideSummary per side (Allied, Japanese): damaged ships, at sea and in port, in Shipyard mode, tonnage."""
    out = []
    for side in SIDES:
        mine = [r for r in rows if r.side == side]
        in_port = sum(1 for r in mine if r.port_id is not None)
        out.append(SideSummary(side, len(mine), len(mine) - in_port, in_port,
                               sum(1 for r in mine if r.mode == SHIPYARD), sum(r.tons for r in mine)))
    return out
