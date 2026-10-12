"""Air groups (section 0x14), their pilots (0x16) and commanders (0x15).

Group records are indexed by the group number shown in the game and have
encrypted names like base names. Pilots and commanders have plain names. Views
read and write the section bytearrays in place. Only the first copy of each
pilot skill is written; the byte copy at 78..89 and the byte at 122 are left
alone because their purpose is unknown.
"""

import struct

from .aircraft import AIRCRAFT_RECORD_SIZE, AIRCRAFT_SECTION
from .bases import NAME_SIZE, Field, decode_name
from .factories import _plain_name

GROUP_SECTION = 0x14
GROUP_RECORD_SIZE = 680
GROUP_RECORD_COUNT = 30001
LEADER_SECTION = 0x15
LEADER_RECORD_SIZE = 180
LEADER_RECORD_COUNT = 50000
PILOT_SECTION = 0x16
PILOT_RECORD_SIZE = 180
PILOT_RECORD_COUNT = 70000

AIRCRAFT_OFFSET = 30
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
    Field("train", "Train patrol %", 564, "B", True, False, 0, 100),
]

SKILLS = ["Air", "NavB", "NavT", "NavS", "Recn", "ASW", "Tran", "GrdB", "LowN", "LowG", "Staf", "Defn"]
# The game's pilot list shows the second copy of the skills (78..89); the first
# copy (65..76) is normally identical and is kept in step on every write.
SKILL_OFFSET = 78
SKILL_MIRROR_OFFSET = 65
PILOT_FIELDS = [Field("experience", "Experience", 44, "B", True, True, 0, 99)] + [
    Field("skill_" + name.lower(), name, SKILL_OFFSET + k, "B", True, True, 0, 99)
    for k, name in enumerate(SKILLS)
]

LEADER_FIELDS = [
    Field(name.lower(), name, 26 + k, "B", True, True, 0, 99)
    for k, name in enumerate(["Leadership", "Inspiration", "Naval", "Air", "Land", "Admin", "Aggression"])
]


class _Record:
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


class AirGroup(_Record):
    section, record_size, fields = GROUP_SECTION, GROUP_RECORD_SIZE, GROUP_FIELDS

    @property
    def aircraft_id(self):
        return self._i16(AIRCRAFT_OFFSET)

    @property
    def aircraft_name(self):
        aid = self.aircraft_id
        data = self._save[AIRCRAFT_SECTION].data
        if not 0 <= aid < len(data) // AIRCRAFT_RECORD_SIZE:
            return ""
        return _plain_name(data, aid * AIRCRAFT_RECORD_SIZE)

    @property
    def leader_id(self):
        return self._i16(LEADER_OFFSET)

    @property
    def planes(self):
        return self._u8(PLANES_OFFSET)

    @property
    def pilot_count(self):
        return self._u8(PILOT_COUNT_OFFSET)


class Pilot(_Record):
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


class Leader(_Record):
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
