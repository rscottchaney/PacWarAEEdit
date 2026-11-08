"""Read-only list of land units and air groups scheduled to be withdrawn.

Air groups: the withdraw field (airgroups GROUP_FIELDS, u32 at 392) is an absolute YYMMDD date, the game's "Remove by"
(411219 is 19 Dec 1941); 0 means not scheduled. The return field (u32 at 396, also YYMMDD) is when the group comes
back, 0 or the 9999 sentinel for none. A few scenario dates have an invalid day (440631); the day is clamped to the
last day of the month. A group is overdue when its date is before the game date; the game charges political points
every day until it is withdrawn.

Land units: an i32 at offset 908 (WITHDRAW_DAYS_OFFSET) of the record holds the days until withdrawal, counted from
the save's game date, so the date is the game date plus that many days. 0 means not scheduled; values of 9999 and up
are placeholders of units not yet scheduled to arrive and are skipped. It matches the Withdraw column of the
scenario's land unit table for 249 of the 298 scheduled units of a real save (12 Dec 41) and fell by exactly 1 a day
for 370 units across three consecutive saves; a convoy unit holds its arrival day + 3. The counter never goes
negative: a unit that reached 1 was removed by the game, so land units cannot show as overdue. Not compared yet with
the game's Ground Withdrawal Schedule screen.

A land unit loaded on several ships has fragment records (ids 10000 and up); none of them carried the countdown in
the sample saves, so they need no handling. Nothing here writes to the save.
"""

import calendar
import datetime
import struct
from collections import namedtuple

from . import airgroups, landunits, reports

WITHDRAW_DAYS_OFFSET = 908  # i32 days until withdrawal from the save's game date, see the module docstring
PLACEHOLDER_DAYS = 9999  # this and above: not scheduled yet

LAND_UNIT, AIR_GROUP = "Land unit", "Air group"
NOT_ARRIVED = "not yet arrived"
OVERDUE, DUE, SCHEDULED = "Overdue", "Due", "Scheduled"

WithdrawalRow = namedtuple("WithdrawalRow", "kind id name side type location date days arrived returns")


def parse_yymmdd(value):
    """A YYMMDD integer (years 1900-1999) as a date, or None for 0, the 9999 sentinel or an impossible month.
    A day past the end of the month is clamped to the last day."""
    if value in (0, airgroups.DATE_SENTINEL):
        return None
    yy, rest = divmod(value, 10000)
    month, day = divmod(rest, 100)
    if yy > 99 or not 1 <= month <= 12:
        return None
    year = 1900 + yy
    return datetime.date(year, month, max(1, min(day, calendar.monthrange(year, month)[1])))


def status(days, window):
    if days < 0:
        return OVERDUE
    return DUE if days <= window else SCHEDULED


def _land_rows(save, today):
    rows = []
    for u in landunits.list_land_units(save):
        days = struct.unpack_from("<i", u._data, u._offset + WITHDRAW_DAYS_OFFSET)[0]
        if days <= 0 or days >= PLACEHOLDER_DAYS:
            continue
        arrived = u.arrived
        rows.append(WithdrawalRow(LAND_UNIT, u.id, u.display_name, u.side, u.type,
                                  u.location_name if arrived else NOT_ARRIVED,
                                  today + datetime.timedelta(days=days), days, arrived, None))
    return rows


def _group_rows(save, today):
    rows = []
    for g in airgroups.list_airgroups(save):
        date = parse_yymmdd(g.get("withdraw"))
        if date is None:
            continue
        arrived = g.arrived
        rows.append(WithdrawalRow(AIR_GROUP, g.id, g.name, g.side, g.aircraft_name,
                                  g.location_name if arrived else NOT_ARRIVED, date, (date - today).days, arrived,
                                  parse_yymmdd(g.get("return_date"))))
    return rows


def withdrawal_rows(save):
    """Every scheduled land unit and air group of both sides, arrived or not, sorted by days, kind, then name."""
    day, month, year = reports.game_date(save)
    today = datetime.date(year, month, day)
    rows = _land_rows(save, today) + _group_rows(save, today)
    rows.sort(key=lambda r: (r.days, r.kind, r.name.lower(), r.id))
    return rows
