"""Leaders (section 0x15): ranks, branch, type, and which unit each one commands.

50000 records of 180 bytes indexed by leader id (the id air groups, ships and
land units refer to); an empty name marks an unused record, and the name is
plain latin-1 text. The seven ratings (u8 at 26..32) are the editable part and
are defined in `airgroups.LEADER_FIELDS`; `airgroups.Leader` does the
validation and writing, this module only reads. Layout decoded from the
WiTPTracker reader and the ae-editor field map, and checked on a save (27,732
named leaders):

    25  u8   rank code (not age); the label depends on the code, see RANKS
    26..32   the ratings (verified in-game, editable)
    42  u8   nation, same codes as ships and aircraft (IJA and IJN are Japanese)
    44  i32  delay: days until the leader is available, 0 = available
    48  u8   political points (not verified in game)
    49  u8   type, the kind of command he suits best (TYPES)

Offset 38 (i16) is the unit only for some air group leaders and is not used.
Only the ratings were verified in-game; the other fields are read-only here.

Assignment is not stored on the leader. It is found by reading the leader
field of the unit records: air groups (i16 at 32, `airgroups.LEADER_OFFSET`),
ships (u16 at 32, `SHIP_LEADER_OFFSET`; 10,722 of 10,757 ships on a test save
point at a type-5 leader) and location records (u16 at 128,
`LOCATION_LEADER_OFFSET`): task forces (type 12) and land units and HQs. Only
used records count. A leader named by several units is listed with the first
(air groups, then ships, then locations in id order) and a count of the others.
Rank codes outside 0..53 and types outside 0..6 show their number.

The user-weighted rating (`weighted_rating`) and the `PRESETS` are ported from the
Leaders tab of WitpStaff, whose leader-prefs.csv holds the "good at" multipliers
(-5..5) per kind of command. Its WitP-era ratings map to AE as Air -> air, Sea ->
naval, Land -> land, Skill -> leadership, Administration -> admin, Agressiveness
-> aggression, Inspiration -> inspiration; its minimum rank and side are dropped.
"""

import struct
from collections import namedtuple

from . import landunits, taskforces
from .airgroups import (
    GROUP_RECORD_COUNT, GROUP_RECORD_SIZE, GROUP_SECTION, LEADER_FIELDS, LEADER_OFFSET, LEADER_RECORD_COUNT,
    LEADER_RANK_OFFSET as RANK_OFFSET, LEADER_RECORD_SIZE, LEADER_SECTION, SHIP_RECORD_COUNT, SHIP_RECORD_SIZE,
    SHIP_SECTION,
)
from .bases import LOCATION_SECTION, NAME_SIZE, RECORD_COUNT, RECORD_SIZE, TYPE_OFFSET, decode_name
from .factories import _plain_name
from .nations import nation_label
from .shiprecords import JAPANESE_NATIONS

NATION_OFFSET = 42
DELAY_OFFSET = 44
POLITICAL_OFFSET = 48
TYPE_CODE_OFFSET = 49
SHIP_LEADER_OFFSET = 32
LOCATION_LEADER_OFFSET = 128

RANKS = ("WO 2LT 1LT CPT MAJ LTC COL MGEN LGEN GEN PO2 PO1 CPO WO ENS LTJG LT LCDR CDR CPT RADM VADM ADM "
         "ENS LTJG LT LCDR CDR CPT RADM VADM ADM FO 2LT LT CPT MAJ LTC COL BGEN MGEN LGEN GEN "
         "WO PO FO FLT SLDR WCDR GCPT ACOM AVM AM ACM").split()
TYPES = {0: "None", 1: "Headquarters", 2: "Large Ground Unit", 3: "Small Ground Unit", 4: "Task Force",
         5: "Ship", 6: "Air Group"}
BRANCHES = ("Army", "Navy", "Air")
RATING_NAMES = tuple(f.name for f in LEADER_FIELDS)
WEIGHT_MIN, WEIGHT_MAX = -5, 5
# name -> (weights, type label or "All", branch or "All"); from WitpStaff's leader-prefs.csv.
PRESETS = {
    "Submarine": ({"naval": 5, "leadership": 1, "aggression": -4}, "Ship", "Navy"),
    "Battleship": ({"naval": 5, "admin": 1, "aggression": 2}, "Ship", "Navy"),
    "Fighter group": ({"air": 5, "leadership": 2, "aggression": 4, "inspiration": 2}, "Air Group", "All"),
    "Bomber group": ({"air": 5, "leadership": 2, "admin": 2, "aggression": -4, "inspiration": 5}, "Air Group", "All"),
    "Training group": ({"air": 2, "leadership": 5, "admin": 2, "aggression": -3, "inspiration": 3}, "Air Group",
                       "All"),
    "Carrier TF": ({"air": 5, "naval": 1, "aggression": -4, "inspiration": 4}, "Task Force", "Navy"),
    "Surface combat TF": ({"naval": 5, "aggression": 2}, "Task Force", "Navy"),
    "Bombardment TF": ({"naval": 4, "aggression": 3}, "Task Force", "Navy"),
    "Land HQ": ({"land": 5, "admin": 2, "inspiration": 3}, "Headquarters", "Army"),
    "Air HQ": ({"air": 5, "admin": 2, "inspiration": 4}, "Headquarters", "All"),
}
KIND_AIR_GROUP, KIND_SHIP, KIND_LCU, KIND_TF = "Air group", "Ship", "LCU", "TF"

LeaderRow = namedtuple(
    "LeaderRow",
    "id name side nation_id nation rank_code rank branch type_code type "
    "leadership inspiration naval air land admin aggression political delay "
    "kind unit_id unit extra commands")


def rank_label(code):
    return RANKS[code] if 0 <= code < len(RANKS) else f"Rank {code}"


def branch_label(code):
    """Army, Navy or Air from the rank code, "?" for a code outside the rank table."""
    if 0 <= code <= 9 or 32 <= code <= 42:
        return "Army"
    if 10 <= code <= 31:
        return "Navy"
    if 43 <= code <= 53:
        return "Air"
    return "?"


def type_label(code):
    return TYPES.get(code, f"Type {code}")


def side_of(nation_id):
    return "Japanese" if nation_id in JAPANESE_NATIONS else "Allied"


def assignments(save):
    """{leader id: [(kind, unit id, unit text), ...]} from one scan of each unit table.

    Air groups come first, then ships, then location records, each in id order.
    """
    out = {}
    group_data = save[GROUP_SECTION].data
    for group_id in range(min(GROUP_RECORD_COUNT, len(group_data) // GROUP_RECORD_SIZE)):
        start = group_id * GROUP_RECORD_SIZE
        leader = struct.unpack_from("<h", group_data, start + LEADER_OFFSET)[0]
        if leader > 0:
            name = decode_name(group_data[start:start + NAME_SIZE])
            if name:
                out.setdefault(leader, []).append((KIND_AIR_GROUP, group_id, name))
    ship_data = save[SHIP_SECTION].data
    for ship_id in range(min(SHIP_RECORD_COUNT, len(ship_data) // SHIP_RECORD_SIZE)):
        start = ship_id * SHIP_RECORD_SIZE
        leader = struct.unpack_from("<H", ship_data, start + SHIP_LEADER_OFFSET)[0]
        if leader:
            name = _plain_name(ship_data, start)
            if name:
                out.setdefault(leader, []).append((KIND_SHIP, ship_id, name))
    loc_data = save[LOCATION_SECTION].data
    names = {}
    for loc_id in range(min(RECORD_COUNT, len(loc_data) // RECORD_SIZE)):
        start = loc_id * RECORD_SIZE
        leader = struct.unpack_from("<H", loc_data, start + LOCATION_LEADER_OFFSET)[0]
        if not leader:
            continue
        loc_type = struct.unpack_from("<h", loc_data, start + TYPE_OFFSET)[0]
        if loc_type == taskforces.TF_TYPE:
            if taskforces.is_task_force(save, loc_id) and struct.unpack_from(
                    "<H", loc_data, start + taskforces.COUNT_OFFSET)[0]:
                out.setdefault(leader, []).append((KIND_TF, loc_id, f"TF {loc_id}"))
        elif loc_type in landunits.LAND_TYPES:
            name = decode_name(loc_data[start:start + NAME_SIZE])
            if name:
                unit = landunits.LandUnit(save, loc_id, name, names)
                out.setdefault(leader, []).append((KIND_LCU, loc_id, unit.display_name))
    return out


def make_row(save, leader_id, name, assigned=()):
    """The read model of one leader from the current bytes; `assigned` is its list from assignments()."""
    data = save[LEADER_SECTION].data
    start = leader_id * LEADER_RECORD_SIZE
    rank_code, nation_id = data[start + RANK_OFFSET], data[start + NATION_OFFSET]
    type_code = data[start + TYPE_CODE_OFFSET]
    ratings = data[start + LEADER_FIELDS[0].offset:start + LEADER_FIELDS[-1].offset + 1]
    delay = struct.unpack_from("<i", data, start + DELAY_OFFSET)[0]
    kind, unit_id, unit = assigned[0] if assigned else ("", 0, "")
    extra = max(len(assigned) - 1, 0)
    return LeaderRow(
        leader_id, name, side_of(nation_id), nation_id, nation_label(nation_id), rank_code, rank_label(rank_code),
        branch_label(rank_code), type_code, type_label(type_code), *ratings, data[start + POLITICAL_OFFSET], delay,
        kind, unit_id, unit, extra, f"{unit} +{extra}" if extra else unit)


def list_leaders(save, assigned=None):
    """Every named leader as a LeaderRow in id order. `assigned` defaults to assignments(save)."""
    if assigned is None:
        assigned = assignments(save)
    data = save[LEADER_SECTION].data
    out = []
    for leader_id in range(1, min(LEADER_RECORD_COUNT, len(data) // LEADER_RECORD_SIZE)):
        start = leader_id * LEADER_RECORD_SIZE
        if data[start] == 0:
            continue
        name = _plain_name(data, start)
        if name:
            out.append(make_row(save, leader_id, name, assigned.get(leader_id, ())))
    return out


def filter_leaders(rows, side="All", branch="All", type_text="All", assigned="All", needle=""):
    """Rows matching the GUI filters; needle is matched against the name and the commands text."""
    needle = needle.strip().lower()
    return [r for r in rows
            if (side == "All" or r.side == side) and (branch == "All" or r.branch == branch)
            and (type_text == "All" or r.type == type_text)
            and (assigned == "All" or bool(r.kind) == (assigned == "Assigned"))
            and (not needle or needle in r.name.lower() or needle in r.commands.lower())]


def weighted_rating(row, weights):
    """Sum of weight * rating over the seven ratings; a name missing from `weights` counts 0."""
    return sum(weights.get(name, 0) * getattr(row, name) for name in RATING_NAMES)
