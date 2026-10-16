"""Task force and port ship chains (sections 0x08, 0x13 and 0x46).

Every ship sits in exactly one chain: the chain of its task force (ship u16 at
62) or, when docked outside a task force, the chain of its port (u16 at 60).
Each chain is a doubly linked list through the ship records (next at 64,
previous at 66, 0 ends it). The location record of the TF or port holds the
ship count (656) and the last ship of the chain (818). The TF table (0x46)
holds each TF's flagship at 44. The layout was mapped by diffing in-game
saves; moves made here were verified in-game (slot 27).
"""

import struct
from collections import namedtuple

from . import shiprecords
from .airgroups import SHIP_RECORD_COUNT, SHIP_RECORD_SIZE, SHIP_SECTION
from .bases import (LOCATION_SECTION, NAME_SIZE, RECORD_COUNT, RECORD_SIZE as LOCATION_RECORD_SIZE, SIDES,
                    TYPE_OFFSET, decode_name, is_place, list_places, place_hex, place_side_id)
from .factories import _plain_name

TF_SECTION = 0x46
TF_RECORD_SIZE = 556
TF_BASE_ID = 14000
TF_TYPE = 12
FLAGSHIP_OFFSET = 44
PORT_OFFSET = 422  # port size in the location record, as in bases.FIELDS
NEXT_OFFSET = 64
PREV_OFFSET = 66
COUNT_OFFSET = 656
LAST_OFFSET = 818

# Orders, in the TF table row (0x46). Codes marked "?" were not seen in a game save.
MISSION_OFFSET = 349
HOME_PORT_OFFSET = 54
DEST_OFFSET = 56
DEST_COPY_OFFSET = 58
ROUTE_OFFSET = 118
ROUTE_FLAGS_OFFSET = 318
ROUTE_LENGTH_OFFSET = 320
ORDER_FLAGS_OFFSET = 322
ORDER_MARK_OFFSET = 490
ORDER_BYTE_OFFSET = 8
HOME_PORT_BYTE_BITS = 0x50
DEST_BYTE_BITS = 0xA0
HOME_PORT_FLAGS = 2
DEST_FLAGS = 4
# Location record (0x13) of the TF: destination id, destination hex, and the hex again.
LOC_DEST_OFFSET = 660
LOC_DEST_HEX_OFFSET = 662
LOC_DEST_HEX_COPY_OFFSET = 760
MISSIONS = {
    1: "Air Combat", 2: "Surface Combat", 3: "Bombardment?", 4: "Fast Transport?", 5: "Transport",
    6: "Replenishment", 7: "Mine Laying?", 8: "Sub Patrol", 9: "Sub Minelaying?", 10: "Sub Transport?",
    11: "Cargo", 12: "Barge", 13: "Air Transport", 14: "CV Escort?", 15: "Amphibious", 16: "ASW Combat",
    17: "PT Boat", 18: "Tanker", 19: "Mine Sweeping?", 20: "Landing Craft?", 21: "Midget Submarine",
    22: "Support", 23: "Local Minesweeper", 24: "Midget Sub Carrier", 25: "Follow?",
}

Destination = namedtuple("Destination", "id label kind")  # kind: "tf" or "port"


def _u16(data, pos):
    return struct.unpack_from("<H", data, pos)[0]


def _ship(save, ship_id, offset):
    return _u16(save[SHIP_SECTION].data, ship_id * SHIP_RECORD_SIZE + offset)


def _put_ship(save, ship_id, offset, value):
    struct.pack_into("<H", save[SHIP_SECTION].data, ship_id * SHIP_RECORD_SIZE + offset, value)


def _loc(save, loc_id, offset):
    return _u16(save[LOCATION_SECTION].data, loc_id * LOCATION_RECORD_SIZE + offset)


def _put_loc(save, loc_id, offset, value):
    struct.pack_into("<H", save[LOCATION_SECTION].data, loc_id * LOCATION_RECORD_SIZE + offset, value)


def _ship_exists(save, ship_id):
    return (isinstance(ship_id, int) and not isinstance(ship_id, bool) and 0 <= ship_id < SHIP_RECORD_COUNT
            and (ship_id + 1) * SHIP_RECORD_SIZE <= len(save[SHIP_SECTION].data)
            and bool(_plain_name(save[SHIP_SECTION].data, ship_id * SHIP_RECORD_SIZE)))


def is_task_force(save, tf_id):
    """True when tf_id is a TF location record (type 12) with a row in the TF table."""
    if isinstance(tf_id, bool) or not isinstance(tf_id, int):
        return False
    data = save[LOCATION_SECTION].data
    if not TF_BASE_ID <= tf_id < RECORD_COUNT or (tf_id + 1) * LOCATION_RECORD_SIZE > len(data):
        return False
    if (tf_id - TF_BASE_ID + 1) * TF_RECORD_SIZE > len(save[TF_SECTION].data):
        return False
    return struct.unpack_from("<h", data, tf_id * LOCATION_RECORD_SIZE + TYPE_OFFSET)[0] == TF_TYPE


def ship_side(save, ship_id):
    nation = save[SHIP_SECTION].data[ship_id * SHIP_RECORD_SIZE + shiprecords.NATION_OFFSET]
    return "Japanese" if nation in shiprecords.JAPANESE_NATIONS else "Allied"


def _name(save, loc_id):
    start = loc_id * LOCATION_RECORD_SIZE
    return decode_name(save[LOCATION_SECTION].data[start:start + NAME_SIZE]).strip()


def _arrived(save, ship_id):
    pos = ship_id * SHIP_RECORD_SIZE + shiprecords.ARRIVAL_OFFSET
    return struct.unpack_from("<I", save[SHIP_SECTION].data, pos)[0] == 0


def chain(save, loc_id):
    """Ship ids of the chain of a TF or port, first to last.

    Raises ValueError on any inconsistency: a broken link, a ship that does not
    belong to the chain, a count that disagrees with the walk, a last ship
    that is not the end of the chain.
    """
    is_tf = isinstance(loc_id, int) and loc_id >= TF_BASE_ID
    if not (is_task_force(save, loc_id) if is_tf else is_place(save, loc_id)):
        raise ValueError(f"location {loc_id!r} is not a task force, base or town")
    what = f"TF {loc_id}" if is_tf else f"port {loc_id}"
    count, last = _loc(save, loc_id, COUNT_OFFSET), _loc(save, loc_id, LAST_OFFSET)
    if count == 0:
        if last:
            raise ValueError(f"{what} has no ships but a last ship {last}")
        return []
    out = []
    cur, nxt = last, 0
    while cur:
        if len(out) >= count:
            raise ValueError(f"{what} chain is longer than its ship count {count}")
        if not _ship_exists(save, cur):
            raise ValueError(f"{what} chain has an invalid ship {cur}")
        if _ship(save, cur, NEXT_OFFSET) != nxt:
            raise ValueError(f"{what} chain is broken at ship {cur}")
        owner_tf = _ship(save, cur, shiprecords.TASK_FORCE_OFFSET)
        owner_base = _ship(save, cur, shiprecords.BASE_OFFSET)
        if (owner_tf != loc_id) if is_tf else (owner_tf != 0 or owner_base != loc_id):
            raise ValueError(f"ship {cur} is in the {what} chain but is not recorded there")
        out.append(cur)
        cur, nxt = _ship(save, cur, PREV_OFFSET), cur
    if len(out) != count:
        raise ValueError(f"{what} chain has {len(out)} ships but its count is {count}")
    out.reverse()
    return out


def _flagship(save, tf_id):
    return _u16(save[TF_SECTION].data, (tf_id - TF_BASE_ID) * TF_RECORD_SIZE + FLAGSHIP_OFFSET)


def _put_flagship(save, tf_id, ship_id):
    struct.pack_into("<H", save[TF_SECTION].data, (tf_id - TF_BASE_ID) * TF_RECORD_SIZE + FLAGSHIP_OFFSET, ship_id)


def _tf_u16(save, tf_id, offset):
    return _u16(save[TF_SECTION].data, (tf_id - TF_BASE_ID) * TF_RECORD_SIZE + offset)


def _put_tf_u16(save, tf_id, offset, value):
    struct.pack_into("<H", save[TF_SECTION].data, (tf_id - TF_BASE_ID) * TF_RECORD_SIZE + offset, value)


class TaskForce:
    """Read view of a TF: id, name, hex, flagship, orders and ships in chain order."""

    def __init__(self, save, tf_id):
        if not is_task_force(save, tf_id):
            raise ValueError(f"{tf_id!r} is not a task force")
        self._save = save
        self.id = tf_id

    @property
    def name(self):
        return _name(self._save, self.id)

    @property
    def hex(self):
        return place_hex(self._save, self.id)

    @property
    def flagship(self):
        return _flagship(self._save, self.id)

    @property
    def ships(self):
        return chain(self._save, self.id)

    @property
    def ship_count(self):
        return _loc(self._save, self.id, COUNT_OFFSET)

    @property
    def side(self):
        ships = self.ships
        return ship_side(self._save, ships[0]) if ships else ""

    @property
    def mission(self):
        return self._save[TF_SECTION].data[(self.id - TF_BASE_ID) * TF_RECORD_SIZE + MISSION_OFFSET]

    @property
    def mission_label(self):
        return MISSIONS.get(self.mission, f"Unknown ({self.mission})")

    @property
    def home_port(self):
        return _tf_u16(self._save, self.id, HOME_PORT_OFFSET)

    @property
    def destination(self):
        """Destination id from the TF table; 0 means no destination."""
        return _tf_u16(self._save, self.id, DEST_OFFSET)


def set_flagship(save, tf_id, ship_id):
    """Make ship_id (a member of the TF) its flagship. ValueError, nothing written, on refusal."""
    ships = chain(save, tf_id) if is_task_force(save, tf_id) else None
    if ships is None:
        raise ValueError(f"{tf_id!r} is not a task force")
    if isinstance(ship_id, bool) or not isinstance(ship_id, int) or ship_id not in ships:
        raise ValueError(f"{ship_id!r} is not a ship of TF {tf_id}")
    if _flagship(save, tf_id) != ship_id:
        _put_flagship(save, tf_id, ship_id)


def _checked_tf(save, tf_id):
    """Validate a TF and its chain; returns the ships."""
    if not is_task_force(save, tf_id):
        raise ValueError(f"{tf_id!r} is not a task force")
    return chain(save, tf_id)


def _int(value, what):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{value!r} is not a valid {what}")
    return value


def port_size(save, place_id):
    """Port size of a base (0 for towns and bases without a port)."""
    return struct.unpack_from("<h", save[LOCATION_SECTION].data, place_id * LOCATION_RECORD_SIZE + PORT_OFFSET)[0]


def set_mission(save, tf_id, code):
    """Set the TF's mission code (1..25). Writes only the mission byte; ValueError on refusal."""
    _checked_tf(save, tf_id)
    code = _int(code, "mission code")
    if not 1 <= code <= max(MISSIONS):
        raise ValueError(f"mission code must be between 1 and {max(MISSIONS)}")
    pos = (tf_id - TF_BASE_ID) * TF_RECORD_SIZE + MISSION_OFFSET
    save[TF_SECTION].data[pos] = code


def _or_byte(save, tf_id, bits):
    save[TF_SECTION].data[(tf_id - TF_BASE_ID) * TF_RECORD_SIZE + ORDER_BYTE_OFFSET] |= bits


def _or_flags(save, tf_id, bits):
    pos = ORDER_FLAGS_OFFSET
    _put_tf_u16(save, tf_id, pos, _tf_u16(save, tf_id, pos) | bits)


def set_home_port(save, tf_id, place_id):
    """Set the TF's home port: a base or town of its side that has a port. ValueError on refusal."""
    _checked_tf(save, tf_id)
    place_id = _int(place_id, "home port")
    if not is_place(save, place_id):
        raise ValueError(f"{place_id} is not a base or town")
    if SIDES.get(place_side_id(save, place_id)) != TaskForce(save, tf_id).side:
        raise ValueError("home port belongs to the other side")
    if port_size(save, place_id) <= 0:
        raise ValueError(f"{_name(save, place_id)} has no port")
    if _tf_u16(save, tf_id, HOME_PORT_OFFSET) == place_id:
        return
    _put_tf_u16(save, tf_id, HOME_PORT_OFFSET, place_id)
    _or_byte(save, tf_id, HOME_PORT_BYTE_BITS)
    _or_flags(save, tf_id, HOME_PORT_FLAGS)
    _put_tf_u16(save, tf_id, ORDER_MARK_OFFSET, 2)


def set_destination(save, tf_id, place_id):
    """Order the TF to a base or town of either side, as the game does. ValueError on refusal.

    The route is just the TF's hex and the destination hex; the game plans the real path.
    """
    _checked_tf(save, tf_id)
    place_id = _int(place_id, "destination")
    if not is_place(save, place_id):
        raise ValueError(f"{place_id} is not a base or town")
    here, there = place_hex(save, tf_id), place_hex(save, place_id)
    if here == there:
        raise ValueError("task force is already in the destination's hex")
    if _tf_u16(save, tf_id, DEST_OFFSET) == place_id:
        return
    _put_tf_u16(save, tf_id, DEST_OFFSET, place_id)
    _put_tf_u16(save, tf_id, DEST_COPY_OFFSET, place_id)
    for k, v in enumerate(here + there):
        _put_tf_u16(save, tf_id, ROUTE_OFFSET + 2 * k, v & 0xFFFF)
    _put_tf_u16(save, tf_id, ROUTE_LENGTH_OFFSET, 2)
    _put_tf_u16(save, tf_id, ROUTE_FLAGS_OFFSET, 0)
    _or_byte(save, tf_id, DEST_BYTE_BITS)
    _or_flags(save, tf_id, DEST_FLAGS)
    _put_tf_u16(save, tf_id, ORDER_MARK_OFFSET, 2)
    _put_loc(save, tf_id, LOC_DEST_OFFSET, place_id)
    for off in (LOC_DEST_HEX_OFFSET, LOC_DEST_HEX_COPY_OFFSET):
        _put_loc(save, tf_id, off, there[0] & 0xFFFF)
        _put_loc(save, tf_id, off + 2, there[1] & 0xFFFF)


def _members(save, tf_id):
    if not is_task_force(save, tf_id):
        raise ValueError(f"{tf_id!r} is not a task force")
    data = save[SHIP_SECTION].data
    return [shiprecords.ShipRecord(save, s, _plain_name(data, s * SHIP_RECORD_SIZE)) for s in chain(save, tf_id)]


def repair_task_force(save, tf_id):
    """Clear fires and damage on every ship of the TF; returns the ids of ships that changed."""
    changed = []
    for rec in _members(save, tf_id):
        if any(rec.get(n) for n in shiprecords.DAMAGE_FIELDS):
            rec.repair_all()
            changed.append(rec.id)
    return changed


def refuel_task_force(save, tf_id):
    """Fill every ship of the TF to its class fuel (never lowering it); returns the ids that changed."""
    members = _members(save, tf_id)
    changed = []
    for rec in members:
        top = rec.max_fuel
        if top is not None and rec.get("fuel") < top:
            rec.set("fuel", top)
            changed.append(rec.id)
    return changed


def list_task_forces(save):
    """Every TF with at least one ship, in id order."""
    return [TaskForce(save, i) for i in range(TF_BASE_ID, RECORD_COUNT)
            if is_task_force(save, i) and _loc(save, i, COUNT_OFFSET)]


def _plan(save, ship_id, dest_id):
    """Validate a move and return what is needed to write it, or raise ValueError."""
    if not _ship_exists(save, ship_id):
        raise ValueError(f"{ship_id!r} is not a ship")
    if isinstance(dest_id, bool) or not isinstance(dest_id, int):
        raise ValueError(f"{dest_id!r} is not a destination")
    if not _arrived(save, ship_id):
        raise ValueError("ship has not arrived yet")
    side = ship_side(save, ship_id)
    src_tf = _ship(save, ship_id, shiprecords.TASK_FORCE_OFFSET)
    src = src_tf or _ship(save, ship_id, shiprecords.BASE_OFFSET)
    if not src:
        raise ValueError("ship is at sea alone and is in no task force or port")
    dest_is_tf = dest_id >= TF_BASE_ID
    if not (is_task_force(save, dest_id) if dest_is_tf else is_place(save, dest_id)):
        raise ValueError(f"{dest_id} is not a task force, base or town")
    if dest_id == src:
        raise ValueError("ship is already there")
    if not src_tf and not dest_is_tf:
        raise ValueError("a ship cannot move from one port to another")
    src_ships = chain(save, src)
    if ship_id not in src_ships:
        raise ValueError(f"ship {ship_id} is not in its own chain")
    dest_ships = chain(save, dest_id)
    if src_tf:
        if len(src_ships) < 2:
            raise ValueError("cannot move the last ship out of a task force")
        if _flagship(save, src) not in src_ships:
            raise ValueError(f"flagship of TF {src} is not one of its ships")
    if place_hex(save, src) != place_hex(save, dest_id):
        raise ValueError("destination is not in the same hex")
    if dest_is_tf:
        if not dest_ships:
            raise ValueError(f"TF {dest_id} has no ships")
        if _flagship(save, dest_id) not in dest_ships:
            raise ValueError(f"flagship of TF {dest_id} is not one of its ships")
        if any(ship_side(save, s) != side for s in dest_ships):
            raise ValueError("task force belongs to the other side")
    elif SIDES.get(place_side_id(save, dest_id)) != side:
        raise ValueError("port belongs to the other side")
    return src, src_tf, src_ships, dest_is_tf, dest_ships


def _write_chain(save, loc_id, ships):
    """Rewrite links, count and last ship of a chain from its ordered ship list."""
    for k, s in enumerate(ships):
        _put_ship(save, s, PREV_OFFSET, ships[k - 1] if k else 0)
        _put_ship(save, s, NEXT_OFFSET, ships[k + 1] if k + 1 < len(ships) else 0)
    _put_loc(save, loc_id, COUNT_OFFSET, len(ships))
    _put_loc(save, loc_id, LAST_OFFSET, ships[-1] if ships else 0)


def move_ship(save, ship_id, destination):
    """Move a ship to another TF (id 14000+) or to a port (location id), as the game does.

    Everything is validated before anything is written; ValueError on refusal.
    """
    src, src_tf, src_ships, dest_is_tf, dest_ships = _plan(save, ship_id, destination)
    new_src = [s for s in src_ships if s != ship_id]
    # A port appends at the end; a TF inserts before the first larger id (ascending order;
    # a few saved TFs are not sorted, so this is not a plain sort).
    at = len(dest_ships)
    if dest_is_tf:
        at = next((k for k, s in enumerate(dest_ships) if s > ship_id), at)
    new_dest = dest_ships[:at] + [ship_id] + dest_ships[at:]
    if src_tf and _flagship(save, src) == ship_id:
        _put_flagship(save, src, new_src[-1])
    _write_chain(save, src, new_src)
    _write_chain(save, destination, new_dest)
    _put_ship(save, ship_id, shiprecords.TASK_FORCE_OFFSET, destination if dest_is_tf else 0)
    _put_ship(save, ship_id, shiprecords.BASE_OFFSET, 0 if dest_is_tf else destination)


def can_move(save, ship_id, destination):
    """True when move_ship would accept this move."""
    try:
        _plan(save, ship_id, destination)
    except ValueError:
        return False
    return True


def destinations(save, ship_id):
    """Valid destinations for a ship as Destination tuples (TFs first, then ports); [] if none."""
    if not _ship_exists(save, ship_id):
        return []
    src = _ship(save, ship_id, shiprecords.TASK_FORCE_OFFSET) or _ship(save, ship_id, shiprecords.BASE_OFFSET)
    if not src or not (is_task_force(save, src) if src >= TF_BASE_ID else is_place(save, src)):
        return []
    here = place_hex(save, src)
    # Only candidates in the ship's hex are worth the full validation in _plan.
    candidates = [t.id for t in list_task_forces(save)] + [p.id for p in list_places(save)]
    out = []
    for dest in candidates:
        if place_hex(save, dest) != here:
            continue
        try:
            _plan(save, ship_id, dest)
        except ValueError:
            continue
        if dest >= TF_BASE_ID:
            label = " ".join(p for p in (f"TF {dest}", _name(save, dest)) if p)
            out.append(Destination(dest, f"{label} ({_loc(save, dest, COUNT_OFFSET)} ships)", "tf"))
        else:
            out.append(Destination(dest, f"{_name(save, dest)} (port)", "port"))
    return out
