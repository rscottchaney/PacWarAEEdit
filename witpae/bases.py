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
TYPE_TOWN = 5
# Records a unit can be located at: bases and named towns.
PLACE_TYPES = (TYPE_BASE, TYPE_TOWN)
NAME_SIZE = 24
NAME_KEY = b"AdmiralEdition"
X_OFFSET = 36
Y_OFFSET = 38
SIDE_OFFSET = 8  # within the 20-byte record of the location index section
# Map position in pixels, i32 x at 0 and y at 4 of the index record.
PIXEL_X_OFFSET = 0
PIXEL_Y_OFFSET = 4

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
    # u16. The base screen shows the cap as "Supply (max 500)".
    Field("supply_cap", "Supply cap", 1116, "H", True, True, 0, 65535),
    Field("garrison_allied", "Garrison required (Allied)", 978, "H", True, True, 0, 65535),
    # Not checked against a Japanese-held base yet.
    Field("garrison_japanese", "Garrison required (Japanese)", 902, "H", True, False, 0, 65535),
]
FIELD_BY_NAME = {f.name: f for f in FIELDS}

# Yes/No switches from the base screen share one bitfield byte. Kept apart from
# FIELDS because the names clash with the supply/fuel quantity fields. Bits
# 0x10-0x80 are of unknown meaning and are preserved on write.
STOCKPILE_OFFSET = 109
STOCKPILE_FLAGS = [
    ("supply", "Supply", 0x08),
    ("fuel", "Fuel", 0x04),
    ("resources", "Resources", 0x02),
    ("oil", "Oil", 0x01),
]
STOCKPILE_BY_NAME = {name: bit for name, _label, bit in STOCKPILE_FLAGS}

# Build/expand switches: (name, label, live offset, saved-copy offset), all int16.
# The live value is 0 when switched off; switching on in the game copies the
# saved value back, and switching off leaves the copy alone. Neither is the size.
BUILD_SWITCHES = [
    ("port", "Port", 424, 866),
    ("airfield", "Airfield", 428, 864),
    ("forts", "Forts", 432, 868),
]
BUILD_BY_NAME = {name: (live, copy) for name, _label, live, copy in BUILD_SWITCHES}

# Towns have no port (every port field is 0 on them), so these stay read-only there.
TOWN_READONLY_FIELDS = ("port", "port_max", "port_damage")

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
    def kind(self):
        t = struct.unpack_from("<h", self._save[LOCATION_SECTION].data, self._offset + TYPE_OFFSET)[0]
        return "Town" if t == TYPE_TOWN else "Base"

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
        if name in TOWN_READONLY_FIELDS and self.kind == "Town":
            raise ValueError(f"{f.label} is read-only for towns")
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

    def get_stockpile(self):
        byte = self._save[LOCATION_SECTION].data[self._offset + STOCKPILE_OFFSET]
        return {name: bool(byte & bit) for name, _label, bit in STOCKPILE_FLAGS}

    def set_stockpile(self, flags):
        """Set some or all switches, leaving other bits alone; validate before writing."""
        for name, value in flags.items():
            if name not in STOCKPILE_BY_NAME:
                raise ValueError(f"unknown stockpile switch {name!r}")
            if not isinstance(value, bool):
                raise ValueError(f"stockpile switch {name!r} must be True or False")
        data = self._save[LOCATION_SECTION].data
        pos = self._offset + STOCKPILE_OFFSET
        byte = data[pos]
        for name, value in flags.items():
            bit = STOCKPILE_BY_NAME[name]
            byte = (byte | bit) if value else (byte & ~bit & 0xFF)
        data[pos] = byte

    def get_building(self):
        data = self._save[LOCATION_SECTION].data
        return {name: struct.unpack_from("<h", data, self._offset + live)[0] != 0
                for name, _label, live, _copy in BUILD_SWITCHES}

    def set_building(self, flags):
        """Switch building on or off the way the game does; validate before writing."""
        for name, value in flags.items():
            if name not in BUILD_BY_NAME:
                raise ValueError(f"unknown build switch {name!r}")
            if not isinstance(value, bool):
                raise ValueError(f"build switch {name!r} must be True or False")
            if name == "port" and self.kind == "Town":
                raise ValueError("Port build switch is read-only for towns")
        data = self._save[LOCATION_SECTION].data
        for name, value in flags.items():
            live, copy = (self._offset + off for off in BUILD_BY_NAME[name])
            current = struct.unpack_from("<h", data, live)[0]
            if not value:
                struct.pack_into("<h", data, live, 0)
            elif current == 0:
                # A copy of 0 would read back as off, so fall back to 1 as seen at fresh bases.
                struct.pack_into("<h", data, live, max(struct.unpack_from("<h", data, copy)[0], 1))


def list_bases(save, include_towns=False):
    types = (TYPE_BASE, TYPE_TOWN) if include_towns else (TYPE_BASE,)
    data = save[LOCATION_SECTION].data
    bases = []
    for loc_id in range(min(RECORD_COUNT, len(data) // RECORD_SIZE)):
        start = loc_id * RECORD_SIZE
        if struct.unpack_from("<h", data, start + TYPE_OFFSET)[0] not in types:
            continue
        bases.append(Base(save, loc_id, decode_name(data[start:start + NAME_SIZE])))
    return bases


Place = namedtuple("Place", "id name side_id x y")


def list_places(save):
    """Every base and named town, as Place tuples, in id order."""
    data = save[LOCATION_SECTION].data
    places = []
    for loc_id in range(min(RECORD_COUNT, len(data) // RECORD_SIZE)):
        start = loc_id * RECORD_SIZE
        if struct.unpack_from("<h", data, start + TYPE_OFFSET)[0] not in PLACE_TYPES:
            continue
        places.append(Place(loc_id, decode_name(data[start:start + NAME_SIZE]), place_side_id(save, loc_id),
                            struct.unpack_from("<h", data, start + X_OFFSET)[0],
                            struct.unpack_from("<h", data, start + Y_OFFSET)[0]))
    return places


def is_place(save, loc_id):
    data = save[LOCATION_SECTION].data
    if isinstance(loc_id, bool) or not isinstance(loc_id, int) or not 0 <= loc_id < RECORD_COUNT:
        return False
    start = loc_id * RECORD_SIZE
    return (start + RECORD_SIZE <= len(data)
            and struct.unpack_from("<h", data, start + TYPE_OFFSET)[0] in PLACE_TYPES)


def place_side_id(save, loc_id):
    return struct.unpack_from("<i", save[INDEX_SECTION].data, loc_id * INDEX_RECORD_SIZE + SIDE_OFFSET)[0]


def place_pixel(save, loc_id):
    return struct.unpack_from("<2i", save[INDEX_SECTION].data, loc_id * INDEX_RECORD_SIZE + PIXEL_X_OFFSET)


def place_hex(save, loc_id):
    pos = loc_id * RECORD_SIZE
    data = save[LOCATION_SECTION].data
    return (struct.unpack_from("<h", data, pos + X_OFFSET)[0], struct.unpack_from("<h", data, pos + Y_OFFSET)[0])


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
