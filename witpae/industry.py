"""Read-only industry reports: what factories produce and use per day, by place.

Rules are from the game manual (13.2), per factory size point per day, and only
for factories with production switched on. Size is the working size; damage is
extra capacity awaiting repair and is shown but not subtracted. Not modelled:
supply used by units and fuel used by ships. The daily supply, fuel and oil
allotments of places and the side-wide production pools are read from the save.
Nothing here writes to the save.
"""

import struct
from collections import namedtuple

from . import bases, factories, regions
from .container import SaveFormatError


# Materials in display order: key -> label.
MATERIALS = {
    "oil": "oil", "resources": "resources", "fuel": "fuel", "hi": "HI", "supply": "supply", "manpower": "manpower",
    "naval": "naval points", "merchant": "merchant points", "armament": "armament points",
    "vehicle": "vehicle points", "aircraft": "aircraft", "engines": "engines",
}
# Rows of the balance table: key -> label. Stored amounts exist for the STORED materials only.
BALANCE_ROWS = {"oil": "Oil", "resources": "Resources", "fuel": "Fuel", "supply": "Supply",
                "manpower": "Manpower", "hi": "HI points", "armament": "Armament points",
                "vehicle": "Vehicle points", "naval": "Naval points", "merchant": "Merchant points"}
STORED = ("oil", "resources", "fuel", "supply")

# Side-wide pools: section 0x01 holds (Japan, Allies) i32 pairs, 8 bytes per device id, so a pool is the
# i32 at POOL_BASE + 8 * device + 4 * side.
POOL_SECTION = 0x01
POOL_BASE = 8184
POOL_DEVICES = {"manpower": 520, "hi": 521, "naval": 522, "merchant": 523, "armament": 525, "vehicle": 526}
POOLS = tuple(POOL_DEVICES)
# Daily allotments: u16 in each location record, added to the place every day.
ALLOTMENT_OFFSETS = {"supply": 824, "fuel": 826, "oil": 828}

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
BalanceRow = namedtuple("BalanceRow", "material label stored produced allotted used net days")
FactoryRow = namedtuple("FactoryRow", "place factory group flow")
RawRow = namedtuple("RawRow", "place stored net shortest allotment")

NO_FLOW = Flow({}, {}, True)


def list_industry_places(save, region_map=None):
    """Every named base (type 1), town (type 5) and minor place (type 0, index type 10), in id order."""
    region_map = regions.default_regions() if region_map is None else region_map
    data = save[bases.LOCATION_SECTION].data
    places = []
    for loc_id in range(min(bases.RECORD_COUNT, len(data) // bases.RECORD_SIZE)):
        start = loc_id * bases.RECORD_SIZE
        loc_type = struct.unpack_from("<h", data, start + bases.TYPE_OFFSET)[0]
        if loc_type not in (bases.TYPE_MINOR, bases.TYPE_BASE, bases.TYPE_TOWN):
            continue
        name = bases.decode_name(data[start:start + bases.NAME_SIZE])
        if not name or (loc_type == bases.TYPE_MINOR and not bases.is_minor_place(save, loc_id, name)):
            continue
        region_id, region = region_map.region_of(loc_id)
        base = bases.Base(save, loc_id, name)
        places.append(IndustryPlace(loc_id, name, base.kind, region_id, region, base))
    return places


def side_pools(save):
    """side id -> {pool key: value} of the side-wide production pools."""
    if POOL_SECTION not in save:
        raise SaveFormatError(f"section 0x{POOL_SECTION:02x} (production pools) is missing")
    data = save[POOL_SECTION].data
    last = POOL_BASE + 8 * max(POOL_DEVICES.values()) + 4 * max(bases.SIDES) + 4
    if len(data) < last:
        raise SaveFormatError(f"section 0x{POOL_SECTION:02x} (production pools) is too short")
    return {side: {key: struct.unpack_from("<i", data, POOL_BASE + 8 * device + 4 * side)[0]
                   for key, device in POOL_DEVICES.items()}
            for side in bases.SIDES}


def allotment(place):
    """{"supply", "fuel", "oil"} -> daily amount the game adds to the place; zero entries are omitted."""
    data = place.base._save[bases.LOCATION_SECTION].data
    start = place.id * bases.RECORD_SIZE
    amounts = {key: struct.unpack_from("<H", data, start + offset)[0] for key, offset in ALLOTMENT_OFFSETS.items()}
    return {key: value for key, value in amounts.items() if value}


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


def summarize(places, pools=None, regional=False):
    """(type rows, balance rows) over places; type rows only for groups with factories.

    pools is the {pool key: value} of one side (None when unreadable, stored is then None). The pools are
    side-wide, so with regional=True days left is not given for them.
    """
    groups = {}
    produced, used, allotted = {}, {}, {}
    stored = dict.fromkeys(STORED, 0)
    for p in places:
        for key in STORED:
            stored[key] += p.base.get(key)
        _add(allotted, allotment(p))
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
        extra = allotted.get(key, 0)
        net = made + extra - spent
        have = stored.get(key) if key in STORED else (pools or {}).get(key)
        days = have / -net if have is not None and net < 0 and not (regional and key in POOLS) else None
        balance.append(BalanceRow(key, label, have, made, extra, spent, net, days))
    return type_rows, balance


def factory_rows(places):
    """One row per factory slot of the places, in place then slot order."""
    return [FactoryRow(p, f, group_of(f), factory_flow(f))
            for p in places for f in factories.list_factories(p.base)]


def is_supply_source(given, flows):
    """True for a place with a daily allotment or at least one producing factory."""
    return bool(given) or any(f.size > 0 and flow.makes for f, flow in flows)


def raw_rows(places, only_industry=True):
    """One row per place: own stock and the net daily rate of oil, resources, fuel and supply.

    The net rate includes the place's daily allotment, which is also given as allotment.
    shortest is (material key, days) for the stock that runs out first at the net rate, or None.
    only_industry keeps just the places that are a source: a producing factory or a daily allotment.
    """
    rows = []
    for p in places:
        flows = [(f, factory_flow(f)) for f in factories.list_factories(p.base)]
        given = allotment(p)
        if only_industry and not is_supply_source(given, flows):
            continue
        net = dict.fromkeys(STORED, 0)
        for _f, flow in flows:
            for key in STORED:
                net[key] += flow.makes.get(key, 0) - flow.uses.get(key, 0)
        for key, value in given.items():
            net[key] += value
        stored = {key: p.base.get(key) for key in STORED}
        runs_out = [(stored[key] / -net[key], key) for key in STORED if net[key] < 0]
        shortest = None
        if runs_out:
            days, key = min(runs_out)
            shortest = (key, days)
        rows.append(RawRow(p, stored, net, shortest, given))
    return rows
