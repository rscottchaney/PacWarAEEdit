"""Read-only report of the minefields.

Section 0x1E holds 6000 records of 20 bytes. Per record: hex x u16 at 0, hex y u16 at 2, side u16 at 4 (0 Japanese,
1 Allied, the same codes as bases.SIDES), a u16 at 6 that is probably the minefield's detection level by the enemy
(values 0, 2 and 9 seen; shown as "Detection (unverified)"), the mine device id u16 at 8 (a device of section 0x1F,
device type 21 Mine, for example 1645 Mk 6 Mine, 1650 Mk XVII Mine, 1651 VH Mk II Mine, 1710 Type 4 Mine, 1711 Type
88 Mine) and the number of mines u16 at 10. Bytes 12 to 19 were all zero. The layout comes from WiTPTracker's
minefield reader and was checked on the sample saves (wpae016: 67 used records, the biggest is Bataan with two Mk 6
fields of 495 and 500 mines). A record is used when its mine count is above 0; like the tracker, records with x or y
of 0 or above 250 or a count of 32768 or more are skipped, and so are records whose side is neither 0 nor 1.
Several fields can share a hex (manual 6.6.1), so the report also groups them by (hex, side).
Decay (manual 6.6.1.2.1) is 1% a day at a friendly base with port size 1 or more, 5% a day in shallow water and 33%
a day in deep water. The save has no water depth, so a hex with a base or town of the minefield's own side with
port size 1 or more is "1%/day (friendly port)" and every other hex "5-33%/day". Minefield tenders (manual
6.6.1.2.2): each ACM ship (ship class type 74) that is disbanded at a base, that is docked (ship base set) and in no
task force, protects 150 mines there; ACMs in a task force do not count. The report counts the arrived ACMs of the
minefield's side docked at a base or town in the hex. Nothing here writes to the save.
"""

import struct
from collections import namedtuple

from . import bases, ships, shiprecords
from .container import SaveFormatError
from .shiprepair import _device_name

SECTION = 0x1E
RECORD_SIZE = 20
RECORD_COUNT = 6000
MAX_HEX = 250
MAX_MINES = 32768  # counts at or above this are skipped
ACM_TYPE = 74  # ship class type of a minefield tender
MINES_PER_ACM = 150
SIDES = ("Allied", "Japanese")
DECAY_PORT = "1%/day (friendly port)"
DECAY_OPEN = "5-33%/day"
OPEN_SEA = "-"

MineField = namedtuple("MineField", "id x y side place_id place_name device_id device_name mines detection")
MineHex = namedtuple("MineHex", "x y side place_id place mines fields types detection decay acms protected")
SideSummary = namedtuple("SideSummary", "side fields hexes mines by_device")


def _place_hexes(save):
    """{hex: Base} of the bases and towns, a base winning over a town in the same hex."""
    out = {}
    for b in bases.list_bases(save, include_towns=True):
        key = bases.place_hex(save, b.id)
        if key not in out or (out[key].kind != "Base" and b.kind == "Base"):
            out[key] = b
    return out


def list_fields(save):
    """One MineField per used record, in record order."""
    if SECTION not in save:
        raise SaveFormatError("save has no minefield section")
    data = save[SECTION].data
    places = _place_hexes(save)
    rows = []
    for rec in range(min(RECORD_COUNT, len(data) // RECORD_SIZE)):
        x, y, side, detection, device, mines = struct.unpack_from("<6H", data, rec * RECORD_SIZE)
        if (mines == 0 or mines >= MAX_MINES or not 0 < x <= MAX_HEX or not 0 < y <= MAX_HEX
                or side not in bases.SIDES):
            continue
        place = places.get((x, y))
        rows.append(MineField(rec, x, y, bases.SIDES[side], place.id if place else None,
                              place.name if place else None, device, _device_name(save, device), mines, detection))
    return rows


def types_text(pairs):
    """"Mk 6 Mine 995" or "Mk XVII Mine 300; Mk 6 Mine 145" from (device name, mines) pairs, largest first."""
    totals = {}
    for name, mines in pairs:
        totals[name] = totals.get(name, 0) + mines
    return "; ".join(f"{name} {mines}" for name, mines in sorted(totals.items(), key=lambda t: (-t[1], t[0])))


def _acm_counts(save):
    """{(hex, side): arrived ACMs docked at a base or town in that hex and in no task force}."""
    hex_of = {b.id: bases.place_hex(save, b.id) for b in bases.list_bases(save, include_towns=True)}
    out = {}
    for rec in shiprecords.list_ship_records(save):
        if rec.days_to_arrival != 0 or not rec.base_id or rec.task_force or rec.base_id not in hex_of:
            continue
        start = rec._class_start()
        if start is None or save[ships.SHIP_SECTION].data[start + ships.TYPE_OFFSET] != ACM_TYPE:
            continue
        key = (hex_of[rec.base_id], rec.side)
        out[key] = out.get(key, 0) + 1
    return out


def hex_rows(save, fields):
    """One MineHex per (hex, side) of the fields, largest minefield first."""
    places = _place_hexes(save)
    acms = _acm_counts(save)
    groups = {}
    for f in fields:
        groups.setdefault((f.x, f.y, f.side), []).append(f)
    rows = []
    for (x, y, side), group in groups.items():
        place = places.get((x, y))
        friendly = place is not None and place.side == side
        if place is None:
            text = OPEN_SEA
        elif place.side in SIDES and not friendly:
            text = f"{place.name} (enemy base)"
        else:
            text = place.name
        mines = sum(f.mines for f in group)
        ported = friendly and place.get("port") >= 1
        count = acms.get(((x, y), side), 0)
        rows.append(MineHex(x, y, side, place.id if place else None, text, mines, len(group),
                            types_text((f.device_name, f.mines) for f in group), max(f.detection for f in group),
                            DECAY_PORT if ported else DECAY_OPEN, count, min(mines, count * MINES_PER_ACM)))
    rows.sort(key=lambda r: (-r.mines, r.side, r.y, r.x))
    return rows


def summary_rows(fields, hexes):
    """One SideSummary per side (Allied, Japanese): fields, hexes, mines and the mines by device (largest first)."""
    out = []
    for side in SIDES:
        mine = [f for f in fields if f.side == side]
        totals = {}
        for f in mine:
            totals[f.device_name] = totals.get(f.device_name, 0) + f.mines
        out.append(SideSummary(side, len(mine), sum(1 for h in hexes if h.side == side), sum(totals.values()),
                               tuple(sorted(totals.items(), key=lambda t: (-t[1], t[0])))))
    return out
