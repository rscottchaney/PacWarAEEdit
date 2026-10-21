"""Read-only air production report: per aircraft model and per Japanese engine.

Rules are from the game manual (13.2.2.4/13.2.2.5): a factory builds size / 30 aircraft
or engines per day with production on, using 18 HI per engine (so 18 x the engine count
per airframe), and Japanese airframes also use up one engine per engine fitted; Allied
aircraft do not need engines. A factory whose model is not yet available is researching
and is counted separately. Only set_switches writes to the save, and only the production
and repair switches.
"""

import struct
from collections import namedtuple

from . import aircraft, airgroups, bases, factories, industry
from .container import SaveFormatError

PlantEntry = namedtuple("PlantEntry", "place factory")
AirRow = namedtuple(
    "AirRow", "id name type side engines pool used factories size research damage production_off repair_off "
              "planes_day hi_day engines_day groups in_groups short next_group available active")
EngineRow = namedtuple(
    "EngineRow", "id name factories size damage production_off pool needed net hi_day used_by")

JAPAN = 0
# Names listed in the "Used by" column before the rest is summarised.
USED_BY_NAMES = 4


def plant_entries(places):
    """Every aircraft and engine factory of the places, in place then slot order."""
    return [PlantEntry(p, f) for p in places for f in factories.list_factories(p.base)
            if f.kind in ("aircraft", "engine")]


def model_entries(entries, aircraft_id):
    """The factories building one aircraft model."""
    return [e for e in entries if e.factory.type == factories.AIRCRAFT_BASE + aircraft_id]


def _pools(a):
    """(pool, used) of a model; an unreadable pool section is a format error."""
    try:
        return a.pool, a.used
    except (KeyError, struct.error):
        raise SaveFormatError("section 0x01 (production pools) is missing or too short") from None


def _available_text(a):
    start, end = (aircraft.format_date(*a.get_date(name)) for name in ("from", "to"))
    return f"from {start}" if end == "-" else f"{start} to {end}"


def air_rows(save, entries, groups=None):
    """One AirRow per aircraft model, in id order; active marks models with a factory, a pool or a group."""
    groups = airgroups.list_airgroups(save) if groups is None else groups
    built = {}
    for e in entries:
        if e.factory.kind == "aircraft":
            built.setdefault(e.factory.type - factories.AIRCRAFT_BASE, []).append(e.factory)
    flying = {}
    for g in groups:
        flying.setdefault(g.aircraft_id, []).append(g)
    rows = []
    for a in aircraft.list_aircraft(save):
        plants = built.get(a.id, [])
        researching, working = [], []
        for f in plants:
            (researching if industry.is_researching(save, f) else working).append(f)
        producing = [f for f in working if f.production_on]
        planes_day = sum(f.size for f in producing) / industry.AIRCRAFT_DIVISOR
        japanese = a.side_id == JAPAN
        arrived = [g for g in flying.get(a.id, []) if g.arrived]
        coming = [g.days_to_arrival for g in flying.get(a.id, []) if not g.arrived]
        pool, used = _pools(a)
        rows.append(AirRow(
            a.id, a.name, a.type, bases.SIDES.get(a.side_id, "Unknown"), a.engines_text, pool, used,
            len(plants), sum(f.size for f in producing), sum(f.size for f in researching),
            sum(f.damage for f in plants), sum(f.size for f in working if not f.production_on),
            sum(f.size for f in plants if not f.repair_on), planes_day,
            planes_day * industry.HI_PER_UNIT * a.engine_count,
            planes_day * a.engine_count if japanese else None,
            len(arrived), sum(g.planes for g in arrived),
            sum(max(0, g.get("max_size") - g.planes) for g in arrived), min(coming) if coming else None,
            _available_text(a),
            bool(plants or pool or flying.get(a.id))))
    return rows


def engine_rows(save, entries):
    """One EngineRow per Japanese engine: any engine fitted to a Japanese model or built by a Japanese factory."""
    models = {a.id: a for a in aircraft.list_aircraft(save) if a.side_id == JAPAN and a.engine_id}
    used_by = {}
    for a in models.values():
        used_by.setdefault(a.engine_id, []).append(a.name)
    built = {}
    needed = {}
    for e in entries:
        f = e.factory
        if f.kind == "engine":
            if e.place.base.side_id != JAPAN:
                continue
            built.setdefault(f.type, []).append(f)
        elif f.production_on and not industry.is_researching(save, f):
            model = models.get(f.type - factories.AIRCRAFT_BASE)
            if model is not None:
                needed[model.engine_id] = needed.get(model.engine_id, 0) + f.size * model.engine_count
    rows = []
    for device in sorted(set(used_by) | set(built)):
        plants = built.get(device, [])
        size = sum(f.size for f in plants if f.production_on)
        try:
            pool = industry.pool_value(save, device, JAPAN)
        except SaveFormatError:
            pool = None
        names = sorted(set(used_by.get(device, [])))
        shown = ", ".join(names[:USED_BY_NAMES]) + (f" (+{len(names) - USED_BY_NAMES} more)"
                                                    if len(names) > USED_BY_NAMES else "")
        rows.append(EngineRow(
            device, factories.factory_name(save, device), len(plants), size, sum(f.damage for f in plants),
            sum(f.size for f in plants if not f.production_on), pool, needed.get(device, 0),
            size - needed.get(device, 0), size / industry.AIRCRAFT_DIVISOR * industry.HI_PER_UNIT, shown))
    return rows


def set_switches(entries, aircraft_id, production=None, repair=None):
    """Set the production and/or repair switch (None leaves it) of every factory building a model.

    Only the switch bytes are written (size, damage and the Keep/Upgd switch are kept, and a
    stored damage above the size does not matter). Returns (changed, unchanged, failed): the
    entries that changed, the count already in the requested state, and (entry, message) pairs
    for factories the editor refused.
    """
    changed, unchanged, failed = [], 0, []
    for e in model_entries(entries, aircraft_id):
        f = e.factory
        if (production is None or production == f.production_on) and (repair is None or repair == f.repair_on):
            unchanged += 1
            continue
        try:
            factories.set_switches(e.place.base, f.slot, production, repair)
        except ValueError as exc:
            failed.append((e, str(exc)))
            continue
        changed.append(e)
    return changed, unchanged, failed
