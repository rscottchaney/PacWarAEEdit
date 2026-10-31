"""Read-only report of where land units are heading: the units moving to, or preparing for, each target.

The target of a land unit (i16 at offset 102, landunits.TARGET_OFFSET) is its objective: a march destination or the
base it prepares to attack or defend. Units whose target is their own location are preparing to defend it and are not
listed. A target is any location record that has a name, so it includes named minor places (type 0) that are not
bases or towns; its hex is the record's own X/Y and its side is read from the location index like a place's.

UNVERIFIED: these offsets were read from saves and have not been checked on a game screen. Prep percent is the u8 at
104 (0-100); in saves from 11-13 Dec 41 it rose 1-2 a day on stationary units, stayed frozen while a unit was aboard
a ship and read 100 when complete. A unit is aboard a ship when the u8 at 1115 is 1; the ship id is then the u16 at
666 (in one save every embarked unit pointed to a real transport). An embarked unit has no hex of its own (0,0) and
location 0, so its position is its ship's (mapview.ship_hex).

Status: Aboard ship when embarked, else On the march when the unit's hex is not its location's hex (the editor's
"on the march" test, landunits.LandUnit.move_blocker), else Preparing. Distance is the straight hex distance to the
target, ignoring terrain and sea. Nothing here writes to the save.

A unit loaded on several ships is stored as one record per ship: the original id plus fragment records (ids 10000 and
up) with the same name. target_rows keeps every record; group_parts folds the records of one (side, name, target,
status) into a UnitGroup and target_summaries counts formations, a formation being a distinct (side, name). A
formation whose parts differ in status is counted under each of its statuses, so the Preparing, On the march and
Aboard columns of a summary may add up to more than its Units.
"""

import struct
from collections import namedtuple

from . import bases, landunits, mapview, shiprecords

PREP_OFFSET = 104  # u8, 0-100
EMBARKED_OFFSET = 1115  # u8, 1 = aboard a ship
SHIP_OFFSET = 666  # u16 ship id when embarked

PREPARING, MARCHING, ABOARD = "Preparing", "On the march", "Aboard ship"
STATUSES = (PREPARING, MARCHING, ABOARD)
PREP_COMPLETE = 100
MARCH_BLOCKER = "on the march"

TargetRow = namedtuple("TargetRow", "unit_id name side status location prep target_id target_name target_side enemy "
                                    "x y distance")
UnitGroup = namedtuple("UnitGroup", "unit_id name side status parts location prep target_id target_name target_side "
                                    "enemy distance")
TargetSummary = namedtuple("TargetSummary", "target_id name side enemy units preparing marching aboard ready nearest")


def _side_name(save, loc_id):
    return bases.SIDES.get(bases.place_side_id(save, loc_id), "Unknown")


def _row(save, u, ship_names, sides):
    target = u.target_id
    embarked = u._u8(EMBARKED_OFFSET) == 1
    hex_ = (u._i16(bases.X_OFFSET), u._i16(bases.Y_OFFSET))
    if embarked:
        ship = struct.unpack_from("<H", u._data, u._offset + SHIP_OFFSET)[0]
        location = f"aboard {ship_names.get(ship, f'ship {ship}')}"
        pos = mapview.ship_hex(save, ship)
        status = ABOARD
    else:
        pos = hex_ if hex_ != (0, 0) else None
        if u.location_name:
            location = u.location_name
        else:
            location = f"hex {pos[0]},{pos[1]}" if pos else "unknown"
        status = MARCHING if u.move_blocker == MARCH_BLOCKER else PREPARING
    if target not in sides:
        sides[target] = _side_name(save, target)
    target_side = sides[target]
    distance = mapview.hex_distance(pos, bases.place_hex(save, target)) if pos else None
    return TargetRow(u.id, u.display_name, u.side, status, location, u._u8(PREP_OFFSET), target, u.target_name,
                     target_side, target_side != u.side, pos[0] if pos else None, pos[1] if pos else None, distance)


def target_rows(save, side="All"):
    """TargetRows of the arrived land units of a side (All, Allied or Japanese) that have a target other than
    their own location, sorted by target name, then unit name."""
    if side not in ("All", *bases.SIDES.values()):
        raise ValueError(f"unknown side {side!r}")
    ship_names = {s.id: s.name for s in shiprecords.list_ship_records(save)}
    sides = {}
    out = []
    for u in landunits.list_land_units(save):
        target = u.target_id
        if (side != "All" and u.side != side) or not u.arrived or target in (0, u.location_id):
            continue
        if not 0 < target < bases.RECORD_COUNT or not u.target_name:
            continue
        out.append(_row(save, u, ship_names, sides))
    out.sort(key=_sort_key)
    return out


def _sort_key(r):
    return (r.target_name.lower(), r.name.lower(), r.unit_id)


def group_parts(rows):
    """UnitGroups of the rows, one per (side, name, target, status), in the sort order of target_rows.

    unit_id is the lowest id of the parts, prep and distance the minimum over them (distance None when no part has
    one), and location the single part's location, else "aboard N ships" or "N places"."""
    groups = {}
    for r in rows:
        groups.setdefault((r.side, r.name, r.target_id, r.status), []).append(r)
    out = []
    for parts in groups.values():
        parts.sort(key=_sort_key)
        first = min(parts, key=lambda r: r.unit_id)
        distances = [r.distance for r in parts if r.distance is not None]
        if len(parts) == 1:
            location = first.location
        elif first.status == ABOARD:
            location = f"aboard {len(parts)} ships"
        else:
            location = f"{len(parts)} places"
        out.append(UnitGroup(first.unit_id, first.name, first.side, first.status, len(parts), location,
                             min(r.prep for r in parts), first.target_id, first.target_name, first.target_side,
                             first.enemy, min(distances) if distances else None))
    out.sort(key=lambda g: (g.target_name.lower(), g.name.lower(), g.unit_id))
    return out


def target_summaries(rows):
    """One TargetSummary per target of the rows: enemy targets first, then most units, then by name.

    Units counts distinct (side, name) formations, not records; Preparing, On the march, Aboard and Fully prepared
    count the formations with a part in that status (or at prep 100), so they may add up to more than Units."""
    groups = {}
    for r in rows:
        groups.setdefault(r.target_id, []).append(r)
    out = []
    for target, group in groups.items():
        first = group[0]

        def count(test):
            return len({(r.side, r.name) for r in group if test(r)})

        distances = [r.distance for r in group if r.distance is not None]
        out.append(TargetSummary(
            target, first.target_name, first.target_side, first.enemy, count(lambda r: True),
            count(lambda r: r.status == PREPARING), count(lambda r: r.status == MARCHING),
            count(lambda r: r.status == ABOARD), count(lambda r: r.prep == PREP_COMPLETE),
            min(distances) if distances else None))
    out.sort(key=lambda s: (not s.enemy, -s.units, s.name.lower(), s.target_id))
    return out
