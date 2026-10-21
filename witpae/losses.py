"""Read-only report of the ships sunk and the aircraft lost so far.

A ship record (section 0x08) is a sunk ship when its days to arrival (i32 at 36) is 19999. For a sunk ship the
cause is the u16 at 348 (below 2000 a device id, the weapon that sank it; 2000 to 2012 are the game's other causes,
see CAUSES), the hex is x u16 at 352 and y u16 at 354 (both 0 = sunk at the base), the base (location id) the u16 at
356, and the date year u8 at 358 (two digits), month u8 at 359 and day u8 at 360; u8 at 363 = 1 means scuttled.
The u16 at 350 is unknown and not shown. The ship bytes at 337 and 396 are the other side's sinking claims (fog of
war) and are not shown. An aircraft record (section 0x20) holds eight i32 from 196: this turn's losses to air
combat, on the ground, to flak and in operations, then the same four totals from 212. The offsets come from
WiTPTracker's reader facts and match the game data seen in the sample saves (Tennessee and Prince of Wales sunk
on 7 Dec 41, the Indianapolis on 8 Dec 41; B-17D, PBY-5, P-40E and A6M2 losses); they have not been compared with
the game's own screens yet. Nothing here writes to the save.
"""

import struct
from collections import namedtuple

from . import aircraft, bases, shiprecords
from .bases import LOCATION_SECTION, NAME_SIZE, RECORD_SIZE as LOCATION_RECORD_SIZE, decode_name, is_place
from .factories import DEVICE_RECORD_SIZE, DEVICE_SECTION, _plain_name

SUNK = 19999  # days to arrival (i32 at shiprecords.ARRIVAL_OFFSET) of a sunk ship
CAUSE_OFFSET = 348  # u16
X_OFFSET = 352  # u16
Y_OFFSET = 354  # u16
LOCATION_OFFSET = 356  # u16
YEAR_OFFSET = 358  # u8, two digits
MONTH_OFFSET = 359  # u8
DAY_OFFSET = 360  # u8
SCUTTLED_OFFSET = 363  # u8, 1 = scuttled
FIRST_CAUSE = 2000  # causes below this are device ids
CAUSES = {2000: "Destroyed while building", 2001: "Cancelled", 2002: "Written off", 2003: "Internal explosion",
          2004: "Grounding", 2005: "Foundered", 2006: "Marine casualty", 2007: "Abandoned", 2008: "Accident",
          2009: "Operational casualty", 2010: "Hit obstruction", 2011: "Collision", 2012: "Kamikaze"}

LOSS_OFFSET = 196  # eight i32: this turn air, ground, flak, ops, then the totals in the same order
KINDS = ("air", "ground", "flak", "ops")
SIDES = ("Allied", "Japanese")

SunkRow = namedtuple("SunkRow", "id name side nation type class_name date cause location scuttled")
AircraftLossRow = namedtuple("AircraftLossRow", "id name side nation type turn_air turn_ground turn_flak turn_ops "
                                                "turn_total air ground flak ops total")
SideSummary = namedtuple("SideSummary", "side ships turn_air turn_ground turn_flak turn_ops turn_total "
                                        "air ground flak ops total")


def _device_name(save, device_id):
    """Name of a device id, "" when the id is outside the device table or unnamed."""
    data = save[DEVICE_SECTION].data
    start = device_id * DEVICE_RECORD_SIZE
    if device_id <= 0 or start + DEVICE_RECORD_SIZE > len(data):
        return ""
    return _plain_name(data, start)


def cause_text(save, code):
    if code < FIRST_CAUSE:
        name = _device_name(save, code)
        return name or f"Unknown (#{code})"
    return CAUSES.get(code) or f"Unknown (#{code})"


def _base_name(save, loc):
    if not loc:
        return "unknown"
    if not is_place(save, loc):
        return f"#{loc}"
    start = loc * LOCATION_RECORD_SIZE
    return decode_name(save[LOCATION_SECTION].data[start:start + NAME_SIZE]) or f"#{loc}"


def location_text(save, x, y, loc):
    """The base name when the ship sank at the base (x and y both 0), otherwise "x,y near <base>"."""
    name = _base_name(save, loc)
    return name if not x and not y else f"{x},{y} near {name}"


def sunk_ships(save):
    """One SunkRow per ship record that is sunk, in id order."""
    rows = []
    for rec in shiprecords.list_ship_records(save):
        if rec.days_to_arrival != SUNK:
            continue
        date = rec._u8(YEAR_OFFSET) * 10000 + rec._u8(MONTH_OFFSET) * 100 + rec._u8(DAY_OFFSET)
        rows.append(SunkRow(rec.id, rec.name, rec.side, rec.nation, rec.type or "?",
                            rec.class_name or f"#{rec.class_id}", date, cause_text(save, rec._u16(CAUSE_OFFSET)),
                            location_text(save, rec._u16(X_OFFSET), rec._u16(Y_OFFSET), rec._u16(LOCATION_OFFSET)),
                            rec._u8(SCUTTLED_OFFSET) == 1))
    return rows


def aircraft_losses(save):
    """One AircraftLossRow per aircraft model with any loss this turn or in total, in id order."""
    rows = []
    for a in aircraft.list_aircraft(save):
        values = struct.unpack_from("<8i", a._data, a._offset + LOSS_OFFSET)
        if not any(values):
            continue
        turn, total = values[:4], values[4:]
        rows.append(AircraftLossRow(a.id, a.name, bases.SIDES.get(a.side_id, "Unknown"), a.nation, a.type,
                                    *turn, sum(turn), *total, sum(total)))
    return rows


def summary_rows(sunk, losses):
    """One SideSummary per side (Allied, Japanese): ships sunk and the aircraft lost this turn and in total."""
    out = []
    for side in SIDES:
        mine = [r for r in losses if r.side == side]
        sums = [sum(getattr(r, f) for r in mine) for f in ("turn_air", "turn_ground", "turn_flak", "turn_ops",
                                                           "turn_total", "air", "ground", "flak", "ops", "total")]
        out.append(SideSummary(side, sum(1 for r in sunk if r.side == side), *sums))
    return out
