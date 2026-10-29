"""Land units in the location table (section 0x13) of a WitP:AE save.

Bases, land units and task forces share the table; the int16 at offset 28 is
the record type. Names are stored without the unit-kind suffix the game
appends. Views read and write the section's bytearray in place, so edits made
here and in the Bases tab never touch each other's records. A device can be
added to an empty equipment slot; the devices of existing slots and the TOE
(table of organisation) columns are read-only.
"""

import struct

from .airgroups import Record
from .bases import (
    INDEX_RECORD_SIZE, INDEX_SECTION, LOCATION_SECTION, MAX_VALUE, NAME_SIZE, RECORD_COUNT,
    RECORD_SIZE, SIDE_OFFSET, SIDES, TYPE_OFFSET, X_OFFSET, Y_OFFSET, Field, decode_name, is_place,
    PIXEL_X_OFFSET, PIXEL_Y_OFFSET, place_hex, place_pixel, place_side_id,
)
from .factories import DEVICE_RECORD_SIZE, DEVICE_SECTION, _plain_name

# Type labels; GUESSED_TYPES are not confirmed and are shown with a trailing "?".
TYPES = {4: "HQ", 7: "INF", 9: "ART", 10: "ENG", 11: "CD"}
GUESSED_TYPES = {3: "AA", 8: "ARM"}
LAND_TYPES = frozenset(TYPES) | frozenset(GUESSED_TYPES)

HQ_OFFSET = 122
LOCATION_OFFSET = 86
TARGET_OFFSET = 102
# A unit's map icon sits beside its place: left for Allied, right for Japanese (all but
# 23 of 1725 placed units). The game names a unit's location after the nearest base to
# this point, so a move that leaves it behind shows the old place.
ICON_SHIFT = {0: (14, 9), 1: (-14, 9)}
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
SUPPORT_DEVICES = (252, 253)  # Support, Motorized Support: these count toward the unit's support
NO_SUPPORT_NEEDED = frozenset({252, 253, 254, 255})  # plus Aviation Support and Naval Support


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
        """The HQ's name as the game shows it; the stored name if the id is not an HQ record."""
        hq = LandUnit(self._save, self.hq_id, self._location_name(self.hq_id), self._names)
        ok = 0 <= self.hq_id < RECORD_COUNT and hq._offset + RECORD_SIZE <= len(self._data)
        return hq.display_name if ok and hq.type_id == 4 else hq.name

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

    @property
    def move_blocker(self):
        """Why the unit cannot be moved, or "" when it can."""
        loc = self.location_id
        if not is_place(self._save, loc):
            return "not at a base or town (not arrived)"
        if (self._i16(X_OFFSET), self._i16(Y_OFFSET)) != place_hex(self._save, loc):
            return "on the march"
        return ""

    @property
    def can_move(self):
        return not self.move_blocker

    def move_to(self, place_id):
        """Move to a base or town on the same side; sets location, hex, target and map position."""
        if self.move_blocker:
            raise ValueError(f"{self.name} cannot be moved: {self.move_blocker}")
        if not is_place(self._save, place_id):
            raise ValueError(f"{place_id!r} is not a base or town")
        if place_side_id(self._save, place_id) != place_side_id(self._save, self.id):
            raise ValueError(f"{self.name} can only move to a place on its own side")
        x, y = place_hex(self._save, place_id)
        struct.pack_into("<h", self._data, self._offset + LOCATION_OFFSET, place_id)
        struct.pack_into("<h", self._data, self._offset + X_OFFSET, x)
        struct.pack_into("<h", self._data, self._offset + Y_OFFSET, y)
        struct.pack_into("<h", self._data, self._offset + TARGET_OFFSET, place_id)
        px, py = place_pixel(self._save, place_id)
        dx, dy = ICON_SHIFT[place_side_id(self._save, self.id)]
        index = self._save[INDEX_SECTION].data
        struct.pack_into("<2i", index, self.id * INDEX_RECORD_SIZE + PIXEL_X_OFFSET, px + dx, py + dy)

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

    def add_equipment(self, device_id, count, disabled, allowed):
        """Put a device in the lowest empty slot and return the slot number.

        `allowed` is the device ids available to this unit's side (see available_devices).
        The TOE device and count of the slot stay 0. Nothing is written unless all checks pass.
        """
        if isinstance(device_id, bool) or not isinstance(device_id, int) or device_id not in allowed:
            raise ValueError(f"{device_id!r} is not available to {self.side} units")
        for label, value in (("Count", count), ("Disabled", disabled)):
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"{label} must be an integer")
        if not 1 <= count <= MAX_COUNT:
            raise ValueError(f"Count must be between 1 and {MAX_COUNT}")
        if not 0 <= disabled <= count:
            raise ValueError(f"Disabled must be between 0 and the count ({count})")
        used = set(self.equipment_slots())
        slot = next((k for k in range(SLOTS) if k not in used), None)
        if slot is None:
            raise ValueError(f"{self.name} has no empty equipment slot")
        struct.pack_into("<h", self._data, self._offset + DEVICE_OFFSET + 2 * slot, device_id)
        struct.pack_into("<h", self._data, self._offset + COUNT_OFFSET + 2 * slot, count)
        struct.pack_into("<h", self._data, self._offset + DISABLED_OFFSET + 2 * slot, disabled)
        return slot

    def fill_to_toe(self, percent):
        """Bring every slot that has a TOE entry up to its TOE count, plus `percent` (0, 10 or 25).

        The target is the TOE count plus percent, rounded up and capped at MAX_COUNT. An empty
        slot gets the TOE device; a slot holding another (older) device keeps it. Counts are never
        lowered and disabled is cleared on every TOE slot. Slots without a TOE entry are left alone.
        Returns the number of slots whose bytes changed. Nothing is written if percent is invalid.
        """
        if isinstance(percent, bool) or not isinstance(percent, int) or percent not in (0, 10, 25):
            raise ValueError("Percent must be 0, 10 or 25")
        changed = 0
        for k in range(SLOTS):
            toe_device = self._i16(TOE_DEVICE_OFFSET + 2 * k)
            toe_count = self._i16(TOE_COUNT_OFFSET + 2 * k)
            if not toe_device or toe_count <= 0:
                continue
            target = min(MAX_COUNT, (toe_count * (100 + percent) + 99) // 100)
            device = self._i16(DEVICE_OFFSET + 2 * k) or toe_device
            count = max(self._i16(COUNT_OFFSET + 2 * k), target)
            new = (device, count, 0)
            old = tuple(self._i16(off + 2 * k) for off in (DEVICE_OFFSET, COUNT_OFFSET, DISABLED_OFFSET))
            if new == old:
                continue
            for off, value in zip((DEVICE_OFFSET, COUNT_OFFSET, DISABLED_OFFSET), new):
                struct.pack_into("<h", self._data, self._offset + off + 2 * k, value)
            changed += 1
        return changed

    def support_estimate(self):
        """Return (support, needed), an estimate of the game's support rule from current equipment.

        support is the count in slots holding Support or Motorized Support; needed is the count in
        all other slots with a device, following the manual's one support squad per non-support
        element. It matches the stored value on most but not all units.
        """
        support = needed = 0
        for k in range(SLOTS):
            device = self._i16(DEVICE_OFFSET + 2 * k)
            count = self._i16(COUNT_OFFSET + 2 * k)
            if device in SUPPORT_DEVICES:
                support += count
            elif device and device not in NO_SUPPORT_NEEDED:
                needed += count
        return support, needed

    def raise_support_to_estimate(self):
        """Add support squads up to support_estimate()'s need; return the number added.

        The shortfall goes to the first Support slot, else the first Motorized Support slot, else
        Support in the lowest empty slot (TOE bytes stay 0). Nothing is ever lowered and disabled
        is not changed. The slot count is capped at MAX_COUNT. Raises ValueError, writing nothing,
        if a new slot is needed and none is empty.
        """
        support, needed = self.support_estimate()
        if support >= needed:
            return 0
        shortfall = needed - support
        devices = [self._i16(DEVICE_OFFSET + 2 * k) for k in range(SLOTS)]
        slot = next((k for k, d in enumerate(devices) if d == SUPPORT_DEVICES[0]), None)
        if slot is None:
            slot = next((k for k, d in enumerate(devices) if d == SUPPORT_DEVICES[1]), None)
        if slot is None:
            used = set(self.equipment_slots())
            slot = next((k for k in range(SLOTS) if k not in used), None)
            if slot is None:
                raise ValueError(f"{self.name} has no empty equipment slot for support squads")
            struct.pack_into("<h", self._data, self._offset + DEVICE_OFFSET + 2 * slot, SUPPORT_DEVICES[0])
            struct.pack_into("<h", self._data, self._offset + DISABLED_OFFSET + 2 * slot, 0)
        old = self._i16(COUNT_OFFSET + 2 * slot)
        new = min(MAX_COUNT, old + shortfall)
        struct.pack_into("<h", self._data, self._offset + COUNT_OFFSET + 2 * slot, new)
        return new - old


def available_devices(save):
    """Devices a side can add: those any land unit of that side already uses (current or TOE).

    Returns {side_id: [(device_id, name), ...]} sorted by name. Ids outside the device table
    are ignored.
    """
    data = save[LOCATION_SECTION].data
    device_data = save[DEVICE_SECTION].data
    limit = min(2000, len(device_data) // DEVICE_RECORD_SIZE)
    ids = {side: set() for side in SIDES}
    for unit in list_land_units(save):
        used = ids.get(place_side_id(save, unit.id))
        if used is None:
            continue
        base = unit.id * RECORD_SIZE
        for offset in (DEVICE_OFFSET, TOE_DEVICE_OFFSET):
            used.update(struct.unpack_from(f"<{SLOTS}h", data, base + offset))
    return {side: sorted(((d, _plain_name(device_data, d * DEVICE_RECORD_SIZE)) for d in used if 0 < d < limit),
                         key=lambda item: (item[1].lower(), item[0]))
            for side, used in ids.items()}


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
