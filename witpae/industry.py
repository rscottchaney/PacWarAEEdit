"""Read-only industry reports: what factories produce and use per day, by place.

Rules are from the game manual (13.2), per factory size point per day, and only
for factories with production switched on. Size is the working size; damage is
extra capacity awaiting repair and is shown but not subtracted. Not modelled:
supply used by units, fuel used by ships, daily supply and fuel allotments, and
the side-wide HI and manpower pools. Nothing here writes to the save.
"""

import struct
from collections import namedtuple

from . import bases, factories, regions

TYPE_MINOR = 0
KIND_BY_TYPE = {TYPE_MINOR: "Minor", bases.TYPE_BASE: "Base", bases.TYPE_TOWN: "Town"}

# Materials in display order: key -> label.
MATERIALS = {
    "oil": "oil", "resources": "resources", "fuel": "fuel", "hi": "HI", "supply": "supply", "manpower": "manpower",
    "naval": "naval points", "merchant": "merchant points", "armament": "armament points",
    "vehicle": "vehicle points", "aircraft": "aircraft", "engines": "engines",
}
# Rows of the balance table: key -> label. Stored amounts exist for the STORED materials only.
BALANCE_ROWS = {"oil": "Oil", "resources": "Resources", "fuel": "Fuel", "supply": "Supply",
                "manpower": "Manpower", "hi": "HI points"}
STORED = ("oil", "resources", "fuel", "supply")

# Factory type id -> (group label, uses, makes) per size point per day.
RULES = {
    518: ("Oil", {}, {"oil": 10}),
    519: ("Resources", {}, {"resources": 20}),
    520: ("Manpower", {}, {"manpower": 5}),
    521: ("Heavy Industry", {"resources": 20, "fuel": 2}, {"hi": 2, "supply": 2}),
    527: ("Light Industry", {"resources": 15}, {"supply": 1}),
    528: ("Refinery", {"oil": 10}, {"fuel": 9, "supply": 1}),
    522: ("Naval Shipyard", {"hi": 3}, {"naval": 1}),
    523: ("Merchant Shipyard", {"hi": 3}, {"merchant": 1}),
    525: ("Armament", {"hi": 6}, {"armament": 1}),
    526: ("Vehicle", {"hi": 6}, {"vehicle": 1}),
    524: ("Repair Shipyard", {}, {}),
}
# Aircraft and engine factories build size / 30 per day; their HI use depends on the
# engines per aircraft, which is not mapped, so their inputs are unknown.
AIRCRAFT_DIVISOR = 30
# Row order of the Industry report; also the choices of the Factories report.
GROUP_ORDER = ["Oil", "Resources", "Manpower", "Heavy Industry", "Light Industry", "Refinery", "Naval Shipyard",
               "Merchant Shipyard", "Repair Shipyard", "Armament", "Vehicle", "Aircraft", "Engines"]

IndustryPlace = namedtuple("IndustryPlace", "id name kind region_id region base")
Flow = namedtuple("Flow", "uses makes uses_known")
TypeRow = namedtuple("TypeRow", "group count size damage production_off repair_off makes uses uses_known")
BalanceRow = namedtuple("BalanceRow", "material label stored produced used net days")
FactoryRow = namedtuple("FactoryRow", "place factory group flow")
RawRow = namedtuple("RawRow", "place stored net shortest")

NO_FLOW = Flow({}, {}, True)


def list_industry_places(save, region_map=None):
    """Every location of type 0 (minor), 1 (base) or 5 (town) with a name, in id order."""
    region_map = regions.default_regions() if region_map is None else region_map
    data = save[bases.LOCATION_SECTION].data
    places = []
    for loc_id in range(min(bases.RECORD_COUNT, len(data) // bases.RECORD_SIZE)):
        start = loc_id * bases.RECORD_SIZE
        kind = KIND_BY_TYPE.get(struct.unpack_from("<h", data, start + bases.TYPE_OFFSET)[0])
        if kind is None:
            continue
        name = bases.decode_name(data[start:start + bases.NAME_SIZE])
        if not name:
            continue
        region_id, region = region_map.region_of(loc_id)
        places.append(IndustryPlace(loc_id, name, kind, region_id, region, bases.Base(save, loc_id, name)))
    return places


def group_of(factory):
    if factory.kind == "aircraft":
        return "Aircraft"
    return RULES[factory.type][0] if factory.kind == "industry" else "Engines"


def factory_flow(factory):
    """Daily uses and makes of one factory; empty when production is off."""
    if not factory.production_on:
        return NO_FLOW
    if factory.kind == "industry":
        _label, uses, makes = RULES[factory.type]
        return Flow({k: v * factory.size for k, v in uses.items()},
                    {k: v * factory.size for k, v in makes.items()}, True)
    key = "aircraft" if factory.kind == "aircraft" else "engines"
    return Flow({}, {key: factory.size / AIRCRAFT_DIVISOR}, False)


def flow_text(amounts):
    """e.g. "14,548 HI, 14,548 supply"; "-" when empty."""
    parts = []
    for key, label in MATERIALS.items():
        value = amounts.get(key)
        if value:
            parts.append(f"{value:,.1f} {label}" if value != int(value) else f"{int(value):,} {label}")
    return ", ".join(parts) or "-"


def filter_places(places, side=None, region_id=None):
    """Places of one side name and/or region id; None means any."""
    return [p for p in places
            if (side is None or p.base.side == side) and (region_id is None or p.region_id == region_id)]


def _add(total, amounts):
    for key, value in amounts.items():
        total[key] = total.get(key, 0) + value


def summarize(places):
    """(type rows, balance rows) over places; type rows only for groups with factories."""
    groups = {}
    produced, used = {}, {}
    stored = dict.fromkeys(STORED, 0)
    for p in places:
        for key in STORED:
            stored[key] += p.base.get(key)
        for f in factories.list_factories(p.base):
            g = groups.setdefault(group_of(f), {"count": 0, "size": 0, "damage": 0, "production_off": 0,
                                                "repair_off": 0, "makes": {}, "uses": {}, "uses_known": True})
            g["count"] += 1
            g["size"] += f.size
            g["damage"] += f.damage
            g["production_off"] += 0 if f.production_on else f.size
            g["repair_off"] += 0 if f.repair_on else f.size
            flow = factory_flow(f)
            _add(g["makes"], flow.makes)
            _add(g["uses"], flow.uses)
            _add(produced, flow.makes)
            _add(used, flow.uses)
            if not flow.uses_known:
                g["uses_known"] = False
    type_rows = [TypeRow(name, g["count"], g["size"], g["damage"], g["production_off"], g["repair_off"],
                         g["makes"], g["uses"], g["uses_known"])
                 for name in GROUP_ORDER for g in [groups.get(name)] if g]
    balance = []
    for key, label in BALANCE_ROWS.items():
        made, spent = produced.get(key, 0), used.get(key, 0)
        net = made - spent
        have = stored.get(key)
        days = have / -net if have is not None and net < 0 else None
        balance.append(BalanceRow(key, label, have, made, spent, net, days))
    return type_rows, balance


def factory_rows(places):
    """One row per factory slot of the places, in place then slot order."""
    return [FactoryRow(p, f, group_of(f), factory_flow(f))
            for p in places for f in factories.list_factories(p.base)]


def raw_rows(places, only_industry=True):
    """One row per place: own stock and the net daily rate of oil, resources, fuel and supply.

    shortest is (material key, days) for the stock that runs out first at the net rate, or None.
    only_industry keeps just the places with at least one producing factory.
    """
    rows = []
    for p in places:
        flows = [(f, factory_flow(f)) for f in factories.list_factories(p.base)]
        if only_industry and not any(f.size > 0 and flow.makes for f, flow in flows):
            continue
        net = dict.fromkeys(STORED, 0)
        for _f, flow in flows:
            for key in STORED:
                net[key] += flow.makes.get(key, 0) - flow.uses.get(key, 0)
        stored = {key: p.base.get(key) for key in STORED}
        runs_out = [(stored[key] / -net[key], key) for key in STORED if net[key] < 0]
        shortest = None
        if runs_out:
            days, key = min(runs_out)
            shortest = (key, days)
        rows.append(RawRow(p, stored, net, shortest))
    return rows
