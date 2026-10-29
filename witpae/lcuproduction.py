"""Read-only report of what land units lack against their TOE and what that costs in production points.

Rules are from the game manual (13.2.2.6, 13.2.2.7, 13.7). A squad (device types 23 Squad and 24 Engineer) costs
1 armament point plus manpower equal to its load cost; a weapon (any other device that is not a vehicle) costs
armament points equal to its load cost plus the same manpower; a vehicle (types 22 AFV and 25 Vehicle) costs
vehicle points equal to its load cost plus the same manpower. Japanese reinforcements must be filled from
production when they arrive (otherwise they arrive at 25% TOE without charge); Allied units are fed from their
device pools, so daily production is only given for the Japanese. The days to arrival of a land unit (i16 at
offset 564) and the device load cost (i16 at 28 of the device record) are not yet checked in the game. Nothing
here writes to the save.
"""

import struct
from collections import namedtuple

from . import bases, factories, industry, landunits
from .container import SaveFormatError

DAYS_OFFSET = landunits.DAYS_OFFSET
SENTINEL_DAYS = frozenset({9999, 19999, 29999})
DEVICE_TYPE_OFFSET = 26  # u8
DEVICE_LOAD_OFFSET = 28  # i16
DEVICE_TYPES = {0: "Aircraft Cannon", 1: "GA Rocket", 2: "PGM", 3: "GP Bomb", 4: "AP Bomb", 5: "Drop Tank",
                6: "Radar Detect", 7: "Jammer", 8: "Nav Radar", 9: "Aircraft Radar", 10: "Surface Radar",
                11: "AA Rocket", 12: "Flak", 13: "Balloon", 14: "Factory Machine", 15: "ELINT", 16: "Torpedo",
                17: "DP Gun", 18: "Navy Gun", 19: "Army Weapon", 20: "ASW", 21: "Mine", 22: "AFV", 23: "Squad",
                24: "Engineer", 25: "Vehicle", 26: "Resource", 27: "Engine Factory"}
SQUAD_TYPES = frozenset({23, 24})
VEHICLE_TYPES = frozenset({22, 25})

ACTIVE, REINFORCEMENT, NOT_SCHEDULED, NO_DATE = "Active", "Reinforcement", "Not scheduled", "Not arrived (no date)"
STATUSES = (ACTIVE, REINFORCEMENT, NOT_SCHEDULED, NO_DATE)
ARMAMENT, VEHICLE, MANPOWER = "armament", "vehicle", "manpower"
POINTS = (ARMAMENT, VEHICLE, MANPOWER)
POINT_LABELS = {ARMAMENT: "Armament", VEHICLE: "Vehicle", MANPOWER: "Manpower"}
SIDE_IDS = {name: sid for sid, name in bases.SIDES.items()}

Device = namedtuple("Device", "id name type load")
Cost = namedtuple("Cost", "armament vehicle manpower")
UnitRow = namedtuple("UnitRow", "unit status days toe current armament vehicle manpower")
DeviceRow = namedtuple("DeviceRow", "id name type_name kind load pool toe current lacking reinforcement "
                                    "armament vehicle manpower")
Summary = namedtuple("Summary", "kind label pool per_day arrived reinforcement days")


def read_device(save, device_id):
    """The Device of an id, or None when the id is outside the device table."""
    data = save[factories.DEVICE_SECTION].data
    start = device_id * factories.DEVICE_RECORD_SIZE
    if device_id <= 0 or start + factories.DEVICE_RECORD_SIZE > len(data):
        return None
    return Device(device_id, factories._plain_name(data, start), data[start + DEVICE_TYPE_OFFSET],
                  struct.unpack_from("<h", data, start + DEVICE_LOAD_OFFSET)[0])


def cost(device_type, load, count):
    """Armament, vehicle and manpower points of count devices of a type and load cost."""
    if device_type in VEHICLE_TYPES:
        return Cost(0, count * load, count * load)
    return Cost(count if device_type in SQUAD_TYPES else count * load, 0, count * load)


def kind_of(device_type):
    return VEHICLE if device_type in VEHICLE_TYPES else ARMAMENT


def lack(device_id, count, toe_device, toe_count):
    """How many of the TOE device a slot lacks; a different (older) current device counts the whole TOE count."""
    if toe_count <= 0:
        return 0
    if device_id in (0, toe_device):
        return max(0, toe_count - count)
    return toe_count


def days_to_arrival(unit):
    return unit._i16(DAYS_OFFSET)


def status_of(unit):
    days = days_to_arrival(unit)
    if days in SENTINEL_DAYS:
        return NOT_SCHEDULED
    if days > 0:
        return REINFORCEMENT
    return NO_DATE if unit.move_blocker.startswith("not at a base") else ACTIVE


def slots_of(unit):
    """(current device id, count, TOE device id, TOE count) of each slot with a TOE device and count."""
    slots = []
    for k in range(landunits.SLOTS):
        toe_device = unit._i16(landunits.TOE_DEVICE_OFFSET + 2 * k)
        toe_count = unit._i16(landunits.TOE_COUNT_OFFSET + 2 * k)
        if toe_device and toe_count > 0:
            slots.append((unit._i16(landunits.DEVICE_OFFSET + 2 * k), unit._i16(landunits.COUNT_OFFSET + 2 * k),
                          toe_device, toe_count))
    return slots


def _entries(save, side, window, units):
    """[(unit, status, days, slot lacks)] for the units of a side that the window keeps.

    slot lacks is [(TOE device, TOE count, lacking)]: active units lack what their slots miss, reinforcements
    due in 1..window days (None = any) lack their whole TOE, other units nothing.
    """
    units = landunits.list_land_units(save) if units is None else units
    out = []
    for u in units:
        if u.side != side:
            continue
        status, days = status_of(u), days_to_arrival(u)
        if status == REINFORCEMENT and window is not None and days > window:
            continue
        lacks = []
        for device, count, toe_device, toe_count in slots_of(u):
            missing = lack(device, count, toe_device, toe_count) if status == ACTIVE else (
                toe_count if status == REINFORCEMENT else 0)
            lacks.append((toe_device, toe_count, missing))
        out.append((u, status, days, lacks))
    return out


class _Devices:
    """Device records read once each."""

    def __init__(self, save):
        self._save, self._cache = save, {}

    def get(self, device_id):
        if device_id not in self._cache:
            self._cache[device_id] = read_device(self._save, device_id)
        return self._cache[device_id]

    def cost(self, needs):
        """Total Cost of {device id: count}; devices outside the table cost nothing."""
        total = Cost(0, 0, 0)
        for device_id, count in needs.items():
            d = self.get(device_id)
            if d is not None:
                total = Cost(*(a + b for a, b in zip(total, cost(d.type, d.load, count))))
        return total


def unit_rows(save, side="Japanese", window=30, units=None):
    """One UnitRow per land unit of the side; reinforcements only when due within window days (None = any).

    toe and current are the TOE count and the part of it present; the points are what an active unit lacks or
    a reinforcement needs.
    """
    devices = _Devices(save)
    rows = []
    for u, status, days, lacks in _entries(save, side, window, units):
        needs = {}
        for toe_device, _toe_count, missing in lacks:
            if missing:
                needs[toe_device] = needs.get(toe_device, 0) + missing
        toe = sum(t for _d, t, _m in lacks)
        rows.append(UnitRow(u, status, days, toe, toe - sum(m for _d, _t, m in lacks) if status == ACTIVE else 0,
                            *devices.cost(needs)))
    return rows


def pool_of(save, device_id, side):
    try:
        return industry.pool_value(save, device_id, SIDE_IDS[side])
    except SaveFormatError:
        return None


def device_rows(save, side="Japanese", window=30, units=None):
    """One DeviceRow per TOE device that active units lack or reinforcements due in the window need.

    toe, current and lacking are summed over the active units; reinforcement is the whole TOE count of the
    reinforcements in the window; the points cover lacking plus reinforcement.
    """
    totals = {}
    for _u, status, _days, lacks in _entries(save, side, window, units):
        for device_id, toe_count, missing in lacks:
            t = totals.setdefault(device_id, [0, 0, 0, 0])
            if status == ACTIVE:
                t[0] += toe_count
                t[1] += toe_count - missing
                t[2] += missing
            elif status == REINFORCEMENT:
                t[3] += missing
    devices = _Devices(save)
    rows = []
    for device_id, (toe, current, lacking, reinforcement) in totals.items():
        d = devices.get(device_id)
        if d is None or not (lacking or reinforcement):
            continue
        rows.append(DeviceRow(device_id, d.name, DEVICE_TYPES.get(d.type, str(d.type)), POINT_LABELS[kind_of(d.type)],
                              d.load, pool_of(save, device_id, side), toe, current, lacking, reinforcement,
                              *cost(d.type, d.load, lacking + reinforcement)))
    return sorted(rows, key=lambda r: (r.name.lower(), r.id))


def daily_production(places, side="Japanese"):
    """{ARMAMENT, VEHICLE, MANPOWER} -> points made per day by the side's factories with production on."""
    made = dict.fromkeys(POINTS, 0)
    for p in places:
        if p.base.side != side:
            continue
        for f in factories.list_factories(p.base):
            if f.kind == "industry":
                for key, value in industry.factory_flow(f).makes.items():
                    if key in made:
                        made[key] += value
    return made


def summary_rows(save, rows, places, side="Japanese"):
    """One Summary per point type from unit_rows output.

    pool is None when the pools cannot be read. Production (and so days) is only given for the Japanese, whose
    reinforcements are filled from production; for the Allies per_day and days are None. days is the days of
    production needed to cover arrived plus reinforcement needs, None when there is no production.
    """
    try:
        pools = industry.side_pools(save)[SIDE_IDS[side]]
    except SaveFormatError:
        pools = None
    made = daily_production(places, side) if side == "Japanese" else None
    out = []
    for kind in POINTS:
        arrived = sum(getattr(r, kind) for r in rows if r.status == ACTIVE)
        reinforcement = sum(getattr(r, kind) for r in rows if r.status == REINFORCEMENT)
        per_day = None if made is None else made[kind]
        days = (arrived + reinforcement) / per_day if per_day else None
        out.append(Summary(kind, POINT_LABELS[kind], None if pools is None else pools[kind], per_day, arrived,
                           reinforcement, days))
    return out
