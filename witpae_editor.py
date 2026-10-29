"""Tkinter front end for the WitP:AE base editor.

Usage: python witpae_editor.py [save.pws]

All data logic lives in the witpae package; this file only wires widgets.
"""

import base64
import datetime
import os
import struct
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from witpae import (aircraft, airgroups, airproduction, alerts, bases, chart, combat, factories, history, industry, intel, landunits, lcuproduction, leaders, losses, mapview, minefields,
                    pilotpool, planeart, regions, reports, shipproduction, shiprecords, shiprepair, ships, taskforces, victory)
from witpae.container import SaveFile, SaveFormatError
from witpae.fileio import is_pbem, save_with_backup

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DIR = os.path.normpath(os.path.join(HERE, "..", "SAVE"))

# (column id, heading, width, numeric, value getter)
COLUMNS = [
    ("id", "ID", 55, True, lambda b: b.id),
    ("name", "Name", 150, False, lambda b: b.name),
    ("kind", "Type", 50, False, lambda b: b.kind),
    ("side", "Side", 70, False, lambda b: b.side),
    ("hex", "Hex x,y", 70, True, lambda b: (b.x, b.y)),
    ("supply", "Supply", 80, True, lambda b: b.get("supply")),
    ("fuel", "Fuel", 80, True, lambda b: b.get("fuel")),
    ("port", "Port", 45, True, lambda b: b.get("port")),
    ("airfield", "Airfield", 60, True, lambda b: b.get("airfield")),
]
COLUMN_BY_ID = {c[0]: c for c in COLUMNS}

AIRCRAFT_COLUMNS = [
    ("id", "ID", 55, True, lambda a: a.id),
    ("name", "Name", 170, False, lambda a: a.name),
    ("nation", "Nation", 70, False, lambda a: a.nation),
    ("type", "Type", 110, False, lambda a: a.type),
    ("from", "From", 60, True, lambda a: a.get_date("from")[::-1]),
    ("to", "To", 60, True, lambda a: a.get_date("to")[::-1]),
    ("pool", "Pool", 55, True, lambda a: a.pool),
]
AIRCRAFT_COLUMN_BY_ID = {c[0]: c for c in AIRCRAFT_COLUMNS}

SHIP_COLUMNS = [
    ("id", "ID", 55, True, lambda s: s.id),
    ("name", "Name", 170, False, lambda s: s.name),
    ("type", "Type", 70, False, lambda s: s.type),
    ("nation", "Nation", 70, False, lambda s: s.nation),
    ("date", "Date", 60, True, lambda s: s.date[::-1]),
    ("speed", "Speed", 50, True, lambda s: s.get("speed")),
    ("durability", "Durability", 70, True, lambda s: s.get("durability")),
]
SHIP_COLUMN_BY_ID = {c[0]: c for c in SHIP_COLUMNS}

SHIPREC_COLUMNS = [
    ("id", "ID", 55, True, lambda s: s.id),
    ("name", "Name", 150, False, lambda s: s.name),
    ("type", "Type", 60, False, lambda s: s.type),
    ("class", "Class", 130, False, lambda s: s.class_name),
    ("nation", "Nation", 60, False, lambda s: s.nation),
    ("side", "Side", 65, False, lambda s: s.side),
    ("location", "Location", 120, False, lambda s: s.location),
]
SHIPREC_COLUMN_BY_ID = {c[0]: c for c in SHIPREC_COLUMNS}

# Rows are dicts built by EditorApp._tf_row.
TF_COLUMNS = [
    ("id", "ID", 55, True, lambda r: r["id"]),
    ("name", "Name", 170, False, lambda r: r["name"]),
    ("side", "Side", 65, False, lambda r: r["side"]),
    ("location", "Location", 140, False, lambda r: r["location"]),
    ("mission", "Mission", 120, False, lambda r: r["mission"]),
    ("destination", "Destination", 120, False, lambda r: r["destination"]),
    ("ships", "Ships", 45, True, lambda r: r["ships"]),
    ("flagship", "Flagship", 130, False, lambda r: r["flagship"]),
]
TF_COLUMN_BY_ID = {c[0]: c for c in TF_COLUMNS}
TF_SHIP_COLUMNS = [
    ("flag", "Flag", 35), ("name", "Name", 130), ("type", "Type", 50), ("class", "Class", 110),
    ("fuel", "Fuel", 90), ("sys", "Sys", 35), ("float", "Float", 40), ("eng", "Eng", 35), ("fires", "Fires", 40),
]

GROUP_COLUMNS = [
    ("id", "ID", 55, True, lambda g: g.id),
    ("name", "Name", 170, False, lambda g: g.name),
    ("aircraft", "Aircraft", 120, False, lambda g: g.aircraft_name),
    ("planes", "Planes", 55, True, lambda g: g.planes),
    # Active pilots from the pilot table; the group's own count byte disagrees for many groups.
    ("pilots", "Pilots", 50, True, lambda g: g.active_pilots),
    ("morale", "Morale", 55, True, lambda g: g.get("morale")),
    ("exp", "Exp", 45, True, lambda g: g.get("experience")),
    ("location", "Location", 120, False, lambda g: g.location_name),
]
GROUP_COLUMN_BY_ID = {c[0]: c for c in GROUP_COLUMNS}

UNIT_COLUMNS = [
    ("id", "ID", 55, True, lambda u: u.id),
    ("name", "Name", 190, False, lambda u: u.display_name),
    ("type", "Type", 50, False, lambda u: u.type),
    ("hq", "HQ", 110, False, lambda u: u.hq_name),
    ("location", "Location", 110, False, lambda u: u.location_name),
    ("exp", "Exp", 45, True, lambda u: u.get("experience")),
    ("morale", "Morale", 55, True, lambda u: u.get("morale")),
    ("fatigue", "Fatigue", 55, True, lambda u: u.get("fatigue")),
    ("supplies", "Supplies", 95, True, lambda u: u.get("supplies")),
]
UNIT_COLUMN_BY_ID = {c[0]: c for c in UNIT_COLUMNS}
# Cell text where it differs from the sort value: a short unit's supplies read "have / required".
UNIT_TEXT = {"supplies": lambda u: f"{u.get('supplies')} / {u.supplies_required}" if u.arrived and u.supplies_short
             else u.get("supplies")}

# Rows are the LeaderRow tuples of witpae.leaders.
LEADER_COLUMNS = [
    ("id", "ID", 50, True, lambda r: r.id),
    ("name", "Name", 140, False, lambda r: r.name),
    ("nation", "Nation", 55, False, lambda r: r.nation),
    ("rank", "Rank", 50, False, lambda r: r.rank),
    ("type", "Type", 110, False, lambda r: r.type),
    ("leadership", "Leadership", 70, True, lambda r: r.leadership),
    ("inspiration", "Inspiration", 70, True, lambda r: r.inspiration),
    ("naval", "Naval", 45, True, lambda r: r.naval),
    ("air", "Air", 35, True, lambda r: r.air),
    ("land", "Land", 40, True, lambda r: r.land),
    ("admin", "Admin", 45, True, lambda r: r.admin),
    ("aggression", "Aggression", 70, True, lambda r: r.aggression),
    ("political", "Political", 55, True, lambda r: r.political),
    ("delay", "Delay", 45, True, lambda r: r.delay),
    ("commands", "Commands", 150, False, lambda r: r.commands),
]
LEADER_COLUMN_BY_ID = {c[0]: c for c in LEADER_COLUMNS}

# Report rows are the namedtuples of witpae.reports. Over values, dates and due months sort
# on the raw getter value and are shown through the *_TEXT formatters.
SPOILAGE_COLUMNS = [
    ("id", "ID", 55, True, lambda r: r.base.id),
    ("name", "Name", 150, False, lambda r: r.base.name),
    ("kind", "Type", 50, False, lambda r: r.base.kind),
    ("side", "Side", 70, False, lambda r: r.base.side),
    ("region", "Region", 110, False, lambda r: regions.default_regions().region_of(r.base.id)[1]),
    ("port", "Port", 45, True, lambda r: r.base.get("port")),
    ("airfield", "Airfield", 60, True, lambda r: r.base.get("airfield")),
    ("supply", "Supply", 80, True, lambda r: r.supply),
    ("supply_limit", "Supply limit", 80, True, lambda r: r.supply_limit),
    ("supply_over", "Supply over", 80, True, lambda r: r.supply_over),
    ("fuel", "Fuel", 80, True, lambda r: r.fuel),
    ("fuel_limit", "Fuel limit", 80, True, lambda r: r.fuel_limit),
    ("fuel_over", "Fuel over", 80, True, lambda r: r.fuel_over),
]
SPOILAGE_COLUMN_BY_ID = {c[0]: c for c in SPOILAGE_COLUMNS}
SPOILAGE_TEXT = {cid: (lambda v: v if v > 0 else "-") for cid in ("supply_over", "fuel_over")}
SPOILAGE_NOTE = ("Limits from the game manual: none when port + airfield size is 10 or more; "
                 "supply 5000 + 3000 x s\u00b2, fuel 1000 + 2000 x s\u00b2 (s = port + airfield size).")


def _due_text(months):
    if months <= 0:
        return "now"
    return "1 month" if months == 1 else f"{months} months"


def _class_text(cls):
    return f"{cls.name} #{cls.id}"


UPGRADE_COLUMNS = [
    ("id", "ID", 55, True, lambda r: r.ship.id),
    ("ship", "Ship", 150, False, lambda r: r.ship.name),
    ("type", "Type", 60, False, lambda r: r.ship.type),
    ("side", "Side", 65, False, lambda r: r.ship.side),
    ("class", "Class", 150, False, lambda r: _class_text(r.current)),
    ("target", "Upgrade to", 150, False, lambda r: _class_text(r.target)),
    ("change", "Type change", 80, False, lambda r: r.type_change),
    ("date", "Date", 55, True, lambda r: (r.year, r.month)),
    ("due", "Due", 75, True, lambda r: r.months),
    ("yard", "Yard?", 50, True, lambda r: r.yard),
    ("location", "Location", 120, False, lambda r: r.location),
]
UPGRADE_COLUMN_BY_ID = {c[0]: c for c in UPGRADE_COLUMNS}
UPGRADE_TEXT = {"date": lambda v: f"{v[1]}/{v[0]:02d}", "due": _due_text}
# "Due within" choices: label -> months, None for all.
UPGRADE_DUE = {"Now": 0, "1 month": 1, "3 months": 3, "6 months": 6, "12 months": 12, "All": None}


PRODUCTION_COLUMNS = [
    ("id", "ID", 55, True, lambda r: r.ship.id),
    ("ship", "Ship", 150, False, lambda r: r.ship.name),
    ("type", "Type", 60, False, lambda r: r.type),
    ("class", "Class", 150, False, lambda r: _class_text(r.current)),
    ("durability", "Durability", 70, True, lambda r: r.durability),
    ("yard", "Yard", 65, False, lambda r: r.yard),
    ("delay", "Delay", 60, True, lambda r: r.delay),
    ("arrival", "Arrives", 90, True, lambda r: r.arrival.toordinal() if r.arrival else 0),
    ("status", "Status", 140, False, lambda r: r.status),
    ("starts_in", "Starts costing in", 100, True, lambda r: r.starts_in),
    ("per_day", "Points/day", 70, True, lambda r: r.per_day),
    ("to_finish", "Points to finish", 100, True, lambda r: r.to_finish),
    ("accel", "Accelerated/day", 100, True, lambda r: -1 if r.accel_per_day is None else r.accel_per_day),
]
PRODUCTION_COLUMN_BY_ID = {c[0]: c for c in PRODUCTION_COLUMNS}
PRODUCTION_SUMMARY_COLUMNS = [
    ("yard", "Yard", 80, False, lambda r: r.yard),
    ("size", "Points made/day", 110, True, lambda r: r.size),
    ("hi_day", "HI/day", 70, True, lambda r: r.hi_per_day),
    ("pool", "Pool", 70, True, lambda r: -1 if r.pool is None else r.pool),
    ("needed", "Needed/day", 85, True, lambda r: r.needed),
    ("net", "Net/day", 75, True, lambda r: r.net),
    ("building", "Building", 70, True, lambda r: r.building),
    ("can_accelerate", "Can accelerate", 100, True, lambda r: r.can_accelerate),
    ("blueprint", "Blue print", 80, True, lambda r: r.blueprint),
]
PRODUCTION_ALL = "All"
PRODUCTION_NOTE = (
    "Manual 13.4: only the Japanese build ships; the Allies receive ships as scheduled reinforcements. With durability "
    "D and delay L (days to arrival): L over 30 x D is a Blue print (1 day removed free per day, cannot be "
    "accelerated); L over 10 x D up to 30 x D Can accelerate (1 day free per day, 1 more per day for D points); "
    "L up to 10 x D is Building (D points per day remove 1 day, accelerated 3 x D points remove 2). Each "
    "shipyard size point with production on makes 1 point per day for 3 HI (13.2.2.8). Points/day assumes normal "
    "construction: the ship's Normal / Accelerate / Halt setting is not known in the save. Which Building ships "
    "are paid when the pool runs short is not in the manual, so only the daily shortfall per yard is shown. "
    "Midget submarines (SSX) use no points (they sit at 1 day to arrival in saves): they are listed with their own "
    "status and are not counted or charged.")


def _num(v):
    return f"{v:,}"


def _rate(v):
    return f"{v:+,}" if v else "0"


def _arrival_text(v):
    if not v:
        return "-"
    d = datetime.date.fromordinal(v)
    return f"{d.day} {MONTH_NAMES[d.month - 1]} {d.year}"


PRODUCTION_TEXT = {"arrival": _arrival_text, "delay": _num, "starts_in": _num, "per_day": _num, "to_finish": _num,
                   "accel": lambda v: "-" if v < 0 else _num(v)}
PRODUCTION_SUMMARY_TEXT = {"size": _num, "hi_day": _num, "pool": lambda v: "?" if v < 0 else _num(v),
                           "needed": _num, "net": _rate, "building": _num, "can_accelerate": _num,
                           "blueprint": _num}


LCU_ALL = "All"
LCU_WINDOWS = {"7 days": 7, "14 days": 14, "30 days": 30, "60 days": 60, "90 days": 90, "180 days": 180,
               "365 days": 365, "All": None}
LCU_VIEWS = ("Units", "Devices")
LCU_SUMMARY_COLUMNS = [
    ("label", "Points", 90, False, lambda r: r.label),
    ("pool", "Pool", 85, True, lambda r: -1 if r.pool is None else r.pool),
    ("per_day", "Production/day", 100, True, lambda r: -1 if r.per_day is None else r.per_day),
    ("arrived", "Lacking (arrived)", 115, True, lambda r: r.arrived),
    ("reinforcement", "Reinforcements", 105, True, lambda r: r.reinforcement),
    ("days", "Days of production", 120, True, lambda r: -1 if r.days is None else r.days),
]
LCU_SUMMARY_TEXT = {"pool": lambda v: "?" if v < 0 else _num(v), "per_day": lambda v: "-" if v < 0 else _num(v),
                    "arrived": _num, "reinforcement": _num,
                    "days": lambda v: "-" if v < 0 else f"{v:,.1f}"}
LCU_UNIT_COLUMNS = [
    ("id", "ID", 55, True, lambda r: r.unit.id),
    ("name", "Unit", 200, False, lambda r: r.unit.display_name),
    ("type", "Type", 50, False, lambda r: r.unit.type),
    ("hq", "HQ", 120, False, lambda r: r.unit.hq_name),
    ("status", "Status", 130, False, lambda r: r.status),
    ("days", "Days to arrival", 95, True, lambda r: r.days),
    ("toe", "TOE devices", 80, True, lambda r: r.toe),
    ("current", "Present", 70, True, lambda r: r.current),
    ("strength", "Strength", 70, True, lambda r: r.current / r.toe if r.toe else 0),
    ("armament", "Armament", 75, True, lambda r: r.armament),
    ("vehicle", "Vehicle", 70, True, lambda r: r.vehicle),
    ("manpower", "Manpower", 80, True, lambda r: r.manpower),
]
LCU_UNIT_COLUMN_BY_ID = {c[0]: c for c in LCU_UNIT_COLUMNS}
LCU_UNIT_TEXT = {"days": lambda v: _num(v) if 0 < v < 9999 else "-", "toe": _num, "current": _num,
                 "strength": lambda v: f"{v:.0%}", "armament": _num, "vehicle": _num, "manpower": _num}
LCU_DEVICE_COLUMNS = [
    ("id", "ID", 55, True, lambda r: r.id),
    ("name", "Device", 190, False, lambda r: r.name),
    ("type", "Type", 100, False, lambda r: r.type_name),
    ("kind", "Costs", 75, False, lambda r: r.kind),
    ("load", "Load cost", 70, True, lambda r: r.load),
    ("pool", "Pool", 75, True, lambda r: -1 if r.pool is None else r.pool),
    ("toe", "TOE (arrived)", 90, True, lambda r: r.toe),
    ("current", "Present", 70, True, lambda r: r.current),
    ("lacking", "Lacking", 70, True, lambda r: r.lacking),
    ("reinforcement", "Reinforcements", 100, True, lambda r: r.reinforcement),
    ("armament", "Armament", 75, True, lambda r: r.armament),
    ("vehicle", "Vehicle", 70, True, lambda r: r.vehicle),
    ("manpower", "Manpower", 80, True, lambda r: r.manpower),
]
LCU_DEVICE_COLUMN_BY_ID = {c[0]: c for c in LCU_DEVICE_COLUMNS}
LCU_DEVICE_TEXT = {"load": _num, "pool": lambda v: "?" if v < 0 else _num(v), "toe": _num, "current": _num,
                   "lacking": _num, "reinforcement": _num, "armament": _num, "vehicle": _num, "manpower": _num}
LCU_NOTE = (
    "Lacking = TOE count - current count for a slot holding the TOE device (or empty), never below 0; a slot holding "
    "a different device (an older model awaiting upgrade) lacks its whole TOE count; disabled devices repair and "
    "are not counted. Reinforcements due in 1..window days (Not scheduled = 9999 / 19999 / 29999) need their whole "
    "TOE. Costs (manual 13.2.2.6, 13.2.2.7): a squad (Squad, Engineer) costs 1 armament point plus manpower equal to "
    "its load cost; a weapon costs armament points equal to its load cost plus the same manpower; a vehicle (AFV, "
    "Vehicle) costs vehicle points equal to its load cost plus the same manpower. Manual 13.7: Japanese "
    "reinforcements must be filled from production when they arrive, otherwise they arrive at 25% TOE without "
    "charge; Allied units are fed from their device pools, so production is only shown for the Japanese. Days to "
    "arrival is the i16 at offset 564 of the land unit and the load cost the i16 at 28 of the device record: not "
    "yet checked in the game.")

LOSSES_ALL = "All"
LOSSES_VIEWS = ("Ships sunk", "Aircraft")
LOSSES_SUMMARY_COLUMNS = [
    ("side", "Side", 80, False, lambda r: r.side),
    ("ships", "Ships sunk", 80, True, lambda r: r.ships),
    ("turn_air", "Air (turn)", 75, True, lambda r: r.turn_air),
    ("turn_ground", "Ground (turn)", 90, True, lambda r: r.turn_ground),
    ("turn_flak", "Flak (turn)", 80, True, lambda r: r.turn_flak),
    ("turn_ops", "Ops (turn)", 75, True, lambda r: r.turn_ops),
    ("turn_total", "Total (turn)", 85, True, lambda r: r.turn_total),
    ("air", "Air", 65, True, lambda r: r.air),
    ("ground", "Ground", 70, True, lambda r: r.ground),
    ("flak", "Flak", 65, True, lambda r: r.flak),
    ("ops", "Ops", 65, True, lambda r: r.ops),
    ("total", "Total", 75, True, lambda r: r.total),
]
_LOSS_NUMBERS = ("ships", "turn_air", "turn_ground", "turn_flak", "turn_ops", "turn_total", "air", "ground", "flak",
                 "ops", "total")
LOSSES_SUMMARY_TEXT = dict.fromkeys(_LOSS_NUMBERS, _num)
LOSSES_SUNK_COLUMNS = [
    ("id", "ID", 55, True, lambda r: r.id),
    ("name", "Ship", 170, False, lambda r: r.name),
    ("side", "Side", 70, False, lambda r: r.side),
    ("nation", "Nation", 60, False, lambda r: r.nation),
    ("type", "Type", 55, False, lambda r: r.type),
    ("class", "Class", 150, False, lambda r: r.class_name),
    ("date", "Date", 90, True, lambda r: r.date),
    ("cause", "Cause", 170, False, lambda r: r.cause),
    ("location", "Location", 190, False, lambda r: r.location),
    ("scuttled", "Scuttled", 65, False, lambda r: r.scuttled),
]
LOSSES_SUNK_COLUMN_BY_ID = {c[0]: c for c in LOSSES_SUNK_COLUMNS}
LOSSES_SUNK_TEXT = {"date": airgroups.format_day_date, "scuttled": lambda v: "Yes" if v else ""}
LOSSES_AIRCRAFT_COLUMNS = [
    ("id", "ID", 45, True, lambda r: r.id),
    ("name", "Aircraft", 160, False, lambda r: r.name),
    ("side", "Side", 65, False, lambda r: r.side),
    ("nation", "Nation", 60, False, lambda r: r.nation),
    ("type", "Type", 90, False, lambda r: r.type),
    ("turn_air", "Air (turn)", 75, True, lambda r: r.turn_air),
    ("turn_ground", "Ground (turn)", 90, True, lambda r: r.turn_ground),
    ("turn_flak", "Flak (turn)", 80, True, lambda r: r.turn_flak),
    ("turn_ops", "Ops (turn)", 75, True, lambda r: r.turn_ops),
    ("turn_total", "Total (turn)", 85, True, lambda r: r.turn_total),
    ("air", "Air", 65, True, lambda r: r.air),
    ("ground", "Ground", 70, True, lambda r: r.ground),
    ("flak", "Flak", 65, True, lambda r: r.flak),
    ("ops", "Ops", 65, True, lambda r: r.ops),
    ("total", "Total", 75, True, lambda r: r.total),
]
LOSSES_AIRCRAFT_COLUMN_BY_ID = {c[0]: c for c in LOSSES_AIRCRAFT_COLUMNS}
LOSSES_AIRCRAFT_TEXT = dict.fromkeys(_LOSS_NUMBERS[1:], _num)
LOSSES_NOTE = (
    "Ships sunk: ship records whose days to arrival is 19999. Cause is the u16 at 348: below 2000 the device (weapon) "
    "that sank the ship, 2000 to 2012 the game's other causes (foundered, collision, kamikaze, ...); the hex is "
    "x u16 at 352 and y u16 at 354 (both 0 = sunk at the base), the base the u16 at 356, the date the year, month "
    "and day bytes at 358 to 360, and a byte of 1 at 363 means scuttled. Aircraft: eight i32 per model from 196 of "
    "the aircraft record, this turn's losses to air combat, on the ground, to flak and in operations, then the "
    "totals; only models with a loss are listed. Offsets are from WiTPTracker's reader and match the saves seen; not "
    "yet compared with the game's screens. Sinking claims of the other side (fog of war) are not shown.")

REPAIR_ALL = "All"
REPAIR_VIEWS = ("Ships", "Ports")
REPAIR_SUMMARY_COLUMNS = [
    ("side", "Side", 80, False, lambda r: r.side),
    ("ships", "Damaged ships", 100, True, lambda r: r.ships),
    ("at_sea", "At sea", 70, True, lambda r: r.at_sea),
    ("in_port", "In port", 70, True, lambda r: r.in_port),
    ("shipyard", "Shipyard mode", 100, True, lambda r: r.shipyard),
    ("tons", "Damaged tons", 100, True, lambda r: r.tons),
]
REPAIR_SUMMARY_TEXT = dict.fromkeys(("ships", "at_sea", "in_port", "shipyard", "tons"), _num)
REPAIR_SHIP_COLUMNS = [
    ("id", "ID", 55, True, lambda r: r.id),
    ("name", "Ship", 160, False, lambda r: r.name),
    ("side", "Side", 70, False, lambda r: r.side),
    ("nation", "Nation", 55, False, lambda r: r.nation),
    ("type", "Type", 50, False, lambda r: r.type),
    ("class", "Class", 130, False, lambda r: r.class_name),
    ("tons", "Tons", 65, True, lambda r: r.tons),
    ("location", "Location", 190, False, lambda r: r.location),
    ("fires", "Fires", 45, True, lambda r: r.fires),
    ("system", "Sys", 40, True, lambda r: r.system),
    ("flotation", "Flt", 40, True, lambda r: r.flotation),
    ("major_flotation", "Maj Flt", 55, True, lambda r: r.major_flotation),
    ("engine", "Eng", 40, True, lambda r: r.engine),
    ("major_engine", "Maj Eng", 55, True, lambda r: r.major_engine),
    ("weapons", "Weapons", 60, True, lambda r: r.weapons),
    ("weapon_text", "Damaged weapons", 190, False, lambda r: r.weapon_text),
    ("priority", "Priority", 65, False, lambda r: r.priority),
    ("mode", "Mode", 85, False, lambda r: r.mode),
    ("delay", "Delay", 50, True, lambda r: r.delay),
    ("min_port", "Min port", 60, True, lambda r: r.min_port),
    ("min_yard", "Min yard", 65, True, lambda r: r.min_yard),
]
REPAIR_SHIP_COLUMN_BY_ID = {c[0]: c for c in REPAIR_SHIP_COLUMNS}
REPAIR_SHIP_TEXT = {"tons": _num, "min_port": lambda v: "-" if v >= shiprepair.NO_PORT else str(v),
                    "min_yard": _num}
REPAIR_PORT_COLUMNS = [
    ("id", "ID", 55, True, lambda r: r.id),
    ("name", "Port", 160, False, lambda r: r.name),
    ("side", "Side", 70, False, lambda r: r.side),
    ("port_size", "Port size", 65, True, lambda r: r.port_size),
    ("port_max", "Port max", 65, True, lambda r: r.port_max),
    ("port_damage", "Port damage", 80, True, lambda r: r.port_damage),
    ("largest", "Largest ship", 85, True, lambda r: r.largest),
    ("total", "Total docked", 90, True, lambda r: r.total),
    ("yard_size", "Yard size", 65, True, lambda r: r.yard_size),
    ("yard_damage", "Yard damage", 85, True, lambda r: r.yard_damage),
    ("yard_capacity", "Yard tons", 80, True, lambda r: r.yard_capacity),
    ("repair_points", "Repair pts/day", 95, True, lambda r: r.repair_points),
    ("ships", "Damaged ships", 95, True, lambda r: r.ships),
    ("tons", "Damaged tons", 90, True, lambda r: r.tons),
    ("shipyard_tons", "Shipyard-mode tons", 120, True, lambda r: r.shipyard_tons),
    ("largest_tons", "Largest damaged", 105, True, lambda r: r.largest_tons),
    ("oversize", "Too big", 60, True, lambda r: r.oversize),
]
REPAIR_PORT_COLUMN_BY_ID = {c[0]: c for c in REPAIR_PORT_COLUMNS}
REPAIR_PORT_TEXT = dict.fromkeys(("largest", "total", "yard_capacity", "repair_points", "tons", "shipyard_tons",
                                  "largest_tons"), _num)
REPAIR_PORT_TEXT["oversize"] = lambda v: str(v) if v else ""
REPAIR_NOTE = (
    "Arrived ships with any fires, system, flotation, major flotation, engine or major engine damage (u8 at 331 to "
    "336) or damaged weapon mounts (u8 at 270 + slot; the slot's device is the u16 at 70 + 2 x slot). Priority is "
    "the u8 at 338 (Low, Normal, High, Critical), mode the u8 at 339 (Readiness, Pierside, Repair ship, Shipyard) "
    "and delay the u16 at 342. Tons is the class displacement. Location: the base of a docked ship; a TF is in "
    "port when its hex is the hex of a base of its own side, otherwise at sea. Ports: size, max and damage from the location record, "
    "the repair yard is the factory of type 524; repair points a day = yard size x 10 and yard capacity = yard "
    "size x 1000 tons (manual 14.2.3.1); largest ship and total docked tonnage by port size from the manual's "
    "table (14.2). Min port is the smallest size whose largest ship reaches the tonnage ('-' = none), min yard the "
    "tonnage in thousands rounded up. Too big counts the damaged ships there larger than both the port's "
    "largest ship and the yard capacity. Offsets are from WiTPTracker's reader; not yet compared with the game's "
    "screens.")

MINE_ALL = "All"
MINE_VIEWS = ("By hex", "Fields")
MINE_SUMMARY_COLUMNS = [
    ("side", "Side", 80, False, lambda r: r.side),
    ("fields", "Fields", 60, True, lambda r: r.fields),
    ("hexes", "Hexes", 60, True, lambda r: r.hexes),
    ("mines", "Mines", 70, True, lambda r: r.mines),
    ("types", "Mines by type", 420, False, lambda r: minefields.types_text(r.by_device)),
]
MINE_SUMMARY_TEXT = dict.fromkeys(("fields", "hexes", "mines"), _num)
MINE_HEX_COLUMNS = [
    ("x", "X", 40, True, lambda r: r.x),
    ("y", "Y", 40, True, lambda r: r.y),
    ("side", "Side", 70, False, lambda r: r.side),
    ("place", "Place", 170, False, lambda r: r.place),
    ("mines", "Mines", 65, True, lambda r: r.mines),
    ("fields", "Fields", 50, True, lambda r: r.fields),
    ("types", "Mine types", 250, False, lambda r: r.types),
    ("detection", "Detection (unverified)", 135, True, lambda r: r.detection),
    ("decay", "Decay", 135, False, lambda r: r.decay),
    ("acms", "ACMs", 50, True, lambda r: r.acms),
    ("protected", "Protected", 70, True, lambda r: r.protected),
]
MINE_HEX_COLUMN_BY_ID = {c[0]: c for c in MINE_HEX_COLUMNS}
MINE_HEX_TEXT = dict.fromkeys(("mines", "protected"), _num)
MINE_FIELD_COLUMNS = [
    ("id", "Record", 55, True, lambda r: r.id),
    ("x", "X", 40, True, lambda r: r.x),
    ("y", "Y", 40, True, lambda r: r.y),
    ("side", "Side", 70, False, lambda r: r.side),
    ("place", "Place", 170, False, lambda r: r.place_name or minefields.OPEN_SEA),
    ("device", "Mine type", 150, False, lambda r: r.device_name),
    ("mines", "Mines", 65, True, lambda r: r.mines),
    ("detection", "Detection (unverified)", 135, True, lambda r: r.detection),
]
MINE_FIELD_COLUMN_BY_ID = {c[0]: c for c in MINE_FIELD_COLUMNS}
MINE_FIELD_TEXT = {"mines": _num}
MINE_NOTE = (
    "Section 0x1E, 6000 records of 20 bytes: hex x and y (u16 at 0 and 2), side (u16 at 4), u16 at 6 probably the "
    "detection level by the enemy (unverified), mine device (u16 at 8) and mines (u16 at 10). Records with no "
    "mines, x or y of 0 or above 250, or 32768 or more mines are skipped. Place is the base or town in the hex; "
    "'(enemy base)' marks one of the other side. Decay (manual 6.6.1.2.1): 1%/day at a friendly base with port "
    "size 1 or more, otherwise 5-33%/day (5% in shallow water, 33% in deep water; the save has no water depth). "
    "ACMs are the arrived ships of class type 74 of the side docked at a base or town in the hex and in no task "
    "force; each protects 150 mines (manual 6.6.1.2.2), so Protected = the smaller of Mines and ACMs x 150. "
    "Layout from WiTPTracker's reader; not yet compared with the game's screens.")

VP_ALL = "All"
VP_SUMMARY_COLUMNS = [
    ("side", "Side", 80, False, lambda r: r.side),
    ("score", "Score", 70, True, lambda r: r.score),
    ("bases", "Bases", 60, True, lambda r: r.bases),
    ("base_points", "Base points", 85, True, lambda r: r.base_points),
    ("aircraft", "Aircraft destroyed", 120, True, lambda r: r.aircraft),
    ("aircraft_points", "Aircraft points", 100, True, lambda r: r.aircraft_points),
    ("ground_points", "Ground points", 95, True, lambda r: r.ground_points),
    ("ships_sunk", "Enemy ships sunk", 115, True, lambda r: r.ships_sunk),
    ("other", "Other", 70, True, lambda r: r.other),
    ("political_points", "Political points", 105, True, lambda r: r.political_points),
]
VP_SUMMARY_TEXT = {c[0]: _num for c in VP_SUMMARY_COLUMNS if c[3]}
VP_BASE_COLUMNS = [
    ("name", "Base", 170, False, lambda r: r.name),
    ("side", "Owner", 70, False, lambda r: r.side),
    ("region", "Region", 150, False, lambda r: r.region),
    ("value_japan", "Value J", 60, True, lambda r: r.value_japan),
    ("value_allies", "Value A", 60, True, lambda r: r.value_allies),
    ("port", "Port", 45, True, lambda r: r.port),
    ("airfield", "Airfield", 60, True, lambda r: r.airfield),
    ("supply_pct", "Supply %", 70, True, lambda r: r.supply_pct),
    ("full", "Full", 65, True, lambda r: r.full),
    ("scored", "Scored", 65, True, lambda r: r.scored),
    ("to_japan", "To Japan", 70, True, lambda r: r.to_japan),
    ("to_allies", "To Allies", 70, True, lambda r: r.to_allies),
]
VP_BASE_COLUMN_BY_ID = {c[0]: c for c in VP_BASE_COLUMNS}
VP_BASE_TEXT = dict.fromkeys(("full", "scored", "to_japan", "to_allies"), _num)
VP_NOTE = (
    "Score is the stored victory points (scenario section 0x01, i32 at 116 Japanese and 120 Allied); the columns after "
    "it are an estimate from manual chapter 17. A base or town is worth the owner's basic VP x (port size + 2 x "
    "airfield size) (Value J and A are the basic VP; Full, To Japan and To Allies are for that owner) and scores 25% "
    "of that plus 75% x the supplied share (supply / supply required). Aircraft points are 1 VP per enemy aircraft "
    "lost, 2 for a heavy bomber (4 or more engines). Ground points are the other side's ground losses (i32 at 64876 "
    "Japanese, 64880 Allied; twelfths of a VP) // 12. Other = Score less base, aircraft and ground points; it covers "
    "ships sunk, industry damage and rules not modelled, and can be negative. Political points are the i32 at 65788 "
    "(Japanese) and 65792 (Allied). Victory levels per manual 17.1: ratio 1.75 decisive, 1.25 marginal. Offsets "
    "from WiTPTracker's reader; not yet compared with the game's Intel screen.")

ALERT_ALL = "All"
ALERT_COLUMNS = [
    ("category", "Category", 100, False, lambda r: r.category),
    ("side", "Side", 70, False, lambda r: r.side),
    ("subject", "Subject", 200, False, lambda r: r.subject),
    ("detail", "Detail", 700, False, lambda r: r.detail),
]
ALERT_COLUMN_BY_ID = {c[0]: c for c in ALERT_COLUMNS}
ALERT_NOTE = (
    "Gathers the problems the other reports show. Low supply: a base or town with supply below the chosen share of "
    "its requirement (worst: most victory points lost). Spoilage: supply or fuel over the limit (manual 15.7). "
    "Repair: a damaged ship in port that is above both the port's largest ship and its yard capacity, or a port "
    "whose Shipyard-mode queue is bigger than its yard. Minefields: one line per side with the mines in its own "
    "ports that no docked ACM protects (opens the Minefields report). Pilots: a nation's pool below the chosen "
    "number. Aircraft: a model in production whose groups are missing more planes than the pool plus 30 days of "
    "production. Engines: Japanese engines built in fewer numbers than the factories use. The two thresholds are "
    "not saved. Double-click a row to open the base, ship, pilot pool, aircraft, engine or minefields.")



def _shortest_text(v):
    days, key = v
    if not key:
        return "-"
    n = int(days)
    return f"{industry.BALANCE_ROWS[key]}: {n} day{'' if n == 1 else 's'}"


def _days_text(days):
    return "-" if days is None else _num(int(days))


# The Industry report: one table of factory types, one of daily material balances.
INDUSTRY_COLUMNS = [
    ("group", "Type", 130, False, lambda r: r.group),
    ("count", "Factories", 70, True, lambda r: r.count),
    ("size", "Size", 80, True, lambda r: r.size),
    ("damage", "Damaged", 80, True, lambda r: r.damage),
    ("production_off", "Production off", 90, True, lambda r: r.production_off),
    ("repair_off", "Repair off", 80, True, lambda r: r.repair_off),
    ("output", "Daily output", 260, False, lambda r: r.makes),
    ("input", "Daily input", 260, False, lambda r: r.uses),
]
INDUSTRY_TEXT = {"count": _num, "size": _num, "damage": _num, "production_off": _num, "repair_off": _num,
                 "output": industry.flow_text, "input": industry.flow_text}
BALANCE_COLUMNS = [
    ("label", "Material", 130, False, lambda r: r.label),
    ("stored", "Stored", 100, True, lambda r: r.stored),
    ("produced", "Produced/day", 100, True, lambda r: r.produced),
    ("allotted", "Allotted/day", 100, True, lambda r: r.allotted),
    ("used", "Used/day", 100, True, lambda r: r.used),
    ("net", "Net/day", 100, True, lambda r: r.net),
    ("days", "Days left", 80, True, lambda r: r.days),
]
BALANCE_TEXT = {"stored": lambda v: "?" if v is None else _num(v), "produced": _num, "allotted": _num, "used": _num,
                "net": _rate,
                "days": _days_text}
INDUSTRY_NOTE = ("Factory flows (game manual 13.2) plus the places' daily supply, fuel and oil allotments. Not "
                 "included: supply used by units, fuel used by ships. Manpower and the point rows are side-wide pools, "
                 "so they show no days left when a region is selected.")

FACTORY_COLUMNS = [
    ("id", "Place ID", 60, True, lambda r: r.place.id),
    ("place", "Place", 140, False, lambda r: r.place.name),
    ("kind", "Kind", 50, False, lambda r: r.place.kind),
    ("side", "Side", 70, False, lambda r: r.place.base.side),
    ("region", "Region", 110, False, lambda r: r.place.region),
    ("slot", "Slot", 40, True, lambda r: r.factory.slot),
    ("factory", "Factory", 150, False, lambda r: r.factory.name),
    ("size", "Size", 60, True, lambda r: r.factory.size),
    ("damage", "Damage", 60, True, lambda r: r.factory.damage),
    ("production", "Production", 70, False, lambda r: "Yes" if r.factory.production_on else "No"),
    ("repair", "Repair", 55, False, lambda r: "Yes" if r.factory.repair_on else "No"),
    ("output", "Daily output", 200, False, lambda r: industry.flow_text(r.flow.makes)),
    ("input", "Daily input", 200, False, lambda r: industry.flow_text(r.flow.uses)),
]
FACTORY_COLUMN_BY_ID = {c[0]: c for c in FACTORY_COLUMNS}
FACTORY_TYPE_ALL = "All types"

RAW_COLUMNS = [
    ("id", "Place ID", 60, True, lambda r: r.place.id),
    ("place", "Place", 140, False, lambda r: r.place.name),
    ("kind", "Kind", 50, False, lambda r: r.place.kind),
    ("side", "Side", 70, False, lambda r: r.place.base.side),
    ("region", "Region", 110, False, lambda r: r.place.region),
    ("allotment", "Allotment/day", 170, False, lambda r: industry.flow_text(r.allotment)),
    ("oil", "Oil", 80, True, lambda r: r.stored["oil"]),
    ("oil_day", "Oil/day", 70, True, lambda r: r.net["oil"]),
    ("resources", "Resources", 80, True, lambda r: r.stored["resources"]),
    ("resources_day", "Res/day", 70, True, lambda r: r.net["resources"]),
    ("fuel", "Fuel", 80, True, lambda r: r.stored["fuel"]),
    ("fuel_day", "Fuel/day", 70, True, lambda r: r.net["fuel"]),
    ("supply", "Supply", 80, True, lambda r: r.stored["supply"]),
    ("supply_day", "Supply/day", 70, True, lambda r: r.net["supply"]),
    # (days, material) so it sorts by days; places where nothing runs down sort last.
    ("shortest", "Shortest", 130, True, lambda r: (r.shortest[1], r.shortest[0]) if r.shortest else (float("inf"), "")),
]
RAW_COLUMN_BY_ID = {c[0]: c for c in RAW_COLUMNS}
RAW_TEXT = {"oil": _num, "resources": _num, "fuel": _num, "supply": _num, "oil_day": _rate,
            "resources_day": _rate, "fuel_day": _rate, "supply_day": _rate, "shortest": _shortest_text}
RAW_NOTE = ("Per place, from that place's own factories and daily allotment. The game moves oil, resources and "
            "fuel overland between connected places, so a local shortfall does not always stop a factory.")

# Air production: one row per aircraft model (airproduction.AirRow); the lower table lists the
# factories building the selected model (airproduction.PlantEntry).
AIR_COLUMNS = [
    ("id", "ID", 45, True, lambda r: r.id),
    ("name", "Aircraft", 140, False, lambda r: r.name),
    ("type", "Type", 85, False, lambda r: r.type),
    ("side", "Side", 65, False, lambda r: r.side),
    ("engines", "Engines", 130, False, lambda r: r.engines),
    ("pool", "Pool", 50, True, lambda r: r.pool),
    ("used", "Used", 50, True, lambda r: r.used),
    ("factories", "Factories", 60, True, lambda r: r.factories),
    ("size", "Size", 50, True, lambda r: r.size),
    ("research", "Research", 60, True, lambda r: r.research),
    ("damage", "Damaged", 60, True, lambda r: r.damage),
    ("production_off", "Prod off", 55, True, lambda r: r.production_off),
    ("repair_off", "Repair off", 65, True, lambda r: r.repair_off),
    ("planes_day", "Planes/day", 70, True, lambda r: r.planes_day),
    ("hi_day", "HI/day", 65, True, lambda r: r.hi_day),
    ("engines_day", "Engines/day", 75, True, lambda r: -1 if r.engines_day is None else r.engines_day),
    ("groups", "Groups", 50, True, lambda r: r.groups),
    ("in_groups", "In groups", 65, True, lambda r: r.in_groups),
    ("short", "Short", 45, True, lambda r: r.short),
    ("next_group", "Next group", 75, True, lambda r: float("inf") if r.next_group is None else r.next_group),
    ("available", "Available", 110, False, lambda r: r.available),
]
AIR_COLUMN_BY_ID = {c[0]: c for c in AIR_COLUMNS}
AIR_TEXT = {"pool": _num, "used": _num, "factories": _num, "size": _num, "research": _num, "damage": _num,
            "production_off": _num, "repair_off": _num, "planes_day": lambda v: f"{v:,.1f}",
            "hi_day": lambda v: f"{v:,.1f}", "engines_day": lambda v: "-" if v < 0 else f"{v:,.1f}",
            "in_groups": _num, "next_group": lambda v: "-" if v == float("inf") else v}
AIR_FACTORY_COLUMNS = [
    ("id", "Place ID", 60, True, lambda e: e.place.id),
    ("place", "Place", 140, False, lambda e: e.place.name),
    ("kind", "Kind", 50, False, lambda e: e.place.kind),
    ("side", "Side", 70, False, lambda e: e.place.base.side),
    ("region", "Region", 110, False, lambda e: e.place.region),
    ("slot", "Slot", 40, True, lambda e: e.factory.slot),
    ("size", "Size", 60, True, lambda e: e.factory.size),
    ("damage", "Damage", 60, True, lambda e: e.factory.damage),
    ("production", "Production", 70, False, lambda e: "Yes" if e.factory.production_on else "No"),
    ("repair", "Repair", 55, False, lambda e: "Yes" if e.factory.repair_on else "No"),
    ("upgrade", "Upgrade", 60, False, lambda e: "Upgd" if e.factory.upgrade_on else "Keep"),
    ("available", "Available", 70, False, lambda e: f"{e.factory.available[0]}/{e.factory.available[1]}"),
]
AIR_NOTE = ("Rules (game manual 13.2.2.4, 13.2.2.5): a factory builds size / 30 aircraft per day; HI per day = planes per "
            "day x 18 x engines per aircraft; Japanese aircraft also use one engine per engine fitted, Allied aircraft "
            "need none. Size counts factories with production on whose model is available; Research is the size of "
            "factories whose model is not yet available, which build and use nothing yet. WitPTracker shows a different "
            "HI per day for Allied airframes; its rule is unknown, this report follows the manual. Not yet tested in-game.")

ENGINE_COLUMNS = [
    ("id", "ID", 45, True, lambda r: r.id),
    ("name", "Engine", 140, False, lambda r: r.name),
    ("factories", "Factories", 60, True, lambda r: r.factories),
    ("size", "Size", 55, True, lambda r: r.size),
    ("damage", "Damaged", 60, True, lambda r: r.damage),
    ("production_off", "Prod off", 55, True, lambda r: r.production_off),
    ("pool", "Pool", 60, True, lambda r: -1 if r.pool is None else r.pool),
    ("needed", "Needed/month", 85, True, lambda r: r.needed),
    ("net", "Net/month", 75, True, lambda r: r.net),
    ("hi_day", "HI/day", 60, True, lambda r: r.hi_day),
    ("used_by", "Used by", 500, False, lambda r: r.used_by),
]
ENGINE_COLUMN_BY_ID = {c[0]: c for c in ENGINE_COLUMNS}
ENGINE_TEXT = {"factories": _num, "size": _num, "damage": _num, "production_off": _num,
               "pool": lambda v: "?" if v < 0 else _num(v), "needed": _num, "net": _rate,
               "hi_day": lambda v: f"{v:,.1f}"}
ENGINE_NOTE = ("Japanese engines only. Size is engines per month from factories with production on (size / 30 per day, "
               "18 HI each); Needed/month is the engines the Japanese aircraft factories with production on need "
               "(size x engines per aircraft, available models only). Allied aircraft do not need engines. Not yet "
               "tested in-game.")
COMPARE_NOTE = ("\u25b2 marks the better value of a row (higher is better). Pictures are read from the game's ART folder. "
                "Service rating is not stored in saves.")

REGION_ALL = "All regions"


def region_choices():
    """Region combobox label -> region id (None for all), in id order; a repeated name gets its id."""
    found = regions.default_regions().regions()
    names = [name for _id, name in found]
    choices = {REGION_ALL: None}
    for region_id, name in found:
        choices[f"{name} ({region_id})" if names.count(name) > 1 else name] = region_id
    choices[regions.UNASSIGNED_NAME] = regions.UNASSIGNED_ID
    return choices


MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

HISTORY_SIDE_COLORS = {"Allied": "#2f6fd0", "Japanese": "#d03a2f"}
HISTORY_VIEWS = ("Sides", "Base", "Aircraft")
HISTORY_BOTH = "Both"
HISTORY_NONE_TEXT = "-"
# One table for both views; the view picks the columns it shows.
HISTORY_COLUMNS = [
    ("date", "Date", 90, False, None), ("turn", "Turn", 50, True, None), ("side", "Side", 80, False, None),
    ("allied", "Allied", 110, True, None), ("allied_change", "Allied change", 110, True, None),
    ("japanese", "Japanese", 110, True, None), ("japanese_change", "Japanese change", 120, True, None),
    ("value", "Value", 110, True, None), ("change", "Change", 110, True, None),
]
HISTORY_SIDES_COLUMNS = ("date", "turn", "allied", "allied_change", "japanese", "japanese_change")
HISTORY_BASE_COLUMNS = ("date", "turn", "side", "value", "change")
HISTORY_AIRCRAFT_COLUMNS = ("date", "turn", "value", "change")

MAP_SCALES = {"12%": 8, "25%": 4, "50%": 2, "100%": 1}  # label -> every step-th pixel of the art
MAP_OVERLAYS = ("Locations", "Search arcs", "Task forces", "Combat")
MAP_SIDES = ("All", "Allied", "Japanese")
MAP_TOWNS = ("Bases", "Bases and towns")
MAP_ARC_KINDS = ("Naval", "ASW")
MAP_ARC_MODES = ("All", "Defined", "Random")
MAP_OTHER_COLOR = "#777777"
MAP_COMBAT_COLOR = "#e08a00"
MAP_PLAIN_COLOR = "#c9d6e3"
MAP_CLICK_PIXELS = 3  # a press that moves more than this is a drag of the map, not a click

INTEL_ALL = "All"
INTEL_VIEWS = ("Lines", "By place")
INTEL_NOTE = (
    "Read from the game's asigint_*.txt / jsigint_*.txt and a/joperationsreport_*.txt files in the save's folder "
    "(the parent folder for a save in autosave); an undated copy is used only for a turn that has no dated file. "
    "Lines no rule recognises are kept as Other. Double-click a row that names a place to open it. Nothing here "
    "writes to those files. Combat reads combatreport_*.txt (both sides in one file) and ignores Reports of.")


def _intel_hex(value):
    return "" if value[0] < 0 else f"{value[0]},{value[1]}"


INTEL_TEXT = {"date": chart.date_label, "last": chart.date_label, "hex": _intel_hex}
INTEL_LINE_COLUMNS = [
    ("date", "Date", 80, True, lambda r: r.line.date),
    ("kind", "Type", 100, False, lambda r: r.line.kind),
    ("place", "Place", 140, False, lambda r: r.place),
    ("hex", "Hex", 70, True, lambda r: (-1, -1) if r.line.x is None else (r.line.x, r.line.y)),
    ("unit", "Unit", 240, False, lambda r: r.line.unit),
    ("detail", "Detail", 330, False, lambda r: r.line.detail),
]
INTEL_PLACE_COLUMNS = [
    ("place", "Place", 160, False, lambda r: r.place),
    ("hex", "Hex", 70, True, lambda r: (-1, -1) if r.x is None else (r.x, r.y)),
    ("radio", "Radio", 60, True, lambda r: r.counts.get("Radio", 0)),
    ("heavy", "Heavy radio", 80, True, lambda r: r.counts.get("Heavy radio", 0)),
    ("units", "Units", 60, True, lambda r: r.counts.get("Unit located", 0)),
    ("last", "Last seen", 80, True, lambda r: r.last),
    ("reports", "Reports", 60, True, lambda r: r.total),
    ("named", "Units named", 480, False, lambda r: r.units),
]
INTEL_OPS_COLUMNS = [
    ("date", "Date", 80, True, lambda r: r.line.date),
    ("kind", "Category", 90, False, lambda r: r.line.kind),
    ("place", "Place", 140, False, lambda r: r.place),
    ("hex", "Hex", 70, True, lambda r: (-1, -1) if r.line.x is None else (r.line.x, r.line.y)),
    ("text", "Text", 700, False, lambda r: r.line.text),
]
INTEL_COMBAT_COLUMNS = [
    ("date", "Date", 80, True, lambda r: r.line.date),
    ("kind", "Kind", 120, False, lambda r: r.line.kind),
    ("phase", "Phase", 70, False, lambda r: r.line.phase),
    ("place", "Place", 140, False, lambda r: r.place),
    ("hex", "Hex", 70, True, lambda r: (-1, -1) if r.line.x is None else (r.line.x, r.line.y)),
    ("allied_air", "Allied a/c", 70, True, lambda r: r.line.allied_aircraft),
    ("japanese_air", "Japanese a/c", 80, True, lambda r: r.line.japanese_aircraft),
    ("allied_lost", "Allied a/c lost", 90, True, lambda r: r.line.allied_air_lost),
    ("japanese_lost", "Japanese a/c lost", 100, True, lambda r: r.line.japanese_air_lost),
    ("ships_hit", "Ships hit", 70, True, lambda r: r.line.ships_hit),
    ("ships_sunk", "Ships sunk", 70, True, lambda r: r.line.allied_ships_sunk + r.line.japanese_ships_sunk),
    ("ground", "Ground losses (A/J)", 120, True, lambda r: (r.line.allied_ground_lost, r.line.japanese_ground_lost)),
]
INTEL_COMBAT_TEXT = {**INTEL_TEXT, "ground": lambda v: f"{v[0]}/{v[1]}"}
INTEL_TABLES = {"lines": INTEL_LINE_COLUMNS, "places": INTEL_PLACE_COLUMNS, "ops": INTEL_OPS_COLUMNS,
                "combat": INTEL_COMBAT_COLUMNS}


def _history_number(value):
    return HISTORY_NONE_TEXT if value is None else f"{value:,}"


def _history_change(value):
    return HISTORY_NONE_TEXT if value is None else f"{value:+,}"



class EditorApp:
    def __init__(self, root):
        self.root = root
        root.title("WitP:AE Base Editor")
        self.save = None
        self.path = None
        self.bases = {}
        self.edited = set()
        self.dirty = False
        self.pbem = False
        self.sort_col = "id"
        self.sort_reverse = False
        self.field_vars = {}
        self.stockpile_vars = {}
        self.building_vars = {}
        self.field_entries = {}
        self.building_checks = {}
        self.current = None
        self.factory_slot = None
        self.aircraft = {}
        self.aircraft_edited = set()
        self.aircraft_sort_col = "id"
        self.aircraft_sort_reverse = False
        self.aircraft_vars = {}
        self.compare_cols = []
        self.compare_ids = {}
        self.plane_images = {}
        self.aircraft_current = None
        self.ships = {}
        self.ships_edited = set()
        self.ship_sort_col = "id"
        self.ship_sort_reverse = False
        self.ship_vars = {}
        self.ship_current = None
        self.ship_slot = None
        self.shiprecs = {}
        self.shiprecs_edited = set()
        self.shiprec_sort_col = "id"
        self.shiprec_sort_reverse = False
        self.shiprec_vars = {}
        self.shiprec_current = None
        self.shiprec_slot = None
        self.taskforces = {}
        self.tfs_edited = set()
        self.tf_sort_col = "id"
        self.tf_sort_reverse = False
        self.tf_current = None
        self.tf_info = {}
        self.tf_ship_current = None
        self.tf_destinations = []
        self.tf_add_ships = []
        self.tf_flag_ships = []
        self.places_by_hex = {}
        self.places_by_id = {}
        self.tf_port_items = []
        self.tf_dest_items = []
        self.tf_home_shown = []
        self.tf_dest_shown = []
        self.groups = {}
        self.pilot_index = {}
        self.groups_edited = set()
        self.group_sort_col = "id"
        self.group_sort_reverse = False
        self.group_vars = {}
        self.group_current = None
        self.pilot_current = None
        self.pilot_vars = {}
        self.leader_vars = {}
        self.leader_current = None
        self.ldr_rows = {}
        self.ldr_assign = {}
        self.ldr_edited = set()
        self.ldr_sort_col = "id"
        self.ldr_sort_reverse = False
        self.ldr_vars = {}
        self.ldr_current = None
        self.ldr_search_job = None
        self.pools = {}
        self.pools_edited = set()
        self.pool_current = None
        self.pool_vars = {}
        self.place_ids = {}
        self.place_labels = {}
        self.device_ids = {}
        self.device_labels = {}
        self.aircraft_ids = {}
        self.aircraft_labels = {}
        self.units = {}
        self.units_edited = set()
        self.unit_sort_col = "id"
        self.unit_sort_reverse = False
        self.unit_vars = {}
        self.unit_current = None
        self.unit_slot = None
        self.spoilage_all = []
        self.spoilage_sort_col = "total"
        self.spoilage_sort_reverse = True
        self.upgrades_all = []
        self.upgrade_sort_col = "due"
        self.upgrade_sort_reverse = False
        self.production_all = []
        self.production_summary = []
        self.production_sort_col = "delay"
        self.production_sort_reverse = False
        self.lcu_unit_all = []
        self.lcu_device_all = []
        self.lcu_summary = []
        self.lcu_unit_sort_col = "armament"
        self.lcu_unit_sort_reverse = True
        self.lcu_device_sort_col = "armament"
        self.lcu_device_sort_reverse = True
        self.losses_sunk_all = []
        self.losses_aircraft_all = []
        self.losses_summary = []
        self.losses_sunk_sort_col = "date"
        self.losses_sunk_sort_reverse = False
        self.losses_aircraft_sort_col = "total"
        self.losses_aircraft_sort_reverse = True
        self.repair_ships_all = []
        self.repair_ports_all = []
        self.repair_summary = []
        self.repair_ship_sort_col = "tons"
        self.repair_ship_sort_reverse = True
        self.repair_port_sort_col = "tons"
        self.repair_port_sort_reverse = True
        self.minefield_fields_all = []
        self.minefield_hexes_all = []
        self.minefield_summary = []
        self.minefield_hex_sort_col = "mines"
        self.minefield_hex_sort_reverse = True
        self.minefield_field_sort_col = "mines"
        self.minefield_field_sort_reverse = True
        self.vp_summary = []
        self.vp_bases_all = []
        self.vp_sort_col = "scored"
        self.vp_sort_reverse = True
        self.alerts_all = []
        self.alerts_skipped = []
        self.alerts_by_iid = {}
        self.alert_sort_col = None  # None keeps the order alerts.collect gives
        self.alert_sort_reverse = False
        self.history_dir = None
        self.history_snaps = []
        self.history_problems = []
        self.history_kept = None  # the RecordResult of the open save when its date was kept from another file
        self.history_choices = {}
        self.history_aircraft_choices = {}
        self.intel_folder = None
        self.intel_all = {"sigint": [], "ops": []}  # every IntelLine of the folder; the filters only re-select
        self.intel_index = None  # the open save's intel.PlaceIndex
        self.intel_message = ""
        self.intel_combat_all = []  # every CombatAction of the folder
        self.intel_combat_rows = []  # the Resolved rows in the Combat tree, by iid
        self.intel_shown = {"sigint": 0, "ops": 0}
        self.intel_sort = {name: [None, False] for name in INTEL_TABLES}  # column, reverse
        self.intel_place_by_iid = {name: {} for name in INTEL_TABLES}
        self.industry_places = []
        self.region_ids = region_choices()
        self.factory_report_sort_col = "id"
        self.factory_report_sort_reverse = False
        self.raw_sort_col = "shortest"
        self.raw_sort_reverse = False
        self.air_entries = []
        self.air_rows_all = []
        self.engine_rows_all = []
        self.air_sort_col = "size"
        self.air_sort_reverse = True
        self.engine_sort_col = "size"
        self.engine_sort_reverse = True
        self.factory_model_ids = {}

        self._build_menu()
        self._build_header()
        self._build_body()
        self.status = tk.StringVar(value="No save loaded")
        ttk.Label(root, textvariable=self.status, relief="sunken", anchor="w").pack(side="bottom", fill="x")
        root.protocol("WM_DELETE_WINDOW", self.quit)

    # ---- widgets -------------------------------------------------------

    def _build_menu(self):
        menu = tk.Menu(self.root)
        file_menu = tk.Menu(menu, tearoff=False)
        file_menu.add_command(label="Open...", command=self.open_dialog, accelerator="Ctrl+O")
        file_menu.add_command(label="Save As...", command=self.save_as, accelerator="Ctrl+S")
        file_menu.add_separator()
        file_menu.add_command(label="Quit", command=self.quit)
        menu.add_cascade(label="File", menu=file_menu)
        self.root.config(menu=menu)
        self.root.bind("<Control-o>", lambda e: self.open_dialog())
        self.root.bind("<Control-s>", lambda e: self.save_as())

    def _build_header(self):
        head = ttk.Frame(self.root, padding=4)
        head.pack(side="top", fill="x")
        self.file_label = tk.StringVar(value="File: (none)")
        ttk.Label(head, textvariable=self.file_label).grid(row=0, column=0, columnspan=3, sticky="w")
        ttk.Label(head, text="Save title:").grid(row=1, column=0, sticky="w")
        self.title_var = tk.StringVar()
        ttk.Entry(head, textvariable=self.title_var, width=50).grid(row=1, column=1, sticky="we", padx=4)
        ttk.Button(head, text="Apply title", command=self.apply_title).grid(row=1, column=2)
        head.columnconfigure(1, weight=1)

    def _build_body(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(side="top", fill="both", expand=True)
        body = self.bases_tab = ttk.Frame(self.notebook, padding=4)
        self.notebook.add(body, text="Bases")
        self._build_aircraft_tab()
        self._build_ships_tab()
        self._build_shiprecs_tab()
        self._build_taskforces_tab()
        self._build_groups_tab()
        self._build_units_tab()
        self._build_leaders_tab()
        self._build_reports_tab()
        self._build_history_tab()
        self._build_intel_tab()
        self._build_map_tab()

        left = ttk.Frame(body)
        left.pack(side="left", fill="both", expand=True)
        bar = ttk.Frame(left)
        bar.pack(side="top", fill="x")
        ttk.Label(bar, text="Search:").pack(side="left")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *a: self.refresh_list())
        ttk.Entry(bar, textvariable=self.search_var, width=20).pack(side="left", padx=4)
        ttk.Label(bar, text="Side:").pack(side="left")
        self.side_var = tk.StringVar(value="All")
        side_box = ttk.Combobox(bar, textvariable=self.side_var, values=["All", "Allied", "Japanese"],
                                state="readonly", width=9)
        side_box.pack(side="left", padx=4)
        side_box.bind("<<ComboboxSelected>>", lambda e: self.refresh_list())

        self._build_factories(left)

        self.tree = ttk.Treeview(left, columns=[c[0] for c in COLUMNS], show="headings", selectmode="browse")
        for cid, heading, width, _numeric, _get in COLUMNS:
            self.tree.heading(cid, text=heading, command=lambda c=cid: self.sort_by(c))
            self.tree.column(cid, width=width, anchor="w" if cid in ("name", "kind", "side") else "e")
        self.tree.tag_configure("edited", background="#fff2b3")
        scroll = ttk.Scrollbar(left, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", lambda e: self.on_select())

        right = ttk.LabelFrame(body, text="Base", padding=8)
        right.pack(side="right", fill="y", padx=(8, 0))
        self.detail_title = tk.StringVar(value="(select a base)")
        ttk.Label(right, textvariable=self.detail_title, font=("TkDefaultFont", 11, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
        for row, f in enumerate(bases.FIELDS, start=1):
            label = f.label + ("" if f.verified else " (unverified)") + ("" if f.editable else " (read-only)")
            ttk.Label(right, text=label).grid(row=row, column=0, sticky="w", pady=2)
            var = tk.StringVar()
            self.field_vars[f.name] = var
            entry = ttk.Entry(right, textvariable=var, width=14, state="normal" if f.editable else "readonly")
            self.field_entries[f.name] = entry
            entry.grid(row=row, column=1, padx=(8, 0), pady=2)
        stock_row = len(bases.FIELDS) + 1
        ttk.Label(right, text="Stockpile").grid(row=stock_row, column=0, sticky="nw", pady=2)
        stock_box = ttk.Frame(right)
        stock_box.grid(row=stock_row, column=1, sticky="w", padx=(8, 0), pady=2)
        for name, label, _bit in bases.STOCKPILE_FLAGS:
            var = tk.BooleanVar()
            self.stockpile_vars[name] = var
            ttk.Checkbutton(stock_box, text=label, variable=var).pack(anchor="w")
        build_row = stock_row + 1
        ttk.Label(right, text="Build/expand").grid(row=build_row, column=0, sticky="nw", pady=2)
        build_box = ttk.Frame(right)
        build_box.grid(row=build_row, column=1, sticky="w", padx=(8, 0), pady=2)
        for name, label, _live, _copy in bases.BUILD_SWITCHES:
            var = tk.BooleanVar()
            self.building_vars[name] = var
            check = ttk.Checkbutton(build_box, text=label, variable=var)
            check.pack(anchor="w")
            self.building_checks[name] = check
        buttons = ttk.Frame(right)
        buttons.grid(row=build_row + 1, column=0, columnspan=2, pady=(10, 0))
        self.apply_btn = ttk.Button(buttons, text="Apply", command=self.apply)
        self.apply_btn.pack(side="left", padx=2)
        self.history_btn = ttk.Button(buttons, text="History", command=self.show_base_history)
        self.history_btn.pack(side="left", padx=2)

    def _build_reports_tab(self):
        tab = self.reports_tab = ttk.Frame(self.notebook, padding=4)
        self.notebook.add(tab, text="Reports")
        self.game_date_var = tk.StringVar(value="Game date: unknown")
        ttk.Label(tab, textvariable=self.game_date_var).pack(side="top", anchor="w")
        self.reports_notebook = ttk.Notebook(tab)
        self.reports_notebook.pack(side="top", fill="both", expand=True, pady=(4, 0))

        self._build_alerts_report()
        spoil = ttk.Frame(self.reports_notebook, padding=4)
        self.reports_notebook.add(spoil, text="Spoilage")
        bar = ttk.Frame(spoil)
        bar.pack(side="top", fill="x")
        ttk.Label(bar, text="Side:").pack(side="left")
        self.spoilage_side_var = tk.StringVar(value="All")
        side_box = ttk.Combobox(bar, textvariable=self.spoilage_side_var, values=["All", "Allied", "Japanese"],
                                state="readonly", width=9)
        side_box.pack(side="left", padx=4)
        side_box.bind("<<ComboboxSelected>>", lambda e: self.refresh_spoilage_list())
        self.spoilage_count = tk.StringVar()
        ttk.Label(bar, textvariable=self.spoilage_count).pack(side="left", padx=8)
        ttk.Label(spoil, text=SPOILAGE_NOTE).pack(side="bottom", anchor="w", pady=(4, 0))
        self.spoilage_tree = self._report_tree(spoil, SPOILAGE_COLUMNS, self.sort_spoilage_by,
                                               ("name", "kind", "side", "region"), self.jump_to_spoilage_base)

        ups = ttk.Frame(self.reports_notebook, padding=4)
        self.reports_notebook.add(ups, text="Ship upgrades")
        bar = ttk.Frame(ups)
        bar.pack(side="top", fill="x")
        ttk.Label(bar, text="Search:").pack(side="left")
        self.upgrade_search_var = tk.StringVar()
        self.upgrade_search_var.trace_add("write", lambda *a: self.refresh_upgrade_list())
        ttk.Entry(bar, textvariable=self.upgrade_search_var, width=20).pack(side="left", padx=4)
        ttk.Label(bar, text="Side:").pack(side="left")
        self.upgrade_side_var = tk.StringVar(value="All")
        side_box = ttk.Combobox(bar, textvariable=self.upgrade_side_var, values=["All", "Allied", "Japanese"],
                                state="readonly", width=9)
        side_box.pack(side="left", padx=4)
        side_box.bind("<<ComboboxSelected>>", lambda e: self.refresh_upgrade_list())
        ttk.Label(bar, text="Due within:").pack(side="left")
        self.upgrade_due_var = tk.StringVar(value="3 months")
        due_box = ttk.Combobox(bar, textvariable=self.upgrade_due_var, values=list(UPGRADE_DUE),
                               state="readonly", width=10)
        due_box.pack(side="left", padx=4)
        due_box.bind("<<ComboboxSelected>>", lambda e: self.refresh_upgrade_list())
        self.upgrade_count = tk.StringVar()
        ttk.Label(bar, textvariable=self.upgrade_count).pack(side="left", padx=8)
        self.upgrade_tree = self._report_tree(ups, UPGRADE_COLUMNS, self.sort_upgrades_by,
                                              ("ship", "type", "side", "class", "target", "change", "location"),
                                              self.jump_to_upgrade_ship)

        self._build_production_report()
        self._build_lcu_report()
        self._build_industry_reports()
        self._build_air_reports()
        self._build_compare_report()
        self._build_losses_report()
        self._build_repair_report()
        self._build_minefield_report()
        self._build_victory_report()

        # Bound last so the handlers never run before the lists exist.
        self.notebook.bind("<<NotebookTabChanged>>", lambda e: self._reports_shown())
        self.reports_notebook.bind("<<NotebookTabChanged>>", lambda e: self._reports_shown())

    def _build_production_report(self):
        prod = ttk.Frame(self.reports_notebook, padding=4)
        self.reports_notebook.add(prod, text="Ship production")
        ttk.Label(prod, text="Japanese ship construction (the Allies receive ships as scheduled reinforcements)"
                  ).pack(side="top", anchor="w")
        ttk.Label(prod, text=PRODUCTION_NOTE, wraplength=1100, justify="left").pack(side="bottom", anchor="w",
                                                                                    pady=(4, 0))
        top = ttk.Frame(prod)
        top.pack(side="top", fill="x", pady=(4, 0))
        self.production_summary_tree = self._report_tree(top, PRODUCTION_SUMMARY_COLUMNS, lambda c: None,
                                                         ("yard",), lambda: None)
        self.production_summary_tree.configure(height=2)
        bar = ttk.Frame(prod)
        bar.pack(side="top", fill="x", pady=(4, 0))
        ttk.Label(bar, text="Search:").pack(side="left")
        self.production_search_var = tk.StringVar()
        self.production_search_var.trace_add("write", lambda *a: self.refresh_production_list())
        ttk.Entry(bar, textvariable=self.production_search_var, width=20).pack(side="left", padx=4)
        self.production_yard_var = tk.StringVar(value=PRODUCTION_ALL)
        self._report_combo(bar, "Yard:", self.production_yard_var, [PRODUCTION_ALL, *shipproduction.YARDS],
                           self.refresh_production_list, 9)
        self.production_status_var = tk.StringVar(value=PRODUCTION_ALL)
        self._report_combo(bar, "Status:", self.production_status_var, [PRODUCTION_ALL, *shipproduction.STATUSES],
                           self.refresh_production_list, 14)
        self.production_type_var = tk.StringVar(value=PRODUCTION_ALL)
        ttk.Label(bar, text="Type:").pack(side="left")
        self.production_type_box = ttk.Combobox(bar, textvariable=self.production_type_var, values=[PRODUCTION_ALL],
                                                state="readonly", width=8)
        self.production_type_box.pack(side="left", padx=(4, 8))
        self.production_type_box.bind("<<ComboboxSelected>>", lambda e: self.refresh_production_list())
        self.production_count = tk.StringVar()
        ttk.Label(bar, textvariable=self.production_count).pack(side="left", padx=8)
        table = ttk.Frame(prod)
        table.pack(side="top", fill="both", expand=True, pady=(4, 0))
        self.production_tree = self._report_tree(table, PRODUCTION_COLUMNS, self.sort_production_by,
                                                 ("ship", "type", "class", "yard", "status"),
                                                 self.jump_to_production_ship)

    def _build_lcu_report(self):
        lcu = ttk.Frame(self.reports_notebook, padding=4)
        self.reports_notebook.add(lcu, text="LCU production")
        ttk.Label(lcu, text=LCU_NOTE, wraplength=1100, justify="left").pack(side="bottom", anchor="w", pady=(4, 0))
        top = ttk.Frame(lcu)
        top.pack(side="top", fill="x")
        self.lcu_summary_tree = self._report_tree(top, LCU_SUMMARY_COLUMNS, lambda c: None, ("label",), lambda: None)
        self.lcu_summary_tree.configure(height=3)
        bar = ttk.Frame(lcu)
        bar.pack(side="top", fill="x", pady=(4, 0))
        self.lcu_side_var = tk.StringVar(value="Japanese")
        self._report_combo(bar, "Side:", self.lcu_side_var, ["Japanese", "Allied"], self.refresh_lcu_reports, 9)
        self.lcu_window_var = tk.StringVar(value="30 days")
        self._report_combo(bar, "Window:", self.lcu_window_var, list(LCU_WINDOWS), self.refresh_lcu_reports, 9)
        self.lcu_view_var = tk.StringVar(value=LCU_VIEWS[0])
        for view in LCU_VIEWS:
            ttk.Radiobutton(bar, text=view, value=view, variable=self.lcu_view_var,
                            command=self._show_lcu_view).pack(side="left", padx=2)
        self.lcu_status_var = tk.StringVar(value=LCU_ALL)
        self.lcu_status_box = self._report_combo(bar, "  Status:", self.lcu_status_var,
                                                 [LCU_ALL, *lcuproduction.STATUSES], self.refresh_lcu_list, 20)
        ttk.Label(bar, text="Search:").pack(side="left")
        self.lcu_search_var = tk.StringVar()
        self.lcu_search_var.trace_add("write", lambda *a: self.refresh_lcu_list())
        ttk.Entry(bar, textvariable=self.lcu_search_var, width=20).pack(side="left", padx=4)
        self.lcu_count = tk.StringVar()
        ttk.Label(bar, textvariable=self.lcu_count).pack(side="left", padx=8)
        self.lcu_unit_frame = ttk.Frame(lcu)
        self.lcu_unit_tree = self._report_tree(self.lcu_unit_frame, LCU_UNIT_COLUMNS, self.sort_lcu_units_by,
                                               ("name", "type", "hq", "status"), self.jump_to_lcu_unit)
        self.lcu_device_frame = ttk.Frame(lcu)
        self.lcu_device_tree = self._report_tree(self.lcu_device_frame, LCU_DEVICE_COLUMNS,
                                                 self.sort_lcu_devices_by, ("name", "type", "kind"), lambda: None)
        self._show_lcu_view()

    def _show_lcu_view(self):
        units = self.lcu_view_var.get() == LCU_VIEWS[0]
        shown, hidden = (self.lcu_unit_frame, self.lcu_device_frame) if units else (self.lcu_device_frame,
                                                                                    self.lcu_unit_frame)
        hidden.pack_forget()
        shown.pack(side="top", fill="both", expand=True, pady=(4, 0))
        self.lcu_status_box.configure(state="readonly" if units else "disabled")
        self.refresh_lcu_list()

    def _report_combo(self, bar, label, var, values, command, width):
        ttk.Label(bar, text=label).pack(side="left")
        box = ttk.Combobox(bar, textvariable=var, values=list(values), state="readonly", width=width)
        box.pack(side="left", padx=(4, 8))
        box.bind("<<ComboboxSelected>>", lambda e: command())
        return box

    def _build_industry_reports(self):
        sides = ["All", "Allied", "Japanese"]

        ind = ttk.Frame(self.reports_notebook, padding=4)
        self.reports_notebook.add(ind, text="Industry")
        bar = ttk.Frame(ind)
        bar.pack(side="top", fill="x")
        self.industry_side_var = tk.StringVar(value="Allied")
        self._report_combo(bar, "Side:", self.industry_side_var, sides[1:], self.refresh_industry_report, 9)
        self.industry_region_var = tk.StringVar(value=REGION_ALL)
        self._report_combo(bar, "Region:", self.industry_region_var, self.region_ids, self.refresh_industry_report, 22)
        ttk.Label(ind, text=INDUSTRY_NOTE).pack(side="bottom", anchor="w", pady=(4, 0))
        top = ttk.Frame(ind)
        top.pack(side="top", fill="both", expand=True, pady=(4, 0))
        self.industry_tree = self._report_tree(top, INDUSTRY_COLUMNS, lambda c: None, ("group", "output", "input"),
                                               lambda: None)
        ttk.Label(ind, text="Daily balance (factories and allotments)").pack(side="top", anchor="w", pady=(6, 0))
        low = ttk.Frame(ind)
        low.pack(side="top", fill="x")
        self.balance_tree = self._report_tree(low, BALANCE_COLUMNS, lambda c: None, ("label",), lambda: None)
        self.balance_tree.configure(height=10)

        fac = ttk.Frame(self.reports_notebook, padding=4)
        self.reports_notebook.add(fac, text="Factories")
        bar = ttk.Frame(fac)
        bar.pack(side="top", fill="x")
        self.factory_report_side_var = tk.StringVar(value="All")
        self._report_combo(bar, "Side:", self.factory_report_side_var, sides, self.refresh_factory_report, 9)
        self.factory_report_region_var = tk.StringVar(value=REGION_ALL)
        self._report_combo(bar, "Region:", self.factory_report_region_var, self.region_ids,
                           self.refresh_factory_report, 22)
        self.factory_report_type_var = tk.StringVar(value=FACTORY_TYPE_ALL)
        self._report_combo(bar, "Factory type:", self.factory_report_type_var,
                           [FACTORY_TYPE_ALL] + industry.GROUP_ORDER, self.refresh_factory_report, 16)
        self.factory_report_problem_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Only damaged or switched off", variable=self.factory_report_problem_var,
                        command=self.refresh_factory_report).pack(side="left", padx=(0, 8))
        self.factory_report_count = tk.StringVar()
        ttk.Label(bar, textvariable=self.factory_report_count).pack(side="left", padx=8)
        self.factory_report_tree = self._report_tree(
            fac, FACTORY_COLUMNS, self.sort_factory_report_by,
            ("place", "kind", "side", "region", "factory", "production", "repair", "output", "input"),
            lambda: self.jump_to_industry_place(self.factory_report_tree))

        raw = ttk.Frame(self.reports_notebook, padding=4)
        self.reports_notebook.add(raw, text="Raw materials")
        bar = ttk.Frame(raw)
        bar.pack(side="top", fill="x")
        self.raw_side_var = tk.StringVar(value="All")
        self._report_combo(bar, "Side:", self.raw_side_var, sides, self.refresh_raw_list, 9)
        self.raw_region_var = tk.StringVar(value=REGION_ALL)
        self._report_combo(bar, "Region:", self.raw_region_var, self.region_ids, self.refresh_raw_list, 22)
        self.raw_only_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(bar, text="Only places with industry", variable=self.raw_only_var,
                        command=self.refresh_raw_list).pack(side="left", padx=(0, 8))
        self.raw_count = tk.StringVar()
        ttk.Label(bar, textvariable=self.raw_count).pack(side="left", padx=8)
        ttk.Label(raw, text=RAW_NOTE).pack(side="bottom", anchor="w", pady=(4, 0))
        self.raw_tree = self._report_tree(raw, RAW_COLUMNS, self.sort_raw_by, ("place", "kind", "side", "region"),
                                          lambda: self.jump_to_industry_place(self.raw_tree))

    def _build_air_reports(self):
        air = ttk.Frame(self.reports_notebook, padding=4)
        self.reports_notebook.add(air, text="Air production")
        bar = ttk.Frame(air)
        bar.pack(side="top", fill="x")
        ttk.Label(bar, text="Search:").pack(side="left")
        self.air_search_var = tk.StringVar()
        self.air_search_var.trace_add("write", lambda *a: self.refresh_air_list())
        ttk.Entry(bar, textvariable=self.air_search_var, width=20).pack(side="left", padx=4)
        self.air_side_var = tk.StringVar(value="All")
        self._report_combo(bar, "Side:", self.air_side_var, ["All", "Allied", "Japanese"], self.refresh_air_list, 9)
        self.air_only_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(bar, text="Only models in production or use", variable=self.air_only_var,
                        command=self.refresh_air_list).pack(side="left", padx=(0, 8))
        self.air_count = tk.StringVar()
        ttk.Label(bar, textvariable=self.air_count).pack(side="left", padx=8)
        ttk.Label(air, text=AIR_NOTE, wraplength=1100, justify="left").pack(side="bottom", anchor="w", pady=(4, 0))
        buttons = ttk.Frame(air)
        buttons.pack(side="bottom", fill="x", pady=(4, 0))
        ttk.Label(buttons, text="For every factory building the selected model:").pack(side="left")
        for text, production, repair in (("Production on", True, None), ("Production off", False, None),
                                         ("Repair on", None, True), ("Repair off", None, False)):
            ttk.Button(buttons, text=text, command=lambda t=text, p=production, r=repair: self.apply_air_switch(
                t, p, r)).pack(side="left", padx=4)
        low = ttk.LabelFrame(air, text="Factories building the selected model (double-click to open the place)",
                             padding=2)
        low.pack(side="bottom", fill="x", pady=(4, 0))
        self.air_factory_tree = self._report_tree(
            low, AIR_FACTORY_COLUMNS, lambda c: None, ("place", "kind", "side", "region", "production", "repair"),
            lambda: self.jump_to_industry_place(self.air_factory_tree))
        self.air_factory_tree.configure(height=7)
        top = ttk.Frame(air)
        top.pack(side="top", fill="both", expand=True, pady=(4, 0))
        self.air_tree = self._report_tree(top, AIR_COLUMNS, self.sort_air_by,
                                          ("name", "type", "side", "engines", "available"), lambda: None)
        self.air_tree.bind("<<TreeviewSelect>>", lambda e: self.refresh_air_factories())

        eng = ttk.Frame(self.reports_notebook, padding=4)
        self.engine_frame = eng
        self.reports_notebook.add(eng, text="Engines")
        bar = ttk.Frame(eng)
        bar.pack(side="top", fill="x")
        ttk.Label(bar, text="Side: Japan only").pack(side="left")
        self.engine_count = tk.StringVar()
        ttk.Label(bar, textvariable=self.engine_count).pack(side="left", padx=8)
        ttk.Label(eng, text=ENGINE_NOTE, wraplength=1100, justify="left").pack(side="bottom", anchor="w", pady=(4, 0))
        self.engine_tree = self._report_tree(eng, ENGINE_COLUMNS, self.sort_engines_by, ("name", "used_by"),
                                             lambda: None)

    def _build_compare_report(self):
        cmp = self.compare_frame = ttk.Frame(self.reports_notebook, padding=4)
        self.reports_notebook.add(cmp, text="Aircraft comparison")
        top = ttk.Frame(cmp)
        top.pack(side="top", fill="x")
        for k, letter in enumerate("AB"):
            box = ttk.LabelFrame(top, text=f"Aircraft {letter}", padding=4)
            box.pack(side="left", fill="x", expand=True, padx=(0, 4) if k == 0 else (4, 0))
            col = {"side": tk.StringVar(value="All"), "type": tk.StringVar(value="All"), "model": tk.StringVar()}
            bar = ttk.Frame(box)
            bar.pack(side="top", fill="x")
            ttk.Label(bar, text="Side:").pack(side="left")
            side_box = ttk.Combobox(bar, textvariable=col["side"], values=["All", "Allied", "Japanese"],
                                    state="readonly", width=9)
            side_box.pack(side="left", padx=4)
            ttk.Label(bar, text="Type:").pack(side="left")
            col["type_box"] = type_box = ttk.Combobox(bar, textvariable=col["type"], values=["All"],
                                                      state="readonly", width=14)
            type_box.pack(side="left", padx=4)
            col["model_box"] = ttk.Combobox(box, textvariable=col["model"], state="readonly", width=48)
            col["model_box"].pack(side="top", fill="x", pady=4)
            col["picture"] = self._picture_label(box)
            col["picture"].master.pack(side="top", anchor="w")
            for widget in (side_box, type_box):
                widget.bind("<<ComboboxSelected>>", lambda e, c=col: self.refresh_compare_choices(c))
            col["model_box"].bind("<<ComboboxSelected>>", lambda e: self.refresh_compare_table())
            self.compare_cols.append(col)
        table = ttk.Frame(cmp)
        ttk.Label(cmp, text=COMPARE_NOTE).pack(side="bottom", anchor="w", pady=(4, 0))
        table.pack(side="top", fill="both", expand=True, pady=(4, 0))
        self.compare_tree = ttk.Treeview(table, columns=("prop", "a", "b"), show="headings", selectmode="none")
        for cid, heading, width in (("prop", "Property", 180), ("a", "Aircraft A", 330), ("b", "Aircraft B", 330)):
            self.compare_tree.heading(cid, text=heading)
            self.compare_tree.column(cid, width=width, anchor="w")
        scroll = ttk.Scrollbar(table, orient="vertical", command=self.compare_tree.yview)
        self.compare_tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.compare_tree.pack(side="left", fill="both", expand=True)

    def _build_losses_report(self):
        loss = ttk.Frame(self.reports_notebook, padding=4)
        self.reports_notebook.add(loss, text="Losses")
        ttk.Label(loss, text=LOSSES_NOTE, wraplength=1100, justify="left").pack(side="bottom", anchor="w",
                                                                                pady=(4, 0))
        top = ttk.Frame(loss)
        top.pack(side="top", fill="x")
        self.losses_summary_tree = self._report_tree(top, LOSSES_SUMMARY_COLUMNS, lambda c: None, ("side",),
                                                     lambda: None)
        self.losses_summary_tree.configure(height=2)
        bar = ttk.Frame(loss)
        bar.pack(side="top", fill="x", pady=(4, 0))
        self.losses_side_var = tk.StringVar(value=LOSSES_ALL)
        self._report_combo(bar, "Side:", self.losses_side_var, [LOSSES_ALL, "Allied", "Japanese"],
                           self.refresh_losses_list, 9)
        self.losses_view_var = tk.StringVar(value=LOSSES_VIEWS[0])
        for view in LOSSES_VIEWS:
            ttk.Radiobutton(bar, text=view, value=view, variable=self.losses_view_var,
                            command=self._show_losses_view).pack(side="left", padx=2)
        ttk.Label(bar, text="  Search:").pack(side="left")
        self.losses_search_var = tk.StringVar()
        self.losses_search_var.trace_add("write", lambda *a: self.refresh_losses_list())
        ttk.Entry(bar, textvariable=self.losses_search_var, width=20).pack(side="left", padx=4)
        self.losses_count = tk.StringVar()
        ttk.Label(bar, textvariable=self.losses_count).pack(side="left", padx=8)
        self.losses_sunk_frame = ttk.Frame(loss)
        self.losses_sunk_tree = self._report_tree(self.losses_sunk_frame, LOSSES_SUNK_COLUMNS,
                                                  self.sort_losses_sunk_by,
                                                  ("name", "side", "nation", "type", "class", "cause", "location",
                                                   "scuttled"), self.jump_to_losses_ship)
        self.losses_aircraft_frame = ttk.Frame(loss)
        self.losses_aircraft_tree = self._report_tree(self.losses_aircraft_frame, LOSSES_AIRCRAFT_COLUMNS,
                                                      self.sort_losses_aircraft_by,
                                                      ("name", "side", "nation", "type"), lambda: None)
        self._show_losses_view()

    def _show_losses_view(self):
        ships = self.losses_view_var.get() == LOSSES_VIEWS[0]
        shown, hidden = (self.losses_sunk_frame, self.losses_aircraft_frame) if ships else (
            self.losses_aircraft_frame, self.losses_sunk_frame)
        hidden.pack_forget()
        shown.pack(side="top", fill="both", expand=True, pady=(4, 0))
        self.refresh_losses_list()

    def _build_repair_report(self):
        rep = ttk.Frame(self.reports_notebook, padding=4)
        self.reports_notebook.add(rep, text="Ship repair")
        ttk.Label(rep, text=REPAIR_NOTE, wraplength=1100, justify="left").pack(side="bottom", anchor="w",
                                                                               pady=(4, 0))
        top = ttk.Frame(rep)
        top.pack(side="top", fill="x")
        self.repair_summary_tree = self._report_tree(top, REPAIR_SUMMARY_COLUMNS, lambda c: None, ("side",),
                                                     lambda: None)
        self.repair_summary_tree.configure(height=2)
        bar = ttk.Frame(rep)
        bar.pack(side="top", fill="x", pady=(4, 0))
        self.repair_side_var = tk.StringVar(value=REPAIR_ALL)
        self._report_combo(bar, "Side:", self.repair_side_var, [REPAIR_ALL, "Allied", "Japanese"],
                           self.refresh_repair_list, 9)
        self.repair_view_var = tk.StringVar(value=REPAIR_VIEWS[0])
        for view in REPAIR_VIEWS:
            ttk.Radiobutton(bar, text=view, value=view, variable=self.repair_view_var,
                            command=self._show_repair_view).pack(side="left", padx=2)
        ttk.Label(bar, text="  Search:").pack(side="left")
        self.repair_search_var = tk.StringVar()
        self.repair_search_var.trace_add("write", lambda *a: self.refresh_repair_list())
        ttk.Entry(bar, textvariable=self.repair_search_var, width=20).pack(side="left", padx=4)
        self.repair_count = tk.StringVar()
        ttk.Label(bar, textvariable=self.repair_count).pack(side="left", padx=8)
        self.repair_ship_frame = ttk.Frame(rep)
        self.repair_ship_tree = self._report_tree(self.repair_ship_frame, REPAIR_SHIP_COLUMNS,
                                                  self.sort_repair_ships_by,
                                                  ("name", "side", "nation", "type", "class", "location",
                                                   "weapon_text", "priority", "mode"), self.jump_to_repair_ship)
        self.repair_port_frame = ttk.Frame(rep)
        self.repair_port_tree = self._report_tree(self.repair_port_frame, REPAIR_PORT_COLUMNS,
                                                  self.sort_repair_ports_by, ("name", "side"),
                                                  self.jump_to_repair_port)
        self._show_repair_view()

    def _show_repair_view(self):
        ships = self.repair_view_var.get() == REPAIR_VIEWS[0]
        shown, hidden = (self.repair_ship_frame, self.repair_port_frame) if ships else (
            self.repair_port_frame, self.repair_ship_frame)
        hidden.pack_forget()
        shown.pack(side="top", fill="both", expand=True, pady=(4, 0))
        self.refresh_repair_list()

    def _build_minefield_report(self):
        rep = self.minefield_frame = ttk.Frame(self.reports_notebook, padding=4)
        self.reports_notebook.add(rep, text="Minefields")
        ttk.Label(rep, text=MINE_NOTE, wraplength=1100, justify="left").pack(side="bottom", anchor="w", pady=(4, 0))
        top = ttk.Frame(rep)
        top.pack(side="top", fill="x")
        self.minefield_summary_tree = self._report_tree(top, MINE_SUMMARY_COLUMNS, lambda c: None, ("side", "types"),
                                                        lambda: None)
        self.minefield_summary_tree.configure(height=2)
        bar = ttk.Frame(rep)
        bar.pack(side="top", fill="x", pady=(4, 0))
        self.minefield_side_var = tk.StringVar(value=MINE_ALL)
        self._report_combo(bar, "Side:", self.minefield_side_var, [MINE_ALL, "Allied", "Japanese"],
                           self.refresh_minefield_list, 9)
        self.minefield_view_var = tk.StringVar(value=MINE_VIEWS[0])
        for view in MINE_VIEWS:
            ttk.Radiobutton(bar, text=view, value=view, variable=self.minefield_view_var,
                            command=self._show_minefield_view).pack(side="left", padx=2)
        ttk.Label(bar, text="  Search:").pack(side="left")
        self.minefield_search_var = tk.StringVar()
        self.minefield_search_var.trace_add("write", lambda *a: self.refresh_minefield_list())
        ttk.Entry(bar, textvariable=self.minefield_search_var, width=20).pack(side="left", padx=4)
        self.minefield_count = tk.StringVar()
        ttk.Label(bar, textvariable=self.minefield_count).pack(side="left", padx=8)
        self.minefield_hex_frame = ttk.Frame(rep)
        self.minefield_hex_tree = self._report_tree(self.minefield_hex_frame, MINE_HEX_COLUMNS,
                                                    self.sort_minefield_hexes_by, ("side", "place", "types", "decay"),
                                                    self.jump_to_minefield_place)
        self.minefield_field_frame = ttk.Frame(rep)
        self.minefield_field_tree = self._report_tree(self.minefield_field_frame, MINE_FIELD_COLUMNS,
                                                      self.sort_minefield_fields_by, ("side", "place", "device"),
                                                      self.jump_to_minefield_place)
        self._show_minefield_view()

    def _show_minefield_view(self):
        hexes = self.minefield_view_var.get() == MINE_VIEWS[0]
        shown, hidden = (self.minefield_hex_frame, self.minefield_field_frame) if hexes else (
            self.minefield_field_frame, self.minefield_hex_frame)
        hidden.pack_forget()
        shown.pack(side="top", fill="both", expand=True, pady=(4, 0))
        self.refresh_minefield_list()

    def _build_alerts_report(self):
        rep = self.alerts_frame = ttk.Frame(self.reports_notebook, padding=4)
        self.reports_notebook.add(rep, text="Alerts")
        bar = ttk.Frame(rep)
        bar.pack(side="top", fill="x")
        self.alert_side_var = tk.StringVar(value=ALERT_ALL)
        self._report_combo(bar, "Side:", self.alert_side_var, [ALERT_ALL, "Allied", "Japanese"],
                           self.refresh_alert_list, 9)
        self.alert_category_var = tk.StringVar(value=ALERT_ALL)
        self._report_combo(bar, "Category:", self.alert_category_var, [ALERT_ALL, *alerts.CATEGORIES],
                           self.refresh_alert_list, 11)
        ttk.Label(bar, text="Search:").pack(side="left")
        self.alert_search_var = tk.StringVar()
        self.alert_search_var.trace_add("write", lambda *a: self.refresh_alert_list())
        ttk.Entry(bar, textvariable=self.alert_search_var, width=20).pack(side="left", padx=(4, 8))
        self.alert_supply_var = tk.StringVar(value=str(alerts.DEFAULTS["supply_pct"]))
        self.alert_pool_var = tk.StringVar(value=str(alerts.DEFAULTS["pilot_pool"]))
        for text, var, top in (("Supply below %", self.alert_supply_var, 100),
                               ("Pilot pool below", self.alert_pool_var, 32767)):
            ttk.Label(bar, text=text).pack(side="left")
            ttk.Spinbox(bar, from_=0, to=top, textvariable=var, width=6).pack(side="left", padx=(4, 8))
            var.trace_add("write", lambda *a: self.refresh_alerts())
        self.alert_count = tk.StringVar()
        ttk.Label(bar, textvariable=self.alert_count).pack(side="left", padx=8)
        ttk.Label(rep, text=ALERT_NOTE, wraplength=1100, justify="left").pack(side="bottom", anchor="w", pady=(4, 0))
        self.alert_tree = self._report_tree(rep, ALERT_COLUMNS, self.sort_alerts_by,
                                            ("category", "side", "subject", "detail"), self.open_alert)

    def _build_victory_report(self):
        rep = ttk.Frame(self.reports_notebook, padding=4)
        self.reports_notebook.add(rep, text="Victory points")
        ttk.Label(rep, text=VP_NOTE, wraplength=1100, justify="left").pack(side="bottom", anchor="w", pady=(4, 0))
        top = ttk.Frame(rep)
        top.pack(side="top", fill="x")
        self.vp_summary_tree = self._report_tree(top, VP_SUMMARY_COLUMNS, lambda c: None, ("side",), lambda: None)
        self.vp_summary_tree.configure(height=2)
        self.vp_status = tk.StringVar()
        ttk.Label(rep, textvariable=self.vp_status, justify="left").pack(side="top", anchor="w", pady=(4, 0))
        bar = ttk.Frame(rep)
        bar.pack(side="top", fill="x", pady=(4, 0))
        self.vp_side_var = tk.StringVar(value=VP_ALL)
        self._report_combo(bar, "Side:", self.vp_side_var, [VP_ALL, "Allied", "Japanese"], self.refresh_vp_list, 9)
        ttk.Label(bar, text="  Search:").pack(side="left")
        self.vp_search_var = tk.StringVar()
        self.vp_search_var.trace_add("write", lambda *a: self.refresh_vp_list())
        ttk.Entry(bar, textvariable=self.vp_search_var, width=20).pack(side="left", padx=4)
        self.vp_count = tk.StringVar()
        ttk.Label(bar, textvariable=self.vp_count).pack(side="left", padx=8)
        frame = ttk.Frame(rep)
        frame.pack(side="top", fill="both", expand=True, pady=(4, 0))
        self.vp_tree = self._report_tree(frame, VP_BASE_COLUMNS, self.sort_vp_by, ("name", "side", "region"),
                                         self.jump_to_vp_base)

    def _report_tree(self, parent, columns, sort_command, left_aligned, on_open):
        tree = ttk.Treeview(parent, columns=[c[0] for c in columns], show="headings", selectmode="browse")
        for cid, heading, width, _numeric, _get in columns:
            tree.heading(cid, text=heading, command=lambda c=cid: sort_command(c))
            tree.column(cid, width=width, anchor="w" if cid in left_aligned else "e")
        scroll = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        tree.pack(side="left", fill="both", expand=True)
        tree.bind("<Double-1>", lambda e: on_open())
        return tree

    def _build_aircraft_tab(self):
        tab = self.aircraft_tab = ttk.Frame(self.notebook, padding=4)
        self.notebook.add(tab, text="Aircraft")
        left = ttk.Frame(tab)
        left.pack(side="left", fill="both", expand=True)
        bar = ttk.Frame(left)
        bar.pack(side="top", fill="x")
        ttk.Label(bar, text="Search:").pack(side="left")
        self.aircraft_search_var = tk.StringVar()
        self.aircraft_search_var.trace_add("write", lambda *a: self.refresh_aircraft_list())
        ttk.Entry(bar, textvariable=self.aircraft_search_var, width=20).pack(side="left", padx=4)
        self.aircraft_tree = ttk.Treeview(left, columns=[c[0] for c in AIRCRAFT_COLUMNS], show="headings",
                                          selectmode="browse")
        for cid, heading, width, _numeric, _get in AIRCRAFT_COLUMNS:
            self.aircraft_tree.heading(cid, text=heading, command=lambda c=cid: self.sort_aircraft_by(c))
            self.aircraft_tree.column(cid, width=width, anchor="w" if cid in ("name", "nation", "type") else "e")
        self.aircraft_tree.tag_configure("edited", background="#fff2b3")
        # Models whose availability date is after the game date are dimmed.
        self.aircraft_tree.tag_configure("pending", foreground="gray55")
        scroll = ttk.Scrollbar(left, orient="vertical", command=self.aircraft_tree.yview)
        self.aircraft_tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.aircraft_tree.pack(side="left", fill="both", expand=True)
        self.aircraft_tree.bind("<<TreeviewSelect>>", lambda e: self.on_aircraft_select())

        right = ttk.LabelFrame(tab, text="Aircraft", padding=8)
        right.pack(side="right", fill="y", padx=(8, 0))
        self.aircraft_picture = self._picture_label(right)
        self.aircraft_picture.master.grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
        self.aircraft_title = tk.StringVar(value="(select an aircraft)")
        ttk.Label(right, textvariable=self.aircraft_title, font=("TkDefaultFont", 11, "bold")).grid(
            row=1, column=0, columnspan=2, sticky="w", pady=(0, 6))
        rows = [(f.name, f.label) for f in aircraft.SCALAR_FIELDS] + [("from", "Available from (m/yy)"),
                                                                ("to", "Available to (m/yy)"),
                                                                ("pool", "In pool")]
        row = 2
        for name, label in rows:
            ttk.Label(right, text=label).grid(row=row, column=0, sticky="w", pady=2)
            self.aircraft_vars[name] = tk.StringVar()
            ttk.Entry(right, textvariable=self.aircraft_vars[name], width=14).grid(
                row=row, column=1, padx=(8, 0), pady=2)
            row += 1
        for name, label, _hex, _miles in aircraft.RANGES:
            ttk.Label(right, text=label + " (hex, mi)").grid(row=row, column=0, sticky="w", pady=2)
            pair = ttk.Frame(right)
            pair.grid(row=row, column=1, padx=(8, 0), pady=2, sticky="w")
            for suffix in ("_hex", "_miles"):
                self.aircraft_vars[name + suffix] = tk.StringVar()
                ttk.Entry(pair, textvariable=self.aircraft_vars[name + suffix], width=6).pack(side="left", padx=(0, 2))
            row += 1
        self.aircraft_carrier_var = tk.BooleanVar()
        ttk.Checkbutton(right, text="Carrier capable", variable=self.aircraft_carrier_var).grid(
            row=row, column=0, columnspan=2, sticky="w", pady=2)
        row += 1
        ttk.Button(right, text="Apply", command=self.apply_aircraft).grid(row=row, column=0, columnspan=2, pady=6)
        row += 1
        buttons = ttk.Frame(right)
        buttons.grid(row=row, column=0, columnspan=2)
        for k, letter in enumerate("AB"):
            ttk.Button(buttons, text=f"Compare as {letter}", command=lambda k=k: self.compare_aircraft(k)).pack(
                side="left", padx=4)
        ttk.Button(buttons, text="History", command=self.show_aircraft_history).pack(side="left", padx=4)
        row += 1
        self.aircraft_info = {}
        for name, label in (("type", "Type (read-only)"), ("nation", "Nation (read-only)"),
                            ("bitmap", "Picture number (read-only)"), ("upgrade", "Upgrade (read-only)"), ("engines", "Engines (read-only)"), ("gun", "Gun value (read-only)"),
                            ("endurance", "Endurance (calculated)"),
                            ("used", "Used (read-only)"), ("last_turn", "Produced last turn (read-only)"),
                            ("this_month", "Produced this month (read-only)"),
                            ("mods", "Maneuver mods (read-only)")):
            ttk.Label(right, text=label).grid(row=row, column=0, sticky="w", pady=1)
            self.aircraft_info[name] = tk.StringVar()
            ttk.Label(right, textvariable=self.aircraft_info[name]).grid(row=row, column=1, sticky="w", padx=(8, 0))
            row += 1
        self.aircraft_weapon_trees = {}
        for key, title in (("max", "Weapons, max load"), ("reduced", "Weapons, reduced load")):
            box = ttk.LabelFrame(right, text=title, padding=2)
            box.grid(row=row, column=0, columnspan=2, sticky="we", pady=(4, 0))
            tree = ttk.Treeview(box, columns=("name", "count", "facing"), show="headings", height=5,
                                selectmode="none")
            for cid, heading, width in (("name", "Name", 150), ("count", "Count", 50), ("facing", "Facing", 50)):
                tree.heading(cid, text=heading)
                tree.column(cid, width=width, anchor="w" if cid == "name" else "e")
            tree.pack(fill="x")
            self.aircraft_weapon_trees[key] = tree
            row += 1

    def _build_ships_tab(self):
        tab = ttk.Frame(self.notebook, padding=4)
        self.notebook.add(tab, text="Ship Classes")
        left = ttk.Frame(tab)
        left.pack(side="left", fill="both", expand=True)
        bar = ttk.Frame(left)
        bar.pack(side="top", fill="x")
        ttk.Label(bar, text="Search:").pack(side="left")
        self.ship_search_var = tk.StringVar()
        self.ship_search_var.trace_add("write", lambda *a: self.refresh_ship_list())
        ttk.Entry(bar, textvariable=self.ship_search_var, width=20).pack(side="left", padx=4)
        self.ship_tree = ttk.Treeview(left, columns=[c[0] for c in SHIP_COLUMNS], show="headings",
                                      selectmode="browse")
        for cid, heading, width, _numeric, _get in SHIP_COLUMNS:
            self.ship_tree.heading(cid, text=heading, command=lambda c=cid: self.sort_ships_by(c))
            self.ship_tree.column(cid, width=width, anchor="w" if cid in ("name", "type", "nation") else "e")
        self.ship_tree.tag_configure("edited", background="#fff2b3")
        scroll = ttk.Scrollbar(left, orient="vertical", command=self.ship_tree.yview)
        self.ship_tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.ship_tree.pack(side="left", fill="both", expand=True)
        self.ship_tree.bind("<<TreeviewSelect>>", lambda e: self.on_ship_select())

        right = ttk.LabelFrame(tab, text="Ship class", padding=8)
        right.pack(side="right", fill="y", padx=(8, 0))
        self.ship_title = tk.StringVar(value="(select a ship class)")
        ttk.Label(right, textvariable=self.ship_title, font=("TkDefaultFont", 11, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
        row = 1
        for f in ships.FIELDS:
            ttk.Label(right, text=f.label).grid(row=row, column=0, sticky="w", pady=2)
            self.ship_vars[f.name] = tk.StringVar()
            ttk.Entry(right, textvariable=self.ship_vars[f.name], width=14).grid(
                row=row, column=1, padx=(8, 0), pady=2)
            row += 1
        ttk.Button(right, text="Apply", command=self.apply_ship).grid(row=row, column=0, columnspan=2, pady=6)
        row += 1
        self.ship_info = {}
        for name, label in (("type", "Type (read-only)"), ("nation", "Nation (read-only)"),
                            ("displacement", "Displacement (unverified, read-only)"),
                            ("date", "Date (unverified, read-only)")):
            ttk.Label(right, text=label).grid(row=row, column=0, sticky="w", pady=1)
            self.ship_info[name] = tk.StringVar()
            ttk.Label(right, textvariable=self.ship_info[name]).grid(row=row, column=1, sticky="w", padx=(8, 0))
            row += 1
        box = ttk.LabelFrame(right, text="Weapons and electronics", padding=2)
        box.grid(row=row, column=0, columnspan=2, sticky="we", pady=(4, 0))
        cols = [("name", "Name", 150), ("num", "Num", 40), ("face", "Face", 40), ("mount", "Mount", 50),
                ("armor", "Armor", 50), ("ammo", "Ammo", 50)]
        self.ship_weapon_tree = ttk.Treeview(box, columns=[c[0] for c in cols], show="headings",
                                             selectmode="browse", height=8)
        for cid, heading, width in cols:
            self.ship_weapon_tree.heading(cid, text=heading)
            self.ship_weapon_tree.column(cid, width=width, anchor="w" if cid == "name" else "e")
        self.ship_weapon_tree.pack(side="top", fill="x")
        self.ship_weapon_tree.bind("<<TreeviewSelect>>", lambda e: self.on_ship_weapon_select())
        edit = ttk.Frame(box)
        edit.pack(side="top", fill="x", pady=(4, 0))
        self.ship_weapon_vars = {}
        for name, label, width in (("num", "Num", 5), ("face", "Face", 5), ("mount", "Mount", 5),
                                   ("armor", "Armor", 5), ("ammo", "Ammo", 5)):
            ttk.Label(edit, text=label + ":").pack(side="left")
            var = tk.StringVar()
            self.ship_weapon_vars[name] = var
            if name == "face":
                ttk.Combobox(edit, textvariable=var, values=list(ships.FACES.values()), width=width).pack(
                    side="left", padx=(2, 6))
            else:
                ttk.Entry(edit, textvariable=var, width=width).pack(side="left", padx=(2, 6))
        ttk.Button(edit, text="Apply weapon", command=self.apply_ship_weapon).pack(side="left", padx=4)

    def _build_shiprecs_tab(self):
        tab = self.shiprec_tab = ttk.Frame(self.notebook, padding=4)
        self.notebook.add(tab, text="Ships")
        left = ttk.Frame(tab)
        left.pack(side="left", fill="both", expand=True)
        bar = ttk.Frame(left)
        bar.pack(side="top", fill="x")
        ttk.Label(bar, text="Search:").pack(side="left")
        self.shiprec_search_var = tk.StringVar()
        self.shiprec_search_var.trace_add("write", lambda *a: self.refresh_shiprec_list())
        ttk.Entry(bar, textvariable=self.shiprec_search_var, width=20).pack(side="left", padx=4)
        ttk.Label(bar, text="Side:").pack(side="left")
        self.shiprec_side_var = tk.StringVar(value="All")
        side_box = ttk.Combobox(bar, textvariable=self.shiprec_side_var, values=["All", "Allied", "Japanese"],
                                state="readonly", width=9)
        side_box.pack(side="left", padx=4)
        side_box.bind("<<ComboboxSelected>>", lambda e: self.refresh_shiprec_list())
        self.shiprec_tree = ttk.Treeview(left, columns=[c[0] for c in SHIPREC_COLUMNS], show="headings",
                                         selectmode="browse")
        for cid, heading, width, _numeric, _get in SHIPREC_COLUMNS:
            self.shiprec_tree.heading(cid, text=heading, command=lambda c=cid: self.sort_shiprecs_by(c))
            self.shiprec_tree.column(cid, width=width, anchor="e" if cid == "id" else "w")
        self.shiprec_tree.tag_configure("edited", background="#fff2b3")
        # Ships not yet arrived (reinforcements, sunk) are dimmed.
        self.shiprec_tree.tag_configure("pending", foreground="gray55")
        scroll = ttk.Scrollbar(left, orient="vertical", command=self.shiprec_tree.yview)
        self.shiprec_tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.shiprec_tree.pack(side="left", fill="both", expand=True)
        self.shiprec_tree.bind("<<TreeviewSelect>>", lambda e: self.on_shiprec_select())

        right = ttk.LabelFrame(tab, text="Ship", padding=8)
        right.pack(side="right", fill="y", padx=(8, 0))
        self.shiprec_title = tk.StringVar(value="(select a ship)")
        ttk.Label(right, textvariable=self.shiprec_title, font=("TkDefaultFont", 11, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
        row = 1
        for f in shiprecords.FIELDS:
            ttk.Label(right, text=f.label).grid(row=row, column=0, sticky="w", pady=2)
            self.shiprec_vars[f.name] = tk.StringVar()
            ttk.Entry(right, textvariable=self.shiprec_vars[f.name], width=10).grid(
                row=row, column=1, padx=(8, 0), pady=2)
            row += 1
        buttons = ttk.Frame(right)
        buttons.grid(row=row, column=0, columnspan=2, pady=6)
        ttk.Button(buttons, text="Apply", command=self.apply_shiprec).pack(side="left", padx=4)
        ttk.Button(buttons, text="Repair all", command=self.repair_shiprec).pack(side="left", padx=4)
        row += 1
        self.shiprec_info = {}
        for name, label in (("class", "Class (read-only)"), ("nation", "Nation (read-only)"),
                            ("base", "Current base (read-only)"), ("tf", "Task force (read-only)"),
                            ("arrival", "Days to arrival (read-only)")):
            ttk.Label(right, text=label).grid(row=row, column=0, sticky="w", pady=1)
            self.shiprec_info[name] = tk.StringVar()
            ttk.Label(right, textvariable=self.shiprec_info[name]).grid(row=row, column=1, sticky="w", padx=(8, 0))
            row += 1
        move = ttk.LabelFrame(right, text="Move between task forces and ports", padding=4)
        move.grid(row=row, column=0, columnspan=2, sticky="we", pady=(4, 0))
        self.shiprec_move_var = tk.StringVar()
        self.shiprec_move_box = ttk.Combobox(move, textvariable=self.shiprec_move_var, state="readonly", width=34)
        self.shiprec_move_box.pack(side="left")
        self.shiprec_move_button = ttk.Button(move, text="Move", command=self.move_shiprec)
        self.shiprec_move_button.pack(side="left", padx=4)
        self.shiprec_move_note = tk.StringVar()
        ttk.Label(move, textvariable=self.shiprec_move_note).pack(side="left")
        self.shiprec_destinations = []
        row += 1
        box = ttk.LabelFrame(right, text="Weapons and electronics", padding=2)
        box.grid(row=row, column=0, columnspan=2, sticky="we", pady=(4, 0))
        cols = [("name", "Name", 150), ("num", "Num", 40), ("face", "Face", 40), ("mount", "Mount", 50),
                ("armor", "Armor", 50), ("ammo", "Ammo", 50)]
        self.shiprec_weapon_tree = ttk.Treeview(box, columns=[c[0] for c in cols], show="headings",
                                                selectmode="browse", height=8)
        for cid, heading, width in cols:
            self.shiprec_weapon_tree.heading(cid, text=heading)
            self.shiprec_weapon_tree.column(cid, width=width, anchor="w" if cid == "name" else "e")
        self.shiprec_weapon_tree.pack(side="top", fill="x")
        self.shiprec_weapon_tree.bind("<<TreeviewSelect>>", lambda e: self.on_shiprec_weapon_select())
        edit = ttk.Frame(box)
        edit.pack(side="top", fill="x", pady=(4, 0))
        self.shiprec_weapon_vars = {}
        for name, label in (("num", "Num"), ("ammo", "Ammo")):
            ttk.Label(edit, text=label + ":").pack(side="left")
            self.shiprec_weapon_vars[name] = tk.StringVar()
            ttk.Entry(edit, textvariable=self.shiprec_weapon_vars[name], width=6).pack(side="left", padx=(2, 6))
        ttk.Button(edit, text="Apply weapon", command=self.apply_shiprec_weapon).pack(side="left", padx=4)

    def _build_taskforces_tab(self):
        tab = self.tf_tab = ttk.Frame(self.notebook, padding=4)
        self.notebook.add(tab, text="Task Forces")
        left = ttk.Frame(tab)
        left.pack(side="left", fill="both", expand=True)
        bar = ttk.Frame(left)
        bar.pack(side="top", fill="x")
        ttk.Label(bar, text="Search:").pack(side="left")
        self.tf_search_var = tk.StringVar()
        self.tf_search_var.trace_add("write", lambda *a: self.refresh_tf_list())
        ttk.Entry(bar, textvariable=self.tf_search_var, width=20).pack(side="left", padx=4)
        ttk.Label(bar, text="Side:").pack(side="left")
        self.tf_side_var = tk.StringVar(value="All")
        side_box = ttk.Combobox(bar, textvariable=self.tf_side_var, values=["All", "Allied", "Japanese"],
                                state="readonly", width=9)
        side_box.pack(side="left", padx=4)
        side_box.bind("<<ComboboxSelected>>", lambda e: self.refresh_tf_list())
        self.tf_tree = ttk.Treeview(left, columns=[c[0] for c in TF_COLUMNS], show="headings", selectmode="browse")
        for cid, heading, width, numeric, _get in TF_COLUMNS:
            self.tf_tree.heading(cid, text=heading, command=lambda c=cid: self.sort_tfs_by(c))
            self.tf_tree.column(cid, width=width, anchor="e" if numeric else "w")
        self.tf_tree.tag_configure("edited", background="#fff2b3")
        scroll = ttk.Scrollbar(left, orient="vertical", command=self.tf_tree.yview)
        self.tf_tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.tf_tree.pack(side="left", fill="both", expand=True)
        self.tf_tree.bind("<<TreeviewSelect>>", lambda e: self.on_tf_select())

        right = ttk.LabelFrame(tab, text="Task force", padding=8)
        right.pack(side="right", fill="y", padx=(8, 0))
        self.tf_title = tk.StringVar(value="(select a task force)")
        ttk.Label(right, textvariable=self.tf_title, font=("TkDefaultFont", 11, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
        row = 1
        for name, label in (("hex", "Hex x,y (read-only)"), ("location", "Location (read-only)"),
                            ("side", "Side (read-only)")):
            ttk.Label(right, text=label).grid(row=row, column=0, sticky="w", pady=1)
            self.tf_info[name] = tk.StringVar()
            ttk.Label(right, textvariable=self.tf_info[name]).grid(row=row, column=1, sticky="w", padx=(8, 0))
            row += 1
        orders = ttk.LabelFrame(right, text="Orders", padding=4)
        orders.grid(row=row, column=0, columnspan=2, sticky="we", pady=(4, 0))
        self.tf_mission_var = tk.StringVar()
        self.tf_home_var = tk.StringVar()
        self.tf_dest_var = tk.StringVar()
        self.tf_dest_filter_var = tk.StringVar()
        self.tf_dest_filter_var.trace_add("write", lambda *a: self.show_tf_destinations())
        self.tf_mission_box = ttk.Combobox(orders, textvariable=self.tf_mission_var, state="readonly", width=30,
                                           values=[f"{code:02d} - {label}" for code, label in taskforces.MISSIONS.items()])
        self.tf_home_box = ttk.Combobox(orders, textvariable=self.tf_home_var, state="readonly", width=30)
        self.tf_dest_box = ttk.Combobox(orders, textvariable=self.tf_dest_var, state="readonly", width=30)
        for name, label, widget, command, r in (
                ("mission", "Mission", self.tf_mission_box, self.set_tf_mission, 0),
                ("home_port", "Home port", self.tf_home_box, self.set_tf_home_port, 2),
                ("destination", "Destination", self.tf_dest_box, self.set_tf_destination, 5)):
            ttk.Label(orders, text=label + ":").grid(row=r, column=0, sticky="w")
            widget.grid(row=r, column=1, sticky="w", padx=2)
            ttk.Button(orders, text="Set", command=command).grid(row=r, column=2, padx=2)
            self.tf_info[name] = tk.StringVar()
            ttk.Label(orders, text="now:").grid(row=r + 1, column=0, sticky="e")
            ttk.Label(orders, textvariable=self.tf_info[name]).grid(row=r + 1, column=1, sticky="w", padx=2)
        ttk.Label(orders, text="Dest. filter:").grid(row=4, column=0, sticky="w")
        ttk.Entry(orders, textvariable=self.tf_dest_filter_var, width=20).grid(row=4, column=1, sticky="w", padx=2)
        row += 1
        box = ttk.LabelFrame(right, text="Ships (chain order)", padding=2)
        box.grid(row=row, column=0, columnspan=2, sticky="we", pady=(4, 0))
        self.tf_ship_tree = ttk.Treeview(box, columns=[c[0] for c in TF_SHIP_COLUMNS], show="headings",
                                         selectmode="browse", height=10)
        for cid, heading, width in TF_SHIP_COLUMNS:
            self.tf_ship_tree.heading(cid, text=heading)
            self.tf_ship_tree.column(cid, width=width, anchor="w" if cid in ("name", "type", "class") else "e")
        self.tf_ship_tree.pack(side="top", fill="x")
        self.tf_ship_tree.bind("<<TreeviewSelect>>", lambda e: self.on_tf_ship_select())
        row += 1
        flag = ttk.LabelFrame(right, text="Flagship", padding=4)
        flag.grid(row=row, column=0, columnspan=2, sticky="we", pady=(4, 0))
        self.tf_flag_var = tk.StringVar()
        self.tf_flag_box = ttk.Combobox(flag, textvariable=self.tf_flag_var, state="readonly", width=30)
        self.tf_flag_box.pack(side="left")
        ttk.Button(flag, text="Set flagship", command=self.set_tf_flagship).pack(side="left", padx=4)
        row += 1
        move = ttk.LabelFrame(right, text="Move the selected ship", padding=4)
        move.grid(row=row, column=0, columnspan=2, sticky="we", pady=(4, 0))
        self.tf_move_var = tk.StringVar()
        self.tf_move_box = ttk.Combobox(move, textvariable=self.tf_move_var, state="readonly", width=34)
        self.tf_move_box.pack(side="left")
        self.tf_move_button = ttk.Button(move, text="Move", command=self.move_tf_ship)
        self.tf_move_button.pack(side="left", padx=4)
        self.tf_move_note = tk.StringVar()
        ttk.Label(move, textvariable=self.tf_move_note).pack(side="left")
        row += 1
        add = ttk.LabelFrame(right, text="Add ship from port", padding=4)
        add.grid(row=row, column=0, columnspan=2, sticky="we", pady=(4, 0))
        self.tf_add_var = tk.StringVar()
        self.tf_add_box = ttk.Combobox(add, textvariable=self.tf_add_var, state="readonly", width=34)
        self.tf_add_box.pack(side="left")
        self.tf_add_button = ttk.Button(add, text="Add", command=self.add_tf_ship)
        self.tf_add_button.pack(side="left", padx=4)
        self.tf_add_note = tk.StringVar()
        ttk.Label(add, textvariable=self.tf_add_note).pack(side="left")
        row += 1
        quick = ttk.Frame(right)
        quick.grid(row=row, column=0, columnspan=2, pady=(8, 0))
        ttk.Button(quick, text="Repair all ships", command=self.repair_tf).pack(side="left", padx=4)
        ttk.Button(quick, text="Refuel all ships", command=self.refuel_tf).pack(side="left", padx=4)

    def _build_groups_tab(self):
        tab = self.groups_tab = ttk.Frame(self.notebook, padding=4)
        self.notebook.add(tab, text="Air Groups")
        # The pilot pool is nation-wide, not per group, so it gets its own page beside the group editor.
        self.groups_notebook = ttk.Notebook(tab)
        self.groups_notebook.pack(fill="both", expand=True)
        groups_page = self.groups_page = ttk.Frame(self.groups_notebook, padding=4)
        self.groups_notebook.add(groups_page, text="Groups")
        pool_page = self.pool_page = ttk.Frame(self.groups_notebook, padding=4)
        self.groups_notebook.add(pool_page, text="Pilot pool")
        self._build_pilot_pool(pool_page)
        tab = groups_page
        right = ttk.LabelFrame(tab, text="Air group", padding=8)
        right.pack(side="right", fill="y", padx=(8, 0))
        left = ttk.Frame(tab)
        left.pack(side="left", fill="both", expand=True)

        bar = ttk.Frame(left)
        bar.pack(side="top", fill="x")
        ttk.Label(bar, text="Search:").pack(side="left")
        self.group_search_var = tk.StringVar()
        self.group_search_var.trace_add("write", lambda *a: self.refresh_group_list())
        ttk.Entry(bar, textvariable=self.group_search_var, width=20).pack(side="left", padx=4)
        ttk.Label(bar, text="Side:").pack(side="left")
        self.group_side_var = tk.StringVar(value="All")
        side_box = ttk.Combobox(bar, textvariable=self.group_side_var, values=["All", "Allied", "Japanese"],
                                state="readonly", width=9)
        side_box.pack(side="left", padx=4)
        side_box.bind("<<ComboboxSelected>>", lambda e: self.refresh_group_list())

        # Pilots and commander sit below the list so the tab stays short enough for small screens.
        lower = ttk.Frame(left)
        lower.pack(side="bottom", fill="x", pady=(6, 0))
        self._build_pilots(lower)
        self._build_leader(lower)

        self.group_tree = ttk.Treeview(left, columns=[c[0] for c in GROUP_COLUMNS], show="headings",
                                       selectmode="browse", height=8)
        for cid, heading, width, _numeric, _get in GROUP_COLUMNS:
            self.group_tree.heading(cid, text=heading, command=lambda c=cid: self.sort_groups_by(c))
            self.group_tree.column(cid, width=width, anchor="w" if cid in ("name", "aircraft", "location") else "e")
        self.group_tree.tag_configure("edited", background="#fff2b3")
        # Groups not yet arrived are dimmed.
        self.group_tree.tag_configure("pending", foreground="gray55")
        scroll = ttk.Scrollbar(left, orient="vertical", command=self.group_tree.yview)
        self.group_tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.group_tree.pack(side="left", fill="both", expand=True)
        self.group_tree.bind("<<TreeviewSelect>>", lambda e: self.on_group_select())

        self.group_title = tk.StringVar(value="(select an air group)")
        ttk.Label(right, textvariable=self.group_title, font=("TkDefaultFont", 11, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
        row = 1
        for f in airgroups.GROUP_FIELDS:
            ttk.Label(right, text=f.label + ("" if f.verified else " (unverified)")).grid(
                row=row, column=0, sticky="w", pady=2)
            self.group_vars[f.name] = tk.StringVar()
            ttk.Entry(right, textvariable=self.group_vars[f.name],
                      width=12 if f.name in airgroups.DATE_FIELDS else 10).grid(
                row=row, column=1, padx=(8, 0), pady=2)
            row += 1
        ttk.Button(right, text="Apply", command=self.apply_group).grid(row=row, column=0, columnspan=2, pady=6)
        row += 1
        self.group_info = {}
        for name, label in (("aircraft", "Aircraft"), ("upgrade", "Upgrade to"), ("planes", "Aircraft total (read-only)"),
                            ("pilots", "Pilot count byte (read-only, meaning unclear)"), ("leader", "Commander (read-only)"),
                            ("formation", "Formation (read-only)"), ("parent", "Parent group (read-only)"),
                            ("return_as", "Returns as (read-only)"), ("location", "Location")):
            ttk.Label(right, text=label).grid(row=row, column=0, sticky="w", pady=1)
            self.group_info[name] = tk.StringVar()
            ttk.Label(right, textvariable=self.group_info[name]).grid(row=row, column=1, sticky="w", padx=(8, 0))
            row += 1
        self._build_planes(right, row)
        row += 1
        self._build_schedule(right, row)
        row += 1
        self.group_move_var, self.group_move_box, self.group_move_button, self.group_move_note = self._build_move_row(
            right, row, self.move_group)
        row += 3
        ttk.Label(right, text="Change aircraft").grid(row=row, column=0, sticky="w", pady=(8, 2))
        self.group_aircraft_var = tk.StringVar()
        self.group_aircraft_box = ttk.Combobox(right, textvariable=self.group_aircraft_var, state="disabled", width=24)
        self.group_aircraft_box.grid(row=row, column=1, padx=(8, 0), pady=(8, 2))
        self.group_aircraft_button = ttk.Button(right, text="Change", command=self.change_group_aircraft)
        self.group_aircraft_button.grid(row=row + 1, column=0, columnspan=2, pady=2)
        row += 2
        ttk.Label(right, text="Upgrade to").grid(row=row, column=0, sticky="w", pady=(8, 2))
        self.group_upgrade_var = tk.StringVar()
        self.group_upgrade_box = ttk.Combobox(right, textvariable=self.group_upgrade_var, state="disabled", width=24)
        self.group_upgrade_box.grid(row=row, column=1, padx=(8, 0), pady=(8, 2))
        self.group_upgrade_button = ttk.Button(right, text="Set upgrade", command=self.change_group_upgrade)
        self.group_upgrade_button.grid(row=row + 1, column=0, columnspan=2, pady=2)
        row += 2
        ttk.Label(right, text="The game probably recalculates\naverage experience from the pilots.",
                  foreground="gray40").grid(row=row, column=0, columnspan=2, sticky="w", pady=(6, 0))

    def _build_pilot_pool(self, parent):
        bar = ttk.Frame(parent)
        bar.pack(side="top", fill="x")
        ttk.Label(bar, text="Side:").pack(side="left")
        self.pool_side_var = tk.StringVar(value="All")
        side_box = ttk.Combobox(bar, textvariable=self.pool_side_var, values=["All", "Allied", "Japanese"],
                                state="readonly", width=9)
        side_box.pack(side="left", padx=4)
        side_box.bind("<<ComboboxSelected>>", lambda e: self.refresh_pool_list())
        self.pool_empty_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Show empty nations", variable=self.pool_empty_var,
                        command=self.refresh_pool_list).pack(side="left", padx=8)
        ttk.Label(bar, text="Offsets from WitPTracker, not yet checked in-game.", foreground="gray40").pack(
            side="left", padx=8)

        cols = [("nation", "Nation", 70), ("pool", "Pool", 60), ("experience", "Exp", 40), ("rate", "Rate/month", 80),
                ("training", "In training", 80)] + [(f"t{k + 1}", f"T{k + 1}", 70) for k in range(pilotpool.INTAKES)]
        self.pool_tree = ttk.Treeview(parent, columns=[c[0] for c in cols], show="headings",
                                      selectmode="browse", height=10)
        for cid, heading, width in cols:
            self.pool_tree.heading(cid, text=heading)
            self.pool_tree.column(cid, width=width, anchor="w" if cid == "nation" else "e")
        self.pool_tree.tag_configure("edited", background="#fff2b3")
        self.pool_tree.pack(side="top", fill="both", expand=True, pady=(6, 0))
        self.pool_tree.bind("<<TreeviewSelect>>", lambda e: self.on_pool_select())

        box = ttk.LabelFrame(parent, text="Nation", padding=4)
        box.pack(side="top", fill="x", pady=(6, 0))
        self.pool_title = tk.StringVar(value="(select a nation)")
        ttk.Label(box, textvariable=self.pool_title, font=("TkDefaultFont", 11, "bold")).grid(
            row=0, column=0, columnspan=12, sticky="w", pady=(0, 4))
        for k, name in enumerate(("pool", "experience", "rate")):
            ttk.Label(box, text=pilotpool.field_label(name)).grid(row=1, column=3 * k, sticky="w", padx=(0, 2), pady=1)
            self.pool_vars[name] = tk.StringVar()
            ttk.Entry(box, textvariable=self.pool_vars[name], width=6).grid(
                row=1, column=3 * k + 1, sticky="w", padx=(0, 12), pady=1)
        ttk.Label(box, text="Training intakes: count and experience (T1 is the newest)").grid(
            row=2, column=0, columnspan=12, sticky="w", pady=(6, 0))
        per_row = 4
        for k in range(pilotpool.INTAKES):
            row, col = divmod(k, per_row)
            ttk.Label(box, text=f"T{k + 1}").grid(row=row + 3, column=3 * col, sticky="w", padx=(0, 2), pady=1)
            inner = ttk.Frame(box)
            inner.grid(row=row + 3, column=3 * col + 1, columnspan=2, sticky="w", padx=(0, 12), pady=1)
            for name in (f"count{k}", f"exp{k}"):
                self.pool_vars[name] = tk.StringVar()
                ttk.Entry(inner, textvariable=self.pool_vars[name], width=6 if name.startswith("count") else 4).pack(
                    side="left", padx=(0, 4))
        self.pool_button = ttk.Button(box, text="Apply pilot pool", command=self.apply_pool, state="disabled")
        self.pool_button.grid(row=3 + pilotpool.INTAKES // per_row, column=0, columnspan=3, sticky="w", pady=(4, 0))

    def _build_planes(self, parent, row):
        """Ready / maintenance / damaged / reserve split of the group's planes; the total stays fixed."""
        box = ttk.LabelFrame(parent, text="Planes", padding=4)
        box.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(8, 2))
        self.plane_vars, self.plane_entries = {}, []
        for k, (name, label) in enumerate((("ready", "Ready"), ("maintenance", "Maintenance"),
                                           ("damaged", "Damaged"), ("reserve", "Reserve"))):
            r, c = divmod(k, 2)
            ttk.Label(box, text=label).grid(row=r, column=2 * c, sticky="w", padx=(0, 2), pady=1)
            self.plane_vars[name] = tk.StringVar()
            entry = ttk.Entry(box, textvariable=self.plane_vars[name], width=5, state="disabled")
            entry.grid(row=r, column=2 * c + 1, sticky="w", padx=(0, 10), pady=1)
            self.plane_entries.append(entry)
        ttk.Label(box, text="Total").grid(row=2, column=0, sticky="w", pady=1)
        self.plane_total = tk.StringVar()
        ttk.Label(box, textvariable=self.plane_total).grid(row=2, column=1, sticky="w", pady=1)
        self.plane_apply_button = ttk.Button(box, text="Apply planes", command=self.apply_planes, state="disabled")
        self.plane_apply_button.grid(row=3, column=0, columnspan=2, sticky="w", pady=(2, 0))
        self.plane_repair_button = ttk.Button(box, text="Repair all", command=self.repair_planes, state="disabled")
        self.plane_repair_button.grid(row=3, column=2, columnspan=2, sticky="w", pady=(2, 0))
        self.plane_note = tk.StringVar()
        ttk.Label(box, textvariable=self.plane_note, foreground="gray40").grid(
            row=4, column=0, columnspan=4, sticky="w")

    def _build_schedule(self, parent, row):
        """The group's five scheduled size changes (date, new size); schedule data, so always editable."""
        box = ttk.LabelFrame(parent, text="Size changes", padding=4)
        box.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(8, 2))
        ttk.Label(box, text="Date (e.g. Jul 42)").grid(row=0, column=0, sticky="w")
        ttk.Label(box, text="New size").grid(row=0, column=1, sticky="w", padx=(8, 0))
        self.schedule_vars = []
        for k in range(airgroups.SCHEDULE_COUNT):
            date_var, size_var = tk.StringVar(), tk.StringVar()
            ttk.Entry(box, textvariable=date_var, width=12).grid(row=k + 1, column=0, sticky="w", pady=1)
            ttk.Entry(box, textvariable=size_var, width=6).grid(row=k + 1, column=1, sticky="w", padx=(8, 0), pady=1)
            self.schedule_vars.append((date_var, size_var))
        ttk.Button(box, text="Apply size changes", command=self.apply_schedule).grid(
            row=airgroups.SCHEDULE_COUNT + 1, column=0, columnspan=2, sticky="w", pady=(2, 0))

    def _build_pilots(self, parent):
        box = ttk.LabelFrame(parent, text="Pilots", padding=4)
        box.pack(side="top", fill="x")
        cols = [("id", "ID", 50), ("name", "Name", 100), ("status", "Status", 60), ("experience", "Exp", 35)] + [
            ("skill_" + n.lower(), n, 38) for n in airgroups.SKILLS]
        self.pilot_tree = ttk.Treeview(box, columns=[c[0] for c in cols], show="headings",
                                       selectmode="extended", height=4)
        for cid, heading, width in cols:
            self.pilot_tree.heading(cid, text=heading)
            self.pilot_tree.column(cid, width=width, anchor="w" if cid == "name" else "e")
        self.pilot_tree.pack(side="top", fill="x")
        self.pilot_tree.bind("<<TreeviewSelect>>", lambda e: self.on_pilot_select())
        # Bulk edit sits to the right of the single-pilot editor so the tab stays short.
        lower = ttk.Frame(box)
        lower.pack(side="top", fill="x", pady=(4, 0))
        edit = ttk.Frame(lower)
        edit.pack(side="left", anchor="n")
        ttk.Separator(lower, orient="vertical").pack(side="left", fill="y", padx=8)
        # Scope is the selected pilots, or every active pilot of the group when none are selected.
        bulk = ttk.Frame(lower)
        bulk.pack(side="left", anchor="n")
        ttk.Label(bulk, text="Bulk edit").grid(row=0, column=0, sticky="w", padx=(0, 4), pady=1)
        self.bulk_targets = ["Experience", "All skills"] + [airgroups.SKILL_NAMES[n] for n in airgroups.SKILLS]
        self.bulk_field_var = tk.StringVar(value=self.bulk_targets[0])
        ttk.Combobox(bulk, textvariable=self.bulk_field_var, values=self.bulk_targets, state="readonly",
                     width=16).grid(row=0, column=1, columnspan=2, sticky="w", pady=1)
        self.bulk_modes = {"Set to": "set", "Raise to at least": "raise", "Add": "add"}
        self.bulk_mode_var = tk.StringVar(value="Set to")
        ttk.Combobox(bulk, textvariable=self.bulk_mode_var, values=list(self.bulk_modes), state="readonly",
                     width=16).grid(row=1, column=1, columnspan=2, sticky="w", pady=1)
        ttk.Label(bulk, text="Amount").grid(row=2, column=0, sticky="w", padx=(0, 4), pady=1)
        self.bulk_amount_var = tk.StringVar()
        ttk.Entry(bulk, textvariable=self.bulk_amount_var, width=5).grid(row=2, column=1, sticky="w", pady=1)
        ttk.Button(bulk, text="Apply to pilots", command=self.apply_bulk_pilots).grid(
            row=2, column=2, sticky="w", padx=(4, 0), pady=1)
        self.bulk_scope = tk.StringVar()
        ttk.Label(bulk, textvariable=self.bulk_scope).grid(row=3, column=0, columnspan=3, sticky="w", pady=1)
        # Four label/entry pairs per row so the full skill names fit.
        per_row = 4
        for k, f in enumerate(airgroups.PILOT_FIELDS):
            row, col = divmod(k, per_row)
            ttk.Label(edit, text=f.label).grid(row=row, column=2 * col, sticky="w", padx=(0, 2), pady=1)
            self.pilot_vars[f.name] = tk.StringVar()
            ttk.Entry(edit, textvariable=self.pilot_vars[f.name], width=4).grid(
                row=row, column=2 * col + 1, sticky="w", padx=(0, 12), pady=1)
        k = len(airgroups.PILOT_FIELDS)
        ttk.Button(edit, text="Apply pilot", command=self.apply_pilot).grid(
            row=k // per_row, column=2 * (k % per_row), columnspan=2, sticky="w", pady=1)

    def _build_leader(self, parent):
        box = ttk.LabelFrame(parent, text="Commander", padding=4)
        box.pack(side="top", fill="x", pady=(6, 0))
        self.leader_name = tk.StringVar(value="(none)")
        ttk.Label(box, textvariable=self.leader_name).grid(row=0, column=0, columnspan=2, sticky="w", pady=1)
        self.leader_rank = tk.StringVar()
        ttk.Label(box, text="Rank").grid(row=0, column=2, sticky="w", padx=(0, 2), pady=1)
        ttk.Label(box, textvariable=self.leader_rank).grid(row=0, column=3, sticky="w", pady=1)
        # Same four-per-row grid as the pilot editor, below the name row.
        per_row = 4
        self.leader_entries = []
        for k, f in enumerate(airgroups.LEADER_FIELDS):
            row, col = divmod(k, per_row)
            ttk.Label(box, text=f.label).grid(row=row + 1, column=2 * col, sticky="w", padx=(0, 2), pady=1)
            self.leader_vars[f.name] = tk.StringVar()
            entry = ttk.Entry(box, textvariable=self.leader_vars[f.name], width=4)
            entry.grid(row=row + 1, column=2 * col + 1, sticky="w", padx=(0, 12), pady=1)
            self.leader_entries.append(entry)
        k = len(airgroups.LEADER_FIELDS)
        self.leader_button = ttk.Button(box, text="Apply commander", command=self.apply_leader)
        self.leader_button.grid(row=k // per_row + 1, column=2 * (k % per_row), columnspan=2, sticky="w", pady=1)

    def _build_units_tab(self):
        tab = self.units_tab = ttk.Frame(self.notebook, padding=4)
        self.notebook.add(tab, text="Land Units")
        right = ttk.LabelFrame(tab, text="Land unit", padding=8)
        right.pack(side="right", fill="y", padx=(8, 0))
        left = ttk.Frame(tab)
        left.pack(side="left", fill="both", expand=True)

        bar = ttk.Frame(left)
        bar.pack(side="top", fill="x")
        ttk.Label(bar, text="Search:").pack(side="left")
        self.unit_search_var = tk.StringVar()
        self.unit_search_var.trace_add("write", lambda *a: self.refresh_unit_list())
        ttk.Entry(bar, textvariable=self.unit_search_var, width=20).pack(side="left", padx=4)
        ttk.Label(bar, text="Side:").pack(side="left")
        self.unit_side_var = tk.StringVar(value="All")
        side_box = ttk.Combobox(bar, textvariable=self.unit_side_var, values=["All", "Allied", "Japanese"],
                                state="readonly", width=9)
        side_box.pack(side="left", padx=4)
        side_box.bind("<<ComboboxSelected>>", lambda e: self.refresh_unit_list())

        box = ttk.LabelFrame(left, text="Equipment", padding=4)
        box.pack(side="bottom", fill="x", pady=(6, 0))
        cols = [("slot", "Slot", 40), ("device", "Device", 150), ("count", "Count", 55),
                ("disabled", "Disabled", 60), ("toe_device", "TOE device", 150), ("toe_count", "TOE count", 65)]
        self.unit_equipment_tree = ttk.Treeview(box, columns=[c[0] for c in cols], show="headings",
                                                selectmode="browse", height=6)
        for cid, heading, width in cols:
            self.unit_equipment_tree.heading(cid, text=heading)
            self.unit_equipment_tree.column(cid, width=width, anchor="w" if "device" in cid else "e")
        self.unit_equipment_tree.pack(side="top", fill="x")
        self.unit_equipment_tree.bind("<<TreeviewSelect>>", lambda e: self.on_unit_equipment_select())
        edit = ttk.Frame(box)
        edit.pack(side="top", fill="x", pady=(4, 0))
        self.unit_equipment_vars = {}
        for name, label in (("count", "Count"), ("disabled", "Disabled")):
            ttk.Label(edit, text=label + ":").pack(side="left")
            self.unit_equipment_vars[name] = tk.StringVar()
            ttk.Entry(edit, textvariable=self.unit_equipment_vars[name], width=8).pack(side="left", padx=(2, 8))
        ttk.Button(edit, text="Apply equipment", command=self.apply_unit_equipment).pack(side="left", padx=4)
        fill = ttk.Frame(box)
        fill.pack(side="top", fill="x", pady=(4, 0))
        ttk.Label(fill, text="Bring up to TOE:").pack(side="left")
        for text, percent in (("Fill to TOE", 0), ("TOE +10%", 10), ("TOE +25%", 25)):
            ttk.Button(fill, text=text, command=lambda p=percent: self.fill_unit_to_toe(p)).pack(side="left", padx=(6, 0))
        add = ttk.Frame(box)
        add.pack(side="top", fill="x", pady=(4, 0))
        ttk.Label(add, text="Add:").pack(side="left")
        self.unit_add_device_var = tk.StringVar()
        self.unit_add_box = ttk.Combobox(add, textvariable=self.unit_add_device_var, state="disabled", width=26)
        self.unit_add_box.pack(side="left", padx=(2, 8))
        self.unit_add_vars = {}
        for name, label, default in (("count", "Count", ""), ("disabled", "Disabled", "0")):
            ttk.Label(add, text=label + ":").pack(side="left")
            self.unit_add_vars[name] = tk.StringVar(value=default)
            ttk.Entry(add, textvariable=self.unit_add_vars[name], width=6).pack(side="left", padx=(2, 8))
        self.unit_add_button = ttk.Button(add, text="Add equipment", command=self.add_unit_equipment)
        self.unit_add_button.pack(side="left", padx=4)

        self.unit_tree = ttk.Treeview(left, columns=[c[0] for c in UNIT_COLUMNS], show="headings",
                                      selectmode="browse", height=8)
        for cid, heading, width, _numeric, _get in UNIT_COLUMNS:
            self.unit_tree.heading(cid, text=heading, command=lambda c=cid: self.sort_units_by(c))
            self.unit_tree.column(cid, width=width, anchor="w" if cid in ("name", "type", "hq", "location") else "e")
        self.unit_tree.tag_configure("edited", background="#fff2b3")
        # Red text like the game's unit screen when supplies are below supplies required.
        self.unit_tree.tag_configure("short", foreground="red")
        # Units not yet arrived (reinforcements, not scheduled) are dimmed.
        self.unit_tree.tag_configure("pending", foreground="gray55")
        scroll = ttk.Scrollbar(left, orient="vertical", command=self.unit_tree.yview)
        self.unit_tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.unit_tree.pack(side="left", fill="both", expand=True)
        self.unit_tree.bind("<<TreeviewSelect>>", lambda e: self.on_unit_select())

        self.unit_title = tk.StringVar(value="(select a land unit)")
        ttk.Label(right, textvariable=self.unit_title, font=("TkDefaultFont", 11, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
        row = 1
        for f in landunits.FIELDS:
            ttk.Label(right, text=f.label + ("" if f.verified else " (unverified)")).grid(
                row=row, column=0, sticky="w", pady=2)
            self.unit_vars[f.name] = tk.StringVar()
            ttk.Entry(right, textvariable=self.unit_vars[f.name], width=12).grid(
                row=row, column=1, padx=(8, 0), pady=2)
            row += 1
        ttk.Button(right, text="Apply", command=self.apply_unit).grid(row=row, column=0, columnspan=2, pady=6)
        row += 1
        self.unit_info = {}
        self.unit_info_labels = {}
        for name, label in (("hq", "HQ (read-only)"), ("location", "Location"),
                            ("target", "Target (set by a move)"), ("required", "Supplies required (read-only)"),
                            ("support", "Support (game, read-only)"),
                            ("support_required", "Support required (game, read-only)"),
                            ("support_estimate", "Support required (estimate)")):
            ttk.Label(right, text=label).grid(row=row, column=0, sticky="w", pady=1)
            self.unit_info[name] = tk.StringVar()
            self.unit_info_labels[name] = ttk.Label(right, textvariable=self.unit_info[name])
            self.unit_info_labels[name].grid(row=row, column=1, sticky="w", padx=(8, 0))
            row += 1
        ttk.Button(right, text="Raise support to estimate", command=self.raise_unit_support).grid(
            row=row, column=0, columnspan=2, pady=4)
        row += 1
        self.unit_move_var, self.unit_move_box, self.unit_move_button, self.unit_move_note = self._build_move_row(
            right, row, self.move_unit)

    def _build_leaders_tab(self):
        tab = self.leaders_tab = ttk.Frame(self.notebook, padding=4)
        self.notebook.add(tab, text="Leaders")
        right = ttk.LabelFrame(tab, text="Leader", padding=8)
        right.pack(side="right", fill="y", padx=(8, 0))
        left = ttk.Frame(tab)
        left.pack(side="left", fill="both", expand=True)

        bar = ttk.Frame(left)
        bar.pack(side="top", fill="x")
        ttk.Label(bar, text="Search:").pack(side="left")
        self.ldr_search_var = tk.StringVar()
        self.ldr_search_var.trace_add("write", lambda *a: self._ldr_search_changed())
        ttk.Entry(bar, textvariable=self.ldr_search_var, width=20).pack(side="left", padx=4)
        self.ldr_filter_vars = {}
        for name, label, values, width in (
                ("side", "Side:", ["All", "Allied", "Japanese"], 9),
                ("branch", "Branch:", ["All"] + list(leaders.BRANCHES), 6),
                ("type", "Type:", ["All"] + list(leaders.TYPES.values()), 17),
                ("assigned", "Assigned:", ["All", "Assigned", "Unassigned"], 11)):
            ttk.Label(bar, text=label).pack(side="left")
            var = self.ldr_filter_vars[name] = tk.StringVar(value="All")
            box = ttk.Combobox(bar, textvariable=var, values=values, state="readonly", width=width)
            box.pack(side="left", padx=4)
            box.bind("<<ComboboxSelected>>", lambda e: self.refresh_ldr_list())
        self.ldr_count = tk.StringVar()
        ttk.Label(bar, textvariable=self.ldr_count).pack(side="right")

        self.ldr_tree = ttk.Treeview(left, columns=[c[0] for c in LEADER_COLUMNS], show="headings",
                                     selectmode="browse", height=8)
        for cid, heading, width, _numeric, _get in LEADER_COLUMNS:
            self.ldr_tree.heading(cid, text=heading, command=lambda c=cid: self.sort_ldr_by(c))
            self.ldr_tree.column(cid, width=width, anchor="w" if cid in ("name", "nation", "rank", "type", "commands")
                                 else "e")
        self.ldr_tree.tag_configure("edited", background="#fff2b3")
        # Leaders not yet available (delay above 0) are dimmed.
        self.ldr_tree.tag_configure("pending", foreground="gray55")
        scroll = ttk.Scrollbar(left, orient="vertical", command=self.ldr_tree.yview)
        self.ldr_tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.ldr_tree.pack(side="left", fill="both", expand=True)
        self.ldr_tree.bind("<<TreeviewSelect>>", lambda e: self.on_ldr_select())
        self.ldr_tree.bind("<Double-1>", lambda e: self.jump_to_ldr_unit())

        self.ldr_title = tk.StringVar(value="(select a leader)")
        ttk.Label(right, textvariable=self.ldr_title, font=("TkDefaultFont", 11, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
        row = 1
        for f in airgroups.LEADER_FIELDS:
            ttk.Label(right, text=f.label).grid(row=row, column=0, sticky="w", pady=2)
            self.ldr_vars[f.name] = tk.StringVar()
            ttk.Entry(right, textvariable=self.ldr_vars[f.name], width=12).grid(row=row, column=1, padx=(8, 0), pady=2)
            row += 1
        self.ldr_button = ttk.Button(right, text="Apply", command=self.apply_ldr)
        self.ldr_button.grid(row=row, column=0, columnspan=2, pady=6)
        row += 1
        self.ldr_info = {}
        for name, label in (("rank", "Rank (read-only)"), ("branch", "Branch"), ("nation", "Nation"),
                            ("type", "Type (read-only)"), ("political", "Political (unverified)"),
                            ("delay", "Delay, days"), ("commands", "Commands")):
            ttk.Label(right, text=label).grid(row=row, column=0, sticky="w", pady=1)
            self.ldr_info[name] = tk.StringVar()
            ttk.Label(right, textvariable=self.ldr_info[name]).grid(row=row, column=1, sticky="w", padx=(8, 0))
            row += 1
        ttk.Label(right, text="Double-click a leader to jump to the unit.", foreground="gray").grid(
            row=row, column=0, columnspan=2, sticky="w", pady=(6, 0))

    def _build_move_row(self, parent, row, command):
        """Destination box, Move button and a gray note for why moving is not possible."""
        ttk.Label(parent, text="Move to").grid(row=row, column=0, sticky="w", pady=(8, 2))
        var = tk.StringVar()
        box = ttk.Combobox(parent, textvariable=var, state="readonly", width=24)
        box.grid(row=row, column=1, padx=(8, 0), pady=(8, 2))
        button = ttk.Button(parent, text="Move", command=command)
        button.grid(row=row + 1, column=0, columnspan=2, pady=2)
        note = tk.StringVar()
        ttk.Label(parent, textvariable=note, foreground="gray40").grid(row=row + 2, column=0, columnspan=2, sticky="w")
        return var, box, button, note

    def _show_move(self, record, var, box, button, note):
        """Fill the destination box for a record, or disable it and say why it cannot move."""
        if record is None or not record.can_move:
            var.set("")
            box.configure(values=[], state="disabled")
            button.state(["disabled"])
            note.set(f"Cannot move: {record.move_blocker}" if record is not None else "")
            return
        box.configure(values=self.place_labels.get(record.side, []), state="readonly")
        button.state(["!disabled"])
        note.set("")
        var.set("")

    def _build_factories(self, parent):
        box = ttk.LabelFrame(parent, text="Factories", padding=4)
        box.pack(side="bottom", fill="x", pady=(6, 0))
        cols = [("slot", "Slot", 40), ("name", "Name", 150), ("kind", "Kind", 65), ("size", "Size", 55),
                ("damage", "Damage", 60), ("production", "Production", 75), ("repair", "Repair", 55),
                ("upgrade", "Upgrade", 60), ("available", "Available", 65)]
        self.factory_tree = ttk.Treeview(box, columns=[c[0] for c in cols], show="headings",
                                         selectmode="browse", height=6)
        for cid, heading, width in cols:
            self.factory_tree.heading(cid, text=heading)
            self.factory_tree.column(cid, width=width, anchor="w" if cid in ("name", "kind") else "e")
        self.factory_tree.pack(side="top", fill="x")
        self.factory_tree.bind("<<TreeviewSelect>>", lambda e: self.on_factory_select())
        edit = ttk.Frame(box)
        edit.pack(side="top", fill="x", pady=(4, 0))
        self.factory_size_var = tk.StringVar()
        self.factory_damage_var = tk.StringVar()
        self.factory_production_var = tk.BooleanVar()
        self.factory_repair_var = tk.BooleanVar()
        self.factory_upgrade_var = tk.BooleanVar()
        ttk.Label(edit, text="Size:").pack(side="left")
        ttk.Entry(edit, textvariable=self.factory_size_var, width=8).pack(side="left", padx=(2, 8))
        ttk.Label(edit, text="Damage:").pack(side="left")
        ttk.Entry(edit, textvariable=self.factory_damage_var, width=8).pack(side="left", padx=(2, 8))
        self.factory_production_check = ttk.Checkbutton(edit, text="Production", variable=self.factory_production_var)
        self.factory_production_check.pack(side="left", padx=4)
        ttk.Checkbutton(edit, text="Repair", variable=self.factory_repair_var).pack(side="left", padx=4)
        self.factory_upgrade_check = ttk.Checkbutton(edit, text="Upgrade", variable=self.factory_upgrade_var)
        self.factory_upgrade_check.pack(side="left", padx=4)
        ttk.Button(edit, text="Apply factory", command=self.apply_factory).pack(side="left", padx=8)
        model = ttk.Frame(box)
        model.pack(side="top", fill="x", pady=(4, 0))
        self.factory_model_var = tk.StringVar()
        ttk.Label(model, text="Model:").pack(side="left")
        self.factory_model_box = ttk.Combobox(model, textvariable=self.factory_model_var, state="readonly", width=34)
        self.factory_model_box.pack(side="left", padx=(2, 8))
        self.factory_model_button = ttk.Button(model, text="Set model", command=self.apply_factory_model)
        self.factory_model_button.pack(side="left")
        ttk.Label(model, text="(aircraft factories only, same side; size and switches are kept; not yet tested "
                              "in-game)").pack(side="left", padx=8)

    # ---- loading -------------------------------------------------------

    def open_dialog(self, initial_dir=None):
        if not self.confirm_discard():
            return
        start = initial_dir if initial_dir else (DEFAULT_DIR if os.path.isdir(DEFAULT_DIR) else HERE)
        path = filedialog.askopenfilename(title="Open save", initialdir=start,
                                          filetypes=[("WitP:AE saves", "*.pws"), ("All files", "*.*")])
        if path:
            self.load(path)

    def load(self, path):
        # Windows reports opening a folder as "Permission denied", which is misleading.
        if os.path.isdir(path):
            messagebox.showerror("Cannot open save", f"{path}\n\nThis is a folder. Choose a .pws save file inside it.")
            return False
        if not os.path.isfile(path):
            messagebox.showerror("Cannot open save", f"{path}\n\nFile not found.")
            return False
        try:
            save = SaveFile.load(path)
            blist = bases.list_bases(save, include_towns=True, include_minor=True)
            alist = aircraft.list_aircraft(save)
            slist = ships.list_ships(save)
            srlist = shiprecords.list_ship_records(save)
            tflist = self._load_task_forces(save)
            glist = airgroups.list_airgroups(save)
            ulist = landunits.list_land_units(save)
            lassign = leaders.assignments(save)
            lrows = leaders.list_leaders(save, lassign)
            pindex = airgroups.pilots_by_group(save)
            places = bases.list_places(save)
            devices = landunits.available_devices(save)
        except (OSError, SaveFormatError, KeyError) as exc:
            messagebox.showerror("Cannot open save", f"{path}\n\n{exc}")
            return False
        self.save, self.path = save, path
        # Judged on the title as loaded, so retitling the save cannot lift the block.
        self.pbem = is_pbem(save)
        self.bases = {b.id: b for b in blist}
        self.edited.clear()
        self.dirty = False
        self.current = None
        self.factory_slot = None
        self.aircraft = {a.id: a for a in alist}
        self.aircraft_edited.clear()
        self.aircraft_current = None
        self.ships = {x.id: x for x in slist}
        self.ships_edited.clear()
        self.ship_current = None
        self.ship_slot = None
        self.shiprecs = {x.id: x for x in srlist}
        self.shiprecs_edited.clear()
        self.shiprec_current = None
        self.shiprec_slot = None
        self.places_by_hex = {}
        for p in places:
            self.places_by_hex.setdefault((p.x, p.y), []).append(p)
        self.places_by_id = {p.id: p for p in places}
        # Built once per load: list_places is slow, and the orders boxes filter these lists.
        self.tf_port_items = [(p, f"{p.name} ({p.id})") for p in places if taskforces.port_size(save, p.id) > 0]
        self.tf_dest_items = [(p, f"{p.name} ({p.id}, {bases.SIDES.get(p.side_id, '?')})") for p in places]
        self.taskforces = {t.id: t for t in tflist}
        self.tfs_edited.clear()
        self.tf_current = None
        self.tf_ship_current = None
        self.groups = {g.id: g for g in glist}
        self.pilot_index = pindex
        for g in glist:
            g.active_pilots = sum(1 for p in pindex.get(g.id, []) if p.status == 1)
        self.groups_edited.clear()
        self.group_current = None
        self.pilot_current = None
        self.leader_current = None
        try:
            self.pools = {p.nation_id: p for p in pilotpool.list_pools(save)}
        except SaveFormatError:
            self.pools = {}  # the other tabs still work without the pool section
        self.pools_edited.clear()
        self.pool_current = None
        # Built once per load: decrypting every place name is slow.
        self.place_ids = {}
        self.place_labels = {}
        for p in sorted(places, key=lambda p: (p.name.lower(), p.id)):
            label = f"{p.name} ({p.id})"
            self.place_ids[label] = p.id
            self.place_labels.setdefault(bases.SIDES.get(p.side_id, "Unknown"), []).append(label)
        self.device_ids = {}
        self.device_labels = {}
        for side_id, items in devices.items():
            for device_id, name in items:
                label = f"{name} ({device_id})"
                self.device_ids[label] = device_id
                self.device_labels.setdefault(bases.SIDES[side_id], []).append(label)
        self.aircraft_ids = {}
        self.aircraft_labels = {}
        for a in sorted(alist, key=lambda a: (a.name.lower(), a.id)):
            month, year = a.get_date("from")
            label = f"{a.name} ({a.id}, {aircraft.format_date(month, year)})"
            self.aircraft_ids[label] = a.id
            self.aircraft_labels.setdefault(bases.SIDES.get(a.side_id, "Unknown"), []).append(label)
        self.plane_images = {}
        self.setup_compare()
        self.units = {u.id: u for u in ulist}
        self.units_edited.clear()
        self.unit_current = None
        self.unit_slot = None
        self.ldr_assign = lassign
        self.ldr_rows = {r.id: r for r in lrows}
        self.ldr_edited.clear()
        self.ldr_current = None
        self.file_label.set(f"File: {os.path.basename(path)}    Key variant: {save.variant}")
        self.title_var.set(save.description)
        self.status.set(f"{path} - {len(blist)} bases, towns and minor places, {len(alist)} aircraft, {len(slist)} ship classes, {len(srlist)} ships, {len(glist)} air groups, {len(ulist)} land units"
                        + (" - PBEM game: saving is disabled" if self.pbem else ""))
        self.refresh_list()
        self.show_detail(None)
        self.refresh_aircraft_list()
        self.show_aircraft(None)
        self.refresh_ship_list()
        self.show_ship(None)
        self.refresh_shiprec_list()
        self.show_shiprec(None)
        self.refresh_tf_list()
        self.show_tf(None)
        self.refresh_group_list()
        self.show_group(None)
        self.refresh_pool_list()
        self.show_pool(None)
        self.refresh_unit_list()
        self.show_unit(None)
        self.refresh_ldr_list()
        self.show_ldr(None)
        self.industry_places = industry.list_industry_places(save, regions.default_regions())
        self.refresh_reports()
        self.record_history()
        self.load_intel_view()
        self.load_map_view()
        return True

    def confirm_discard(self):
        if not self.dirty:
            return True
        return messagebox.askyesno("Unsaved changes", "There are unsaved changes. Discard them?")

    def quit(self):
        if self.confirm_discard():
            self.root.destroy()

    # ---- list ----------------------------------------------------------

    def _row_values(self, b):
        vals = []
        for cid, _h, _w, _n, get in COLUMNS:
            v = get(b)
            vals.append(f"{v[0]},{v[1]}" if cid == "hex" else v)
        return vals

    def _sort_key(self, b):
        _cid, _h, _w, numeric, get = COLUMN_BY_ID[self.sort_col]
        v = get(b)
        return v if numeric else str(v).lower()

    def refresh_list(self):
        selected = self.current
        self.tree.delete(*self.tree.get_children())
        needle = self.search_var.get().strip().lower()
        side = self.side_var.get()
        rows = [b for b in self.bases.values()
                if needle in b.name.lower() and (side == "All" or b.side == side)]
        rows.sort(key=self._sort_key, reverse=self.sort_reverse)
        for b in rows:
            tags = ("edited",) if b.id in self.edited else ()
            self.tree.insert("", "end", iid=str(b.id), values=self._row_values(b), tags=tags)
        if selected is not None and self.tree.exists(str(selected)):
            self.tree.selection_set(str(selected))

    def sort_by(self, col):
        self.sort_reverse = (not self.sort_reverse) if col == self.sort_col else False
        self.sort_col = col
        self.refresh_list()

    # ---- detail --------------------------------------------------------

    def on_select(self):
        sel = self.tree.selection()
        self.show_detail(self.bases[int(sel[0])] if sel else None)

    def show_detail(self, base):
        previous = self.current
        self.current = base.id if base else None
        if base is None:
            self.detail_title.set("(select a base)")
            for var in self.field_vars.values():
                var.set("")
            for var in list(self.stockpile_vars.values()) + list(self.building_vars.values()):
                var.set(False)
            self._set_port_editable("Base")
            self.show_factories(None)
            return
        self._set_port_editable(base.kind)
        self.detail_title.set(f"{base.name} (#{base.id}, {base.side}, hex {base.x},{base.y})")
        for f in bases.FIELDS:
            self.field_vars[f.name].set(str(base.get(f.name)))
        for name, on in base.get_stockpile().items():
            self.stockpile_vars[name].set(on)
        for name, on in base.get_building().items():
            self.building_vars[name].set(on)
        if base.id != previous:
            self.factory_slot = None
        self.show_factories(base)

    def _set_port_editable(self, kind):
        """Lock the port entries and build switch for towns, and the airfield ones too for minor places."""
        locked_fields, locked_builds = self._locked_for(kind)
        for name in bases.MINOR_READONLY_FIELDS:
            self.field_entries[name].state(["disabled" if name in locked_fields else "!disabled"])
        for name in bases.MINOR_READONLY_BUILD:
            self.building_checks[name].state(["disabled" if name in locked_builds else "!disabled"])

    @staticmethod
    def _locked_for(kind):
        """(read-only field names, read-only build switch names) for a Base.kind."""
        if kind == "Minor":
            return bases.MINOR_READONLY_FIELDS, bases.MINOR_READONLY_BUILD
        if kind == "Town":
            return bases.TOWN_READONLY_FIELDS, ("port",)
        return (), ()

    def show_factories(self, base):
        self.factory_tree.delete(*self.factory_tree.get_children())
        if base is None:
            self.factory_slot = None
            self._fill_factory_edit(None)
            return
        yn = lambda v: "Yes" if v else "No"
        for f in factories.list_factories(base):
            self.factory_tree.insert("", "end", iid=str(f.slot), values=(
                f.slot, f.name, f.kind, f.size, f.damage, yn(f.production_on), yn(f.repair_on),
                "-" if factories.upgrade_locked(f.type) else ("Upgd" if f.upgrade_on else "Keep"),
                f"{f.available[0]}/{f.available[1]}" if f.available else ""))
        slot = self.factory_slot
        if slot is not None and self.factory_tree.exists(str(slot)):
            self.factory_tree.selection_set(str(slot))
        else:
            self.factory_slot = None
            self._fill_factory_edit(None)

    def _fill_factory_edit(self, factory):
        if factory is None:
            self.factory_size_var.set("")
            self.factory_damage_var.set("")
            self.factory_production_var.set(True)
            self.factory_repair_var.set(True)
            self.factory_upgrade_var.set(False)
            self.factory_production_check.state(["disabled"])
            self.factory_upgrade_check.state(["disabled"])
            self._fill_factory_model(None)
            return
        self._fill_factory_model(factory)
        self.factory_size_var.set(str(factory.size))
        self.factory_damage_var.set(str(factory.damage))
        self.factory_production_var.set(factory.production_on)
        self.factory_repair_var.set(factory.repair_on)
        self.factory_upgrade_var.set(factory.upgrade_on)
        self.factory_production_check.state(["disabled" if factories.production_locked(factory.type) else "!disabled"])
        self.factory_upgrade_check.state(["disabled" if factories.upgrade_locked(factory.type) else "!disabled"])

    def _fill_factory_model(self, factory):
        """List the models of the factory's side in the Model box; it is disabled for other factories."""
        self.factory_model_ids = {}
        if factory is None or factory.kind != "aircraft":
            self.factory_model_var.set("")
            self.factory_model_box.configure(values=[])
            self.factory_model_box.state(["disabled"])
            self.factory_model_button.state(["disabled"])
            return
        current = self.aircraft.get(factory.type - factories.AIRCRAFT_BASE)
        side = current.side_id if current else None
        for a in sorted(self.aircraft.values(), key=lambda a: (a.name.lower(), a.id)):
            if a.side_id == side:
                self.factory_model_ids[f"{a.name} (#{a.id})"] = a.id
        self.factory_model_box.configure(values=list(self.factory_model_ids))
        self.factory_model_var.set(f"{factory.name} (#{factory.type - factories.AIRCRAFT_BASE})")
        self.factory_model_box.state(["!disabled"])
        self.factory_model_button.state(["!disabled"])

    def apply_factory_model(self):
        if self.current is None or self.factory_slot is None:
            return
        base = self.bases[self.current]
        aircraft_id = self.factory_model_ids.get(self.factory_model_var.get())
        try:
            if aircraft_id is None:
                raise ValueError("Choose a model from the list.")
            factories.set_aircraft_model(base, self.factory_slot, aircraft_id)
        except ValueError as exc:
            messagebox.showerror("Cannot change model", str(exc))
            return
        self.edited.add(base.id)
        self.dirty = True
        self.refresh_list()
        self.show_factories(base)
        self._fill_factory_edit(factories.get_factory(base, self.factory_slot))

    def on_factory_select(self):
        sel = self.factory_tree.selection()
        if not sel or self.current is None:
            return
        self.factory_slot = int(sel[0])
        self._fill_factory_edit(factories.get_factory(self.bases[self.current], self.factory_slot))

    def apply_factory(self):
        if self.current is None or self.factory_slot is None:
            return
        base = self.bases[self.current]
        before = factories.get_factory(base, self.factory_slot)
        try:
            size = int(self.factory_size_var.get().strip())
            damage = int(self.factory_damage_var.get().strip())
        except ValueError:
            messagebox.showerror("Invalid value", "Size and damage must be whole numbers.")
            return
        try:
            factories.set_factory(base, self.factory_slot, size, damage,
                                  bool(self.factory_production_var.get()), bool(self.factory_repair_var.get()),
                                  None if factories.upgrade_locked(before.type) else bool(self.factory_upgrade_var.get()))
        except ValueError as exc:
            messagebox.showerror("Invalid value", str(exc))
            return
        if factories.get_factory(base, self.factory_slot) != before:
            self.edited.add(base.id)
            self.dirty = True
        self.refresh_list()
        self.show_factories(base)

    def apply(self):
        if self.current is None:
            return
        base = self.bases[self.current]
        values = {}
        locked_fields, locked_builds = self._locked_for(base.kind)
        for f in bases.FIELDS:
            if not f.editable or f.name in locked_fields:
                continue
            text = self.field_vars[f.name].get().strip()
            try:
                values[f.name] = int(text)
                base.validate(f.name, values[f.name])
            except ValueError:
                messagebox.showerror("Invalid value",
                                     f"{f.label} must be a whole number from {f.min} to {f.max} (got {text!r}).")
                return
        before = {n: base.get(n) for n in values}
        flags = {n: bool(v.get()) for n, v in self.stockpile_vars.items()}
        flags_before = base.get_stockpile()
        building = {n: bool(v.get()) for n, v in self.building_vars.items() if n not in locked_builds}
        building_before = {n: v for n, v in base.get_building().items() if n in building}
        base.set_many(values)
        base.set_stockpile(flags)
        base.set_building(building)
        if before != values or flags_before != flags or building_before != building:
            self.edited.add(base.id)
            self.dirty = True
        self.refresh_list()
        self.show_detail(base)

    # ---- aircraft ------------------------------------------------------

    def _aircraft_row(self, a):
        return [aircraft.format_date(*a.get_date(cid)) if cid in ("from", "to") else get(a)
                for cid, _h, _w, _n, get in AIRCRAFT_COLUMNS]

    def _aircraft_sort_key(self, a):
        _cid, _h, _w, numeric, get = AIRCRAFT_COLUMN_BY_ID[self.aircraft_sort_col]
        v = get(a)
        # Ties fall back to the id so the order is stable.
        return (v if numeric else str(v).lower(), a.id)

    def _game_month_year(self):
        """(month, year) of the save's game date, or None when it cannot be read."""
        try:
            _, month, year = reports.game_date(self.save)
        except (SaveFormatError, IndexError):
            return None
        return month, year

    def refresh_aircraft_list(self):
        selected = self.aircraft_current
        self.aircraft_tree.delete(*self.aircraft_tree.get_children())
        needle = self.aircraft_search_var.get().strip().lower()
        rows = [a for a in self.aircraft.values() if needle in a.name.lower()]
        rows.sort(key=self._aircraft_sort_key, reverse=self.aircraft_sort_reverse)
        game_date = self._game_month_year()
        for a in rows:
            tags = ("edited",) if a.id in self.aircraft_edited else ()
            if game_date and not a.is_available(*game_date):
                tags += ("pending",)
            self.aircraft_tree.insert("", "end", iid=str(a.id), values=self._aircraft_row(a), tags=tags)
        if selected is not None and self.aircraft_tree.exists(str(selected)):
            self.aircraft_tree.selection_set(str(selected))

    def sort_aircraft_by(self, col):
        self.aircraft_sort_reverse = (not self.aircraft_sort_reverse) if col == self.aircraft_sort_col else False
        self.aircraft_sort_col = col
        self.refresh_aircraft_list()

    def on_aircraft_select(self):
        sel = self.aircraft_tree.selection()
        self.show_aircraft(self.aircraft[int(sel[0])] if sel else None)

    def show_aircraft(self, a):
        self.aircraft_current = a.id if a else None
        for tree in self.aircraft_weapon_trees.values():
            tree.delete(*tree.get_children())
        if a is None:
            self.aircraft_title.set("(select an aircraft)")
            self._show_plane(self.aircraft_picture, None)
            for var in list(self.aircraft_vars.values()) + list(self.aircraft_info.values()):
                var.set("")
            self.aircraft_carrier_var.set(False)
            return
        self.aircraft_title.set(f"{a.name} (#{a.id})")
        self._show_plane(self.aircraft_picture, a)
        for f in aircraft.FIELDS:
            self.aircraft_vars[f.name].set(str(a.get(f.name)))
        for name in ("from", "to"):
            self.aircraft_vars[name].set(aircraft.format_date(*a.get_date(name)))
        self.aircraft_vars["pool"].set(str(a.pool))
        self.aircraft_carrier_var.set(a.get_carrier())
        info = {"type": a.type, "nation": a.nation,
                "bitmap": str(a.bitmap), "upgrade": f"{a.upgrade_text} (unverified)",
                "engines": a.engines_text,
                "gun": str(a.gun_value),
                "endurance": "-" if a.endurance is None else str(a.endurance),
                "used": str(a.used), "last_turn": str(a.last_turn), "this_month": str(a.this_month),
                "mods": ", ".join(f"{band} {m}" for band, m in zip(aircraft.MANEUVER_MOD_BANDS, a.maneuver_mods))}
        for name, text in info.items():
            self.aircraft_info[name].set(text)
        for key, weapons in (("max", a.max_weapons), ("reduced", a.reduced_weapons)):
            for w in weapons:
                self.aircraft_weapon_trees[key].insert("", "end", values=w)

    # ---- aircraft pictures and comparison ------------------------------

    @staticmethod
    def _picture_label(parent):
        """A label in a fixed 150 x 60 frame (the caller places the frame), so a missing picture moves nothing."""
        frame = tk.Frame(parent, width=planeart.TILE_W, height=planeart.TILE_H)
        frame.pack_propagate(False)
        label = tk.Label(frame, wraplength=planeart.TILE_W, justify="left")
        label.pack(fill="both", expand=True)
        label.image = None
        return label

    def _art_dirs(self):
        dirs = [os.path.join(HERE, "..", "ART")]
        if self.path:
            dirs.insert(0, os.path.join(os.path.dirname(os.path.abspath(self.path)), "..", "ART"))
        return [os.path.normpath(d) for d in dirs]

    def _plane_image(self, a):
        key = (a.side_id, a.bitmap)
        if key not in self.plane_images:
            png = planeart.plane_png(self._art_dirs(), a.side_id, a.bitmap)
            self.plane_images[key] = tk.PhotoImage(master=self.root, data=base64.b64encode(png).decode("ascii"))
        return self.plane_images[key]

    def _show_plane(self, label, a):
        """Show the model's side-view picture in the label, or a short reason when there is none."""
        image, text = None, ""
        if a is not None:
            try:
                image = self._plane_image(a)
            except (ValueError, OSError, tk.TclError) as e:
                text = f"No picture ({e})"
        label.configure(image=image or "", text=text)
        label.image = image

    @staticmethod
    def _compare_label(a):
        return f"{a.name} (#{a.id}), {a.nation}"

    def setup_compare(self):
        """Fill the comparison choices from the loaded aircraft; A starts as the first Japanese fighter, B as the Allied."""
        by_id = sorted(self.aircraft.values(), key=lambda a: a.id)
        self.compare_ids = {self._compare_label(a): a.id for a in by_id}
        types = sorted({a.type for a in by_id})
        for col, side_id in zip(self.compare_cols, (0, 1)):
            col["side"].set("All")
            col["type"].set("All")
            col["type_box"].configure(values=["All"] + types)
            first = next((a for a in by_id if a.type_id == 0 and a.side_id == side_id), None)
            col["model"].set(self._compare_label(first) if first else "")
            self.refresh_compare_choices(col, keep=True)

    def refresh_compare_choices(self, col, keep=False):
        """Limit the model list to the column's side and type; the chosen model stays only if it still fits."""
        side, kind = col["side"].get(), col["type"].get()
        labels = [self._compare_label(a) for a in sorted(self.aircraft.values(), key=lambda a: (a.name.lower(), a.id))
                  if (side == "All" or bases.SIDES.get(a.side_id) == side) and (kind == "All" or a.type == kind)]
        col["model_box"].configure(values=labels)
        if col["model"].get() not in labels and not keep:
            col["model"].set("")
        self.refresh_compare_table()

    def refresh_compare_table(self):
        models = [self.aircraft.get(self.compare_ids.get(col["model"].get())) for col in self.compare_cols]
        for col, a in zip(self.compare_cols, models):
            self._show_plane(col["picture"], a)
        self.compare_tree.delete(*self.compare_tree.get_children())
        if None not in models:
            for row in aircraft.compare_rows(*models):
                self.compare_tree.insert("", "end", values=row)

    def compare_aircraft(self, k):
        """Send the model selected in the Aircraft tab to column A or B of the comparison."""
        if self.aircraft_current is None:
            return
        col = self.compare_cols[k]
        col["side"].set("All")
        col["type"].set("All")
        col["model"].set(self._compare_label(self.aircraft[self.aircraft_current]))
        self.refresh_compare_choices(col, keep=True)
        self.notebook.select(self.reports_tab)
        self.reports_notebook.select(self.compare_frame)

    def apply_aircraft(self):
        if self.aircraft_current is None:
            return
        a = self.aircraft[self.aircraft_current]
        values, dates = {}, {}
        try:
            for f in aircraft.FIELDS:
                text = self.aircraft_vars[f.name].get().strip()
                try:
                    values[f.name] = a.validate(f.name, int(text))
                except ValueError:
                    raise ValueError(f"{f.label} must be a whole number from {f.min} to {f.max} (got {text!r}).")
            for name in ("from", "to"):
                dates[name] = aircraft.parse_date(self.aircraft_vars[name].get())
            text = self.aircraft_vars["pool"].get().strip()
            try:
                pool = aircraft.check_pool(int(text))
            except ValueError:
                raise ValueError(f"In pool must be a whole number from 0 to {aircraft.MAX_POOL} (got {text!r}).")
        except ValueError as exc:
            messagebox.showerror("Invalid value", str(exc))
            return
        carrier = bool(self.aircraft_carrier_var.get())
        before = ({n: a.get(n) for n in values}, {n: a.get_date(n) for n in dates}, a.get_carrier(), a.pool)
        a.set_many(values)
        for name, value in dates.items():
            a.set_date(name, value)
        a.set_carrier(carrier)
        a.set_pool(pool)
        if before != (values, dates, carrier, pool):
            self.aircraft_edited.add(a.id)
            self.dirty = True
        self.refresh_aircraft_list()
        self.show_aircraft(a)

    # ---- ships ---------------------------------------------------------

    def _ship_row(self, x):
        return [aircraft.format_date(*x.date) if cid == "date" else get(x)
                for cid, _h, _w, _n, get in SHIP_COLUMNS]

    def _ship_sort_key(self, x):
        _cid, _h, _w, numeric, get = SHIP_COLUMN_BY_ID[self.ship_sort_col]
        v = get(x)
        return (v if numeric else str(v).lower(), x.id)

    def refresh_ship_list(self):
        selected = self.ship_current
        self.ship_tree.delete(*self.ship_tree.get_children())
        needle = self.ship_search_var.get().strip().lower()
        rows = [x for x in self.ships.values() if needle in x.name.lower()]
        rows.sort(key=self._ship_sort_key, reverse=self.ship_sort_reverse)
        for x in rows:
            tags = ("edited",) if x.id in self.ships_edited else ()
            self.ship_tree.insert("", "end", iid=str(x.id), values=self._ship_row(x), tags=tags)
        if selected is not None and self.ship_tree.exists(str(selected)):
            self.ship_tree.selection_set(str(selected))

    def sort_ships_by(self, col):
        self.ship_sort_reverse = (not self.ship_sort_reverse) if col == self.ship_sort_col else False
        self.ship_sort_col = col
        self.refresh_ship_list()

    def on_ship_select(self):
        sel = self.ship_tree.selection()
        self.show_ship(self.ships[int(sel[0])] if sel else None)

    def show_ship(self, x):
        previous = self.ship_current
        self.ship_current = x.id if x else None
        if x is None or x.id != previous:
            self.ship_slot = None
        if x is None:
            self.ship_title.set("(select a ship class)")
            for var in list(self.ship_vars.values()) + list(self.ship_info.values()):
                var.set("")
            self.show_ship_weapons(None)
            return
        self.ship_title.set(f"{x.name} (#{x.id}, {aircraft.format_date(*x.date)})")
        for f in ships.FIELDS:
            self.ship_vars[f.name].set(str(x.get(f.name)))
        self.ship_info["type"].set(x.type)
        self.ship_info["nation"].set(x.nation)
        self.ship_info["displacement"].set(str(x.displacement))
        self.ship_info["date"].set(aircraft.format_date(*x.date))
        self.show_ship_weapons(x)

    def show_ship_weapons(self, x):
        self.ship_weapon_tree.delete(*self.ship_weapon_tree.get_children())
        if x is not None:
            for slot, w in x.list_weapons():
                self.ship_weapon_tree.insert("", "end", iid=str(slot), values=(
                    w["name"], w["num"], ships.face_label(w["face"]), w["mount"], w["armor"], w["ammo"]))
        if x is not None and self.ship_slot is not None and self.ship_weapon_tree.exists(str(self.ship_slot)):
            self.ship_weapon_tree.selection_set(str(self.ship_slot))
        else:
            self.ship_slot = None
            self._fill_ship_weapon_edit(None)

    def _fill_ship_weapon_edit(self, w):
        for name, var in self.ship_weapon_vars.items():
            var.set("" if w is None else (ships.face_label(w[name]) if name == "face" else str(w[name])))

    def on_ship_weapon_select(self):
        sel = self.ship_weapon_tree.selection()
        if not sel or self.ship_current is None:
            return
        self.ship_slot = int(sel[0])
        self._fill_ship_weapon_edit(self.ships[self.ship_current].get_weapon(self.ship_slot))

    def apply_ship(self):
        if self.ship_current is None:
            return
        x = self.ships[self.ship_current]
        values = {}
        for f in ships.FIELDS:
            text = self.ship_vars[f.name].get().strip()
            try:
                values[f.name] = x.validate(f.name, int(text))
            except ValueError:
                messagebox.showerror("Invalid value",
                                     f"{f.label} must be a whole number from {f.min} to {f.max} (got {text!r}).")
                return
        before = {n: x.get(n) for n in values}
        x.set_many(values)
        if before != values:
            self.ships_edited.add(x.id)
            self.dirty = True
        self.refresh_ship_list()
        self.show_ship(x)

    def apply_ship_weapon(self):
        if self.ship_current is None or self.ship_slot is None:
            return
        x = self.ships[self.ship_current]
        values = {}
        try:
            for name, var in self.ship_weapon_vars.items():
                text = var.get().strip()
                if name == "face":
                    values[name] = ships.parse_face(text)
                else:
                    label = ships.WEAPON_FIELDS[name][0]
                    try:
                        values[name] = int(text)
                    except ValueError:
                        raise ValueError(f"{label} must be a whole number (got {text!r}).") from None
            x.check_weapon(self.ship_slot, **values)
        except ValueError as exc:
            messagebox.showerror("Invalid value", str(exc))
            return
        before = x.get_weapon(self.ship_slot)
        x.set_weapon(self.ship_slot, **values)
        if any(before[n] != v for n, v in values.items()):
            self.ships_edited.add(x.id)
            self.dirty = True
        self.refresh_ship_list()
        self.show_ship_weapons(x)

    # ---- ships in play -------------------------------------------------

    def _shiprec_sort_key(self, x):
        _cid, _h, _w, numeric, get = SHIPREC_COLUMN_BY_ID[self.shiprec_sort_col]
        v = get(x)
        return (v if numeric else str(v).lower(), x.id)

    def refresh_shiprec_list(self):
        selected = self.shiprec_current
        self.shiprec_tree.delete(*self.shiprec_tree.get_children())
        needle = self.shiprec_search_var.get().strip().lower()
        side = self.shiprec_side_var.get()
        rows = [x for x in self.shiprecs.values()
                if needle in x.name.lower() and (side == "All" or x.side == side)]
        rows.sort(key=self._shiprec_sort_key, reverse=self.shiprec_sort_reverse)
        for x in rows:
            tags = ("edited",) if x.id in self.shiprecs_edited else ()
            if not x.arrived:
                tags += ("pending",)
            self.shiprec_tree.insert("", "end", iid=str(x.id), values=[get(x) for *_, get in SHIPREC_COLUMNS],
                                     tags=tags)
        if selected is not None and self.shiprec_tree.exists(str(selected)):
            self.shiprec_tree.selection_set(str(selected))

    def sort_shiprecs_by(self, col):
        self.shiprec_sort_reverse = (not self.shiprec_sort_reverse) if col == self.shiprec_sort_col else False
        self.shiprec_sort_col = col
        self.refresh_shiprec_list()

    def on_shiprec_select(self):
        sel = self.shiprec_tree.selection()
        self.show_shiprec(self.shiprecs[int(sel[0])] if sel else None)

    def show_shiprec(self, x):
        previous = self.shiprec_current
        self.shiprec_current = x.id if x else None
        if x is None or x.id != previous:
            self.shiprec_slot = None
        if x is None:
            self.shiprec_title.set("(select a ship)")
            for var in list(self.shiprec_vars.values()) + list(self.shiprec_info.values()):
                var.set("")
            self.show_shiprec_move(None)
            self.show_shiprec_weapons(None)
            return
        self.shiprec_title.set(f"{x.name} (#{x.id})")
        for f in shiprecords.FIELDS:
            self.shiprec_vars[f.name].set(str(x.get(f.name)))
        self.shiprec_info["class"].set(f"{x.class_name} ({x.type}, #{x.class_id})")
        self.shiprec_info["nation"].set(f"{x.nation} ({x.side})")
        self.shiprec_info["base"].set(x.base_name or "at sea")
        self.shiprec_info["tf"].set(self._shiprec_tf_text(x))
        self.shiprec_info["arrival"].set(str(x.days_to_arrival) if x.days_to_arrival else "arrived")
        self.show_shiprec_move(x)
        self.show_shiprec_weapons(x)

    def _shiprec_tf_text(self, x):
        if not x.task_force:
            return "none"
        try:
            tf = taskforces.TaskForce(self.save, x.task_force)
        except ValueError:
            return str(x.task_force)
        flag = self.shiprecs.get(tf.flagship)
        text = " ".join(p for p in (str(tf.id), tf.name) if p)
        return f"{text} (flagship {flag.name})" if flag else text

    def show_shiprec_move(self, x):
        self.shiprec_destinations = taskforces.destinations(self.save, x.id) if x else []
        box = self.shiprec_move_box
        box.configure(values=[d.label for d in self.shiprec_destinations])
        self.shiprec_move_var.set("")
        if self.shiprec_destinations:
            box.configure(state="readonly")
            box.current(0)
            self.shiprec_move_button.state(["!disabled"])
            self.shiprec_move_note.set("")
        else:
            box.configure(state="disabled")
            self.shiprec_move_button.state(["disabled"])
            self.shiprec_move_note.set("no valid destination" if x else "")

    def move_shiprec(self):
        if self.shiprec_current is None or not self.shiprec_destinations:
            return
        index = self.shiprec_move_box.current()
        if index < 0:
            return
        x = self.shiprecs[self.shiprec_current]
        old_tf, dest = x.task_force, self.shiprec_destinations[index].id
        try:
            taskforces.move_ship(self.save, x.id, dest)
        except ValueError as exc:
            messagebox.showerror("Cannot move ship", str(exc))
            return
        # Redraws both tabs: the move changes ship counts (and maybe the flagship) of both TFs.
        self._tf_edited([old_tf, dest], [x.id])
        self.show_shiprec(x)

    def show_shiprec_weapons(self, x):
        tree = self.shiprec_weapon_tree
        tree.delete(*tree.get_children())
        if x is not None:
            for slot, w in x.list_weapons():
                tree.insert("", "end", iid=str(slot), values=(
                    w["name"], w["num"], ships.face_label(w["face"]), w["mount"], w["armor"], w["ammo"]))
        if x is not None and self.shiprec_slot is not None and tree.exists(str(self.shiprec_slot)):
            tree.selection_set(str(self.shiprec_slot))
        else:
            self.shiprec_slot = None
            self._fill_shiprec_weapon_edit(None)

    def _fill_shiprec_weapon_edit(self, w):
        for name, var in self.shiprec_weapon_vars.items():
            var.set("" if w is None else str(w[name]))

    def on_shiprec_weapon_select(self):
        sel = self.shiprec_weapon_tree.selection()
        if not sel or self.shiprec_current is None:
            return
        self.shiprec_slot = int(sel[0])
        self._fill_shiprec_weapon_edit(self.shiprecs[self.shiprec_current].get_weapon(self.shiprec_slot))

    def apply_shiprec(self):
        if self.shiprec_current is None:
            return
        x = self.shiprecs[self.shiprec_current]
        values = self._read_entries(x, shiprecords.FIELDS, self.shiprec_vars)
        if values is None:
            return
        before = {n: x.get(n) for n in values}
        try:
            x.set_many(values)
        except ValueError as exc:
            messagebox.showerror("Invalid value", str(exc))
            return
        if before != values:
            self.shiprecs_edited.add(x.id)
            self.dirty = True
        self.refresh_shiprec_list()
        self.show_shiprec(x)
        self._refresh_tf_of(x)

    def repair_shiprec(self):
        if self.shiprec_current is None:
            return
        x = self.shiprecs[self.shiprec_current]
        if any(x.get(n) for n in shiprecords.DAMAGE_FIELDS):
            x.repair_all()
            self.shiprecs_edited.add(x.id)
            self.dirty = True
        self.refresh_shiprec_list()
        self.show_shiprec(x)
        self._refresh_tf_of(x)

    def _refresh_tf_of(self, x):
        """Redraw the Task Forces detail when it shows the ship's TF (its fuel/damage grid)."""
        if self.tf_current is not None and x.task_force == self.tf_current:
            self.show_tf(self.taskforces[self.tf_current])

    def apply_shiprec_weapon(self):
        if self.shiprec_current is None or self.shiprec_slot is None:
            return
        x = self.shiprecs[self.shiprec_current]
        values = {}
        try:
            for name, var in self.shiprec_weapon_vars.items():
                text = var.get().strip()
                try:
                    values[name] = int(text)
                except ValueError:
                    raise ValueError(f"{shiprecords.WEAPON_FIELDS[name][0]} must be a whole number "
                                     f"(got {text!r}).") from None
            x.check_weapon(self.shiprec_slot, **values)
        except ValueError as exc:
            messagebox.showerror("Invalid value", str(exc))
            return
        before = x.get_weapon(self.shiprec_slot)
        x.set_weapon(self.shiprec_slot, **values)
        if any(before[n] != v for n, v in values.items()):
            self.shiprecs_edited.add(x.id)
            self.dirty = True
        self.refresh_shiprec_list()
        self.show_shiprec_weapons(x)

    # ---- task forces ---------------------------------------------------

    @staticmethod
    def _load_task_forces(save):
        """Task forces with ships and a readable chain; a damaged chain only hides its own TF."""
        out = []
        for i in range(taskforces.TF_BASE_ID, bases.RECORD_COUNT):
            if not taskforces.is_task_force(save, i):
                continue
            tf = taskforces.TaskForce(save, i)
            if tf.ship_count:
                try:
                    tf.ships
                except ValueError:
                    continue
                out.append(tf)
        return out

    def _tf_location(self, tf):
        places = self.places_by_hex.get(tf.hex)
        if places:
            return f"{places[0].name} (in port)"
        return "at sea {},{}".format(*tf.hex)

    def _place_name(self, place_id):
        place = self.places_by_id.get(place_id)
        return place.name if place else ("-" if not place_id else str(place_id))

    def _tf_row(self, tf):
        flag = self.shiprecs.get(tf.flagship)
        return {"id": tf.id, "name": tf.name, "side": tf.side, "location": self._tf_location(tf),
                "mission": tf.mission_label, "destination": self._place_name(tf.destination),
                "ships": tf.ship_count, "flagship": flag.name if flag else ""}

    def _tf_sort_key(self, row):
        _cid, _h, _w, numeric, get = TF_COLUMN_BY_ID[self.tf_sort_col]
        v = get(row)
        return (v if numeric else str(v).lower(), row["id"])

    def refresh_tf_list(self):
        selected = self.tf_current
        self.tf_tree.delete(*self.tf_tree.get_children())
        needle = self.tf_search_var.get().strip().lower()
        side = self.tf_side_var.get()
        rows = []
        for tf in self.taskforces.values():
            try:
                row = self._tf_row(tf)
            except ValueError:
                continue
            if needle in row["name"].lower() and (side == "All" or row["side"] == side):
                rows.append(row)
        rows.sort(key=self._tf_sort_key, reverse=self.tf_sort_reverse)
        for row in rows:
            tags = ("edited",) if row["id"] in self.tfs_edited else ()
            self.tf_tree.insert("", "end", iid=str(row["id"]), values=[get(row) for *_, get in TF_COLUMNS],
                                tags=tags)
        if selected is not None and self.tf_tree.exists(str(selected)):
            self.tf_tree.selection_set(str(selected))

    def sort_tfs_by(self, col):
        self.tf_sort_reverse = (not self.tf_sort_reverse) if col == self.tf_sort_col else False
        self.tf_sort_col = col
        self.refresh_tf_list()

    def on_tf_select(self):
        sel = self.tf_tree.selection()
        self.show_tf(self.taskforces[int(sel[0])] if sel else None)

    def show_tf(self, tf):
        previous = self.tf_current
        self.tf_current = tf.id if tf else None
        if tf is None or tf.id != previous:
            self.tf_ship_current = None
        tree = self.tf_ship_tree
        tree.delete(*tree.get_children())
        self.tf_flag_ships = []
        self.tf_flag_box.configure(values=[])
        self.tf_flag_var.set("")
        if tf is None:
            self.tf_title.set("(select a task force)")
            for var in self.tf_info.values():
                var.set("")
            self.show_tf_move(None)
            self.show_tf_add(None)
            self.show_tf_orders(None)
            return
        self.tf_title.set(f"{tf.name} (TF {tf.id})")
        self.tf_info["hex"].set("{},{}".format(*tf.hex))
        self.tf_info["location"].set(self._tf_location(tf))
        self.tf_info["side"].set(tf.side)
        flagship = tf.flagship
        ship_ids = tf.ships
        for sid in ship_ids:
            x = self.shiprecs[sid]
            top = x.max_fuel
            tree.insert("", "end", iid=str(sid), values=(
                "*" if sid == flagship else "", x.name, x.type, x.class_name,
                f"{x.get('fuel')}/{top if top is not None else '?'}", x.get("sys_dmg"), x.get("float_dmg"),
                x.get("eng_dmg"), x.get("fires")))
        if self.tf_ship_current in ship_ids:
            tree.selection_set(str(self.tf_ship_current))
        else:
            self.tf_ship_current = None
        self.tf_flag_ships = ship_ids
        self.tf_flag_box.configure(values=[f"{self.shiprecs[s].name} ({s})" for s in ship_ids])
        if flagship in ship_ids:
            self.tf_flag_box.current(ship_ids.index(flagship))
        self.show_tf_move(self.tf_ship_current)
        self.show_tf_add(tf)
        self.show_tf_orders(tf)

    def show_tf_orders(self, tf):
        """Fill the Orders box: current values and the home port list for the TF's side."""
        self.tf_home_shown = []
        if tf is None:
            for name in ("mission", "home_port", "destination"):
                self.tf_info[name].set("")
            self.tf_mission_var.set("")
            self.tf_home_box.configure(values=[])
            self.tf_home_var.set("")
        else:
            self.tf_info["mission"].set(f"{tf.mission:02d} - {tf.mission_label}")
            home = tf.home_port
            self.tf_info["home_port"].set(f"{self._place_name(home)} ({home})" if home else "-")
            dest = tf.destination
            self.tf_info["destination"].set(f"{self._place_name(dest)} ({dest})" if dest else "-")
            self.tf_mission_var.set(f"{tf.mission:02d} - {taskforces.MISSIONS[tf.mission]}"
                                    if tf.mission in taskforces.MISSIONS else "")
            side = tf.side
            self.tf_home_shown = [p for p, _label in self.tf_port_items if bases.SIDES.get(p.side_id) == side]
            labels = {p.id: label for p, label in self.tf_port_items}
            self.tf_home_box.configure(values=[labels[p.id] for p in self.tf_home_shown])
            self.tf_home_var.set("")
        self.show_tf_destinations()

    def show_tf_destinations(self):
        """Destination choices: every base and town whose label contains the filter text."""
        needle = self.tf_dest_filter_var.get().strip().lower()
        items = [(p, label) for p, label in self.tf_dest_items if needle in label.lower()]
        self.tf_dest_shown = [p for p, _label in items]
        self.tf_dest_box.configure(values=[label for _p, label in items])
        self.tf_dest_var.set("")

    def on_tf_ship_select(self):
        sel = self.tf_ship_tree.selection()
        self.tf_ship_current = int(sel[0]) if sel else None
        self.show_tf_move(self.tf_ship_current)

    def show_tf_move(self, ship_id):
        self.tf_destinations = taskforces.destinations(self.save, ship_id) if ship_id is not None else []
        box = self.tf_move_box
        box.configure(values=[d.label for d in self.tf_destinations])
        self.tf_move_var.set("")
        if self.tf_destinations:
            box.configure(state="readonly")
            box.current(0)
            self.tf_move_button.state(["!disabled"])
            self.tf_move_note.set("")
        else:
            box.configure(state="disabled")
            self.tf_move_button.state(["disabled"])
            self.tf_move_note.set("no valid destination" if ship_id is not None else "select a ship")

    def show_tf_add(self, tf):
        """Ships docked in the TF's port hex that may join it."""
        self.tf_add_ships = []
        if tf is not None:
            for place in self.places_by_hex.get(tf.hex, []):
                try:
                    docked = taskforces.chain(self.save, place.id)
                except ValueError:
                    continue
                self.tf_add_ships += [s for s in docked if taskforces.can_move(self.save, s, tf.id)]
        box = self.tf_add_box
        box.configure(values=[f"{self.shiprecs[s].name} ({s})" for s in self.tf_add_ships])
        self.tf_add_var.set("")
        if self.tf_add_ships:
            box.configure(state="readonly")
            box.current(0)
            self.tf_add_button.state(["!disabled"])
            self.tf_add_note.set("")
        else:
            box.configure(state="disabled")
            self.tf_add_button.state(["disabled"])
            self.tf_add_note.set("" if tf is None else
                                 "no ship in port can join" if self.places_by_hex.get(tf.hex) else "not in a port")

    def _tf_edited(self, tf_ids, ship_ids):
        """Mark rows edited, then redraw this tab and the Ships tab."""
        self.tfs_edited.update(i for i in tf_ids if i in self.taskforces)
        self.shiprecs_edited.update(ship_ids)
        self.dirty = True
        self.refresh_tf_list()
        self.refresh_shiprec_list()
        if self.shiprec_current in ship_ids:
            self.show_shiprec(self.shiprecs[self.shiprec_current])
        self.show_tf(self.taskforces[self.tf_current] if self.tf_current is not None else None)

    def set_tf_flagship(self):
        if self.tf_current is None:
            return
        index = self.tf_flag_box.current()
        if index < 0:
            return
        tf = self.taskforces[self.tf_current]
        before = tf.flagship
        try:
            taskforces.set_flagship(self.save, tf.id, self.tf_flag_ships[index])
        except ValueError as exc:
            messagebox.showerror("Cannot set flagship", str(exc))
            return
        if tf.flagship != before:
            self._tf_edited([tf.id], [])

    def _apply_tf_order(self, action, value, title):
        if self.tf_current is None or value is None:
            return
        tf = self.taskforces[self.tf_current]
        before = (tf.mission, tf.home_port, tf.destination)
        try:
            action(self.save, tf.id, value)
        except ValueError as exc:
            messagebox.showerror(title, str(exc))
            return
        if (tf.mission, tf.home_port, tf.destination) != before:
            self._tf_edited([tf.id], [])

    def set_tf_mission(self):
        text = self.tf_mission_var.get()
        code = int(text.split(" - ", 1)[0]) if " - " in text else None
        self._apply_tf_order(taskforces.set_mission, code, "Cannot set mission")

    def set_tf_home_port(self):
        index = self.tf_home_box.current()
        place = self.tf_home_shown[index] if index >= 0 else None
        self._apply_tf_order(taskforces.set_home_port, place.id if place else None, "Cannot set home port")

    def set_tf_destination(self):
        index = self.tf_dest_box.current()
        place = self.tf_dest_shown[index] if index >= 0 else None
        self._apply_tf_order(taskforces.set_destination, place.id if place else None, "Cannot set destination")

    def _move_ship_to(self, ship_id, dest_id):
        tf_ids = [i for i in (self.shiprecs[ship_id].task_force, dest_id) if i >= taskforces.TF_BASE_ID]
        try:
            taskforces.move_ship(self.save, ship_id, dest_id)
        except ValueError as exc:
            messagebox.showerror("Cannot move ship", str(exc))
            return
        self._tf_edited(tf_ids, [ship_id])

    def move_tf_ship(self):
        if self.tf_ship_current is None or not self.tf_destinations:
            return
        index = self.tf_move_box.current()
        if index >= 0:
            self._move_ship_to(self.tf_ship_current, self.tf_destinations[index].id)

    def add_tf_ship(self):
        if self.tf_current is None or not self.tf_add_ships:
            return
        index = self.tf_add_box.current()
        if index >= 0:
            self._move_ship_to(self.tf_add_ships[index], self.tf_current)

    def _tf_quick(self, action, title):
        if self.tf_current is None:
            return
        try:
            changed = action(self.save, self.tf_current)
        except ValueError as exc:
            messagebox.showerror(title, str(exc))
            return
        if changed:
            self._tf_edited([self.tf_current], changed)

    def repair_tf(self):
        self._tf_quick(taskforces.repair_task_force, "Cannot repair ships")

    def refuel_tf(self):
        self._tf_quick(taskforces.refuel_task_force, "Cannot refuel ships")

    # ---- air groups ----------------------------------------------------

    def _group_sort_key(self, g):
        _cid, _h, _w, numeric, get = GROUP_COLUMN_BY_ID[self.group_sort_col]
        v = get(g)
        return (v if numeric else str(v).lower(), g.id)

    def refresh_group_list(self):
        selected = self.group_current
        self.group_tree.delete(*self.group_tree.get_children())
        needle = self.group_search_var.get().strip().lower()
        side = self.group_side_var.get()
        rows = [g for g in self.groups.values()
                if needle in g.name.lower() and (side == "All" or g.side == side)]
        rows.sort(key=self._group_sort_key, reverse=self.group_sort_reverse)
        for g in rows:
            tags = ("edited",) if g.id in self.groups_edited else ()
            if not g.arrived:
                tags += ("pending",)
            self.group_tree.insert("", "end", iid=str(g.id), values=[get(g) for *_, get in GROUP_COLUMNS],
                                   tags=tags)
        if selected is not None and self.group_tree.exists(str(selected)):
            self.group_tree.selection_set(str(selected))

    def sort_groups_by(self, col):
        self.group_sort_reverse = (not self.group_sort_reverse) if col == self.group_sort_col else False
        self.group_sort_col = col
        self.refresh_group_list()

    def on_group_select(self):
        sel = self.group_tree.selection()
        self.show_group(self.groups[int(sel[0])] if sel else None)

    def show_group(self, g):
        previous = self.group_current
        self.group_current = g.id if g else None
        if g is None or g.id != previous:
            self.pilot_current = None
        if g is None:
            self.group_title.set("(select an air group)")
            for var in list(self.group_vars.values()) + list(self.group_info.values()):
                var.set("")
            self._show_move(None, self.group_move_var, self.group_move_box, self.group_move_button,
                            self.group_move_note)
            self._show_aircraft_choice(None)
            self._show_planes(None)
            self._show_schedule(None)
            self.show_pilots(None)
            self.show_leader(None)
            return
        self.group_title.set(f"{g.name} (#{g.id})")
        for f in airgroups.GROUP_FIELDS:
            value = g.get(f.name)
            self.group_vars[f.name].set(airgroups.format_day_date(value) if f.name in airgroups.DATE_FIELDS
                                        else str(value))
        leader = airgroups.get_leader(self.save, g.leader_id)
        self.group_info["aircraft"].set(f"{g.aircraft_id} {g.aircraft_name}")
        self.group_info["upgrade"].set(f"{g.upgrade_id} {g.upgrade_name}")
        self.group_info["planes"].set(str(g.planes))
        self.group_info["pilots"].set(str(g.pilot_count))
        self.group_info["leader"].set(f"{g.leader_id} {leader.name}" if leader else str(g.leader_id))
        self.group_info["formation"].set(g.formation_label)
        self.group_info["parent"].set(g.related_label(g.parent_id))
        self.group_info["return_as"].set(g.related_label(g.return_as_id))
        self.group_info["location"].set(f"{g.location_id} {g.location_name}")
        self._show_move(g, self.group_move_var, self.group_move_box, self.group_move_button, self.group_move_note)
        self._show_aircraft_choice(g)
        self._show_planes(g)
        self._show_schedule(g)
        self.show_pilots(g)
        self.show_leader(leader)

    def _show_schedule(self, g):
        entries = g.size_schedule() if g is not None else [None] * airgroups.SCHEDULE_COUNT
        for (date_var, size_var), entry in zip(self.schedule_vars, entries):
            date_var.set("" if entry is None or entry[0] == 0 else airgroups.format_month_date(entry[0]))
            size_var.set("" if entry is None or entry[0] == 0 else str(entry[1]))

    def apply_schedule(self):
        if self.group_current is None:
            return
        g = self.groups[self.group_current]
        entries = []
        for k, (date_var, size_var) in enumerate(self.schedule_vars, 1):
            try:
                date = airgroups.parse_month_date(date_var.get())
            except ValueError as exc:
                messagebox.showerror("Invalid value", f"Size change {k}: {exc}")
                return
            text = size_var.get().strip()
            try:
                size = int(text) if text not in ("", "-") else 0
            except ValueError:
                messagebox.showerror("Invalid value", f"Size change {k}: size must be a whole number (got {text!r}).")
                return
            entries.append((date, size))
        before = g.size_schedule()
        try:
            g.set_size_schedule(entries)
        except ValueError as exc:
            messagebox.showerror("Cannot change size changes", str(exc))
            return
        if before != entries:
            self.groups_edited.add(g.id)
            self.dirty = True
        self.refresh_group_list()
        self.show_group(g)

    def _show_planes(self, g):
        counts = {} if g is None else {"ready": g.ready, "maintenance": g.maintenance,
                                       "damaged": g.damaged, "reserve": g.reserve}
        for name, var in self.plane_vars.items():
            var.set(str(counts[name]) if g is not None else "")
        self.plane_total.set(str(g.planes) if g is not None else "")
        state = "normal" if g is not None and g.arrived else "disabled"
        for entry in self.plane_entries:
            entry.configure(state=state)
        for button in (self.plane_apply_button, self.plane_repair_button):
            button.state(["disabled"] if state == "disabled" else ["!disabled"])
        self.plane_note.set("not arrived" if g is not None and not g.arrived else "")

    def apply_planes(self):
        if self.group_current is None:
            return
        g = self.groups[self.group_current]
        counts = []
        for name in ("ready", "maintenance", "damaged", "reserve"):
            text = self.plane_vars[name].get().strip()
            try:
                counts.append(int(text))
            except ValueError:
                messagebox.showerror("Invalid value", f"{name.capitalize()} must be a whole number (got {text!r}).")
                return
        self._change_planes(g, lambda: g.set_plane_status(*counts))

    def repair_planes(self):
        if self.group_current is None:
            return
        g = self.groups[self.group_current]
        self._change_planes(g, g.repair_all)

    def _change_planes(self, g, change):
        before = (g.ready, g.maintenance, g.damaged, g.reserve)
        try:
            change()
        except ValueError as exc:
            messagebox.showerror("Cannot change planes", str(exc))
            return
        if before != (g.ready, g.maintenance, g.damaged, g.reserve):
            self.groups_edited.add(g.id)
            self.dirty = True
        self.refresh_group_list()
        self.show_group(g)

    def _show_aircraft_choice(self, g):
        for var, box, button in ((self.group_aircraft_var, self.group_aircraft_box, self.group_aircraft_button),
                                 (self.group_upgrade_var, self.group_upgrade_box, self.group_upgrade_button)):
            var.set("")
            if g is None:
                box.configure(values=[], state="disabled")
                button.state(["disabled"])
            else:
                box.configure(values=self.aircraft_labels.get(g.side, []), state="readonly")
                button.state(["!disabled"])

    def change_group_aircraft(self):
        self._change_group_model(self.group_aircraft_var, airgroups.AirGroup.set_aircraft, "Cannot change aircraft")

    def change_group_upgrade(self):
        self._change_group_model(self.group_upgrade_var, airgroups.AirGroup.set_upgrade, "Cannot set upgrade")

    def _change_group_model(self, var, setter, title):
        if self.group_current is None:
            messagebox.showerror(title, "Select an air group first.")
            return
        g = self.groups[self.group_current]
        aircraft_id = self.aircraft_ids.get(var.get())
        if aircraft_id is None:
            messagebox.showerror(title, "Choose an aircraft first.")
            return
        try:
            setter(g, aircraft_id)
        except ValueError as exc:
            messagebox.showerror(title, str(exc))
            return
        self.groups_edited.add(g.id)
        self.dirty = True
        self.refresh_group_list()
        self.show_group(g)

    def move_group(self):
        if self.group_current is None:
            return
        g = self.groups[self.group_current]
        dest = self.place_ids.get(self.group_move_var.get())
        if dest is None:
            messagebox.showerror("Cannot move", "Choose a destination first.")
            return
        self._move(g, dest, self.groups_edited, self.refresh_group_list, self.show_group)

    def _move(self, record, dest, edited, refresh, show):
        try:
            changed = dest != record.location_id
            record.move_to(dest)
        except ValueError as exc:
            messagebox.showerror("Cannot move", str(exc))
            return
        if changed:
            edited.add(record.id)
            self.dirty = True
        refresh()
        show(record)

    def apply_group(self):
        if self.group_current is None:
            return
        g = self.groups[self.group_current]
        values = {}
        for f in airgroups.GROUP_FIELDS:
            text = self.group_vars[f.name].get().strip()
            if f.name in airgroups.DATE_FIELDS:
                try:
                    values[f.name] = g.validate(f.name, airgroups.parse_day_date(text))
                except ValueError as exc:
                    messagebox.showerror("Invalid value", f"{f.label}: {exc}")
                    return
                continue
            try:
                values[f.name] = g.validate(f.name, int(text))
            except ValueError:
                messagebox.showerror("Invalid value",
                                     f"{f.label} must be a whole number from {f.min} to {f.max} (got {text!r}).")
                return
        before = {n: g.get(n) for n in values}
        g.set_many(values)
        if before != values:
            self.groups_edited.add(g.id)
            self.dirty = True
        self.refresh_group_list()
        self.show_group(g)

    def _read_entries(self, record, fields, vars_):
        """Checked values from a row of entries, or None after showing the error."""
        values = {}
        for f in fields:
            text = vars_[f.name].get().strip()
            try:
                values[f.name] = record.validate(f.name, int(text))
            except ValueError:
                messagebox.showerror("Invalid value",
                                     f"{f.label} must be a whole number from {f.min} to {f.max} (got {text!r}).")
                return None
        return values

    def show_pilots(self, g):
        previous = self.pilot_tree.selection()
        self.pilot_tree.delete(*self.pilot_tree.get_children())
        if g is not None:
            for p in self.pilot_index.get(g.id, []):
                self.pilot_tree.insert("", "end", iid=str(p.id), values=[p.id, p.name, p.status_label] + [
                    p.get(f.name) for f in airgroups.PILOT_FIELDS])
        # Keep the selection (a pilot id belongs to one group, so another group's rows never match).
        selected = [i for i in previous if self.pilot_tree.exists(i)] if g is not None else []
        if selected:
            self.pilot_tree.selection_set(selected)
        if len(selected) == 1:
            self.pilot_current = int(selected[0])
        else:
            self.pilot_current = None
            for var in self.pilot_vars.values():
                var.set("")
        self._update_bulk_scope()

    def _selected_pilot(self):
        if self.group_current is None or self.pilot_current is None:
            return None
        return next((p for p in self.pilot_index.get(self.group_current, []) if p.id == self.pilot_current), None)

    def on_pilot_select(self):
        sel = self.pilot_tree.selection()
        self._update_bulk_scope()
        if len(sel) != 1 or self.group_current is None:
            # Several pilots (or none): the single-pilot editor is idle and the bulk edit applies.
            self.pilot_current = None
            for var in self.pilot_vars.values():
                var.set("")
            return
        self.pilot_current = int(sel[0])
        pilot = self._selected_pilot()
        for f in airgroups.PILOT_FIELDS:
            self.pilot_vars[f.name].set(str(pilot.get(f.name)))

    def _bulk_pilots(self):
        """Selected pilots of the current group, else all its active pilots."""
        pilots = self.pilot_index.get(self.group_current, []) if self.group_current is not None else []
        selected = {int(i) for i in self.pilot_tree.selection()}
        if selected:
            return [p for p in pilots if p.id in selected]
        return [p for p in pilots if p.status == 1]

    def _update_bulk_scope(self):
        count = len(self._bulk_pilots())
        if self.pilot_tree.selection():
            self.bulk_scope.set(f"{count} selected pilot{'s' if count != 1 else ''}")
        else:
            self.bulk_scope.set(f"all {count} active pilot{'s' if count != 1 else ''}")

    def apply_bulk_pilots(self):
        if self.group_current is None:
            return
        text = self.bulk_amount_var.get().strip()
        try:
            amount = int(text)
        except ValueError:
            messagebox.showerror("Invalid value", f"Amount must be a whole number (got {text!r}).")
            return
        target = self.bulk_field_var.get()
        if target == "All skills":
            fields = airgroups.SKILL_FIELDS
        elif target == "Experience":
            fields = ["experience"]
        else:
            fields = [next(f.name for f in airgroups.PILOT_FIELDS[1:] if f.label.startswith(target + " ("))]
        pilots = self._bulk_pilots()
        try:
            changed = airgroups.bulk_edit_pilots(pilots, fields, self.bulk_modes[self.bulk_mode_var.get()], amount)
        except ValueError as e:
            messagebox.showerror("Invalid value", str(e))
            return
        g = self.groups[self.group_current]
        if changed:
            self.groups_edited.add(self.group_current)
            self.dirty = True
            self.status.set(f"Bulk edit changed {changed} pilot{'s' if changed != 1 else ''} of {g.name} (not yet saved)")
        self.refresh_group_list()
        self.show_pilots(g)

    def apply_pilot(self):
        pilot = self._selected_pilot()
        if pilot is None:
            return
        values = self._read_entries(pilot, airgroups.PILOT_FIELDS, self.pilot_vars)
        if values is None:
            return
        before = {n: pilot.get(n) for n in values}
        pilot.set_many(values)
        if before != values:
            self.groups_edited.add(self.group_current)
            self.dirty = True
        self.refresh_group_list()
        self.show_pilots(self.groups[self.group_current])

    def show_leader(self, leader):
        self.leader_current = leader
        state = "!disabled" if leader else "disabled"
        for widget in self.leader_entries + [self.leader_button]:
            widget.state([state])
        self.leader_name.set(leader.name if leader else "(none)")
        self.leader_rank.set(f"{leaders.rank_label(leader.rank_code)} ({leader.rank_code})" if leader else "")
        for f in airgroups.LEADER_FIELDS:
            self.leader_vars[f.name].set(str(leader.get(f.name)) if leader else "")

    def apply_leader(self):
        leader = self.leader_current
        if leader is None or self.group_current is None:
            return
        values = self._read_entries(leader, airgroups.LEADER_FIELDS, self.leader_vars)
        if values is None:
            return
        before = {n: leader.get(n) for n in values}
        leader.set_many(values)
        if before != values:
            self.groups_edited.add(self.group_current)
            self.dirty = True
            self._leader_changed(leader.id)
        self.refresh_group_list()
        self.show_leader(leader)

    # ---- pilot pool ----------------------------------------------------

    @staticmethod
    def _pool_row(pool):
        intakes = [f"{c} ({e})" for c, e in zip(pool.counts, pool.experiences)]
        return [pool.label, pool.get("pool"), pool.get("experience"), pool.get("rate"), pool.in_training] + intakes

    def refresh_pool_list(self):
        selected = self.pool_current
        self.pool_tree.delete(*self.pool_tree.get_children())
        side = self.pool_side_var.get()
        for pool in self.pools.values():
            if side != "All" and pool.side != side:
                continue
            if pool.is_empty and not self.pool_empty_var.get() and pool.nation_id not in self.pools_edited:
                continue
            tags = ("edited",) if pool.nation_id in self.pools_edited else ()
            self.pool_tree.insert("", "end", iid=str(pool.nation_id), values=self._pool_row(pool), tags=tags)
        if selected is not None and self.pool_tree.exists(str(selected)):
            self.pool_tree.selection_set(str(selected))

    def on_pool_select(self):
        sel = self.pool_tree.selection()
        self.show_pool(self.pools[int(sel[0])] if sel else None)

    def show_pool(self, pool):
        self.pool_current = pool.nation_id if pool else None
        self.pool_title.set(f"{pool.label} ({pool.side}, nation {pool.nation_id})" if pool else "(select a nation)")
        self.pool_button.state(["!disabled" if pool else "disabled"])
        for name, var in self.pool_vars.items():
            var.set(str(pool.get(name)) if pool else "")

    def apply_pool(self):
        if self.pool_current is None:
            return
        pool = self.pools[self.pool_current]
        values = {}
        for name, var in self.pool_vars.items():
            text = var.get().strip()
            try:
                number = int(text)
            except ValueError:
                messagebox.showerror("Invalid value", f"{pilotpool.field_label(name)} must be a whole number (got {text!r}).")
                return
            try:
                values[name] = pool.validate(name, number)
            except ValueError as exc:
                messagebox.showerror("Invalid value", str(exc))
                return
        before = {n: pool.get(n) for n in values}
        pool.set_many(values)
        if before != values:
            self.pools_edited.add(pool.nation_id)
            self.dirty = True
            self.status.set(f"Pilot pool of {pool.label} changed (not yet saved)")
        self.refresh_pool_list()
        self.show_pool(pool)

    # ---- land units ----------------------------------------------------

    def _unit_sort_key(self, u):
        _cid, _h, _w, numeric, get = UNIT_COLUMN_BY_ID[self.unit_sort_col]
        v = get(u)
        return (v if numeric else str(v).lower(), u.id)

    def refresh_unit_list(self):
        selected = self.unit_current
        self.unit_tree.delete(*self.unit_tree.get_children())
        needle = self.unit_search_var.get().strip().lower()
        side = self.unit_side_var.get()
        rows = [u for u in self.units.values()
                if needle in u.display_name.lower() and (side == "All" or u.side == side)]
        rows.sort(key=self._unit_sort_key, reverse=self.unit_sort_reverse)
        for u in rows:
            # Text colour: dimmed while not arrived (a shortage is not shown then), else red when short.
            colour = ("pending",) if not u.arrived else ("short",) if u.supplies_short else ()
            tags = (("edited",) if u.id in self.units_edited else ()) + colour
            self.unit_tree.insert("", "end", iid=str(u.id), values=[UNIT_TEXT.get(cid, get)(u)
                                                                    for cid, *_, get in UNIT_COLUMNS],
                                  tags=tags)
        if selected is not None and self.unit_tree.exists(str(selected)):
            self.unit_tree.selection_set(str(selected))

    def sort_units_by(self, col):
        self.unit_sort_reverse = (not self.unit_sort_reverse) if col == self.unit_sort_col else False
        self.unit_sort_col = col
        self.refresh_unit_list()

    def on_unit_select(self):
        sel = self.unit_tree.selection()
        self.show_unit(self.units[int(sel[0])] if sel else None)

    def show_unit(self, u):
        previous = self.unit_current
        self.unit_current = u.id if u else None
        if u is None or u.id != previous:
            self.unit_slot = None
        if u is None:
            self.unit_title.set("(select a land unit)")
            for var in list(self.unit_vars.values()) + list(self.unit_info.values()):
                var.set("")
            self._show_move(None, self.unit_move_var, self.unit_move_box, self.unit_move_button, self.unit_move_note)
            self.show_unit_equipment(None)
            self._show_add_equipment(None)
            return
        self.unit_title.set(f"{u.display_name} (#{u.id}, {u.type}, class {u.class_id}, {u.side})")
        for f in landunits.FIELDS:
            self.unit_vars[f.name].set(str(u.get(f.name)))
        self.unit_info["hq"].set(f"{u.hq_id} {u.hq_name}")
        self.unit_info["location"].set(f"{u.location_id} {u.location_name}")
        self.unit_info["target"].set(f"{u.target_id} {u.target_name}")
        self.unit_info["required"].set(f"{u.supplies_required} (short)" if u.supplies_short else str(u.supplies_required))
        self.unit_info_labels["required"].configure(foreground="red" if u.supplies_short else "")
        self.unit_info["support"].set(str(u.support))
        self.unit_info["support_required"].set(str(u.support_required))
        self._show_move(u, self.unit_move_var, self.unit_move_box, self.unit_move_button, self.unit_move_note)
        self.show_unit_equipment(u)
        self._show_add_equipment(u)

    def move_unit(self):
        if self.unit_current is None:
            return
        u = self.units[self.unit_current]
        dest = self.place_ids.get(self.unit_move_var.get())
        if dest is None:
            messagebox.showerror("Cannot move", "Choose a destination first.")
            return
        self._move(u, dest, self.units_edited, self.refresh_unit_list, self.show_unit)

    def show_unit_equipment(self, u):
        if u is None:
            self.unit_info["support_estimate"].set("")
        else:
            support, needed = u.support_estimate()
            short = needed - support
            self.unit_info["support_estimate"].set(f"{needed} ({short} short)" if short > 0 else str(needed))
        self.unit_equipment_tree.delete(*self.unit_equipment_tree.get_children())
        if u is not None:
            for slot, e in u.list_equipment():
                self.unit_equipment_tree.insert("", "end", iid=str(slot), values=(
                    slot, e["device"], e["count"], e["disabled"], e["toe_device"], e["toe_count"]))
        if u is not None and self.unit_slot is not None and self.unit_equipment_tree.exists(str(self.unit_slot)):
            self.unit_equipment_tree.selection_set(str(self.unit_slot))
        else:
            self.unit_slot = None
            for var in self.unit_equipment_vars.values():
                var.set("")

    def _show_add_equipment(self, u):
        """Offer the unit's side's devices in the Add box; disabled when no unit is selected."""
        self.unit_add_device_var.set("")
        if u is None:
            self.unit_add_box.configure(values=[], state="disabled")
            self.unit_add_button.state(["disabled"])
        else:
            self.unit_add_box.configure(values=self.device_labels.get(u.side, []), state="readonly")
            self.unit_add_button.state(["!disabled"])

    def on_unit_equipment_select(self):
        sel = self.unit_equipment_tree.selection()
        if not sel or self.unit_current is None:
            return
        self.unit_slot = int(sel[0])
        e = self.units[self.unit_current].get_equipment(self.unit_slot)
        self.unit_equipment_vars["count"].set(str(e["count"]))
        self.unit_equipment_vars["disabled"].set(str(e["disabled"]))

    def apply_unit(self):
        if self.unit_current is None:
            return
        u = self.units[self.unit_current]
        values = {}
        for f in landunits.FIELDS:
            text = self.unit_vars[f.name].get().strip()
            try:
                values[f.name] = u.validate(f.name, int(text))
            except ValueError:
                messagebox.showerror("Invalid value",
                                     f"{f.label} must be a whole number from {f.min} to {f.max} (got {text!r}).")
                return
        before = {n: u.get(n) for n in values}
        u.set_many(values)
        if before != values:
            self.units_edited.add(u.id)
            self.dirty = True
        self.refresh_unit_list()
        self.show_unit(u)

    def apply_unit_equipment(self):
        if self.unit_current is None or self.unit_slot is None:
            return
        u = self.units[self.unit_current]
        try:
            count = int(self.unit_equipment_vars["count"].get().strip())
            disabled = int(self.unit_equipment_vars["disabled"].get().strip())
        except ValueError:
            messagebox.showerror("Invalid value", "Count and disabled must be whole numbers.")
            return
        before = u.get_equipment(self.unit_slot)
        try:
            u.set_equipment(self.unit_slot, count, disabled)
        except ValueError as exc:
            messagebox.showerror("Invalid value", str(exc))
            return
        if (before["count"], before["disabled"]) != (count, disabled):
            self.units_edited.add(u.id)
            self.dirty = True
        self.refresh_unit_list()
        self.show_unit_equipment(u)

    def fill_unit_to_toe(self, percent):
        if self.unit_current is None:
            return
        u = self.units[self.unit_current]
        level = "TOE" if percent == 0 else f"TOE +{percent}%"
        changed = u.fill_to_toe(percent)
        if not changed:
            self.status.set(f"{u.name} is already at {level}")
            return
        self.units_edited.add(u.id)
        self.dirty = True
        self.refresh_unit_list()
        self.show_unit_equipment(u)
        self.status.set(f"Filled {changed} slot{'s' if changed != 1 else ''} of {u.name} to {level} (not yet saved)")

    def raise_unit_support(self):
        if self.unit_current is None:
            return
        u = self.units[self.unit_current]
        try:
            added = u.raise_support_to_estimate()
        except ValueError as exc:
            messagebox.showerror("Cannot raise support", str(exc))
            return
        if not added:
            self.status.set(f"{u.name} already has enough support (estimate)")
            return
        self.units_edited.add(u.id)
        self.dirty = True
        self.refresh_unit_list()
        self.show_unit_equipment(u)
        self.status.set(f"Added {added} support squad{'s' if added != 1 else ''} to {u.name} (not yet saved)")

    def add_unit_equipment(self):
        if self.unit_current is None:
            return
        u = self.units[self.unit_current]
        device_id = self.device_ids.get(self.unit_add_device_var.get())
        if device_id is None:
            messagebox.showerror("Cannot add equipment", "Choose a device first.")
            return
        try:
            count = int(self.unit_add_vars["count"].get().strip())
            disabled = int(self.unit_add_vars["disabled"].get().strip())
        except ValueError:
            messagebox.showerror("Invalid value", "Count and disabled must be whole numbers.")
            return
        allowed = {self.device_ids[label] for label in self.device_labels.get(u.side, [])}
        try:
            slot = u.add_equipment(device_id, count, disabled, allowed)
        except ValueError as exc:
            messagebox.showerror("Cannot add equipment", str(exc))
            return
        self.units_edited.add(u.id)
        self.dirty = True
        self.unit_add_vars["count"].set("")
        self.unit_add_vars["disabled"].set("0")
        self.unit_add_device_var.set("")
        self.refresh_unit_list()
        self.unit_slot = slot
        self.show_unit_equipment(u)
        self.unit_equipment_vars["count"].set(str(count))
        self.unit_equipment_vars["disabled"].set(str(disabled))

    # ---- leaders -------------------------------------------------------

    def _ldr_search_changed(self):
        """Rebuilding 27,000 rows per keystroke is slow, so wait until typing pauses."""
        if self.ldr_search_job is not None:
            self.root.after_cancel(self.ldr_search_job)
        self.ldr_search_job = self.root.after(250, self.refresh_ldr_list)

    def _ldr_sort_key(self, r):
        _cid, _h, _w, numeric, get = LEADER_COLUMN_BY_ID[self.ldr_sort_col]
        v = get(r)
        return (v if numeric else str(v).lower(), r.id)

    def refresh_ldr_list(self):
        if self.ldr_search_job is not None:
            self.root.after_cancel(self.ldr_search_job)
            self.ldr_search_job = None
        selected = self.ldr_current
        self.ldr_tree.delete(*self.ldr_tree.get_children())
        f = self.ldr_filter_vars
        rows = leaders.filter_leaders(self.ldr_rows.values(), f["side"].get(), f["branch"].get(), f["type"].get(),
                                      f["assigned"].get(), self.ldr_search_var.get())
        rows.sort(key=self._ldr_sort_key, reverse=self.ldr_sort_reverse)
        for r in rows:
            tags = ("edited",) if r.id in self.ldr_edited else ()
            if r.delay > 0:
                tags += ("pending",)
            self.ldr_tree.insert("", "end", iid=str(r.id), values=[get(r) for *_, get in LEADER_COLUMNS], tags=tags)
        self.ldr_count.set(f"{len(rows)} of {len(self.ldr_rows)} leaders")
        if selected is not None and self.ldr_tree.exists(str(selected)):
            self.ldr_tree.selection_set(str(selected))

    def sort_ldr_by(self, col):
        self.ldr_sort_reverse = (not self.ldr_sort_reverse) if col == self.ldr_sort_col else False
        self.ldr_sort_col = col
        self.refresh_ldr_list()

    def on_ldr_select(self):
        sel = self.ldr_tree.selection()
        self.show_ldr(self.ldr_rows[int(sel[0])] if sel else None)

    def show_ldr(self, r):
        self.ldr_current = r.id if r else None
        self.ldr_button.state(["!disabled" if r else "disabled"])
        if r is None:
            self.ldr_title.set("(select a leader)")
            for var in list(self.ldr_vars.values()) + list(self.ldr_info.values()):
                var.set("")
            return
        self.ldr_title.set(f"{r.name} (#{r.id}, {r.side})")
        for f in airgroups.LEADER_FIELDS:
            self.ldr_vars[f.name].set(str(getattr(r, f.name)))
        self.ldr_info["rank"].set(f"{r.rank} ({r.rank_code})")
        self.ldr_info["branch"].set(r.branch)
        self.ldr_info["nation"].set(f"{r.nation} ({r.nation_id})")
        self.ldr_info["type"].set(r.type)
        self.ldr_info["political"].set(str(r.political))
        self.ldr_info["delay"].set("available" if r.delay == 0 else str(r.delay))
        self.ldr_info["commands"].set(f"{r.kind}: {r.commands}" if r.kind else "")

    def _leader_changed(self, leader_id):
        """Rebuild a leader's row after an edit in either tab and mark it edited."""
        old = self.ldr_rows.get(leader_id)
        if old is None:
            return
        self.ldr_rows[leader_id] = leaders.make_row(self.save, leader_id, old.name, self.ldr_assign.get(leader_id, ()))
        self.ldr_edited.add(leader_id)
        self.refresh_ldr_list()
        if self.ldr_current == leader_id:
            self.show_ldr(self.ldr_rows[leader_id])

    def apply_ldr(self):
        if self.ldr_current is None:
            return
        leader = airgroups.get_leader(self.save, self.ldr_current)
        values = self._read_entries(leader, airgroups.LEADER_FIELDS, self.ldr_vars)
        if values is None:
            return
        before = {n: leader.get(n) for n in values}
        leader.set_many(values)
        if before != values:
            self.dirty = True
            self._leader_changed(leader.id)
            # The Air Groups tab shows the commander of the selected group and highlights the group.
            for kind, group_id, _text in self.ldr_assign.get(leader.id, ()):
                if kind == leaders.KIND_AIR_GROUP:
                    self.groups_edited.add(group_id)
            self.refresh_group_list()
            if self.leader_current is not None and self.leader_current.id == leader.id:
                self.show_leader(self.leader_current)
        self.show_ldr(self.ldr_rows[leader.id])

    def jump_to_ldr_unit(self):
        """Select the unit the leader commands in its own tab; nothing for an unassigned leader."""
        row = self.ldr_rows.get(self.ldr_current)
        if row is None or not row.kind:
            return
        iid = str(row.unit_id)
        if row.kind == leaders.KIND_AIR_GROUP:
            tab, tree = self.groups_tab, self.group_tree
            filters = ((self.group_search_var, ""), (self.group_side_var, "All"))
            refresh = self.refresh_group_list
        elif row.kind == leaders.KIND_SHIP:
            tab, tree = self.shiprec_tab, self.shiprec_tree
            filters = ((self.shiprec_search_var, ""), (self.shiprec_side_var, "All"))
            refresh = self.refresh_shiprec_list
        elif row.kind == leaders.KIND_TF:
            tab, tree = self.tf_tab, self.tf_tree
            filters = ((self.tf_search_var, ""), (self.tf_side_var, "All"))
            refresh = self.refresh_tf_list
        else:
            tab, tree = self.units_tab, self.unit_tree
            filters = ((self.unit_search_var, ""), (self.unit_side_var, "All"))
            refresh = self.refresh_unit_list
        if not tree.exists(iid):
            for var, value in filters:
                var.set(value)
            refresh()
        if not tree.exists(iid):
            return
        self.notebook.select(tab)
        if tab is self.groups_tab:
            self.groups_notebook.select(self.groups_page)
        tree.selection_set(iid)
        tree.see(iid)

    # ---- reports -------------------------------------------------------

    def _reports_shown(self):
        # Edits in the Bases tab change the spoilage list, so rebuild when the reports are opened.
        if self.notebook.select() == str(self.reports_tab):
            self.refresh_reports()

    def refresh_reports(self):
        if self.save is None:
            return
        try:
            day, month, year = reports.game_date(self.save)
            self.game_date_var.set(f"Game date: {day} {MONTH_NAMES[month - 1]} {year}")
            self.upgrades_all = reports.upgrade_rows(self.save, self.shiprecs.values(), self.ships)
        except (SaveFormatError, IndexError):
            self.game_date_var.set("Game date: unknown")
            self.upgrades_all = []
        # Whether minor places spoil is unknown, so the report stays with bases and towns.
        self.spoilage_all = reports.spoilage_rows(b for b in self.bases.values() if b.kind != "Minor")
        self.refresh_spoilage_list()
        self.refresh_upgrade_list()
        self.refresh_production_reports()
        self.refresh_lcu_reports()
        self.refresh_industry_report()
        self.refresh_factory_report()
        self.refresh_raw_list()
        self.refresh_air_reports()
        self.refresh_compare_table()
        self.refresh_losses_reports()
        self.refresh_repair_reports()
        self.refresh_minefield_reports()
        self.refresh_vp_reports()
        self.refresh_alerts()

    @staticmethod
    def _report_values(columns, texts, row):
        return [texts[cid](get(row)) if cid in texts else get(row) for cid, _h, _w, _n, get in columns]

    def _spoilage_sort_key(self, r):
        if self.spoilage_sort_col == "total":
            return (r.total_over, r.base.name.lower(), r.base.id)
        _cid, _h, _w, numeric, get = SPOILAGE_COLUMN_BY_ID[self.spoilage_sort_col]
        v = get(r)
        return (v if numeric else str(v).lower(), r.base.id)

    def refresh_spoilage_list(self):
        self.spoilage_tree.delete(*self.spoilage_tree.get_children())
        side = self.spoilage_side_var.get()
        rows = [r for r in self.spoilage_all if side == "All" or r.base.side == side]
        rows.sort(key=self._spoilage_sort_key, reverse=self.spoilage_sort_reverse)
        for r in rows:
            self.spoilage_tree.insert("", "end", iid=str(r.base.id),
                                      values=self._report_values(SPOILAGE_COLUMNS, SPOILAGE_TEXT, r))
        self.spoilage_count.set(f"{len(rows)} base{'' if len(rows) == 1 else 's'} over a limit")

    def sort_spoilage_by(self, col):
        self.spoilage_sort_reverse = (not self.spoilage_sort_reverse) if col == self.spoilage_sort_col else False
        self.spoilage_sort_col = col
        self.refresh_spoilage_list()

    def _upgrade_sort_key(self, r):
        _cid, _h, _w, numeric, get = UPGRADE_COLUMN_BY_ID[self.upgrade_sort_col]
        v = get(r)
        return (v if numeric else str(v).lower(), r.months, r.ship.name.lower(), r.ship.id)

    def refresh_upgrade_list(self):
        self.upgrade_tree.delete(*self.upgrade_tree.get_children())
        needle = self.upgrade_search_var.get().strip().lower()
        side = self.upgrade_side_var.get()
        within = UPGRADE_DUE[self.upgrade_due_var.get()]
        rows = [r for r in self.upgrades_all
                if (needle in r.ship.name.lower() or needle in r.current.name.lower())
                and (side == "All" or r.ship.side == side) and (within is None or r.months <= within)]
        rows.sort(key=self._upgrade_sort_key, reverse=self.upgrade_sort_reverse)
        for r in rows:
            self.upgrade_tree.insert("", "end", iid=str(r.ship.id),
                                     values=self._report_values(UPGRADE_COLUMNS, UPGRADE_TEXT, r))
        self.upgrade_count.set(f"{len(rows)} ship{'' if len(rows) == 1 else 's'}")

    def sort_upgrades_by(self, col):
        self.upgrade_sort_reverse = (not self.upgrade_sort_reverse) if col == self.upgrade_sort_col else False
        self.upgrade_sort_col = col
        self.refresh_upgrade_list()

    def refresh_production_reports(self):
        """Recompute the rows and the yard summary from the save; the filters only re-select from the rows."""
        try:
            self.production_all = shipproduction.production_rows(self.save, self.shiprecs.values(), self.ships)
            self.production_summary = shipproduction.summary_rows(self.save, self.production_all,
                                                                  self.industry_places)
        except (SaveFormatError, IndexError):
            self.production_all, self.production_summary = [], []
        self.production_summary_tree.delete(*self.production_summary_tree.get_children())
        for r in self.production_summary:
            self.production_summary_tree.insert("", "end", iid=r.yard, values=self._report_values(
                PRODUCTION_SUMMARY_COLUMNS, PRODUCTION_SUMMARY_TEXT, r))
        types = sorted({r.type for r in self.production_all})
        self.production_type_box.configure(values=[PRODUCTION_ALL, *types])
        if self.production_type_var.get() not in types:
            self.production_type_var.set(PRODUCTION_ALL)
        self.refresh_production_list()

    def refresh_production_list(self):
        self.production_tree.delete(*self.production_tree.get_children())
        needle = self.production_search_var.get().strip().lower()
        yard, status, type_ = (v.get() for v in (self.production_yard_var, self.production_status_var,
                                                 self.production_type_var))
        rows = [r for r in self.production_all
                if (needle in r.ship.name.lower() or needle in r.current.name.lower())
                and yard in (PRODUCTION_ALL, r.yard) and status in (PRODUCTION_ALL, r.status)
                and type_ in (PRODUCTION_ALL, r.type)]
        rows.sort(key=lambda r: self._industry_sort_key(PRODUCTION_COLUMN_BY_ID, self.production_sort_col, r,
                                                        r.ship.id),
                  reverse=self.production_sort_reverse)
        for r in rows:
            self.production_tree.insert("", "end", iid=str(r.ship.id),
                                        values=self._report_values(PRODUCTION_COLUMNS, PRODUCTION_TEXT, r))
        self.production_count.set(f"{len(rows)} ship{'' if len(rows) == 1 else 's'}")

    def sort_production_by(self, col):
        self.production_sort_reverse = (not self.production_sort_reverse) if col == self.production_sort_col else False
        self.production_sort_col = col
        self.refresh_production_list()

    def refresh_lcu_reports(self):
        """Recompute the rows and the summary from the save; the view, status and search only re-select."""
        side, window = self.lcu_side_var.get(), LCU_WINDOWS[self.lcu_window_var.get()]
        units = list(self.units.values())
        try:
            self.lcu_unit_all = lcuproduction.unit_rows(self.save, side, window, units)
            self.lcu_device_all = lcuproduction.device_rows(self.save, side, window, units)
            self.lcu_summary = lcuproduction.summary_rows(self.save, self.lcu_unit_all, self.industry_places, side)
        except (SaveFormatError, IndexError):
            self.lcu_unit_all, self.lcu_device_all, self.lcu_summary = [], [], []
        self.lcu_summary_tree.delete(*self.lcu_summary_tree.get_children())
        for r in self.lcu_summary:
            self.lcu_summary_tree.insert("", "end", iid=r.kind, values=self._report_values(
                LCU_SUMMARY_COLUMNS, LCU_SUMMARY_TEXT, r))
        self.refresh_lcu_list()

    def refresh_lcu_list(self):
        needle = self.lcu_search_var.get().strip().lower()
        if self.lcu_view_var.get() == LCU_VIEWS[0]:
            status = self.lcu_status_var.get()
            rows = [r for r in self.lcu_unit_all if needle in r.unit.display_name.lower()
                    and status in (LCU_ALL, r.status)]
            rows.sort(key=lambda r: self._industry_sort_key(LCU_UNIT_COLUMN_BY_ID, self.lcu_unit_sort_col, r,
                                                            r.unit.id), reverse=self.lcu_unit_sort_reverse)
            tree, columns, texts, noun = self.lcu_unit_tree, LCU_UNIT_COLUMNS, LCU_UNIT_TEXT, "unit"
            ids = [str(r.unit.id) for r in rows]
        else:
            rows = [r for r in self.lcu_device_all if needle in r.name.lower()]
            rows.sort(key=lambda r: self._industry_sort_key(LCU_DEVICE_COLUMN_BY_ID, self.lcu_device_sort_col, r,
                                                            r.id), reverse=self.lcu_device_sort_reverse)
            tree, columns, texts, noun = self.lcu_device_tree, LCU_DEVICE_COLUMNS, LCU_DEVICE_TEXT, "device"
            ids = [str(r.id) for r in rows]
        tree.delete(*tree.get_children())
        for iid, r in zip(ids, rows):
            tree.insert("", "end", iid=iid, values=self._report_values(columns, texts, r))
        self.lcu_count.set(f"{len(rows)} {noun}{'' if len(rows) == 1 else 's'}")

    def sort_lcu_units_by(self, col):
        self.lcu_unit_sort_reverse = (not self.lcu_unit_sort_reverse) if col == self.lcu_unit_sort_col else False
        self.lcu_unit_sort_col = col
        self.refresh_lcu_list()

    def sort_lcu_devices_by(self, col):
        self.lcu_device_sort_reverse = (not self.lcu_device_sort_reverse) if col == self.lcu_device_sort_col else False
        self.lcu_device_sort_col = col
        self.refresh_lcu_list()

    def jump_to_lcu_unit(self):
        sel = self.lcu_unit_tree.selection()
        if not sel:
            return
        iid = sel[0]
        if not self.unit_tree.exists(iid):
            self.unit_search_var.set("")
            self.unit_side_var.set("All")
            self.refresh_unit_list()
        self.notebook.select(self.units_tab)
        self.unit_tree.selection_set(iid)
        self.unit_tree.see(iid)

    def refresh_losses_reports(self):
        """Recompute the rows and the summary from the save; the side, view and search only re-select."""
        try:
            self.losses_sunk_all = losses.sunk_ships(self.save)
            self.losses_aircraft_all = losses.aircraft_losses(self.save)
            self.losses_summary = losses.summary_rows(self.losses_sunk_all, self.losses_aircraft_all)
        except (SaveFormatError, IndexError):
            self.losses_sunk_all, self.losses_aircraft_all, self.losses_summary = [], [], []
        self.losses_summary_tree.delete(*self.losses_summary_tree.get_children())
        for r in self.losses_summary:
            self.losses_summary_tree.insert("", "end", iid=r.side, values=self._report_values(
                LOSSES_SUMMARY_COLUMNS, LOSSES_SUMMARY_TEXT, r))
        self.refresh_losses_list()

    def refresh_losses_list(self):
        needle = self.losses_search_var.get().strip().lower()
        side = self.losses_side_var.get()
        if self.losses_view_var.get() == LOSSES_VIEWS[0]:
            rows = [r for r in self.losses_sunk_all if side in (LOSSES_ALL, r.side)
                    and (needle in r.name.lower() or needle in r.class_name.lower())]
            rows.sort(key=lambda r: self._industry_sort_key(LOSSES_SUNK_COLUMN_BY_ID, self.losses_sunk_sort_col, r,
                                                            r.id), reverse=self.losses_sunk_sort_reverse)
            tree, columns, texts, noun = self.losses_sunk_tree, LOSSES_SUNK_COLUMNS, LOSSES_SUNK_TEXT, "ship"
        else:
            rows = [r for r in self.losses_aircraft_all if side in (LOSSES_ALL, r.side) and needle in r.name.lower()]
            rows.sort(key=lambda r: self._industry_sort_key(LOSSES_AIRCRAFT_COLUMN_BY_ID,
                                                            self.losses_aircraft_sort_col, r, r.id),
                      reverse=self.losses_aircraft_sort_reverse)
            tree, columns, texts, noun = (self.losses_aircraft_tree, LOSSES_AIRCRAFT_COLUMNS, LOSSES_AIRCRAFT_TEXT,
                                          "model")
        tree.delete(*tree.get_children())
        for r in rows:
            tree.insert("", "end", iid=str(r.id), values=self._report_values(columns, texts, r))
        self.losses_count.set(f"{len(rows)} {noun}{'' if len(rows) == 1 else 's'}")

    def sort_losses_sunk_by(self, col):
        same = col == self.losses_sunk_sort_col
        self.losses_sunk_sort_reverse = (not self.losses_sunk_sort_reverse) if same else False
        self.losses_sunk_sort_col = col
        self.refresh_losses_list()

    def sort_losses_aircraft_by(self, col):
        same = col == self.losses_aircraft_sort_col
        self.losses_aircraft_sort_reverse = (not self.losses_aircraft_sort_reverse) if same else False
        self.losses_aircraft_sort_col = col
        self.refresh_losses_list()

    def jump_to_losses_ship(self):
        self._jump_to_ship(self.losses_sunk_tree)

    def refresh_repair_reports(self):
        """Recompute the rows and the summary from the save; the side, view and search only re-select."""
        try:
            self.repair_ships_all = shiprepair.damaged_ships(self.save)
            self.repair_ports_all = shiprepair.repair_ports(self.save, self.repair_ships_all)
            self.repair_summary = shiprepair.summary_rows(self.repair_ships_all)
        except (SaveFormatError, IndexError):
            self.repair_ships_all, self.repair_ports_all, self.repair_summary = [], [], []
        self.repair_summary_tree.delete(*self.repair_summary_tree.get_children())
        for r in self.repair_summary:
            self.repair_summary_tree.insert("", "end", iid=r.side, values=self._report_values(
                REPAIR_SUMMARY_COLUMNS, REPAIR_SUMMARY_TEXT, r))
        self.refresh_repair_list()

    def refresh_repair_list(self):
        needle = self.repair_search_var.get().strip().lower()
        side = self.repair_side_var.get()
        if self.repair_view_var.get() == REPAIR_VIEWS[0]:
            rows = [r for r in self.repair_ships_all if side in (REPAIR_ALL, r.side)
                    and (needle in r.name.lower() or needle in r.class_name.lower()
                         or needle in r.location.lower())]
            rows.sort(key=lambda r: self._industry_sort_key(REPAIR_SHIP_COLUMN_BY_ID, self.repair_ship_sort_col, r,
                                                            r.id), reverse=self.repair_ship_sort_reverse)
            tree, columns, texts, noun = self.repair_ship_tree, REPAIR_SHIP_COLUMNS, REPAIR_SHIP_TEXT, "ship"
        else:
            rows = [r for r in self.repair_ports_all if side in (REPAIR_ALL, r.side) and needle in r.name.lower()]
            rows.sort(key=lambda r: self._industry_sort_key(REPAIR_PORT_COLUMN_BY_ID, self.repair_port_sort_col, r,
                                                            r.id), reverse=self.repair_port_sort_reverse)
            tree, columns, texts, noun = self.repair_port_tree, REPAIR_PORT_COLUMNS, REPAIR_PORT_TEXT, "port"
        tree.delete(*tree.get_children())
        for r in rows:
            tree.insert("", "end", iid=str(r.id), values=self._report_values(columns, texts, r))
        self.repair_count.set(f"{len(rows)} {noun}{'' if len(rows) == 1 else 's'}")

    def sort_repair_ships_by(self, col):
        same = col == self.repair_ship_sort_col
        self.repair_ship_sort_reverse = (not self.repair_ship_sort_reverse) if same else False
        self.repair_ship_sort_col = col
        self.refresh_repair_list()

    def sort_repair_ports_by(self, col):
        same = col == self.repair_port_sort_col
        self.repair_port_sort_reverse = (not self.repair_port_sort_reverse) if same else False
        self.repair_port_sort_col = col
        self.refresh_repair_list()

    def jump_to_repair_ship(self):
        self._jump_to_ship(self.repair_ship_tree)

    def jump_to_repair_port(self):
        self.jump_to_industry_place(self.repair_port_tree)

    def refresh_minefield_reports(self):
        """Recompute the rows and the summary from the save; the side, view and search only re-select."""
        try:
            self.minefield_fields_all = minefields.list_fields(self.save)
            self.minefield_hexes_all = minefields.hex_rows(self.save, self.minefield_fields_all)
            self.minefield_summary = minefields.summary_rows(self.minefield_fields_all, self.minefield_hexes_all)
        except (SaveFormatError, IndexError):
            self.minefield_fields_all, self.minefield_hexes_all, self.minefield_summary = [], [], []
        tree = self.minefield_summary_tree
        tree.delete(*tree.get_children())
        for r in self.minefield_summary:
            tree.insert("", "end", iid=r.side, values=self._report_values(MINE_SUMMARY_COLUMNS, MINE_SUMMARY_TEXT, r))
        self.refresh_minefield_list()

    def refresh_minefield_list(self):
        # Row ids are "<place id>:<key>" so jump_to_industry_place can read the place; "-" marks open sea.
        needle = self.minefield_search_var.get().strip().lower()
        side = self.minefield_side_var.get()
        if self.minefield_view_var.get() == MINE_VIEWS[0]:
            rows = [r for r in self.minefield_hexes_all if side in (MINE_ALL, r.side)
                    and (needle in r.place.lower() or needle in r.types.lower())]
            rows.sort(key=lambda r: self._industry_sort_key(MINE_HEX_COLUMN_BY_ID, self.minefield_hex_sort_col, r,
                                                            (r.x, r.y, r.side)),
                      reverse=self.minefield_hex_sort_reverse)
            tree, columns, texts = self.minefield_hex_tree, MINE_HEX_COLUMNS, MINE_HEX_TEXT
            ids = [f"{'-' if r.place_id is None else r.place_id}:{r.x},{r.y},{r.side}" for r in rows]
            noun, plural = "hex", "hexes"
        else:
            rows = [r for r in self.minefield_fields_all if side in (MINE_ALL, r.side)
                    and (needle in (r.place_name or "").lower() or needle in r.device_name.lower())]
            rows.sort(key=lambda r: self._industry_sort_key(MINE_FIELD_COLUMN_BY_ID, self.minefield_field_sort_col,
                                                            r, r.id), reverse=self.minefield_field_sort_reverse)
            tree, columns, texts = self.minefield_field_tree, MINE_FIELD_COLUMNS, MINE_FIELD_TEXT
            ids = [f"{'-' if r.place_id is None else r.place_id}:{r.id}" for r in rows]
            noun, plural = "field", "fields"
        tree.delete(*tree.get_children())
        for iid, r in zip(ids, rows):
            tree.insert("", "end", iid=iid, values=self._report_values(columns, texts, r))
        self.minefield_count.set(f"{len(rows)} {noun if len(rows) == 1 else plural}")

    def sort_minefield_hexes_by(self, col):
        same = col == self.minefield_hex_sort_col
        self.minefield_hex_sort_reverse = (not self.minefield_hex_sort_reverse) if same else False
        self.minefield_hex_sort_col = col
        self.refresh_minefield_list()

    def sort_minefield_fields_by(self, col):
        same = col == self.minefield_field_sort_col
        self.minefield_field_sort_reverse = (not self.minefield_field_sort_reverse) if same else False
        self.minefield_field_sort_col = col
        self.refresh_minefield_list()

    def jump_to_minefield_place(self):
        hexes = self.minefield_view_var.get() == MINE_VIEWS[0]
        tree = self.minefield_hex_tree if hexes else self.minefield_field_tree
        sel = tree.selection()
        if sel and not sel[0].startswith("-"):  # open-sea rows have no place to jump to
            self.jump_to_industry_place(tree)

    def refresh_vp_reports(self):
        """Recompute the scores and the base rows from the save; the side and search only re-select."""
        try:
            self.vp_summary = victory.scores(self.save)
            self.vp_bases_all = victory.base_rows(self.save)
        except (SaveFormatError, IndexError):
            self.vp_summary, self.vp_bases_all = [], []
        try:
            level, automatic = victory.status_lines(self.save, self.vp_summary or None)
            self.vp_status.set(f"{level}. {automatic}.")
        except (SaveFormatError, IndexError):
            self.vp_status.set("")
        tree = self.vp_summary_tree
        tree.delete(*tree.get_children())
        for r in self.vp_summary:
            tree.insert("", "end", iid=r.side, values=self._report_values(VP_SUMMARY_COLUMNS, VP_SUMMARY_TEXT, r))
        self.refresh_vp_list()

    def refresh_vp_list(self):
        needle = self.vp_search_var.get().strip().lower()
        side = self.vp_side_var.get()
        rows = [r for r in self.vp_bases_all if side in (VP_ALL, r.side)
                and (needle in r.name.lower() or needle in r.region.lower())]
        rows.sort(key=lambda r: self._industry_sort_key(VP_BASE_COLUMN_BY_ID, self.vp_sort_col, r, r.id),
                  reverse=self.vp_sort_reverse)
        tree = self.vp_tree
        tree.delete(*tree.get_children())
        for r in rows:
            tree.insert("", "end", iid=str(r.id), values=self._report_values(VP_BASE_COLUMNS, VP_BASE_TEXT, r))
        self.vp_count.set(f"{len(rows)} base{'' if len(rows) == 1 else 's'}")

    def sort_vp_by(self, col):
        self.vp_sort_reverse = (not self.vp_sort_reverse) if col == self.vp_sort_col else False
        self.vp_sort_col = col
        self.refresh_vp_list()

    def jump_to_vp_base(self):
        self.jump_to_industry_place(self.vp_tree)

    def _alert_thresholds(self):
        """(supply %, pilot pool) from the spinboxes; text that is not a number falls back to the defaults."""
        out = []
        for var, key in ((self.alert_supply_var, "supply_pct"), (self.alert_pool_var, "pilot_pool")):
            try:
                out.append(int(var.get().strip()))
            except ValueError:
                out.append(alerts.DEFAULTS[key])
        return out

    def refresh_alerts(self):
        """Recompute the alerts from the save; the filters, search and sort only re-select from the result."""
        if self.save is None:
            return
        supply_pct, pilot_pool = self._alert_thresholds()
        self.alerts_all, self.alerts_skipped = alerts.collect(
            self.save, supply_pct, pilot_pool, self.industry_places, list(self.groups.values()))
        self.refresh_alert_list()

    def refresh_alert_list(self):
        needle = self.alert_search_var.get().strip().lower()
        side = self.alert_side_var.get()
        category = self.alert_category_var.get()
        rows = [(k, a) for k, a in enumerate(self.alerts_all)
                if side in (ALERT_ALL, a.side) and category in (ALERT_ALL, a.category)
                and (needle in a.subject.lower() or needle in a.detail.lower())]
        if self.alert_sort_col is not None:
            get = ALERT_COLUMN_BY_ID[self.alert_sort_col][4]
            rows.sort(key=lambda t: (str(get(t[1])).lower(), t[0]), reverse=self.alert_sort_reverse)
        tree = self.alert_tree
        tree.delete(*tree.get_children())
        self.alerts_by_iid = {}
        for k, a in rows:
            self.alerts_by_iid[str(k)] = a
            tree.insert("", "end", iid=str(k), values=self._report_values(ALERT_COLUMNS, {}, a))
        text = f"{len(rows)} alert{'' if len(rows) == 1 else 's'}"
        if self.alerts_skipped:
            text += f" (skipped: {', '.join(self.alerts_skipped)})"
        self.alert_count.set(text)

    def sort_alerts_by(self, col):
        self.alert_sort_reverse = (not self.alert_sort_reverse) if col == self.alert_sort_col else False
        self.alert_sort_col = col
        self.refresh_alert_list()

    def open_alert(self):
        """Double-click: open the alert's base, ship, pilot pool, aircraft, engine or minefields where it is edited or listed."""
        sel = self.alert_tree.selection()
        alert = self.alerts_by_iid.get(sel[0]) if sel else None
        if alert is None:
            return
        target = str(alert.target_id)
        if alert.kind == "base":
            self.jump_to_industry_place(self.alert_tree, target)
        elif alert.kind == "ship":
            self._jump_to_ship(self.alert_tree, target)
        elif alert.kind == "pilots":
            if alert.target_id not in self.pools:
                return
            self.pool_side_var.set("All")
            self.refresh_pool_list()
            self.notebook.select(self.groups_tab)
            self.groups_notebook.select(self.pool_page)
            self.pool_tree.selection_set(target)
            self.pool_tree.see(target)
        elif alert.kind == "aircraft":
            if alert.target_id not in self.aircraft:
                return
            if not self.aircraft_tree.exists(target):
                self.aircraft_search_var.set("")
                self.refresh_aircraft_list()
            self.notebook.select(self.aircraft_tab)
            self.aircraft_tree.selection_set(target)
            self.aircraft_tree.see(target)
        elif alert.kind == "minefields":
            self.reports_notebook.select(self.minefield_frame)
            self.minefield_side_var.set(alert.target_id)
            self.minefield_view_var.set(MINE_VIEWS[0])
            self._show_minefield_view()
        elif alert.kind == "engine":
            # An engine is a device, not an aircraft; the Engines report is the nearest place that lists it.
            self.reports_notebook.select(self.engine_frame)
            if self.engine_tree.exists(target):
                self.engine_tree.selection_set(target)
                self.engine_tree.see(target)

    def _industry_places_for(self, side_var, region_var):
        side = side_var.get()
        return industry.filter_places(self.industry_places, None if side == "All" else side,
                                      self.region_ids[region_var.get()])

    def refresh_industry_report(self):
        side_id = {name: sid for sid, name in bases.SIDES.items()}[self.industry_side_var.get()]
        try:
            pools = industry.side_pools(self.save)[side_id]
        except SaveFormatError:
            pools = None
        type_rows, balance = industry.summarize(
            self._industry_places_for(self.industry_side_var, self.industry_region_var), pools,
            self.region_ids[self.industry_region_var.get()] is not None)
        for tree, columns, texts, rows, key in (
                (self.industry_tree, INDUSTRY_COLUMNS, INDUSTRY_TEXT, type_rows, lambda r: r.group),
                (self.balance_tree, BALANCE_COLUMNS, BALANCE_TEXT, balance, lambda r: r.material)):
            tree.delete(*tree.get_children())
            for r in rows:
                tree.insert("", "end", iid=key(r), values=self._report_values(columns, texts, r))

    @staticmethod
    def _industry_sort_key(columns, col, r, tie):
        _cid, _h, _w, numeric, get = columns[col]
        v = get(r)
        return (v if numeric else str(v).lower(), tie)

    def refresh_factory_report(self):
        self.factory_report_tree.delete(*self.factory_report_tree.get_children())
        rows = industry.factory_rows(self._industry_places_for(self.factory_report_side_var,
                                                               self.factory_report_region_var))
        group = self.factory_report_type_var.get()
        if group != FACTORY_TYPE_ALL:
            rows = [r for r in rows if r.group == group]
        if self.factory_report_problem_var.get():
            rows = [r for r in rows if r.factory.damage > 0 or not r.factory.production_on or not r.factory.repair_on]
        rows.sort(key=lambda r: self._industry_sort_key(FACTORY_COLUMN_BY_ID, self.factory_report_sort_col, r,
                                                        (r.place.id, r.factory.slot)),
                  reverse=self.factory_report_sort_reverse)
        for r in rows:
            self.factory_report_tree.insert("", "end", iid=f"{r.place.id}:{r.factory.slot}",
                                     values=self._report_values(FACTORY_COLUMNS, {}, r))
        self.factory_report_count.set(f"{len(rows)} factor{'y' if len(rows) == 1 else 'ies'}")

    def sort_factory_report_by(self, col):
        same = col == self.factory_report_sort_col
        self.factory_report_sort_reverse = (not self.factory_report_sort_reverse) if same else False
        self.factory_report_sort_col = col
        self.refresh_factory_report()

    def refresh_raw_list(self):
        self.raw_tree.delete(*self.raw_tree.get_children())
        rows = industry.raw_rows(self._industry_places_for(self.raw_side_var, self.raw_region_var),
                                 self.raw_only_var.get())
        rows.sort(key=lambda r: self._industry_sort_key(RAW_COLUMN_BY_ID, self.raw_sort_col, r,
                                                        (r.place.name.lower(), r.place.id)),
                  reverse=self.raw_sort_reverse)
        for r in rows:
            self.raw_tree.insert("", "end", iid=str(r.place.id), values=self._report_values(RAW_COLUMNS, RAW_TEXT, r))
        self.raw_count.set(f"{len(rows)} place{'' if len(rows) == 1 else 's'}")

    def sort_raw_by(self, col):
        self.raw_sort_reverse = (not self.raw_sort_reverse) if col == self.raw_sort_col else False
        self.raw_sort_col = col
        self.refresh_raw_list()

    def refresh_air_reports(self):
        """Recompute both air production tables from the save; the filters only re-select from the result."""
        self.air_entries = airproduction.plant_entries(self.industry_places)
        try:
            self.air_rows_all = airproduction.air_rows(self.save, self.air_entries, self.groups.values())
            self.engine_rows_all = airproduction.engine_rows(self.save, self.air_entries)
        except SaveFormatError:
            self.air_rows_all = self.engine_rows_all = []
        self.refresh_air_list()
        self.refresh_engine_list()

    def refresh_air_list(self):
        selected = self.air_tree.selection()
        self.air_tree.delete(*self.air_tree.get_children())
        needle = self.air_search_var.get().strip().lower()
        side = self.air_side_var.get()
        rows = [r for r in self.air_rows_all
                if needle in r.name.lower() and (side == "All" or r.side == side) and (r.active or not self.air_only_var.get())]
        rows.sort(key=lambda r: self._industry_sort_key(AIR_COLUMN_BY_ID, self.air_sort_col, r, r.id),
                  reverse=self.air_sort_reverse)
        for r in rows:
            self.air_tree.insert("", "end", iid=str(r.id), values=self._report_values(AIR_COLUMNS, AIR_TEXT, r))
        if selected and self.air_tree.exists(selected[0]):
            self.air_tree.selection_set(selected[0])
        self.air_count.set(f"{len(rows)} model{'' if len(rows) == 1 else 's'}")
        self.refresh_air_factories()

    def sort_air_by(self, col):
        self.air_sort_reverse = (not self.air_sort_reverse) if col == self.air_sort_col else False
        self.air_sort_col = col
        self.refresh_air_list()

    def refresh_air_factories(self):
        self.air_factory_tree.delete(*self.air_factory_tree.get_children())
        sel = self.air_tree.selection()
        if not sel:
            return
        for e in airproduction.model_entries(self.air_entries, int(sel[0])):
            self.air_factory_tree.insert("", "end", iid=f"{e.place.id}:{e.factory.slot}",
                                         values=self._report_values(AIR_FACTORY_COLUMNS, {}, e))

    def apply_air_switch(self, label, production, repair):
        """Set the production and/or repair switch of every factory building the selected model."""
        sel = self.air_tree.selection()
        if not sel:
            self.status.set(f"{label}: select a model first")
            return
        changed, unchanged, failed = airproduction.set_switches(self.air_entries, int(sel[0]), production, repair)
        for e in changed:
            self.edited.add(e.place.id)
        if changed:
            self.dirty = True
        text = f"{label}: {len(changed)} of {len(changed) + unchanged + len(failed)} factories changed"
        if failed:
            text += f"; {len(failed)} refused ({failed[0][1]})"
        self.status.set(text + (" (not yet saved)" if changed else ""))
        self.refresh_list()
        if self.current is not None:
            self.show_factories(self.bases[self.current])
        self.refresh_air_reports()

    def refresh_engine_list(self):
        selected = self.engine_tree.selection()
        self.engine_tree.delete(*self.engine_tree.get_children())
        rows = sorted(self.engine_rows_all,
                      key=lambda r: self._industry_sort_key(ENGINE_COLUMN_BY_ID, self.engine_sort_col, r, r.id),
                      reverse=self.engine_sort_reverse)
        for r in rows:
            self.engine_tree.insert("", "end", iid=str(r.id), values=self._report_values(ENGINE_COLUMNS, ENGINE_TEXT, r))
        if selected and self.engine_tree.exists(selected[0]):
            self.engine_tree.selection_set(selected[0])
        self.engine_count.set(f"{len(rows)} engine{'' if len(rows) == 1 else 's'}")

    def sort_engines_by(self, col):
        self.engine_sort_reverse = (not self.engine_sort_reverse) if col == self.engine_sort_col else False
        self.engine_sort_col = col
        self.refresh_engine_list()

    def jump_to_industry_place(self, report_tree, iid=None):
        sel = report_tree.selection()
        if not sel:
            return
        place_id = int((iid or sel[0]).split(":")[0])
        if place_id not in self.bases:
            return
        iid = str(place_id)
        if not self.tree.exists(iid):
            self.search_var.set("")
            self.side_var.set("All")
            self.refresh_list()
        self.notebook.select(self.bases_tab)
        self.tree.selection_set(iid)
        self.tree.see(iid)

    def jump_to_spoilage_base(self):
        sel = self.spoilage_tree.selection()
        if not sel:
            return
        iid = sel[0]
        if not self.tree.exists(iid):
            self.search_var.set("")
            self.side_var.set("All")
            self.refresh_list()
        self.notebook.select(self.bases_tab)
        self.tree.selection_set(iid)
        self.tree.see(iid)

    def jump_to_upgrade_ship(self):
        self._jump_to_ship(self.upgrade_tree)

    def jump_to_production_ship(self):
        self._jump_to_ship(self.production_tree)

    def _jump_to_ship(self, report_tree, iid=None):
        sel = report_tree.selection()
        if not sel:
            return
        iid = iid or sel[0]
        if not self.shiprec_tree.exists(iid):
            self.shiprec_search_var.set("")
            self.shiprec_side_var.set("All")
            self.refresh_shiprec_list()
        self.notebook.select(self.shiprec_tab)
        self.shiprec_tree.selection_set(iid)
        self.shiprec_tree.see(iid)

    # ---- history -------------------------------------------------------

    history_root = None  # replaces <save folder>/history; the tests set it so they never write next to the saves

    def _build_history_tab(self):
        tab = self.history_tab = ttk.Frame(self.notebook, padding=4)
        self.notebook.add(tab, text="History")
        self.history_info = tk.StringVar(value="Open a save to see its history")
        ttk.Label(tab, textvariable=self.history_info).pack(side="top", anchor="w")
        self.history_status = tk.StringVar()
        ttk.Label(tab, textvariable=self.history_status, wraplength=1100, justify="left").pack(side="top", anchor="w")
        bar = ttk.Frame(tab)
        bar.pack(side="top", fill="x", pady=(4, 0))
        ttk.Button(bar, text="Import saves...", command=self.import_history).pack(side="left", padx=2)
        self.history_record_btn = ttk.Button(bar, text="Record this save", command=self.record_this_save,
                                             state="disabled")
        self.history_record_btn.pack(side="left", padx=2)
        self.history_delete_btn = ttk.Button(bar, text="Delete turn", command=self.delete_history_turn)
        self.history_delete_btn.pack(side="left", padx=2)
        view_bar = ttk.Frame(tab)
        view_bar.pack(side="top", fill="x", pady=(4, 0))
        self.history_view_var = tk.StringVar(value=HISTORY_VIEWS[0])
        for view in HISTORY_VIEWS:
            ttk.Radiobutton(view_bar, text=view, value=view, variable=self.history_view_var,
                            command=self._show_history_view).pack(side="left", padx=2)
        self.history_sides_bar = ttk.Frame(view_bar)
        self.history_metric_var = tk.StringVar(value=history.SIDE_METRICS["supply"])
        self._report_combo(self.history_sides_bar, "Metric:", self.history_metric_var,
                           history.SIDE_METRICS.values(), self.refresh_history_view, 34)
        self.history_side_var = tk.StringVar(value=HISTORY_BOTH)
        self._report_combo(self.history_sides_bar, "Side:", self.history_side_var,
                           [HISTORY_BOTH, "Allied", "Japanese"], self.refresh_history_view, 9)
        self.history_base_bar = ttk.Frame(view_bar)
        ttk.Label(self.history_base_bar, text="Base filter:").pack(side="left")
        self.history_filter_var = tk.StringVar()
        self.history_filter_var.trace_add("write", lambda *a: self.show_history_base_choices())
        ttk.Entry(self.history_base_bar, textvariable=self.history_filter_var, width=16).pack(side="left", padx=4)
        self.history_base_var = tk.StringVar()
        self.history_base_box = self._report_combo(self.history_base_bar, "Base:", self.history_base_var, [],
                                                   self.refresh_history_view, 28)
        self.history_base_metric_var = tk.StringVar(value=history.BASE_METRICS["supply"])
        self._report_combo(self.history_base_bar, "Metric:", self.history_base_metric_var,
                           history.BASE_METRICS.values(), self.refresh_history_view, 11)
        self.history_aircraft_bar = ttk.Frame(view_bar)
        ttk.Label(self.history_aircraft_bar, text="Aircraft filter:").pack(side="left")
        self.history_aircraft_filter_var = tk.StringVar()
        self.history_aircraft_filter_var.trace_add("write", lambda *a: self.show_history_aircraft_choices())
        ttk.Entry(self.history_aircraft_bar, textvariable=self.history_aircraft_filter_var, width=16).pack(
            side="left", padx=4)
        self.history_aircraft_var = tk.StringVar()
        self.history_aircraft_box = self._report_combo(self.history_aircraft_bar, "Aircraft:",
                                                       self.history_aircraft_var, [], self.refresh_history_view, 30)
        self.history_aircraft_metric_var = tk.StringVar(value=history.AIRCRAFT_METRICS["pool"])
        self._report_combo(self.history_aircraft_bar, "Metric:", self.history_aircraft_metric_var,
                           history.AIRCRAFT_METRICS.values(), self.refresh_history_view, 18)
        self.history_chart = chart.LineChart(tab)
        self.history_chart.pack(side="top", fill="both", expand=True, pady=(4, 0))
        table = ttk.Frame(tab)
        table.pack(side="top", fill="both", expand=True, pady=(4, 0))
        self.history_tree = self._report_tree(table, HISTORY_COLUMNS, lambda c: None, ("date", "side"), lambda: None)
        self.history_tree.configure(height=8)
        self._show_history_view()

    def _show_history_view(self):
        bars = dict(zip(HISTORY_VIEWS, (self.history_sides_bar, self.history_base_bar, self.history_aircraft_bar)))
        for view, bar in bars.items():
            bar.pack_forget()
        bars[self.history_view_var.get()].pack(side="left", padx=(12, 0))
        self.refresh_history_view()

    def show_history_base_choices(self):
        """Fill the base picker with the recorded bases whose label contains the filter text."""
        needle = self.history_filter_var.get().strip().lower()
        self.history_base_box.configure(values=[l for l in self.history_choices if needle in l.lower()])

    def show_history_aircraft_choices(self):
        needle = self.history_aircraft_filter_var.get().strip().lower()
        self.history_aircraft_box.configure(
            values=[l for l in self.history_aircraft_choices if needle in l.lower()])

    def _set_history_choices(self, extra=None, extra_aircraft=None):
        names = {b.id: b.name for b in self.bases.values()}
        items = history.base_choices(self.history_snaps, names)
        if extra is not None and extra not in [i for _l, i in items]:
            items.append((f"{names[extra]} ({extra})" if extra in names else f"#{extra}", extra))
        self.history_choices = dict(items)
        self.show_history_base_choices()
        planes = history.aircraft_choices(self.history_snaps, {a.id: a.name for a in self.aircraft.values()})
        if extra_aircraft is not None and extra_aircraft not in [i for _l, i in planes]:
            a = self.aircraft.get(extra_aircraft)
            side = bases.SIDES.get(a.side_id, "?") if a else "?"
            planes.append((f"{a.name} ({side})" if a else f"#{extra_aircraft} ({side})", extra_aircraft))
        self.history_aircraft_choices = dict(planes)
        self.show_history_aircraft_choices()

    def load_history_view(self):
        """Read the history folder of the open save and redraw."""
        if self.save is None:
            return
        self.history_dir = history.campaign_dir(self.save, self.path, self.history_root)
        self.history_snaps, self.history_problems = history.load_history(self.history_dir)
        self._set_history_choices()
        if self.history_base_var.get() not in self.history_choices:
            self.history_base_var.set(next(iter(self.history_choices), ""))
        if self.history_aircraft_var.get() not in self.history_aircraft_choices:
            self.history_aircraft_var.set(next(iter(self.history_aircraft_choices), ""))
        self.history_info.set(f"Campaign: {history.slug(history.scenario_name(self.save))}    "
                              f"Folder: {self.history_dir}    Turns recorded: {len(self.history_snaps)}")
        self.refresh_history_view()

    def _history_status(self, text):
        problems = "".join(f"  Skipped {name}: {why}." for name, why in self.history_problems)
        self.history_status.set(text + problems)

    def record_history(self, replace=False):
        """Record the open save (see witpae.history.record); failures go to the History tab's status line."""
        if self.save is None:
            return
        self.history_kept = None
        try:
            if replace:
                # The file as it is on disk, not the edited copy in memory.
                result = history.record(SaveFile.load(self.path), self.path, True, self.history_root)
            else:
                result = history.record(self.save, self.path, False, self.history_root,
                                        getattr(self, "industry_places", None))
        except (OSError, SaveFormatError, KeyError, ValueError, struct.error) as exc:
            self.load_history_view()
            self._history_status(f"History not recorded: {exc}")
            self.history_record_btn.configure(state="disabled")
            return
        self.load_history_view()
        label = chart.date_label(result.date) if result.date is not None else ""
        if result.status == history.SKIPPED_PBEM:
            text = "PBEM game: nothing recorded."
        elif result.status == history.KEPT:
            self.history_kept = result
            text = f"{label} already recorded from {result.source}."
        else:
            text = f"{label} {result.status}."
        self._history_status(text)
        self.history_record_btn.configure(state="normal" if self.history_kept else "disabled")

    def record_this_save(self):
        if self.history_kept is not None:
            self.record_history(replace=True)

    def import_history(self):
        start = os.path.dirname(self.path) if self.path else (DEFAULT_DIR if os.path.isdir(DEFAULT_DIR) else HERE)
        paths = filedialog.askopenfilenames(title="Import saves into the history", initialdir=start,
                                            filetypes=[("WitP:AE saves", "*.pws"), ("All files", "*.*")])
        if not paths:
            return

        def progress(name):
            self.history_status.set(f"Importing {name}...")
            self.root.update_idletasks()

        result = history.import_saves(paths, self.history_root, progress)
        text = f"{len(result.imported)} imported, {len(result.skipped)} skipped"
        if result.skipped:
            text += " (" + "; ".join(f"{name}: {why}" for name, why in result.skipped) + ")"
        self.load_history_view()
        self._history_status(text)

    def delete_history_turn(self):
        sel = self.history_tree.selection()
        if not sel or self.history_dir is None:
            return
        date = int(sel[0])
        if not messagebox.askyesno("Delete turn", f"Delete the recorded turn of {chart.date_label(date)}?"):
            return
        try:
            history.delete_snapshot(self.history_dir, date)
        except OSError as exc:
            self._history_status(f"Could not delete: {exc}")
            return
        self.load_history_view()
        self._history_status(f"{chart.date_label(date)} deleted.")

    def show_base_history(self):
        """The Bases tab's History button: the History tab in Base view with the selected base."""
        if self.current is None:
            return
        self._set_history_choices(self.current)
        self.history_base_var.set(next(l for l, i in self.history_choices.items() if i == self.current))
        self.history_filter_var.set("")
        self.history_view_var.set(HISTORY_VIEWS[1])
        self.notebook.select(self.history_tab)
        self._show_history_view()

    def show_aircraft_history(self):
        """The Aircraft tab's History button: the History tab in Aircraft view with the selected model."""
        if self.aircraft_current is None:
            return
        self._set_history_choices(extra_aircraft=self.aircraft_current)
        self.history_aircraft_var.set(
            next(l for l, i in self.history_aircraft_choices.items() if i == self.aircraft_current))
        self.history_aircraft_filter_var.set("")
        self.history_view_var.set(HISTORY_VIEWS[2])
        self.notebook.select(self.history_tab)
        self._show_history_view()

    def refresh_history_view(self):
        """Redraw the chart and the table from the loaded snapshots."""
        tree = self.history_tree
        tree.delete(*tree.get_children())
        snaps = self.history_snaps
        if self.history_view_var.get() == HISTORY_VIEWS[0]:
            key = next(k for k, label in history.SIDE_METRICS.items() if label == self.history_metric_var.get())
            rows = history.side_series(snaps, key)
            changes = history.changes([r[2] for r in rows]), history.changes([r[3] for r in rows])
            wanted = self.history_side_var.get()
            series = [chart.Series(side, HISTORY_SIDE_COLORS[side], [(r[0], r[i]) for r in rows])
                      for side, i in (("Allied", 2), ("Japanese", 3)) if wanted in (HISTORY_BOTH, side)]
            shown = [c for c in HISTORY_SIDES_COLUMNS
                     if wanted == HISTORY_BOTH or c in ("date", "turn") or c.startswith(wanted.lower())]
            for n, r in reversed(list(enumerate(rows))):
                tree.insert("", "end", iid=str(r[0]), values=self._history_values({
                    "date": chart.date_label(r[0]), "turn": r[1], "allied": _history_number(r[2]),
                    "allied_change": _history_change(changes[0][n]), "japanese": _history_number(r[3]),
                    "japanese_change": _history_change(changes[1][n])}))
            message = "No turns recorded yet" if not snaps else "No data for this metric"
        elif self.history_view_var.get() == HISTORY_VIEWS[2]:
            plane_id = self.history_aircraft_choices.get(self.history_aircraft_var.get())
            key = next(k for k, label in history.AIRCRAFT_METRICS.items()
                       if label == self.history_aircraft_metric_var.get())
            rows = history.aircraft_series(snaps, plane_id, key) if plane_id is not None else []
            changes = history.changes([r[3] for r in rows])
            side = bases.SIDES.get(rows[0][2]) if rows else None
            series = [chart.Series(side, HISTORY_SIDE_COLORS[side], [(r[0], r[3]) for r in rows])] if side else []
            shown = HISTORY_AIRCRAFT_COLUMNS
            for n, r in reversed(list(enumerate(rows))):
                tree.insert("", "end", iid=str(r[0]), values=self._history_values({
                    "date": chart.date_label(r[0]), "turn": r[1], "value": _history_number(r[3]),
                    "change": _history_change(changes[n])}))
            message = "No turns recorded yet" if not snaps else "No data for this aircraft"
        else:
            loc_id = self.history_choices.get(self.history_base_var.get())
            key = next(k for k, label in history.BASE_METRICS.items() if label == self.history_base_metric_var.get())
            rows = history.base_series(snaps, loc_id, key) if loc_id is not None else []
            changes = history.changes([r[3] for r in rows])
            series = [chart.Series(side, HISTORY_SIDE_COLORS[side],
                                   [(r[0], r[3] if r[2] == side_id else None) for r in rows])
                      for side_id, side in sorted(bases.SIDES.items(), key=lambda t: t[1])]
            shown = HISTORY_BASE_COLUMNS
            for n, r in reversed(list(enumerate(rows))):
                tree.insert("", "end", iid=str(r[0]), values=self._history_values({
                    "date": chart.date_label(r[0]), "turn": r[1], "side": bases.SIDES.get(r[2], HISTORY_NONE_TEXT),
                    "value": _history_number(r[3]), "change": _history_change(changes[n])}))
            message = "No turns recorded yet" if not snaps else "No data for this base"
        tree.configure(displaycolumns=list(shown))
        self.history_chart.set_data(series, message)

    @staticmethod
    def _history_values(by_column):
        return [by_column.get(c[0], "") for c in HISTORY_COLUMNS]

    # ---- intel ---------------------------------------------------------

    def _build_intel_tab(self):
        tab = self.intel_tab = ttk.Frame(self.notebook, padding=4)
        self.notebook.add(tab, text="Intel")
        bar = ttk.Frame(tab)
        bar.pack(side="top", fill="x")
        self.intel_side_var = tk.StringVar(value=intel.SIDE_NAMES[0])
        self._report_combo(bar, "Reports of:", self.intel_side_var, intel.SIDE_NAMES, self.refresh_intel, 9)
        self.intel_turns_var = tk.StringVar(value=next(iter(intel.TURN_CHOICES)))
        self._report_combo(bar, "Turns:", self.intel_turns_var, intel.TURN_CHOICES, self.refresh_intel, 8)
        ttk.Button(bar, text="Reload", command=self.load_intel_view).pack(side="left", padx=2)
        self.intel_count = tk.StringVar(value="Open a save to read its intel reports")
        ttk.Label(bar, textvariable=self.intel_count).pack(side="left", padx=8)
        ttk.Label(tab, text=INTEL_NOTE, wraplength=1100, justify="left").pack(side="bottom", anchor="w", pady=(4, 0))
        self.intel_notebook = ttk.Notebook(tab)
        self.intel_notebook.pack(side="top", fill="both", expand=True, pady=(4, 0))

        sig = ttk.Frame(self.intel_notebook, padding=4)
        self.intel_notebook.add(sig, text="SigInt")
        sbar = ttk.Frame(sig)
        sbar.pack(side="top", fill="x")
        self.intel_kind_var = tk.StringVar(value=INTEL_ALL)
        self._report_combo(sbar, "Type:", self.intel_kind_var, [INTEL_ALL, *intel.SIGINT_KINDS],
                           self.refresh_intel_sigint, 14)
        ttk.Label(sbar, text="Search:").pack(side="left")
        self.intel_search_var = tk.StringVar()
        self.intel_search_var.trace_add("write", lambda *a: self.refresh_intel_sigint())
        ttk.Entry(sbar, textvariable=self.intel_search_var, width=20).pack(side="left", padx=(4, 8))
        self.intel_view_var = tk.StringVar(value=INTEL_VIEWS[0])
        for view in INTEL_VIEWS:
            ttk.Radiobutton(sbar, text=view, value=view, variable=self.intel_view_var,
                            command=self._show_intel_view).pack(side="left", padx=2)
        self.intel_lines_frame = ttk.Frame(sig)
        self.intel_lines_tree = self._report_tree(
            self.intel_lines_frame, INTEL_LINE_COLUMNS, lambda c: self.sort_intel_by("lines", c),
            ("kind", "place", "unit", "detail"), lambda: self.open_intel("lines"))
        self.intel_places_frame = ttk.Frame(sig)
        self.intel_places_tree = self._report_tree(
            self.intel_places_frame, INTEL_PLACE_COLUMNS, lambda c: self.sort_intel_by("places", c),
            ("place", "named"), lambda: self.open_intel("places"))

        ops = ttk.Frame(self.intel_notebook, padding=4)
        self.intel_notebook.add(ops, text="Operations")
        obar = ttk.Frame(ops)
        obar.pack(side="top", fill="x")
        self.intel_category_var = tk.StringVar(value=INTEL_ALL)
        self._report_combo(obar, "Category:", self.intel_category_var, [INTEL_ALL, *intel.OPS_KINDS],
                           self.refresh_intel_ops, 11)
        ttk.Label(obar, text="Search:").pack(side="left")
        self.intel_ops_search_var = tk.StringVar()
        self.intel_ops_search_var.trace_add("write", lambda *a: self.refresh_intel_ops())
        ttk.Entry(obar, textvariable=self.intel_ops_search_var, width=20).pack(side="left", padx=4)
        oframe = ttk.Frame(ops)
        oframe.pack(side="top", fill="both", expand=True, pady=(4, 0))
        self.intel_ops_tree = self._report_tree(oframe, INTEL_OPS_COLUMNS, lambda c: self.sort_intel_by("ops", c),
                                                ("kind", "place", "text"), lambda: self.open_intel("ops"))

        combat_tab = ttk.Frame(self.intel_notebook, padding=4)
        self.intel_notebook.add(combat_tab, text="Combat")
        cbar = ttk.Frame(combat_tab)
        cbar.pack(side="top", fill="x")
        self.intel_combat_kind_var = tk.StringVar(value=INTEL_ALL)
        self._report_combo(cbar, "Kind:", self.intel_combat_kind_var, [INTEL_ALL, *combat.KINDS],
                           self.refresh_intel_combat, 17)
        self.intel_combat_involved_var = tk.StringVar(value=combat.INVOLVED_CHOICES[0])
        self._report_combo(cbar, "Involving:", self.intel_combat_involved_var, combat.INVOLVED_CHOICES,
                           self.refresh_intel_combat, 17)
        ttk.Label(cbar, text="Search:").pack(side="left")
        self.intel_combat_search_var = tk.StringVar()
        self.intel_combat_search_var.trace_add("write", lambda *a: self.refresh_intel_combat())
        ttk.Entry(cbar, textvariable=self.intel_combat_search_var, width=20).pack(side="left", padx=4)
        self.intel_combat_totals = tk.StringVar()
        ttk.Label(combat_tab, textvariable=self.intel_combat_totals).pack(side="bottom", anchor="w", pady=(4, 0))
        panes = ttk.PanedWindow(combat_tab, orient="vertical")
        panes.pack(side="top", fill="both", expand=True, pady=(4, 0))
        cframe = ttk.Frame(panes)
        panes.add(cframe, weight=3)
        self.intel_combat_tree = self._report_tree(
            cframe, INTEL_COMBAT_COLUMNS, lambda c: self.sort_intel_by("combat", c), ("kind", "phase", "place"),
            lambda: self.open_intel("combat"))
        self.intel_combat_tree.bind("<<TreeviewSelect>>", lambda e: self.show_intel_combat_text())
        tframe = ttk.Frame(panes)
        panes.add(tframe, weight=2)
        tscroll = ttk.Scrollbar(tframe, orient="vertical")
        self.intel_combat_text = tk.Text(tframe, height=10, wrap="none", state="disabled", font="TkFixedFont",
                                         yscrollcommand=tscroll.set)
        tscroll.configure(command=self.intel_combat_text.yview)
        tscroll.pack(side="right", fill="y")
        self.intel_combat_text.pack(side="left", fill="both", expand=True)
        self._show_intel_view()

    def _show_intel_view(self):
        lines = self.intel_view_var.get() == INTEL_VIEWS[0]
        shown, hidden = (self.intel_lines_frame, self.intel_places_frame) if lines else (
            self.intel_places_frame, self.intel_lines_frame)
        hidden.pack_forget()
        shown.pack(side="top", fill="both", expand=True, pady=(4, 0))
        self.refresh_intel_sigint()

    def load_intel_view(self):
        """Read the report files next to the open save and redraw."""
        if self.save is None:
            return
        self.intel_folder = intel.intel_folder(self.path)
        self.intel_message = ""
        try:
            self.intel_all = intel.load_reports(self.intel_folder)
        except OSError as exc:
            self.intel_all = {"sigint": [], "ops": []}
            self.intel_message = f"Could not read the intel reports: {exc}"
        try:
            self.intel_index = intel.PlaceIndex(self.save)
        except (SaveFormatError, IndexError, KeyError, struct.error):
            self.intel_index = None
        try:
            self.intel_combat_all = combat.load_actions(self.intel_folder)
        except OSError as exc:
            self.intel_combat_all = []
            self.intel_message = self.intel_message or f"Could not read the combat reports: {exc}"
        sides = {line.side for lines in self.intel_all.values() for line in lines}
        if sides and self.intel_side_var.get() not in sides:
            self.intel_side_var.set(next(side for side in intel.SIDE_NAMES if side in sides))
        if not sides and not self.intel_combat_all and not self.intel_message:
            self.intel_message = f"No intel reports found in {self.intel_folder}"
        self.refresh_intel()

    def _intel_lines(self, key, search_var, kind_var):
        """The loaded lines of one report that pass the side, turns, type and search choices."""
        side = self.intel_side_var.get()
        lines = intel.recent([l for l in self.intel_all[key] if l.side == side],
                             intel.TURN_CHOICES[self.intel_turns_var.get()])
        kind = kind_var.get()
        needle = search_var.get().strip().lower()
        return [l for l in lines if kind in (INTEL_ALL, l.kind) and needle in l.text.lower()]

    def refresh_intel(self):
        self.refresh_intel_sigint()
        self.refresh_intel_ops()
        self.refresh_intel_combat()

    def _fill_intel_tree(self, name, tree, rows, place_ids):
        columns = INTEL_TABLES[name]
        sort_col, reverse = self.intel_sort[name]
        order = list(range(len(rows)))
        if sort_col is not None:
            _cid, _h, _w, numeric, get = next(c for c in columns if c[0] == sort_col)
            order.sort(key=lambda k: (get(rows[k]) if numeric else str(get(rows[k])).lower(), k), reverse=reverse)
        tree.delete(*tree.get_children())
        self.intel_place_by_iid[name] = {str(k): place_ids[k] for k in order}
        for k in order:
            tree.insert("", "end", iid=str(k), values=self._report_values(
                columns, INTEL_COMBAT_TEXT if name == "combat" else INTEL_TEXT, rows[k]))

    def refresh_intel_sigint(self):
        lines = self._intel_lines("sigint", self.intel_search_var, self.intel_kind_var)
        if self.intel_view_var.get() == INTEL_VIEWS[0]:
            rows = intel.resolve_lines(lines, self.intel_index)
            self._fill_intel_tree("lines", self.intel_lines_tree, rows, [r.place_id for r in rows])
        else:
            rows = intel.by_place(lines, self.intel_index)
            self._fill_intel_tree("places", self.intel_places_tree, rows, [r.place_id for r in rows])
        self.intel_shown["sigint"] = len(lines)
        self._set_intel_count()

    def refresh_intel_ops(self):
        lines = self._intel_lines("ops", self.intel_ops_search_var, self.intel_category_var)
        rows = intel.resolve_lines(lines, self.intel_index)
        self._fill_intel_tree("ops", self.intel_ops_tree, rows, [r.place_id for r in rows])
        self.intel_shown["ops"] = len(lines)
        self._set_intel_count()

    def refresh_intel_combat(self):
        actions = combat.select(intel.recent(self.intel_combat_all, intel.TURN_CHOICES[self.intel_turns_var.get()]),
                                self.intel_combat_kind_var.get(), self.intel_combat_search_var.get(),
                                self.intel_combat_involved_var.get())
        self.intel_combat_rows = rows = intel.resolve_lines(actions, self.intel_index)
        self._fill_intel_tree("combat", self.intel_combat_tree, rows, [r.place_id for r in rows])
        t = combat.totals(actions)
        self.intel_combat_totals.set(
            f"{t['actions']} of {len(self.intel_combat_all)} actions    "
            f"Aircraft lost: Allied {t['allied_air_lost']}, Japanese {t['japanese_air_lost']}    "
            f"Ships sunk: Allied {t['allied_ships_sunk']}, Japanese {t['japanese_ships_sunk']}")
        self.show_intel_combat_text()

    def show_intel_combat_text(self):
        """The selected action's full report text in the pane below the table (empty when none is selected)."""
        sel = self.intel_combat_tree.selection()
        text = self.intel_combat_rows[int(sel[0])].line.text if sel else ""
        self.intel_combat_text.configure(state="normal")
        self.intel_combat_text.delete("1.0", "end")
        self.intel_combat_text.insert("1.0", text)
        self.intel_combat_text.configure(state="disabled")

    def _set_intel_count(self):
        if self.save is None:
            return
        side = self.intel_side_var.get()
        total = {key: sum(1 for l in lines if l.side == side) for key, lines in self.intel_all.items()}
        self.intel_count.set(self.intel_message or (
            f"SigInt: {self.intel_shown['sigint']} of {total['sigint']} lines    "
            f"Operations: {self.intel_shown['ops']} of {total['ops']} lines"))

    def sort_intel_by(self, name, col):
        state = self.intel_sort[name]
        state[1] = (not state[1]) if col == state[0] else False
        state[0] = col
        if name == "ops":
            self.refresh_intel_ops()
        elif name == "combat":
            self.refresh_intel_combat()
        else:
            self.refresh_intel_sigint()

    def open_intel(self, name):
        """Double-click: open the place the row names, when it is a base or town of the open save."""
        tree = {"lines": self.intel_lines_tree, "places": self.intel_places_tree, "ops": self.intel_ops_tree,
                "combat": self.intel_combat_tree}[name]
        sel = tree.selection()
        place_id = self.intel_place_by_iid[name].get(sel[0]) if sel else None
        if place_id is not None:
            self.jump_to_industry_place(tree, str(place_id))

    # ---- map -----------------------------------------------------------

    def _build_map_tab(self):
        tab = self.map_tab = ttk.Frame(self.notebook, padding=4)
        self.notebook.add(tab, text="Map")
        self.map_image = None  # the background on the canvas, kept alive here
        self.map_images = {}  # (style, step) -> PhotoImage, for the session
        self.map_shown = None  # (style, step) of the background on the canvas
        self.map_size = (1, 1)  # canvas pixels of the map as drawn
        self.map_cache = {}  # overlay data of the open save, by the arguments of its builder
        self.map_index = None
        self.map_places = None
        self.map_stale = True  # the open save has not been drawn yet
        self.map_message = ""
        self.map_press = None
        bar = ttk.Frame(tab)
        bar.pack(side="top", fill="x")
        self.map_style_var = tk.StringVar(value=next(iter(mapview.STYLES)))
        self._report_combo(bar, "Background:", self.map_style_var, mapview.STYLES, self.refresh_map, 9)
        self.map_scale_var = tk.StringVar(value="25%")
        self._report_combo(bar, "Scale:", self.map_scale_var, MAP_SCALES, self.refresh_map, 5)
        self.map_overlay_var = tk.StringVar(value=MAP_OVERLAYS[0])
        self._report_combo(bar, "Overlay:", self.map_overlay_var, MAP_OVERLAYS, self._map_overlay_changed, 11)
        self.map_side_var = tk.StringVar(value=MAP_SIDES[0])
        self.map_side_box = self._report_combo(bar, "Side:", self.map_side_var, MAP_SIDES, self.refresh_map, 9)
        ttk.Label(bar, text="Find:").pack(side="left")
        self.map_find_var = tk.StringVar()
        find = ttk.Entry(bar, textvariable=self.map_find_var, width=18)
        find.pack(side="left", padx=(4, 2))
        find.bind("<Return>", lambda e: self.find_map_place())
        ttk.Button(bar, text="Find", command=self.find_map_place).pack(side="left")

        self.map_filters = ttk.Frame(tab)
        self.map_filters.pack(side="top", fill="x", pady=(4, 0))
        self.map_filter_frames = {}
        loc = self.map_filter_frames["Locations"] = ttk.Frame(self.map_filters)
        self.map_towns_var = tk.StringVar(value=MAP_TOWNS[0])
        self._report_combo(loc, "Show:", self.map_towns_var, MAP_TOWNS, self.refresh_map, 15)
        self.map_region_var = tk.StringVar(value=REGION_ALL)
        self._report_combo(loc, "Region:", self.map_region_var, self.region_ids, self.refresh_map, 22)
        arcs = self.map_filter_frames["Search arcs"] = ttk.Frame(self.map_filters)
        self.map_arc_kind_var = tk.StringVar(value=MAP_ARC_KINDS[0])
        self._report_combo(arcs, "Patrol:", self.map_arc_kind_var, MAP_ARC_KINDS, self.refresh_map, 7)
        self.map_arc_mode_var = tk.StringVar(value=MAP_ARC_MODES[0])
        self._report_combo(arcs, "Arc:", self.map_arc_mode_var, MAP_ARC_MODES, self.refresh_map, 8)
        self.map_filter_frames["Task forces"] = ttk.Frame(self.map_filters)
        cmb = self.map_filter_frames["Combat"] = ttk.Frame(self.map_filters)
        self.map_combat_kind_var = tk.StringVar(value=INTEL_ALL)
        self._report_combo(cmb, "Kind:", self.map_combat_kind_var, [INTEL_ALL, *combat.KINDS], self.refresh_map, 17)
        self.map_combat_turns_var = tk.StringVar(value=next(iter(intel.TURN_CHOICES)))
        self._report_combo(cmb, "Turns:", self.map_combat_turns_var, intel.TURN_CHOICES, self.refresh_map, 8)

        self.map_info = tk.StringVar(value="Open a save to see the map")
        ttk.Label(tab, textvariable=self.map_info).pack(side="bottom", anchor="w", pady=(4, 0))
        dframe = ttk.Frame(tab)
        dframe.pack(side="bottom", fill="x", pady=(4, 0))
        dscroll = ttk.Scrollbar(dframe, orient="vertical")
        self.map_detail = tk.Text(dframe, height=6, wrap="none", state="disabled", yscrollcommand=dscroll.set)
        dscroll.configure(command=self.map_detail.yview)
        dscroll.pack(side="right", fill="y")
        self.map_detail.pack(side="left", fill="x", expand=True)

        frame = ttk.Frame(tab)
        frame.pack(side="top", fill="both", expand=True, pady=(4, 0))
        hbar = ttk.Scrollbar(frame, orient="horizontal")
        vbar = ttk.Scrollbar(frame, orient="vertical")
        c = self.map_canvas = tk.Canvas(frame, background=MAP_PLAIN_COLOR, highlightthickness=0, width=900,
                                        height=420, xscrollcommand=hbar.set, yscrollcommand=vbar.set)
        hbar.configure(command=c.xview)
        vbar.configure(command=c.yview)
        c.grid(row=0, column=0, sticky="nsew")
        vbar.grid(row=0, column=1, sticky="ns")
        hbar.grid(row=1, column=0, sticky="ew")
        frame.grid_rowconfigure(0, weight=1)
        frame.grid_columnconfigure(0, weight=1)
        c.bind("<ButtonPress-1>", self._map_press)
        c.bind("<B1-Motion>", self._map_drag)
        c.bind("<ButtonRelease-1>", self._map_release)
        c.bind("<MouseWheel>", lambda e: c.yview_scroll(-1 if e.delta > 0 else 1, "units"))
        c.bind("<Shift-MouseWheel>", lambda e: c.xview_scroll(-1 if e.delta > 0 else 1, "units"))
        c.bind("<Button-4>", lambda e: c.yview_scroll(-1, "units"))
        c.bind("<Button-5>", lambda e: c.yview_scroll(1, "units"))
        c.bind("<Control-MouseWheel>", lambda e: self.zoom_map(e, 1 if e.delta > 0 else -1))
        c.bind("<Control-Button-4>", lambda e: self.zoom_map(e, 1))
        c.bind("<Control-Button-5>", lambda e: self.zoom_map(e, -1))
        self._map_overlay_changed(draw=False)
        # Bound last (and added) so the Reports handler stays; the map is drawn only when it is first shown.
        self.notebook.bind("<<NotebookTabChanged>>", lambda e: self._map_shown_event(), add="+")

    def _map_overlay_changed(self, draw=True):
        overlay = self.map_overlay_var.get()
        for name, frame in self.map_filter_frames.items():
            frame.pack_forget()
            if name == overlay:
                frame.pack(side="left")
        self.map_side_box.configure(state="disabled" if overlay == "Combat" else "readonly")
        if draw:
            self.refresh_map()

    def _map_visible(self):
        return self.notebook.select() == str(self.map_tab)

    def _map_shown_event(self):
        if self.map_stale and self._map_visible():
            self.refresh_map()

    def load_map_view(self):
        """Forget the overlays of the previous save; the map is redrawn now if its tab is showing, else when shown."""
        self.map_cache = {}
        self.map_index = None
        self.map_places = None
        self.map_shown = None  # the art folder depends on the save's folder
        self.map_stale = True
        self.map_canvas.delete("overlay", "pick")
        self._set_map_detail("")
        if self._map_visible():
            self.refresh_map()

    def _map_step(self):
        return MAP_SCALES[self.map_scale_var.get()]

    def refresh_map(self):
        if self.save is None:
            self.map_info.set("Open a save to see the map")
            return
        self.map_stale = False
        self._draw_map_background()
        try:
            self._draw_map_overlay()
        except (SaveFormatError, IndexError, KeyError, struct.error) as exc:
            self.map_canvas.delete("overlay")
            self.map_info.set(f"Could not read the {self.map_overlay_var.get().lower()}: {exc}")

    def _draw_map_background(self):
        style, step = self.map_style_var.get(), self._map_step()
        if self.map_shown == (style, step):
            return
        c = self.map_canvas
        centre = (sum(c.xview()) / 2, sum(c.yview()) / 2)
        c.delete("bg", "pick")
        self.map_message = ""
        image = self.map_images.get((style, step))
        if image is None:
            folder = mapview.find_art(self._art_dirs(), style)
            if folder is None:
                self.map_message = "Map art (WPEH00.bmp ... WPEN41.bmp) not found in the ART folder; plain background."
            else:
                try:
                    _w, _h, ppm = mapview.render(folder, style, step)
                    image = tk.PhotoImage(master=self.root, data=ppm)
                    if step > 1:  # a full-size image is ~300 MB, so only the one on screen is kept
                        self.map_images[(style, step)] = image
                except (ValueError, tk.TclError) as exc:
                    self.map_message = f"Map art could not be read ({exc}); plain background."
        if image is not None:
            width, height = image.width(), image.height()
            c.create_image(0, 0, anchor="nw", image=image, tags="bg")
        else:
            width, height = -(-mapview.FULL_SIZE[0] // step), -(-mapview.FULL_SIZE[1] // step)
            c.create_rectangle(0, 0, width, height, fill=MAP_PLAIN_COLOR, outline="", tags="bg")
        self.map_image = image
        c.tag_lower("bg")
        self.map_size = (width, height)
        self.map_shown = (style, step)
        c.configure(scrollregion=(0, 0, width, height))
        c.xview_moveto(centre[0] - c.winfo_width() / width / 2)
        c.yview_moveto(centre[1] - c.winfo_height() / height / 2)

    def _map_data(self, key, build):
        if key not in self.map_cache:
            self.map_cache[key] = build()
        return self.map_cache[key]

    @staticmethod
    def _map_color(side):
        return HISTORY_SIDE_COLORS.get(side, MAP_OTHER_COLOR)

    def _draw_map_overlay(self):
        c = self.map_canvas
        c.delete("overlay")
        step = self._map_step()
        scale = 1 / step
        overlay, side = self.map_overlay_var.get(), self.map_side_var.get()

        def point(x, y):
            px, py = mapview.hex_to_pixel(x, y)
            return px * scale, py * scale

        if overlay == "Locations":
            towns = self.map_towns_var.get() == MAP_TOWNS[1]
            region = self.region_ids[self.map_region_var.get()]
            marks = self._map_data(("loc", towns, side, region),
                                   lambda: mapview.location_marks(self.save, towns, side, region))
            r = {8: 2, 4: 3, 2: 4, 1: 6}[step]
            for m in marks:
                x, y = point(m.x, m.y)
                color = self._map_color(m.side)
                c.create_oval(x - r, y - r, x + r, y + r, outline=color, width=2,
                              fill=color if m.kind == "Base" else "", tags="overlay")
                if step == 2 and m.kind == "Base":  # the full-size art has its own names
                    for dx, fill in ((1, "white"), (0, "black")):  # a light shadow keeps the name legible
                        c.create_text(x + r + 3 + dx, y + dx, text=m.name, anchor="w", fill=fill,
                                      font=("TkDefaultFont", 7), tags="overlay")
            summary = f"{len(marks)} {'bases and towns' if towns else 'bases'}"
        elif overlay == "Search arcs":
            kind, mode = self.map_arc_kind_var.get(), self.map_arc_mode_var.get()
            arcs = self._map_data(("arc", kind, mode, side), lambda: mapview.search_arcs(self.save, kind, mode, side))
            for a in arcs:
                x, y = point(a.x, a.y)
                rad = a.radius * mapview.HEX_W * scale
                box = (x - rad, y - rad, x + rad, y + rad)
                style = {"outline": self._map_color(a.side), "dash": (4, 3) if kind == "ASW" else "",
                         "tags": "overlay"}
                if a.full:
                    c.create_oval(*box, **style)
                else:
                    start, extent = mapview.compass_to_tk(a.start, a.end)
                    c.create_arc(*box, start=start, extent=extent, style="pieslice", fill="", **style)
                c.create_oval(x - 2, y - 2, x + 2, y + 2, fill=style["outline"], outline="", tags="overlay")
            summary = f"{len(arcs)} {kind} search arcs ({sum(a.full for a in arcs)} full circle)"
        elif overlay == "Task forces":
            tfs = self._map_data(("tf", side), lambda: mapview.task_force_marks(self.save, side))
            for t in tfs:
                x, y = point(t.x, t.y)
                color = self._map_color(t.side)
                if t.dest_x is not None:
                    dx, dy = point(t.dest_x, t.dest_y)
                    c.create_line(x, y, dx, dy, fill=color, dash=(3, 3), arrow="last", tags="overlay")
                c.create_rectangle(x - 3, y - 3, x + 3, y + 3, fill=color, outline="black", tags="overlay")
            summary = f"{len(tfs)} task forces ({sum(t.dest_x is not None for t in tfs)} with a destination)"
        else:
            kind = self.map_combat_kind_var.get()
            turns = intel.TURN_CHOICES[self.map_combat_turns_var.get()]
            marks = mapview.combat_marks(intel.recent(self.intel_combat_all, turns), kind)
            for m in marks:
                x, y = point(m.x, m.y)
                c.create_polygon(x, y - 5, x + 5, y, x, y + 5, x - 5, y, fill=MAP_COMBAT_COLOR, outline="black",
                                 tags="overlay")
            summary = f"{len(marks)} combat actions"
        self.map_info.set(f"{self.map_message}  {summary}".strip() if self.map_message else summary)

    def zoom_map(self, event, direction):
        """Step the Scale one choice in (direction 1) or out (-1), keeping the map point under the mouse in place."""
        scales = list(MAP_SCALES)
        i = scales.index(self.map_scale_var.get()) + direction
        if self.save is None or not 0 <= i < len(scales):
            return
        c = self.map_canvas
        width, height = self.map_size
        fx, fy = c.canvasx(event.x) / width, c.canvasy(event.y) / height
        self.map_scale_var.set(scales[i])
        self.refresh_map()
        width, height = self.map_size
        c.xview_moveto((fx * width - event.x) / width)
        c.yview_moveto((fy * height - event.y) / height)

    # Left-drag pans the map; a press that hardly moves is a click on a hex.
    def _map_press(self, event):
        self.map_press = (event.x, event.y)
        self.map_canvas.scan_mark(event.x, event.y)

    def _map_drag(self, event):
        self.map_canvas.scan_dragto(event.x, event.y, gain=1)

    def _map_release(self, event):
        start, self.map_press = self.map_press, None
        if start is None or max(abs(event.x - start[0]), abs(event.y - start[1])) > MAP_CLICK_PIXELS:
            return
        step = self._map_step()
        c = self.map_canvas
        self.show_map_hex(*mapview.pixel_to_hex(c.canvasx(event.x) * step, c.canvasy(event.y) * step))

    def _set_map_detail(self, text):
        self.map_detail.configure(state="normal")
        self.map_detail.delete("1.0", "end")
        self.map_detail.insert("1.0", text)
        self.map_detail.configure(state="disabled")

    def _map_hex_index(self):
        if self.map_index is None:
            try:
                self.map_index = mapview.hex_index(self.save, self.intel_combat_all)
            except (SaveFormatError, IndexError, KeyError, struct.error) as exc:
                self.map_index = {}
                self.map_info.set(f"Could not read the hex contents: {exc}")
        return self.map_index

    @staticmethod
    def _map_item_text(category, m):
        if category == "Places":
            return f"{m.name} ({m.kind.lower()}, {m.side})"
        if category == "Task forces":
            dest = f", to {m.dest_x},{m.dest_y}" if m.dest_x is not None else ""
            return f"{m.name or 'TF ' + str(m.id)} ({m.side}, {m.mission}, {m.ships} ships{dest})"
        if category == "Air groups searching":
            arc = "full circle" if m.full else f"arc {m.start} to {m.end} deg"
            return f"{m.name} ({m.side}, {m.kind}, range {m.radius}, {arc})"
        return f"{chart.date_label(m.date)} {m.kind}: {m.title}"

    def show_map_hex(self, x, y):
        """Mark hex (x, y) and list what is in it: places, task forces, air groups searching from it, combat."""
        c = self.map_canvas
        scale = 1 / self._map_step()
        px, py = mapview.hex_to_pixel(x, y)
        r = max(4, mapview.HEX_W / 2 * scale)
        c.delete("pick")
        c.create_oval(px * scale - r, py * scale - r, px * scale + r, py * scale + r, outline="black", width=2,
                      tags="pick")
        contents = self._map_hex_index().get((x, y), {})
        lines = [f"Hex {x},{y}"]
        for category in mapview.INDEX_CATEGORIES:
            if category in contents:
                lines.append(f"{category}:")
                lines.extend(f"  {self._map_item_text(category, m)}" for m in contents[category])
        if not contents:
            lines.append("Nothing here")
        self._set_map_detail("\n".join(lines))

    def find_map_place(self):
        """Centre the map on the base or town whose name matches the Find box (exact, then prefix, then contains)."""
        needle = self.map_find_var.get().strip().lower()
        if self.save is None or not needle:
            return
        if self.map_places is None:
            self.map_places = bases.list_places(self.save)
        places = self.map_places
        match = (next((p for p in places if p.name.lower() == needle), None)
                 or next((p for p in places if p.name.lower().startswith(needle)), None)
                 or next((p for p in places if needle in p.name.lower()), None))
        if match is None:
            self.map_info.set(f"No base or town matches {needle!r}")
            return
        if self.map_stale:
            self.refresh_map()
        c = self.map_canvas
        scale = 1 / self._map_step()
        px, py = mapview.hex_to_pixel(match.x, match.y)
        width, height = self.map_size
        c.xview_moveto((px * scale - c.winfo_width() / 2) / width)
        c.yview_moveto((py * scale - c.winfo_height() / 2) / height)
        self.show_map_hex(match.x, match.y)

    def apply_title(self):
        if self.save is None:
            return
        try:
            bases.set_title(self.save, self.title_var.get())
        except ValueError as exc:
            messagebox.showerror("Invalid title", str(exc))
            return
        self.dirty = True
        self.status.set("Title updated (not yet saved)")

    # ---- saving --------------------------------------------------------

    def save_as(self):
        if self.save is None:
            return
        if self.pbem:
            messagebox.showerror("Save refused", "This is a PBEM game. Saving an edited copy would desynchronise "
                                 "the other player, so PBEM saves are never written.")
            return
        # A typed but unapplied title would otherwise be silently dropped.
        if self.title_var.get() != self.save.description:
            try:
                bases.set_title(self.save, self.title_var.get())
            except ValueError as exc:
                messagebox.showerror("Invalid title", str(exc))
                return
        start = DEFAULT_DIR if os.path.isdir(DEFAULT_DIR) else HERE
        path = filedialog.asksaveasfilename(title="Save As", initialdir=start, defaultextension=".pws",
                                            initialfile=os.path.basename(self.path or ""),
                                            confirmoverwrite=False,
                                            filetypes=[("WitP:AE saves", "*.pws"), ("All files", "*.*")])
        if not path:
            return
        if os.path.exists(path) and not messagebox.askyesno(
                "Overwrite?", f"{path} exists. Overwrite it?\n\nThe old file is first copied to {os.path.basename(path)}.bak."):
            return
        try:
            backup = save_with_backup(self.save, path)
        except (OSError, SaveFormatError) as exc:
            messagebox.showerror("Save failed", str(exc))
            return
        self.dirty = False
        self.status.set(f"Saved {path}" + (f" (backup: {backup})" if backup else ""))


def main(argv):
    root = tk.Tk()
    app = EditorApp(root)
    if len(argv) > 1:
        if os.path.isdir(argv[1]):
            root.after_idle(lambda: app.open_dialog(argv[1]))
        else:
            app.load(argv[1])
    root.mainloop()


if __name__ == "__main__":
    main(sys.argv)
