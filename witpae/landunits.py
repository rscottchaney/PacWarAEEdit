"""Land units in the location table (section 0x13) of a WitP:AE save.

Bases, land units and task forces share the table; the int16 at offset 28 is
the record type. Names are stored without the unit-kind suffix the game
appends. Views read and write the section's bytearray in place, so edits made
here and in the Bases tab never touch each other's records. Equipment device
ids and the TOE (table of organisation) columns are read-only.
"""

import struct

from .airgroups import Record
from .bases import (
    INDEX_RECORD_SIZE, INDEX_SECTION, LOCATION_SECTION, MAX_VALUE, NAME_SIZE, RECORD_COUNT,
    RECORD_SIZE, SIDE_OFFSET, SIDES, TYPE_OFFSET, Field, decode_name,
)
from .factories import DEVICE_RECORD_SIZE, DEVICE_SECTION, _plain_name

# Type labels; GUESSED_TYPES are not confirmed and are shown with a trailing "?".
TYPES = {4: "HQ", 7: "INF", 9: "ART", 10: "ENG", 11: "CD"}
GUESSED_TYPES = {3: "AA", 8: "ARM"}
LAND_TYPES = frozenset(TYPES) | frozenset(GUESSED_TYPES)

HQ_OFFSET = 122
LOCATION_OFFSET = 86
TARGET_OFFSET = 102
SUPPLIES_REQUIRED_OFFSET = 540
# Matched the screen for 2 of 3 units, the third was off by a few.
SUPPORT_REQUIRED_OFFSET = 548
SUPPORT_OFFSET = 552

# fmt is a struct code: B = u8, i = i32.
FIELDS = [
    Field("experience", "Experience", 648, "B", True, True, 0, 99),
    Field("morale", "Morale", 649, "B", True, True, 0, 99),
    Field("fatigue", "Fatigue", 650, "B", True, True, 0, 99),
    # Bases use this offset for runway damage.
    Field("disruption", "Disruption", 440, "B", True, True, 0, 99),
    Field("supplies", "Supplies", 536, "i", True, True, 0, MAX_VALUE),
]

# The game appends a suffix chosen by the unit class byte; the mapping is in the
# game's code, so it is filled in from names seen in game.
CLASS_OFFSET = 576
# An empty suffix means the game shows the unit by name alone.
CLASS_SUFFIXES = {30: "", 31: "AA Rgt", 32: "AA Bn", 37: "Cst AA Rgt", 40: "", 46: "Army", 48: "Corps", 49: "Fleet",
                  70: "", 71: "Div", 72: "Bde", 73: "RCT", 74: "Rgt", 75: "Bn", 77: "Cav Div", 78: "Corps",
                  80: "", 81: "Div", 82: "Bde", 83: "Rgt", 84: "Bn", 91: "FA Rgt", 92: "FA Bn", 93: "Mtn Gun Rgt",
                  94: "AT Rgt", 95: "Bn", 96: "Def Bn", 99: "Rgt", 100: "", 101: "Engr Rgt", 102: "Engr Bn",
                  103: "Const Rgt", 108: "EAB", 109: "Base Force", 110: "", 112: "Cst Gun Bn", 113: "Cst Art Rgt",
                  114: "Cst Art Bn", 115: "Fort"}
# Broad category byte, shown when the class suffix is not known yet.
CATEGORY_OFFSET = 30
CATEGORIES = {3: "AA/Coastal", 4: "HQ", 11: "Armor", 12: "Cavalry", 13: "Airborne", 14: "Infantry",
              15: "Artillery", 16: "Base/Naval", 17: "Engineer"}

SLOTS = 20
DEVICE_OFFSET = 136  # i16 per slot; 0 = empty
COUNT_OFFSET = 176
DISABLED_OFFSET = 216
TOE_DEVICE_OFFSET = 336
TOE_COUNT_OFFSET = 376
MAX_COUNT = 9999


def type_label(type_id):
    if type_id in TYPES:
        return TYPES[type_id]
    if type_id in GUESSED_TYPES:
        return GUESSED_TYPES[type_id] + "?"
    return str(type_id)


class LandUnit(Record):
    section, record_size, fields = LOCATION_SECTION, RECORD_SIZE, FIELDS

    def __init__(self, save, unit_id, name, names=None):
        super().__init__(save, unit_id, name)
        # Shared across the units of one list so each referenced name is decrypted once.
        self._names = {} if names is None else names

    def _location_name(self, loc_id):
        if loc_id not in self._names:
            start = loc_id * RECORD_SIZE
            ok = 0 <= loc_id < RECORD_COUNT and start + NAME_SIZE <= len(self._data)
            self._names[loc_id] = decode_name(self._data[start:start + NAME_SIZE]) if ok else ""
        return self._names[loc_id]

    @property
    def type_id(self):
        return self._i16(TYPE_OFFSET)

    @property
    def type(self):
        return type_label(self.type_id)

    @property
    def class_id(self):
        return self._u8(CLASS_OFFSET)

    @property
    def category(self):
        return CATEGORIES.get(self._u8(CATEGORY_OFFSET), str(self._u8(CATEGORY_OFFSET)))

    @property
    def display_name(self):
        """Name as the game shows it where the class suffix is known, else name plus category."""
        name = self.name.strip()
        suffix = CLASS_SUFFIXES.get(self.class_id)
        if suffix is None:
            return f"{name} ({self.category})"
        return f"{name} {suffix}" if suffix else name

    @property
    def hq_id(self):
        return self._i16(HQ_OFFSET)

    @property
    def hq_name(self):
        return self._location_name(self.hq_id)

    @property
    def location_id(self):
        return self._i16(LOCATION_OFFSET)

    @property
    def location_name(self):
        return self._location_name(self.location_id)

    @property
    def target_id(self):
        return self._i16(TARGET_OFFSET)

    @property
    def target_name(self):
        return self._location_name(self.target_id)

    @property
    def supplies_required(self):
        return struct.unpack_from("<i", self._data, self._offset + SUPPLIES_REQUIRED_OFFSET)[0]

    @property
    def support(self):
        return struct.unpack_from("<i", self._data, self._offset + SUPPORT_OFFSET)[0]

    @property
    def support_required(self):
        return struct.unpack_from("<i", self._data, self._offset + SUPPORT_REQUIRED_OFFSET)[0]

    @property
    def side(self):
        pos = self.id * INDEX_RECORD_SIZE + SIDE_OFFSET
        return SIDES.get(struct.unpack_from("<i", self._save[INDEX_SECTION].data, pos)[0], "Unknown")

    # ---- equipment ------------------------------------------------------

    def _device_name(self, device_id):
        if device_id == 0:
            return ""
        return _plain_name(self._save[DEVICE_SECTION].data, device_id * DEVICE_RECORD_SIZE)

    def equipment_slots(self):
        """Slots with a current or TOE device."""
        return [k for k in range(SLOTS)
                if self._i16(DEVICE_OFFSET + 2 * k) or self._i16(TOE_DEVICE_OFFSET + 2 * k)]

    def _check_slot(self, slot):
        if isinstance(slot, bool) or not isinstance(slot, int) or slot not in self.equipment_slots():
            raise ValueError(f"slot {slot!r} is empty or does not exist")

    def get_equipment(self, slot):
        self._check_slot(slot)
        return {
            "device": self._device_name(self._i16(DEVICE_OFFSET + 2 * slot)),
            "count": self._i16(COUNT_OFFSET + 2 * slot),
            "disabled": self._i16(DISABLED_OFFSET + 2 * slot),
            "toe_device": self._device_name(self._i16(TOE_DEVICE_OFFSET + 2 * slot)),
            "toe_count": self._i16(TOE_COUNT_OFFSET + 2 * slot),
        }

    def list_equipment(self):
        return [(k, self.get_equipment(k)) for k in self.equipment_slots()]

    def check_equipment(self, slot, count, disabled):
        """Return (count, disabled) as checked ints, or raise ValueError."""
        self._check_slot(slot)
        for label, value in (("Count", count), ("Disabled", disabled)):
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"{label} must be an integer")
        if not 0 <= count <= MAX_COUNT:
            raise ValueError(f"Count must be between 0 and {MAX_COUNT}")
        if not 0 <= disabled <= count:
            raise ValueError(f"Disabled must be between 0 and the count ({count})")
        return count, disabled

    def set_equipment(self, slot, count, disabled):
        count, disabled = self.check_equipment(slot, count, disabled)
        struct.pack_into("<h", self._data, self._offset + COUNT_OFFSET + 2 * slot, count)
        struct.pack_into("<h", self._data, self._offset + DISABLED_OFFSET + 2 * slot, disabled)


def list_land_units(save):
    data = save[LOCATION_SECTION].data
    names = {}
    out = []
    for unit_id in range(min(RECORD_COUNT, len(data) // RECORD_SIZE)):
        start = unit_id * RECORD_SIZE
        if struct.unpack_from("<h", data, start + TYPE_OFFSET)[0] not in LAND_TYPES:
            continue
        name = decode_name(data[start:start + NAME_SIZE])
        if name:
            out.append(LandUnit(save, unit_id, name, names))
    return out
