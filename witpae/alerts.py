"""Read-only list of the actionable problems the other reports find, in one place.

Every check reuses a report module and only turns its rows into Alert tuples, so the facts (spoilage limits, the
victory value of a base, which repair yard fits which ship, ...) are the ones those reports show. Categories, in this
order: Low supply (victory.base_rows for the points at stake), Spoilage (reports.spoilage_rows), Repair (damaged ships
too big for the port they sit in, and ports whose Shipyard-mode queue is bigger than the yard; "too big" is the Ship
repair report's oversize rule: the ship is above both the port's largest ship and the yard capacity), Minefields
(one alert per side: the mines in its own ports that no docked ACM protects, and about how many they lose a day),
Pilots (nations with a pilot pool below a threshold), Aircraft (models in production whose arrived groups are missing
more planes than the pool plus PRODUCTION_DAYS of production; models nobody builds are left out) and Engines
(Japanese engines the factories build fewer of than the airframe factories use).
A check that cannot read its section (SaveFormatError, IndexError or a short section) is skipped on its own; collect
returns the names of the skipped categories next to the alerts. Thresholds are arguments, they are not saved.
Nothing here writes to the save.
"""

import struct
from collections import namedtuple

from . import (airproduction, bases, industry, minefields, pilotpool, regions, reports, shiprepair, victory)
from .container import SaveFormatError

Alert = namedtuple("Alert", "category side subject detail kind target_id sort_value")

DEFAULTS = {"supply_pct": 50, "pilot_pool": 100}
CATEGORIES = ("Low supply", "Spoilage", "Repair", "Minefields", "Pilots", "Aircraft", "Engines")
KINDS = ("base", "ship", "pilots", "aircraft", "engine", "minefields")
PRODUCTION_DAYS = 30  # an aircraft shortage the factories fill within this many days is not an alert
SKIPPABLE = (SaveFormatError, IndexError, struct.error)


class _Context:
    """The inputs several checks share, each built on first use."""

    def __init__(self, save, places, groups):
        self.save = save
        self._places = places
        self._groups = groups
        self._base_list = None

    @property
    def base_list(self):
        if self._base_list is None:
            self._base_list = bases.list_bases(self.save, include_towns=True)
        return self._base_list

    @property
    def places(self):
        if self._places is None:
            self._places = industry.list_industry_places(self.save, regions.default_regions())
        return self._places

    @property
    def groups(self):
        return self._groups


def _low_supply(ctx, supply_pct, _pilot_pool):
    points = {r.id: r for r in victory.base_rows(ctx.save) if r.full > 0}
    out = []
    for b in ctx.base_list:
        supply, required = b.get("supply"), b.get("supply_required")
        if required <= 0:
            continue
        pct = supply * 100 // required
        if pct >= supply_pct:
            continue
        detail = f"Supply {supply:,} of {required:,} needed ({pct}%)"
        lost = 0
        vp = points.get(b.id)
        if vp is not None:
            lost = vp.full - vp.scored
            detail += f"; scores {vp.scored:,} of {vp.full:,} VP"
        # Victory points lost first; the percentage points below the threshold break ties (always under 1000).
        out.append(Alert("Low supply", b.side, b.name, detail, "base", b.id, lost * 1000 + (supply_pct - pct)))
    return out


def _spoilage(ctx, _supply_pct, _pilot_pool):
    out = []
    for r in reports.spoilage_rows(ctx.base_list):
        parts = [f"{name} {over:,} over the {limit:,} limit"
                 for name, over, limit in (("Supply", r.supply_over, r.supply_limit), ("Fuel", r.fuel_over,
                                                                                       r.fuel_limit)) if over]
        out.append(Alert("Spoilage", r.base.side, r.base.name, "; ".join(parts), "base", r.base.id, r.total_over))
    return out


def _repair(ctx, _supply_pct, _pilot_pool):
    ships = shiprepair.damaged_ships(ctx.save)
    ports = {p.id: p for p in shiprepair.repair_ports(ctx.save, ships)}
    out = []
    for s in ships:
        port = ports.get(s.port_id)
        if port is not None and s.tons > port.largest and s.tons > port.yard_capacity:
            out.append(Alert("Repair", s.side, s.name,
                             f"Too big for {port.name}: {s.tons:,} t; port takes {port.largest:,} t, yard "
                             f"{port.yard_capacity:,} t", "ship", s.id, s.tons))
    for p in ports.values():
        if p.shipyard_tons > p.yard_capacity:
            over = p.shipyard_tons - p.yard_capacity
            out.append(Alert("Repair", p.side, p.name,
                             f"Shipyard queue {over:,} t over a {p.yard_capacity:,} t yard", "base", p.id, over))
    return out


def _decay_percent(text):
    """The lowest daily decay percentage in a MineHex.decay text ("1%/day (friendly port)", "5-33%/day")."""
    return int(text.split("%")[0].split("-")[0])


def _minefields(ctx, _supply_pct, _pilot_pool):
    totals = {}  # side -> [hexes, unprotected mines, daily loss]
    for r in minefields.hex_rows(ctx.save, minefields.list_fields(ctx.save)):
        # The report marks a place of the other side as "(enemy base)"; the check needs the same fact as an id.
        if r.place_id is None or bases.SIDES.get(bases.place_side_id(ctx.save, r.place_id)) != r.side:
            continue
        unprotected = r.mines - r.protected
        if unprotected <= 0:
            continue
        total = totals.setdefault(r.side, [0, 0, 0.0])
        total[0] += 1
        total[1] += unprotected
        total[2] += unprotected * _decay_percent(r.decay) / 100
    out = []
    for side, (count, unprotected, loss) in totals.items():
        out.append(Alert("Minefields", side, "Own-port minefields",
                         f"{count:,} port{'' if count == 1 else 's'} with {unprotected:,} unprotected mines, "
                         f"losing about {round(loss):,} a day (each docked ACM protects "
                         f"{minefields.MINES_PER_ACM})",
                         "minefields", side, unprotected))
    return out


def _pilots(ctx, _supply_pct, pilot_pool):
    out = []
    for p in pilotpool.list_pools(ctx.save):
        pool = p.get("pool")
        if p.is_empty or pool >= pilot_pool:
            continue
        out.append(Alert("Pilots", p.side, p.label,
                         f"Pool {pool:,} pilots (rate {p.get('rate'):,}/month, {p.in_training:,} in training)",
                         "pilots", p.nation_id, pilot_pool - pool))
    return out


def _entries(ctx):
    return airproduction.plant_entries(ctx.places)


def _aircraft(ctx, _supply_pct, _pilot_pool):
    rows = airproduction.air_rows(ctx.save, _entries(ctx), ctx.groups)
    out = []
    for r in rows:
        coming = PRODUCTION_DAYS * r.planes_day
        if r.planes_day > 0 and r.short > r.pool + coming:
            out.append(Alert("Aircraft", r.side, r.name,
                             f"Groups short {r.short:,} planes; pool {r.pool:,} + {round(coming):,} in "
                             f"{PRODUCTION_DAYS} days at {r.planes_day:.1f}/day", "aircraft", r.id,
                             r.short - (r.pool + coming)))
    return out


def _engines(ctx, _supply_pct, _pilot_pool):
    rows = airproduction.engine_rows(ctx.save, _entries(ctx))
    out = []
    for r in rows:
        if r.net >= 0:
            continue
        pool = "unknown" if r.pool is None else f"{r.pool:,}"
        out.append(Alert("Engines", "Japanese", r.name,
                         f"Factories build {r.size:,} of {r.needed:,} needed (pool {pool})", "engine", r.id, -r.net))
    return out


CHECKS = {"Low supply": _low_supply, "Spoilage": _spoilage, "Repair": _repair, "Minefields": _minefields,
          "Pilots": _pilots, "Aircraft": _aircraft, "Engines": _engines}


def collect(save, supply_pct=DEFAULTS["supply_pct"], pilot_pool=DEFAULTS["pilot_pool"], places=None, groups=None):
    """(alerts, skipped): every alert of the save in category order, worst first within a category, and the names
    of the categories whose check could not read the save. places (industry places) and groups (air groups) may be
    passed in when the caller already has them; they default to being read from the save."""
    ctx = _Context(save, places, groups)
    alerts, skipped = [], []
    for category in CATEGORIES:
        try:
            alerts.extend(CHECKS[category](ctx, supply_pct, pilot_pool))
        except SKIPPABLE:
            skipped.append(category)
    order = {c: k for k, c in enumerate(CATEGORIES)}
    alerts.sort(key=lambda a: (order[a.category], -a.sort_value, a.subject.lower()))
    return alerts, skipped
