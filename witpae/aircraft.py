"""Aircraft models in the aircraft table (section 0x20) of a WitP:AE save.

1000 fixed-size records indexed by aircraft id; an empty name marks an unused
record. Several records can share a name (one per nation), so the id is the
identity. Views read and write the section's bytearray in place. Weapons refer
to records of the device table (section 0x1F).
"""

import struct

from .bases import Field
from .nations import label as lookup_label, nation_label
from .factories import (
    AIRCRAFT_MONTH_OFFSET, AIRCRAFT_RECORD_SIZE, AIRCRAFT_SECTION, AIRCRAFT_SIDE_OFFSET, AIRCRAFT_YEAR_OFFSET,
    DEVICE_RECORD_SIZE, DEVICE_SECTION, _plain_name,
)

RECORD_COUNT = 1000
TYPE_OFFSET = 25
UPGRADE_OFFSET = 26
NATION_OFFSET = 284
# 0 = Japanese, 1 = Allied; matches the side of every group flying the model.
SIDE_OFFSET = AIRCRAFT_SIDE_OFFSET
CARRIER_OFFSET = 232
CARRIER_BIT = 0x08
TO_MONTH_OFFSET = 282
TO_YEAR_OFFSET = 283

# fmt is a struct code: H = u16, h = i16, B = u8.
FIELDS = [
    Field("max_alt", "Max altitude", 28, "H", True, True, 0, 60000),
    Field("speed", "Max speed", 30, "h", True, True, 0, 1000),
    Field("cruise", "Cruise speed", 32, "h", True, True, 0, 1000),
    Field("climb", "Climb", 34, "h", True, True, 0, 20000),
    Field("maneuver", "Maneuver", 36, "h", True, True, 0, 100),
    Field("armor", "Armor", 40, "B", True, True, 0, 10),
    Field("durability", "Durability", 41, "B", True, True, 0, 255),
    Field("load", "Load", 182, "h", True, True, 0, 30000),
    # Monthly production rate shown as "Rate" on the aircraft and engine production screen.
    Field("rate", "Production rate", 188, "h", True, True, 0, 1000),
]
SCALAR_FIELDS = list(FIELDS)  # FIELDS minus the range pairs below, for the editor layout
# Each range is a (hexes, miles) pair stored and shown independently by the game.
RANGES = [
    ("max_range", "Max range", 186, 280),
    ("normal_radius", "Normal radius", 276, 278),
    ("extended_radius", "Extended radius", 288, 290),
    ("max_range_tanks", "Max range (drop tanks)", 302, 304),
    ("normal_radius_tanks", "Normal radius (drop tanks)", 294, 296),
    ("extended_radius_tanks", "Extended radius (drop tanks)", 298, 300),
]
for _name, _label, _hex, _miles in RANGES:
    FIELDS.append(Field(_name + "_hex", _label + " hexes", _hex, "h", True, True, 0, 200))
    FIELDS.append(Field(_name + "_miles", _label + " miles", _miles, "h", True, True, 0, 10000))
FIELD_BY_NAME = {f.name: f for f in FIELDS}

# name -> (month offset, year offset); both are u8, the year has two digits.
DATES = {
    "from": (AIRCRAFT_MONTH_OFFSET, AIRCRAFT_YEAR_OFFSET),
    "to": (TO_MONTH_OFFSET, TO_YEAR_OFFSET),
}

# Only Fighter and Dive Bomber have been confirmed in game; the
# other types are guesses and are shown with a trailing "?".
TYPES = {0: "Fighter", 3: "Dive Bomber"}
GUESSED_TYPES = {1: "Fighter-Bomber", 2: "Night Fighter", 4: "Level Bomber", 5: "Recon",
                 8: "Transport", 9: "Patrol", 10: "Float Plane", 11: "Float Fighter",
                 12: "Torpedo Bomber"}

SLOTS = 10
# (device id, count, facing) offsets of the max-load and reduced-load tables.
MAX_LOAD = (42, 82, 122)
REDUCED_LOAD = (62, 102, 132)
FACINGS = {0: "F", 5: "TR", 8: "C", 12: "XT"}
# The engine is weapon slot 9 of the max-load table: device id and count. The reduced-load
# copies (@80, @120) are never written.
ENGINE_OFFSET = 60
ENGINE_COUNT_OFFSET = 100

DEVICE_TYPE_OFFSET = 26  # 0 = aircraft gun; bombs are 3, drop tanks 5, engines 27
DEVICE_EFFECT_OFFSET = 32

MANEUVER_MOD_OFFSET = 271
MANEUVER_MOD_BANDS = ["<10K", "10-15K", "16-20K", "21-31K", ">32K"]
# The game ignores the stored endurance (@38) and derives it from range and cruise
# speed: miles / (cruise / 60 / 1.15) truncated. Integer maths avoids float error.


# Side-wide production pool, in section 0x01 and indexed by aircraft id:
# (offset of entry 0, stride, paired). Paired tables hold a (Japan, Allies) i32 pair per
# aircraft, read with the model's side; the Allied half was verified against the production screen.
POOL_SECTION = 0x01
POOL = (184, 8, True)
USED = (28184, 8, True)
LAST_TURN = (65848, 4, False)
THIS_MONTH = (69848, 4, False)
MAX_POOL = 99999


def check_pool(value):
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= MAX_POOL:
        raise ValueError(f"In pool must be a whole number from 0 to {MAX_POOL}")
    return value


def type_label(type_id):
    return lookup_label(type_id, TYPES, GUESSED_TYPES)


def parse_date(text):
    """Parse "m/yy" into (month, year); "0/0" or "-" mean no date and give (0, 0)."""
    text = text.strip()
    if text == "-":
        return 0, 0
    parts = text.split("/")
    if len(parts) != 2 or not all(p.strip().isdigit() for p in parts):
        raise ValueError(f"date must look like m/yy, e.g. 12/41 (got {text!r})")
    month, year = int(parts[0]), int(parts[1])
    if (month, year) == (0, 0):
        return 0, 0
    if not 1 <= month <= 12:
        raise ValueError("date month must be between 1 and 12")
    if not 0 <= year <= 99:
        raise ValueError("date year must be between 0 and 99")
    return month, year


def format_date(month, year):
    return "-" if (month, year) == (0, 0) else f"{month}/{year:02d}"


def _check_date(name, value):
    if name not in DATES:
        raise ValueError(f"unknown date {name!r}")
    if (not isinstance(value, tuple) or len(value) != 2
            or any(isinstance(v, bool) or not isinstance(v, int) for v in value)):
        raise ValueError(f"{name} date must be a (month, year) pair of integers")
    month, year = value
    if (month, year) != (0, 0) and not 1 <= month <= 12:
        raise ValueError("date month must be between 1 and 12")
    if not 0 <= year <= 99:
        raise ValueError("date year must be between 0 and 99")
    return value


class Aircraft:
    def __init__(self, save, aircraft_id, name):
        self._save = save
        self.id = aircraft_id
        self.name = name

    @property
    def _data(self):
        return self._save[AIRCRAFT_SECTION].data

    @property
    def _offset(self):
        return self.id * AIRCRAFT_RECORD_SIZE

    def _u8(self, pos):
        return self._data[self._offset + pos]

    def _i16(self, pos):
        return struct.unpack_from("<h", self._data, self._offset + pos)[0]

    def get(self, name):
        f = FIELD_BY_NAME[name]
        return struct.unpack_from("<" + f.fmt, self._data, self._offset + f.offset)[0]

    def validate(self, name, value):
        """Return value as a checked int, or raise ValueError naming the field."""
        f = FIELD_BY_NAME.get(name)
        if f is None:
            raise ValueError(f"unknown field {name!r}")
        if not f.editable:
            raise ValueError(f"{f.label} is read-only")
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{f.label} must be an integer")
        if not f.min <= value <= f.max:
            raise ValueError(f"{f.label} must be between {f.min} and {f.max}")
        return value

    def set(self, name, value):
        value = self.validate(name, value)
        f = FIELD_BY_NAME[name]
        struct.pack_into("<" + f.fmt, self._data, self._offset + f.offset, value)

    def set_many(self, values):
        """Validate everything first so a bad value never leaves a partial edit."""
        checked = {name: self.validate(name, v) for name, v in values.items()}
        for name, v in checked.items():
            self.set(name, v)

    def get_date(self, name):
        """(month, year) of the "from" or "to" availability date; (0, 0) means none."""
        month, year = DATES[name]
        return self._u8(month), self._u8(year)

    def set_date(self, name, value):
        month, year = _check_date(name, value)
        month_pos, year_pos = DATES[name]
        self._data[self._offset + month_pos] = month
        self._data[self._offset + year_pos] = year

    def get_carrier(self):
        return bool(self._u8(CARRIER_OFFSET) & CARRIER_BIT)

    def set_carrier(self, value):
        """Set the carrier bit only; the other bits of the byte are of unknown meaning."""
        if not isinstance(value, bool):
            raise ValueError("Carrier capable must be True or False")
        pos = self._offset + CARRIER_OFFSET
        byte = self._data[pos]
        self._data[pos] = (byte | CARRIER_BIT) if value else (byte & ~CARRIER_BIT & 0xFF)

    def _pool_pos(self, table):
        start, stride, paired = table
        return start + self.id * stride + (4 * self.side_id if paired else 0)

    def _pool_value(self, table):
        return struct.unpack_from("<i", self._save[POOL_SECTION].data, self._pool_pos(table))[0]

    @property
    def pool(self):
        return self._pool_value(POOL)

    def set_pool(self, value):
        value = check_pool(value)
        struct.pack_into("<i", self._save[POOL_SECTION].data, self._pool_pos(POOL), value)

    # ---- read-only ------------------------------------------------------

    @property
    def used(self):
        return self._pool_value(USED)

    @property
    def last_turn(self):
        """Aircraft produced last turn."""
        return self._pool_value(LAST_TURN)

    @property
    def this_month(self):
        """Aircraft produced so far this month."""
        return self._pool_value(THIS_MONTH)

    @property
    def type_id(self):
        return self._u8(TYPE_OFFSET)

    @property
    def type(self):
        return type_label(self.type_id)

    @property
    def side_id(self):
        return self._u8(SIDE_OFFSET)

    @property
    def nation_id(self):
        return self._u8(NATION_OFFSET)

    @property
    def nation(self):
        return nation_label(self.nation_id)

    @property
    def upgrade_id(self):
        return self._i16(UPGRADE_OFFSET)

    @property
    def upgrade_name(self):
        """Name of the record the upgrade field points at (meaning unverified), or ""."""
        up = self.upgrade_id
        if not 0 <= up < RECORD_COUNT:
            return ""
        return _plain_name(self._data, up * AIRCRAFT_RECORD_SIZE)

    def _device(self, device_id):
        return device_id * DEVICE_RECORD_SIZE

    def _weapons(self, table):
        dev_off, count_off, facing_off = table
        devices = self._save[DEVICE_SECTION].data
        out = []
        for k in range(SLOTS):
            device_id = self._i16(dev_off + 2 * k)
            if device_id == 0:
                continue
            facing = self._u8(facing_off + k)
            out.append((_plain_name(devices, self._device(device_id)), self._i16(count_off + 2 * k),
                        FACINGS.get(facing, str(facing))))
        return out

    @property
    def max_weapons(self):
        return self._weapons(MAX_LOAD)

    @property
    def reduced_weapons(self):
        return self._weapons(REDUCED_LOAD)

    @property
    def gun_value(self):
        """Sum of effect x count over the max-load aircraft guns, as the game shows it."""
        devices = self._save[DEVICE_SECTION].data
        total = 0
        for k in range(SLOTS):
            device_id = self._i16(MAX_LOAD[0] + 2 * k)
            if device_id == 0:
                continue
            start = self._device(device_id)
            if struct.unpack_from("<h", devices, start + DEVICE_TYPE_OFFSET)[0] == 0:
                total += (struct.unpack_from("<h", devices, start + DEVICE_EFFECT_OFFSET)[0]
                          * self._i16(MAX_LOAD[1] + 2 * k))
        return total

    @property
    def engine_id(self):
        """Device id of the engine: a specific engine for Japanese models, the generic "Engine" for Allied ones."""
        return self._i16(ENGINE_OFFSET)

    @property
    def engine_count(self):
        return self._u8(ENGINE_COUNT_OFFSET)

    @property
    def engine_name(self):
        devices = self._save[DEVICE_SECTION].data
        if not 0 < self.engine_id < len(devices) // DEVICE_RECORD_SIZE:
            return ""
        return _plain_name(devices, self._device(self.engine_id))

    @property
    def engines_text(self):
        """"2 x Nakajima Ha-5" for Japanese models, "2 engines" for Allied ones (generic engine)."""
        count = self.engine_count
        if count == 0:
            return "-"
        if self.side_id == 1:
            return f"{count} engine{'' if count == 1 else 's'}"
        return f"{count} x {self.engine_name}"

    @property
    def maneuver_mods(self):
        return [self._u8(MANEUVER_MOD_OFFSET + k) for k in range(len(MANEUVER_MOD_BANDS))]

    @property
    def endurance(self):
        """Endurance in minutes as the game displays it (miles at 1.15 mph per knot), or None at cruise 0."""
        cruise = self.get("cruise")
        miles = self.get("max_range_tanks_miles") or self.get("max_range_miles")
        if cruise <= 0:
            return None
        return miles * 60 * 115 // (cruise * 100)


def list_aircraft(save):
    data = save[AIRCRAFT_SECTION].data
    out = []
    for aircraft_id in range(min(RECORD_COUNT, len(data) // AIRCRAFT_RECORD_SIZE)):
        name = _plain_name(data, aircraft_id * AIRCRAFT_RECORD_SIZE)
        if name:
            out.append(Aircraft(save, aircraft_id, name))
    return out
