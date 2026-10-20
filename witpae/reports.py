"""Read-only reports over a loaded save: base spoilage and ship class upgrades.

Nothing here writes to the save. The spoilage rule is from the game manual
(15.7); the upgrade link is the ship class table's next-stage id (u16 at 256).
"""

import struct
from collections import namedtuple

from . import shiprecords, ships
from .container import SaveFormatError

DATE_SECTION = 0x01
DAY_OFFSET = 42  # i16
MONTH_OFFSET = 44  # i16
YEAR_OFFSET = 46  # i16, two digits
NO_LIMIT_SIZE = 10

SpoilageRow = namedtuple("SpoilageRow", "base size supply supply_limit supply_over fuel fuel_limit fuel_over total_over")
UpgradeRow = namedtuple("UpgradeRow", "ship current target month year months type_change yard location")


def game_date(save):
    """(day, month, year) of the save with a four-digit year."""
    if DATE_SECTION not in save:
        raise SaveFormatError(f"section 0x{DATE_SECTION:02x} (game date) is missing")
    data = save[DATE_SECTION].data
    if len(data) < YEAR_OFFSET + 2:
        raise SaveFormatError(f"section 0x{DATE_SECTION:02x} (game date) is too short")
    day, month, year = (struct.unpack_from("<h", data, pos)[0] for pos in (DAY_OFFSET, MONTH_OFFSET, YEAR_OFFSET))
    return day, month, 1900 + year


def spoilage_limits(port, airfield):
    """(supply limit, fuel limit) for the combined port and airfield size, None when there is no limit."""
    s = port + airfield
    if s >= NO_LIMIT_SIZE:
        return None
    return 5000 + s * s * 3000, 1000 + s * s * 2000


def spoilage_rows(base_list):
    """Rows for the bases and towns whose supply or fuel is over its limit; overs are clipped at 0."""
    rows = []
    for b in base_list:
        port, airfield = b.get("port"), b.get("airfield")
        limits = spoilage_limits(port, airfield)
        if limits is None:
            continue
        supply, fuel = b.get("supply"), b.get("fuel")
        supply_over, fuel_over = max(supply - limits[0], 0), max(fuel - limits[1], 0)
        if supply_over or fuel_over:
            rows.append(SpoilageRow(b, port + airfield, supply, limits[0], supply_over,
                                    fuel, limits[1], fuel_over, supply_over + fuel_over))
    return rows


def upgrade_target(ship_class, classes):
    """The class a ship class upgrades to, None when there is no further stage or the target is unused."""
    target = ship_class.upgrade_id
    return None if target is None else classes.get(target)


def upgrade_rows(save, records=None, classes=None):
    """One row per arrived ship whose class has an upgrade; months is relative to the game date (<= 0 means now).

    Ships not yet arrived are left out: the game hands reinforcements the upgrades of their arrival date.
    records and classes default to every ship record and a class id -> Ship dict.
    """
    if records is None:
        records = shiprecords.list_ship_records(save)
    if classes is None:
        classes = {c.id: c for c in ships.list_ships(save)}
    _day, gm, gy = game_date(save)
    rows = []
    for rec in records:
        if rec.days_to_arrival:
            continue
        current = classes.get(rec.class_id)
        target = None if current is None else upgrade_target(current, classes)
        if target is None:
            continue
        month, year = target.date
        change = "" if current.type == target.type else f"{current.type} -> {target.type}"
        months = (year * 12 + month) - ((gy % 100) * 12 + gm)
        rows.append(UpgradeRow(rec, current, target, month, year, months, change, target.yard_size, rec.location))
    return rows
