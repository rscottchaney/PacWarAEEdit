"""Air groups (section 0x14), their pilots (0x16) and commanders (0x15).

Group records are indexed by the group number shown in the game and have
encrypted names like base names. Pilots and commanders have plain names. Views
read and write the section bytearrays in place. Only the first copy of each
pilot skill is written; the byte copy at 78..89 and the byte at 122 are left
alone because their purpose is unknown.
"""

import struct

from .aircraft import AIRCRAFT_RECORD_SIZE, AIRCRAFT_SECTION, RECORD_COUNT as AIRCRAFT_RECORD_COUNT
from .aircraft import SIDE_OFFSET as AIRCRAFT_SIDE_OFFSET
from .bases import (
    LOCATION_SECTION, NAME_SIZE, RECORD_SIZE, SIDES, Field, decode_name, is_place, place_side_id,
)
from .factories import _plain_name

GROUP_SECTION = 0x14
GROUP_RECORD_SIZE = 680
GROUP_RECORD_COUNT = 30001
# 0 = Japanese, 1 = Allied; matches the side of the base for every group at one.
SIDE_OFFSET = 26
LOCATION_OFFSET = 40
# The group's base ("Based at" on its screen). Detachments keep their parent's base or
# carrier here while they sit elsewhere.
BASE_OFFSET = 42
# Values from here up are ship id + SHIP_LOCATION_BASE (carrier and tender groups).
SHIP_LOCATION_BASE = 18000
# Ships in play, one record per ship; the name is plain text.
SHIP_SECTION = 0x08
SHIP_RECORD_SIZE = 464
SHIP_RECORD_COUNT = 20000
LEADER_SECTION = 0x15
LEADER_RECORD_SIZE = 180
LEADER_RECORD_COUNT = 50000
PILOT_SECTION = 0x16
PILOT_RECORD_SIZE = 180
PILOT_RECORD_COUNT = 70000

AIRCRAFT_OFFSET = 30
# Upgrade target, stored twice (copies); both equal the current aircraft when no upgrade is pending.
UPGRADE_OFFSET = 308
UPGRADE_COPY_OFFSET = 574
LEADER_OFFSET = 32
PLANES_OFFSET = 210
PILOT_COUNT_OFFSET = 546
PILOT_GROUP_OFFSET = 32
PILOT_AGE_OFFSET = 43
# 1 for active pilots; 2-4 are rarer (a pilot the game counts as killed in action has 2),
# probably killed/wounded/missing. Only 1 is confirmed as active.
PILOT_STATUS_OFFSET = 46
LEADER_AGE_OFFSET = 25

# fmt is a struct code: B = u8, H = u16.
GROUP_FIELDS = [
    Field("morale", "Morale", 184, "B", True, True, 0, 99),
    # The game probably recalculates this from the pilots.
    Field("experience", "Average experience", 185, "B", True, True, 0, 99),
    Field("altitude", "Current altitude", 212, "H", True, True, 0, 50000),
    Field("range", "Maximum range setting", 304, "B", True, True, 0, 99),
    # Patrol levels, in the order of the game's patrol box. ASW, Search, Train and
    # Rest were confirmed by a probe edit; CAP and LRcap follow that order.
    Field("cap", "CAP patrol %", 560, "B", True, False, 0, 100),
    Field("lrcap", "LRcap patrol %", 561, "B", True, False, 0, 100),
    Field("asw", "ASW patrol %", 562, "B", True, True, 0, 100),
    Field("search", "Search patrol %", 563, "B", True, True, 0, 100),
    Field("train", "Train patrol %", 564, "B", True, True, 0, 100),
    Field("rest", "Rest %", 565, "B", True, True, 0, 100),
    # Search arc in degrees, clockwise from start to end; stored in tens of degrees.
    Field("arc_start", "Search arc start (deg)", 630, "B", True, True, 0, 350),
    Field("arc_end", "Search arc end (deg)", 631, "B", True, True, 0, 350),
]
ARC_FIELDS = {"arc_start", "arc_end"}

SKILLS = ["Air", "NavB", "NavT", "NavS", "Recn", "ASW", "Tran", "GrdB", "LowN", "LowG", "Staf", "Defn"]
# Full names for the game's abbreviations, used where there is room for them.
SKILL_NAMES = {"Air": "Air combat", "NavB": "Naval bombing", "NavT": "Naval torpedo", "NavS": "Naval search",
               "Recn": "Reconnaissance", "ASW": "Anti-submarine", "Tran": "Transport", "GrdB": "Ground bombing",
               "LowN": "Low-level naval", "LowG": "Low-level ground", "Staf": "Strafing", "Defn": "Defensive"}
# The game's pilot list shows the second copy of the skills (78..89); the first
# copy (65..76) is normally identical and is kept in step on every write.
SKILL_OFFSET = 78
SKILL_MIRROR_OFFSET = 65
PILOT_FIELDS = [Field("experience", "Experience", 44, "B", True, True, 0, 99)] + [
    Field("skill_" + name.lower(), f"{SKILL_NAMES[name]} ({name})", SKILL_OFFSET + k, "B", True, True, 0, 99)
    for k, name in enumerate(SKILLS)
]

LEADER_FIELDS = [
    Field(name.lower(), name, 26 + k, "B", True, True, 0, 99)
    for k, name in enumerate(["Leadership", "Inspiration", "Naval", "Air", "Land", "Admin", "Aggression"])
]


class Record:
    """A record in a fixed-size table, with get/validate/set over a Field table."""
    section = record_size = None
    fields = ()

    def __init__(self, save, record_id, name):
        self._save = save
        self.id = record_id
        self.name = name

    @property
    def _data(self):
        return self._save[self.section].data

    @property
    def _offset(self):
        return self.id * self.record_size

    def _field(self, name):
        for f in self.fields:
            if f.name == name:
                return f
        raise ValueError(f"unknown field {name!r}")

    def get(self, name):
        f = self._field(name)
        return struct.unpack_from("<" + f.fmt, self._data, self._offset + f.offset)[0]

    def validate(self, name, value):
        """Return value as a checked int, or raise ValueError naming the field."""
        f = self._field(name)
        if not f.editable:
            raise ValueError(f"{f.label} is read-only")
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{f.label} must be an integer")
        if not f.min <= value <= f.max:
            raise ValueError(f"{f.label} must be between {f.min} and {f.max}")
        return value

    def set(self, name, value):
        value = self.validate(name, value)
        f = self._field(name)
        struct.pack_into("<" + f.fmt, self._data, self._offset + f.offset, value)
        mirror = self._mirror(f)
        if mirror is not None:
            struct.pack_into("<" + f.fmt, self._data, self._offset + mirror, value)

    def _mirror(self, field):
        return None

    def set_many(self, values):
        """Validate everything first so a bad value never leaves a partial edit."""
        checked = {name: self.validate(name, v) for name, v in values.items()}
        for name, v in checked.items():
            self.set(name, v)

    def _i16(self, pos):
        return struct.unpack_from("<h", self._data, self._offset + pos)[0]

    def _u8(self, pos):
        return self._data[self._offset + pos]


class AirGroup(Record):
    section, record_size, fields = GROUP_SECTION, GROUP_RECORD_SIZE, GROUP_FIELDS

    def get(self, name):
        value = super().get(name)
        return value * 10 if name in ARC_FIELDS else value

    def validate(self, name, value):
        value = super().validate(name, value)
        if name in ARC_FIELDS and value % 10:
            raise ValueError(f"{self._field(name).label} must be a multiple of 10")
        return value

    def set(self, name, value):
        if name not in ARC_FIELDS:
            super().set(name, value)
            return
        value = self.validate(name, value)
        self._data[self._offset + self._field(name).offset] = value // 10

    @property
    def aircraft_id(self):
        return self._i16(AIRCRAFT_OFFSET)

    @property
    def aircraft_name(self):
        return self._aircraft_name(self.aircraft_id)

    def _aircraft_name(self, aid):
        data = self._save[AIRCRAFT_SECTION].data
        if not 0 <= aid < len(data) // AIRCRAFT_RECORD_SIZE:
            return ""
        return _plain_name(data, aid * AIRCRAFT_RECORD_SIZE)

    @property
    def leader_id(self):
        return self._i16(LEADER_OFFSET)

    @property
    def location_id(self):
        return self._i16(LOCATION_OFFSET)

    @property
    def location_name(self):
        loc = self.location_id
        if is_place(self._save, loc):
            start = loc * RECORD_SIZE
            return decode_name(self._save[LOCATION_SECTION].data[start:start + NAME_SIZE])
        if loc >= SHIP_LOCATION_BASE:
            ship_id = loc - SHIP_LOCATION_BASE
            data = self._save[SHIP_SECTION].data
            start = ship_id * SHIP_RECORD_SIZE
            name = _plain_name(data, start) if ship_id < SHIP_RECORD_COUNT and start < len(data) else ""
            return name or f"ship #{ship_id}"
        return ""

    @property
    def move_blocker(self):
        """Why the group cannot be moved, or "" when it can."""
        if is_place(self._save, self.location_id):
            return ""
        if self.location_id >= SHIP_LOCATION_BASE:
            return "aboard a ship"
        return "not arrived"

    @property
    def can_move(self):
        return not self.move_blocker

    @property
    def side(self):
        return SIDES.get(self._u8(SIDE_OFFSET), "Unknown")

    def move_to(self, place_id):
        """Move to a base or town on the same side; the base follows unless it already differed."""
        if self.move_blocker:
            raise ValueError(f"{self.name} cannot be moved: {self.move_blocker}")
        if not is_place(self._save, place_id):
            raise ValueError(f"{place_id!r} is not a base or town")
        if place_side_id(self._save, place_id) != place_side_id(self._save, self.location_id):
            raise ValueError(f"{self.name} can only move to a place on its own side")
        if self._i16(BASE_OFFSET) == self.location_id:
            struct.pack_into("<h", self._data, self._offset + BASE_OFFSET, place_id)
        struct.pack_into("<h", self._data, self._offset + LOCATION_OFFSET, place_id)

    @property
    def upgrade_id(self):
        return self._i16(UPGRADE_OFFSET)

    @property
    def upgrade_name(self):
        return self._aircraft_name(self.upgrade_id)

    def set_aircraft(self, aircraft_id):
        """Change the aircraft type (the editor's "Air Class") to a model of the group's own side.

        Writes only the aircraft id; plane counts and the upgrade target are untouched.
        """
        self._check_aircraft(aircraft_id)
        struct.pack_into("<h", self._data, self._offset + AIRCRAFT_OFFSET, aircraft_id)

    def set_upgrade(self, aircraft_id):
        """Set the upgrade target to a model of the group's own side; writes both stored copies."""
        self._check_aircraft(aircraft_id)
        for pos in (UPGRADE_OFFSET, UPGRADE_COPY_OFFSET):
            struct.pack_into("<h", self._data, self._offset + pos, aircraft_id)

    def _check_aircraft(self, aircraft_id):
        """Raise ValueError unless this is a named aircraft record of the group's side."""
        if isinstance(aircraft_id, bool) or not isinstance(aircraft_id, int):
            raise ValueError("aircraft id must be an integer")
        data = self._save[AIRCRAFT_SECTION].data
        if not 0 < aircraft_id < min(AIRCRAFT_RECORD_COUNT, len(data) // AIRCRAFT_RECORD_SIZE):
            raise ValueError(f"{aircraft_id!r} is not an aircraft")
        start = aircraft_id * AIRCRAFT_RECORD_SIZE
        if not _plain_name(data, start):
            raise ValueError(f"{aircraft_id!r} is not an aircraft")
        if data[start + AIRCRAFT_SIDE_OFFSET] != self._u8(SIDE_OFFSET):
            raise ValueError(f"{aircraft_id} is not an {self.side} aircraft")

    @property
    def planes(self):
        return self._u8(PLANES_OFFSET)

    @property
    def pilot_count(self):
        return self._u8(PILOT_COUNT_OFFSET)


class Pilot(Record):
    section, record_size, fields = PILOT_SECTION, PILOT_RECORD_SIZE, PILOT_FIELDS

    def _mirror(self, field):
        if field.name.startswith("skill_"):
            return field.offset - SKILL_OFFSET + SKILL_MIRROR_OFFSET
        return None

    @property
    def group_id(self):
        return self._i16(PILOT_GROUP_OFFSET)

    @property
    def age(self):
        return self._u8(PILOT_AGE_OFFSET)

    @property
    def status(self):
        return self._u8(PILOT_STATUS_OFFSET)

    @property
    def status_label(self):
        return "Active" if self.status == 1 else f"Status {self.status}"


class Leader(Record):
    section, record_size, fields = LEADER_SECTION, LEADER_RECORD_SIZE, LEADER_FIELDS

    @property
    def age(self):
        return self._u8(LEADER_AGE_OFFSET)


def list_airgroups(save):
    data = save[GROUP_SECTION].data
    out = []
    for group_id in range(min(GROUP_RECORD_COUNT, len(data) // GROUP_RECORD_SIZE)):
        start = group_id * GROUP_RECORD_SIZE
        name = decode_name(data[start:start + NAME_SIZE])
        if name:
            out.append(AirGroup(save, group_id, name))
    return out


def pilots_by_group(save):
    """{group id: [Pilot, ...]} for every named pilot, built in one scan of the table."""
    data = save[PILOT_SECTION].data
    index = {}
    for pilot_id in range(min(PILOT_RECORD_COUNT, len(data) // PILOT_RECORD_SIZE)):
        start = pilot_id * PILOT_RECORD_SIZE
        if data[start] == 0:
            continue
        name = _plain_name(data, start)
        if name:
            group = struct.unpack_from("<h", data, start + PILOT_GROUP_OFFSET)[0]
            index.setdefault(group, []).append(Pilot(save, pilot_id, name))
    return index


def get_leader(save, leader_id):
    """The commander with this id, or None for 0, an out-of-range id or an unnamed record."""
    data = save[LEADER_SECTION].data
    if not 0 < leader_id < min(LEADER_RECORD_COUNT, len(data) // LEADER_RECORD_SIZE):
        return None
    name = _plain_name(data, leader_id * LEADER_RECORD_SIZE)
    return Leader(save, leader_id, name) if name else None
