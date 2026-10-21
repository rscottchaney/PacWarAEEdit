"""Read-only report of Japanese ship construction (ships not yet arrived).

Rules are from the game manual (13.4, 13.4.1, 13.2.2.8). Only the Japanese build
ships; Allied reinforcements arrive on schedule. For a ship of durability D with
L days to arrival: L > 30 x D is a blue print (1 day removed free per day), L
over 10 x D up to 30 x D can be accelerated (1 day free per day, 1 more for D
shipyard points), and L up to 10 x D is being built (D points per day remove 1
day, accelerated 3 x D points remove 2). The per-ship Normal / Accelerate / Halt
setting is not located in the save, so normal construction is assumed, and the
order in which a short pool pays for ships is not known. Midget submarines (type 28) use no points: they sit
at 1 day to arrival without progressing, so they get a status of their own. Nothing here writes to
the save.
"""

import datetime
from collections import namedtuple

from . import factories, industry, reports, shiprecords, ships
from .container import SaveFormatError

BLUEPRINT, CAN_ACCELERATE, BUILDING = "Blue print", "Can accelerate", "Building"
MIDGET = "Midget sub (no points)"
COUNTED = (BUILDING, CAN_ACCELERATE, BLUEPRINT)  # the statuses that cost or could cost points
STATUSES = COUNTED + (MIDGET,)
MIDGET_TYPE = 28  # SSX
NAVAL, MERCHANT = "Naval", "Merchant"
YARDS = (NAVAL, MERCHANT)
# Class type ids built with naval shipyard points (WitPTracker's list); every other type uses merchant points.
NAVAL_TYPES = frozenset({1, 2, 3, 5, 6, 7, 8, 9, 10, 12, 13, 14, 15, 16, 17, 19, 21, 22, 23, 24, 25, 26, 27, 28,
                         30, 31, 32, 33, 38, 39, 51})
YARD_FACTORY = {NAVAL: 522, MERCHANT: 523}
HI_PER_POINT = 3  # manual 13.2.2.8: one shipyard point per day for 3 HI
JAPAN = 0  # side id of the Japanese pools

ProductionRow = namedtuple("ProductionRow", "ship current type durability yard delay arrival status starts_in "
                                            "per_day to_finish accel_per_day")
YardSummary = namedtuple("YardSummary", "yard size hi_per_day pool needed net building can_accelerate blueprint")


def status_of(durability, delay):
    """Construction status of a ship with the given class durability and days to arrival (delay > 0)."""
    if delay > 30 * durability:
        return BLUEPRINT
    return CAN_ACCELERATE if delay > 10 * durability else BUILDING


def yard_of(type_id):
    return NAVAL if type_id in NAVAL_TYPES else MERCHANT


def make_row(rec, current, type_id, today=None):
    """The row of one unarrived ship record; today is the (day, month, year) of the save or None."""
    durability, delay = current.get("durability"), rec.days_to_arrival
    midget = type_id == MIDGET_TYPE
    status = MIDGET if midget else status_of(durability, delay)
    arrival = None
    if today is not None:
        day, month, year = today
        try:
            arrival = datetime.date(year, month, day) + datetime.timedelta(days=delay)
        except (ValueError, OverflowError):
            arrival = None
    building = status == BUILDING
    return ProductionRow(
        rec, current, current.type, durability, yard_of(type_id), delay, arrival, status,
        0 if midget else max(0, delay - 10 * durability), durability if building else 0,
        0 if midget else durability * min(delay, 10 * durability),
        None if status in (BLUEPRINT, MIDGET) else (3 * durability if building else durability))


def production_rows(save, records=None, classes=None):
    """One row per Japanese ship that has not arrived yet.

    records and classes default to every ship record and a class id -> Ship dict. Ships whose class record
    is out of range are left out.
    """
    if records is None:
        records = shiprecords.list_ship_records(save)
    if classes is None:
        classes = {c.id: c for c in ships.list_ships(save)}
    try:
        today = reports.game_date(save)
    except SaveFormatError:
        today = None
    rows = []
    for rec in records:
        current = classes.get(rec.class_id)
        if rec.side != "Japanese" or not rec.days_to_arrival or current is None:
            continue
        rows.append(make_row(rec, current, current._u8(ships.TYPE_OFFSET), today))
    return rows


def yard_sizes(places):
    """yard -> size of the Japanese shipyard factories with production on (points made per day)."""
    sizes = dict.fromkeys(YARDS, 0)
    for p in places:
        if p.base.side != "Japanese":
            continue
        for f in factories.list_factories(p.base):
            for yard, type_id in YARD_FACTORY.items():
                if f.type == type_id and f.production_on:
                    sizes[yard] += f.size
    return sizes


def summary_rows(save, rows, places):
    """One YardSummary per yard; pool is None when the side pools cannot be read."""
    try:
        pools = industry.side_pools(save)[JAPAN]
    except SaveFormatError:
        pools = None
    sizes = yard_sizes(places)
    out = []
    for yard in YARDS:
        mine = [r for r in rows if r.yard == yard]
        needed = sum(r.per_day for r in mine)
        counts = [sum(1 for r in mine if r.status == s) for s in COUNTED]
        out.append(YardSummary(yard, sizes[yard], sizes[yard] * HI_PER_POINT,
                               None if pools is None else pools[yard.lower()], needed, sizes[yard] - needed,
                               *counts))
    return out
