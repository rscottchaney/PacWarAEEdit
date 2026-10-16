"""Individual ships in play (section 0x08).

20000 fixed-size records indexed by ship id; an empty name marks an unused
record. The name is plain latin-1 text. Offsets were mapped against game
screens; edits are not yet verified in-game. Views read and write the
section's bytearray in place. The class, device and location tables they refer
to stay read-only.
"""

import struct

from . import ships
from .airgroups import SHIP_RECORD_COUNT, SHIP_RECORD_SIZE, SHIP_SECTION, Record
from .bases import LOCATION_SECTION, NAME_SIZE, RECORD_SIZE as LOCATION_RECORD_SIZE, Field, decode_name, is_place
from .factories import DEVICE_RECORD_SIZE, DEVICE_SECTION, _plain_name
from .nations import nation_label

NATION_OFFSET = 25
ARRIVAL_OFFSET = 36  # u32 days to arrival, 0 = arrived
CLASS_OFFSET = 52
BASE_OFFSET = 60  # location id, 0 = at sea
TASK_FORCE_OFFSET = 62
JAPANESE_NATIONS = {1, 2}  # IJA, IJN; every other nation is Allied

# fmt is a struct code: B = u8, H = u16. Values verified against game screens.
FIELDS = [
    Field("exp_day", "Experience (day)", 27, "B", True, True, 0, 99),
    Field("exp_night", "Experience (night)", 28, "B", True, True, 0, 99),
    Field("fuel", "Fuel", 56, "H", True, True, 0, 32767),
    Field("fires", "Fires", 331, "B", True, True, 0, 99),
    Field("sys_dmg", "System damage", 332, "B", True, True, 0, 99),
    Field("float_dmg", "Flotation damage", 333, "B", True, True, 0, 99),
    Field("maj_float_dmg", "Major flotation damage", 334, "B", True, True, 0, 99),
    Field("eng_dmg", "Engine damage", 335, "B", True, True, 0, 99),
    Field("maj_eng_dmg", "Major engine damage", 336, "B", True, True, 0, 99),
]
FIELD_BY_NAME = {f.name: f for f in FIELDS}
DAMAGE_FIELDS = ["fires", "sys_dmg", "float_dmg", "maj_float_dmg", "eng_dmg", "maj_eng_dmg"]
# (major, total): the major part of the damage cannot exceed the damage.
DAMAGE_PAIRS = [("maj_float_dmg", "float_dmg"), ("maj_eng_dmg", "eng_dmg")]

SLOTS = 20
DEVICE_OFFSET = 70  # u16 per slot; 0 = empty
NUM_OFFSET = 110  # u16
FACE_OFFSET = 150  # u8
AMMO_OFFSET = 170  # u16
MOUNT_OFFSET = 210  # u8
ARMOR_OFFSET = 230  # u16
WEAPON_FIELDS = {"num": ("Num", 0, 999), "ammo": ("Ammo", 0, 999)}


class ShipRecord(Record):
    section, record_size, fields = SHIP_SECTION, SHIP_RECORD_SIZE, FIELDS

    def _u16(self, pos):
        return struct.unpack_from("<H", self._data, self._offset + pos)[0]

    def set(self, name, value):
        self.set_many({name: value})

    def set_many(self, values):
        """Validate everything first so a bad value never leaves a partial edit."""
        checked = {name: self.validate(name, v) for name, v in values.items()}
        for major, total in DAMAGE_PAIRS:
            if not any(n in checked and checked[n] != self.get(n) for n in (major, total)):
                continue  # existing records may already break the rule; only refuse a changing apply
            if checked.get(major, self.get(major)) > checked.get(total, self.get(total)):
                raise ValueError(f"{self._field(major).label} cannot exceed {self._field(total).label}")
        for name, v in checked.items():
            Record.set(self, name, v)

    def repair_all(self):
        """Clear fires and all damage; writes nothing when there is none."""
        self.set_many({name: 0 for name in DAMAGE_FIELDS if self.get(name)})

    # ---- read-only ------------------------------------------------------

    @property
    def nation_id(self):
        return self._u8(NATION_OFFSET)

    @property
    def nation(self):
        return nation_label(self.nation_id)

    @property
    def side(self):
        return "Japanese" if self.nation_id in JAPANESE_NATIONS else "Allied"

    @property
    def class_id(self):
        return self._u16(CLASS_OFFSET)

    def _class_start(self):
        start = self.class_id * ships.RECORD_SIZE
        return start if start + ships.RECORD_SIZE <= len(self._save[ships.SHIP_SECTION].data) else None

    @property
    def class_name(self):
        start = self._class_start()
        return "" if start is None else _plain_name(self._save[ships.SHIP_SECTION].data, start)

    @property
    def type(self):
        start = self._class_start()
        if start is None:
            return ""
        return ships.type_label(self._save[ships.SHIP_SECTION].data[start + ships.TYPE_OFFSET])

    @property
    def max_fuel(self):
        """Fuel capacity of the ship's class, None when the class record is out of range."""
        start = self._class_start()
        if start is None:
            return None
        return struct.unpack_from("<h", self._save[ships.SHIP_SECTION].data, start + ships.FIELD_BY_NAME["fuel"].offset)[0]

    @property
    def base_id(self):
        return self._u16(BASE_OFFSET)

    @property
    def task_force(self):
        return self._u16(TASK_FORCE_OFFSET)

    @property
    def days_to_arrival(self):
        return struct.unpack_from("<I", self._data, self._offset + ARRIVAL_OFFSET)[0]

    @property
    def base_name(self):
        """Name of the current base, "" at sea."""
        loc = self.base_id
        if not loc:
            return ""
        if not is_place(self._save, loc):
            return f"#{loc}"
        start = loc * LOCATION_RECORD_SIZE
        return decode_name(self._save[LOCATION_SECTION].data[start:start + NAME_SIZE]) or f"#{loc}"

    @property
    def location(self):
        if self.base_id:
            return self.base_name
        return f"TF {self.task_force}" if self.task_force else "at sea"

    # ---- weapons --------------------------------------------------------

    def weapon_slots(self):
        """Slot numbers that hold a device."""
        return [k for k in range(SLOTS) if self._u16(DEVICE_OFFSET + 2 * k) != 0]

    def _check_slot(self, slot):
        if isinstance(slot, bool) or not isinstance(slot, int) or slot not in self.weapon_slots():
            raise ValueError(f"slot {slot!r} is empty or does not exist")

    def get_weapon(self, slot):
        """Dict with name, device, num, face (code), mount, armor and ammo of a non-empty slot."""
        self._check_slot(slot)
        device = self._u16(DEVICE_OFFSET + 2 * slot)
        return {
            "name": _plain_name(self._save[DEVICE_SECTION].data, device * DEVICE_RECORD_SIZE),
            "device": device,
            "num": self._u16(NUM_OFFSET + 2 * slot),
            "face": self._u8(FACE_OFFSET + slot),
            "mount": self._u8(MOUNT_OFFSET + slot),
            "armor": self._u16(ARMOR_OFFSET + 2 * slot),
            "ammo": self._u16(AMMO_OFFSET + 2 * slot),
        }

    def list_weapons(self):
        return [(k, self.get_weapon(k)) for k in self.weapon_slots()]

    def check_weapon(self, slot, **values):
        """Validate num and/or ammo (the only editable ones) and return them as checked ints."""
        self._check_slot(slot)
        checked = {}
        for name, value in values.items():
            if name not in WEAPON_FIELDS:
                raise ValueError(f"weapon field {name!r} is read-only or unknown")
            label, lo, hi = WEAPON_FIELDS[name]
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"{label} must be an integer")
            if not lo <= value <= hi:
                raise ValueError(f"{label} must be between {lo} and {hi}")
            checked[name] = value
        return checked

    def set_weapon(self, slot, **values):
        """Set num and/or ammo of a slot; validate everything before writing."""
        checked = self.check_weapon(slot, **values)
        offsets = {"num": NUM_OFFSET, "ammo": AMMO_OFFSET}
        for name, value in checked.items():
            struct.pack_into("<H", self._data, self._offset + offsets[name] + 2 * slot, value)


def list_ship_records(save):
    data = save[SHIP_SECTION].data
    out = []
    for ship_id in range(min(SHIP_RECORD_COUNT, len(data) // SHIP_RECORD_SIZE)):
        name = _plain_name(data, ship_id * SHIP_RECORD_SIZE)
        if name:
            out.append(ShipRecord(save, ship_id, name))
    return out
