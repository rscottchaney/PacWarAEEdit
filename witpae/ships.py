"""Ship classes in the ship class table (section 0x1B) of a WitP:AE save.

5000 fixed-size records indexed by class id; an empty name marks an unused
record. Several records share a name: they are refit stages of one class, so
the id and date identify a record. Views read and write the section's
bytearray in place. Weapons and electronics refer to the device table
(section 0x1F), which stays read-only.
"""

import struct

from .bases import Field
from .factories import DEVICE_RECORD_SIZE, DEVICE_SECTION, _plain_name
from .nations import label as lookup_label, nation_label

SHIP_SECTION = 0x1B
RECORD_SIZE = 380
RECORD_COUNT = 5000
TYPE_OFFSET = 25
NATION_OFFSET = 26
DISPLACEMENT_OFFSET = 28
MONTH_OFFSET = 258
YEAR_OFFSET = 259

# fmt is a struct code: h = i16, B = u8.
FIELDS = [
    Field("fuel", "Fuel", 32, "h", True, True, 0, 32767),
    Field("endurance", "Endurance", 34, "h", True, True, 0, 32767),
    Field("speed", "Speed", 36, "B", True, True, 0, 60),
    Field("cruise", "Cruise speed", 37, "B", True, True, 0, 60),
    Field("maneuver", "Maneuver", 38, "B", True, True, 0, 100),
    Field("durability", "Durability", 39, "B", True, True, 0, 255),
    Field("belt", "Belt armor", 42, "h", True, True, 0, 2000),
    Field("deck", "Deck armor", 44, "h", True, True, 0, 2000),
    Field("tower", "Tower armor", 46, "h", True, True, 0, 2000),
    Field("capacity", "Capacity", 48, "h", True, True, 0, 32767),
]
FIELD_BY_NAME = {f.name: f for f in FIELDS}

# Type labels read from the game executable; GUESSED_TYPES are not confirmed.
TYPES = {
    1: "CVB", 2: "CV", 3: "CVL", 4: "CVE", 5: "BB", 6: "BC", 7: "CB", 8: "CA", 9: "CL", 10: "CLAA",
    11: "CS", 12: "DD", 17: "PF", 18: "KV", 19: "PC", 20: "PB", 21: "SC", 22: "PT", 23: "MTB",
    24: "MGB", 25: "ML", 26: "SS", 27: "SST", 28: "SSX", 29: "AMC", 30: "CM", 31: "CMc", 32: "DM",
    33: "DMS", 34: "AM", 35: "AS", 36: "AD", 37: "AV", 38: "AVD", 39: "AVP", 40: "AR", 41: "ARD",
    42: "AGP", 43: "AG", 44: "AO", 45: "AE", 46: "AGC", 47: "APA", 48: "LSI(L)", 49: "LSI(M)",
    50: "LSI(S)", 51: "APD", 52: "AKA", 53: "LSD", 54: "LSV", 55: "AP", 56: "AK", 57: "AKV",
    58: "AKE", 59: "AKL", 60: "TK", 61: "LST", 62: "LCI", 63: "LCI(G)", 64: "LCI(M)", 65: "LCI(R)",
    66: "LSM", 67: "LSM(R)", 68: "LCM", 69: "LCT", 71: "LCVP", 72: "LCS(L)", 73: "YO", 74: "ACM",
    75: "YMS", 76: "YP", 77: "HDML", 78: "APc", 79: "AMc", 80: "xAP", 81: "xAPc", 82: "xAK",
    83: "xAKL",
}
GUESSED_TYPES = {13: "DE", 14: "TB", 16: "PG", 70: "LB"}

SLOTS = 20
DEVICE_OFFSET = 56  # i16 per slot; 0 = empty
NUM_OFFSET = 96  # i16
FACE_OFFSET = 136  # u8
AMMO_OFFSET = 156  # i16
MOUNT_OFFSET = 196  # u8
ARMOR_OFFSET = 216  # i16 (Lexington: 5, 5, then 0 as on the game screen)
FACES = {0: "F", 1: "C", 2: "R", 3: "RS", 4: "LS", 5: "A"}
FACE_BY_LABEL = {v: k for k, v in FACES.items()}

# name -> (label, min, max) of the editable per-slot numbers.
WEAPON_FIELDS = {
    "num": ("Num", 0, 999),
    "ammo": ("Ammo", 0, 999),
    "mount": ("Mount", 0, 99),
    "armor": ("Armor", 0, 999),
}


def type_label(type_id):
    return lookup_label(type_id, TYPES, GUESSED_TYPES)


def face_label(code):
    return FACES.get(code, str(code))


def parse_face(value):
    """A face label ("RS") or a raw code, as an int 0..255 (unknown codes are kept as is)."""
    problem = "Face must be one of " + ", ".join(FACES.values())
    if isinstance(value, bool):
        raise ValueError(problem)
    if isinstance(value, int):
        code = value
    else:
        text = str(value).strip()
        if text in FACE_BY_LABEL:
            return FACE_BY_LABEL[text]
        if not text.isdigit():
            raise ValueError(problem)
        code = int(text)
    if not 0 <= code <= 255:
        raise ValueError(problem)
    return code


class Ship:
    def __init__(self, save, ship_id, name):
        self._save = save
        self.id = ship_id
        self.name = name

    @property
    def _data(self):
        return self._save[SHIP_SECTION].data

    @property
    def _offset(self):
        return self.id * RECORD_SIZE

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

    # ---- read-only ------------------------------------------------------

    @property
    def type(self):
        return type_label(self._u8(TYPE_OFFSET))

    @property
    def nation_id(self):
        return self._u8(NATION_OFFSET)

    @property
    def nation(self):
        return nation_label(self.nation_id)

    @property
    def displacement(self):
        return struct.unpack_from("<H", self._data, self._offset + DISPLACEMENT_OFFSET)[0]

    @property
    def date(self):
        """(month, year) of the refit stage; unverified."""
        return self._u8(MONTH_OFFSET), self._u8(YEAR_OFFSET)

    # ---- weapons --------------------------------------------------------

    def weapon_slots(self):
        """Slot numbers that hold a device."""
        return [k for k in range(SLOTS) if self._i16(DEVICE_OFFSET + 2 * k) != 0]

    def _check_slot(self, slot):
        if isinstance(slot, bool) or not isinstance(slot, int) or slot not in self.weapon_slots():
            raise ValueError(f"slot {slot!r} is empty or does not exist")

    def get_weapon(self, slot):
        """Dict with name, num, face (code), mount, armor and ammo of a non-empty slot."""
        self._check_slot(slot)
        device = self._i16(DEVICE_OFFSET + 2 * slot)
        return {
            "name": _plain_name(self._save[DEVICE_SECTION].data, device * DEVICE_RECORD_SIZE),
            "num": self._i16(NUM_OFFSET + 2 * slot),
            "face": self._u8(FACE_OFFSET + slot),
            "mount": self._u8(MOUNT_OFFSET + slot),
            "armor": self._i16(ARMOR_OFFSET + 2 * slot),
            "ammo": self._i16(AMMO_OFFSET + 2 * slot),
        }

    def list_weapons(self):
        return [(k, self.get_weapon(k)) for k in self.weapon_slots()]

    def check_weapon(self, slot, **values):
        """Validate some of num, face, mount, armor, ammo and return them as checked ints."""
        self._check_slot(slot)
        checked = {}
        for name, value in values.items():
            if name == "face":
                checked[name] = parse_face(value)
                continue
            if name not in WEAPON_FIELDS:
                raise ValueError(f"unknown weapon field {name!r}")
            label, lo, hi = WEAPON_FIELDS[name]
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"{label} must be an integer")
            if not lo <= value <= hi:
                raise ValueError(f"{label} must be between {lo} and {hi}")
            checked[name] = value
        return checked

    def set_weapon(self, slot, **values):
        """Set some weapon values; validate everything before writing."""
        checked = self.check_weapon(slot, **values)
        base = self._offset
        for name, value in checked.items():
            if name == "num":
                struct.pack_into("<h", self._data, base + NUM_OFFSET + 2 * slot, value)
            elif name == "ammo":
                struct.pack_into("<h", self._data, base + AMMO_OFFSET + 2 * slot, value)
            elif name == "armor":
                struct.pack_into("<h", self._data, base + ARMOR_OFFSET + 2 * slot, value)
            else:
                offset = {"face": FACE_OFFSET, "mount": MOUNT_OFFSET}[name]
                self._data[base + offset + slot] = value


def list_ships(save):
    data = save[SHIP_SECTION].data
    out = []
    for ship_id in range(min(RECORD_COUNT, len(data) // RECORD_SIZE)):
        name = _plain_name(data, ship_id * RECORD_SIZE)
        if name:
            out.append(Ship(save, ship_id, name))
    return out
