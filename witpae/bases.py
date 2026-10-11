"""Bases in the location table (section 0x13) of a WitP:AE save.

The table holds 18000 fixed-size records indexed by location id. Bases, land
units and HQs all live in it; the int16 at offset 28 is the record type and
type 1 is a base. Views here read and write the section's bytearray in place,
so the SaveFile stays the single source of truth.
"""

import struct
from collections import namedtuple

from .blowfish import Blowfish

LOCATION_SECTION = 0x13
INDEX_SECTION = 0x12
TITLE_SECTION = 0x26

RECORD_SIZE = 1172
RECORD_COUNT = 18000
INDEX_RECORD_SIZE = 20
TYPE_OFFSET = 28
TYPE_BASE = 1
NAME_SIZE = 24
NAME_KEY = b"AdmiralEdition"
X_OFFSET = 36
Y_OFFSET = 38
SIDE_OFFSET = 8  # within the 20-byte record of the location index section

SIDES = {0: "Japanese", 1: "Allied"}

# The game's old title string area; other data starts at byte 1000.
TITLE_AREA = 1000
MAX_VALUE = 99999999

Field = namedtuple("Field", "name label offset fmt editable verified min max")

# One row per field; adding a field to the editor is adding a row here.
FIELDS = [
    Field("supply", "Supply", 536, "i", True, True, 0, MAX_VALUE),
    Field("fuel", "Fuel", 528, "i", True, True, 0, MAX_VALUE),
    Field("port", "Port size", 422, "h", True, True, 0, 10),
    Field("airfield", "Airfield size", 426, "h", True, True, 0, 10),
    # The bracketed max sizes on the base screen; current size may exceed them.
    Field("port_max", "Port max", 420, "h", True, True, 0, 10),
    Field("airfield_max", "Airfield max", 416, "h", True, True, 0, 10),
    Field("resources", "Resource storage", 508, "i", True, True, 0, MAX_VALUE),
    Field("oil", "Oil storage", 520, "i", True, True, 0, MAX_VALUE),
    Field("forts", "Forts", 430, "h", True, True, 0, 9),
    Field("port_damage", "Port damage", 442, "h", True, True, 0, 100),
    Field("runway_damage", "Airfield runway damage", 440, "h", True, True, 0, 100),
    Field("service_damage", "Airfield service damage", 444, "h", True, True, 0, 100),
    Field("fuel_requested", "Fuel requested", 532, "i", True, True, 0, MAX_VALUE),
    # Recalculated by the game every turn, so editing it would not stick.
    Field("supply_required", "Supply required", 540, "i", False, True, None, None),
    # Bracketed multipliers on "Value to Japan/Allies"; the game shows base value x multiplier.
    Field("value_japan", "Value to Japan (x)", 782, "h", True, True, 0, 1000),
    Field("value_allies", "Value to Allies (x)", 784, "h", True, True, 0, 1000),
    Field("aviation_support", "Aviation support", 560, "i", False, True, None, None),
    Field("ships_in_port", "Ships in port", 656, "h", False, True, None, None),
    Field("aircraft", "Aircraft at base", 584, "h", False, True, None, None),
]
FIELD_BY_NAME = {f.name: f for f in FIELDS}

_cipher = None


def _name_cipher():
    global _cipher
    if _cipher is None:
        _cipher = Blowfish(NAME_KEY)
    return _cipher


def decode_name(record):
    """Decrypt a record's name, block by block, until a NUL or an empty block."""
    cipher = _name_cipher()
    out = b""
    for pos in range(0, NAME_SIZE, 8):
        block = bytes(record[pos:pos + 8])
        if block == bytes(8):
            break
        plain = cipher.decrypt(block)
        if b"\0" in plain:
            out += plain.split(b"\0", 1)[0]
            break
        out += plain
    return out.decode("latin-1")


class Base:
    def __init__(self, save, loc_id, name):
        self._save = save
        self.id = loc_id
        self.name = name

    @property
    def _offset(self):
        return self.id * RECORD_SIZE

    @property
    def side_id(self):
        pos = self.id * INDEX_RECORD_SIZE + SIDE_OFFSET
        return struct.unpack_from("<i", self._save[INDEX_SECTION].data, pos)[0]

    @property
    def side(self):
        return SIDES.get(self.side_id, "Unknown")

    @property
    def x(self):
        return struct.unpack_from("<h", self._save[LOCATION_SECTION].data, self._offset + X_OFFSET)[0]

    @property
    def y(self):
        return struct.unpack_from("<h", self._save[LOCATION_SECTION].data, self._offset + Y_OFFSET)[0]

    def get(self, name):
        f = FIELD_BY_NAME[name]
        return struct.unpack_from("<" + f.fmt, self._save[LOCATION_SECTION].data, self._offset + f.offset)[0]

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
        struct.pack_into("<" + f.fmt, self._save[LOCATION_SECTION].data, self._offset + f.offset, value)

    def set_many(self, values):
        """Validate everything first so a bad value never leaves a partial edit."""
        checked = {name: self.validate(name, v) for name, v in values.items()}
        for name, v in checked.items():
            self.set(name, v)


def list_bases(save):
    data = save[LOCATION_SECTION].data
    bases = []
    for loc_id in range(min(RECORD_COUNT, len(data) // RECORD_SIZE)):
        start = loc_id * RECORD_SIZE
        if struct.unpack_from("<h", data, start + TYPE_OFFSET)[0] != TYPE_BASE:
            continue
        bases.append(Base(save, loc_id, decode_name(data[start:start + NAME_SIZE])))
    return bases


def set_title(save, title):
    """Overwrite the save title, zero-padding the rest of the old string area."""
    try:
        raw = title.encode("latin-1")
    except UnicodeEncodeError:
        raise ValueError("title must be latin-1 text") from None
    if b"\0" in raw:
        raise ValueError("title must not contain NUL characters")
    if len(raw) >= TITLE_AREA:
        raise ValueError(f"title must be shorter than {TITLE_AREA} bytes")
    data = save[TITLE_SECTION].data
    data[0:TITLE_AREA] = raw + bytes(TITLE_AREA - len(raw))
