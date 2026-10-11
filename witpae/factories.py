"""Factory slots of a base (record in section 0x13, 20 slots per base).

Per-slot arrays: type int16 at 136, size int16 at 176, damage int16 at 216,
production-off byte at 844, repair-off byte at 870, upgrade-off byte at 1073
(unverified, read-only here). Other slot arrays (original type/size) are never
touched. Names come from the device section (engine and industry factories) or
the aircraft section (type >= 2000), both plain latin-1 text.
"""

import struct
from collections import namedtuple

from .bases import LOCATION_SECTION, NAME_SIZE, RECORD_SIZE

DEVICE_SECTION = 0x1F
DEVICE_RECORD_SIZE = 236
AIRCRAFT_SECTION = 0x20
AIRCRAFT_RECORD_SIZE = 396

SLOTS = 20
TYPE_OFFSET = 136
SIZE_OFFSET = 176
DAMAGE_OFFSET = 216
PRODUCTION_OFF_OFFSET = 844
REPAIR_OFF_OFFSET = 870
UPGRADE_OFF_OFFSET = 1073  # unverified

AIRCRAFT_BASE = 2000
MAX_SIZE = 30000

INDUSTRIES = {
    518: "Oil", 519: "Resources", 520: "Manpower", 521: "Heavy Industry",
    522: "Naval Shipyard", 523: "Merchant Shipyard", 524: "Repair Shipyard",
    525: "Armament Assembly", 526: "Vehicle Assembly", 527: "Light Industry",
    528: "Refinery",
}
# The game refuses to switch these off (518-520) or shows no switch (524, 527).
PRODUCTION_LOCKED = frozenset({518, 519, 520, 524, 527})

Factory = namedtuple("Factory", "slot type name kind size damage production_on repair_on upgrade_on")


def _plain_name(data, start):
    raw = bytes(data[start:start + NAME_SIZE]).split(b"\0", 1)[0]
    return raw.decode("latin-1").strip()


def kind_of(type_id):
    if type_id >= AIRCRAFT_BASE:
        return "aircraft"
    return "industry" if type_id in INDUSTRIES else "engine"


def factory_name(save, type_id):
    if type_id >= AIRCRAFT_BASE:
        return _plain_name(save[AIRCRAFT_SECTION].data, (type_id - AIRCRAFT_BASE) * AIRCRAFT_RECORD_SIZE)
    return _plain_name(save[DEVICE_SECTION].data, type_id * DEVICE_RECORD_SIZE)


def production_locked(type_id):
    return type_id in PRODUCTION_LOCKED


def _start(base):
    return base.id * RECORD_SIZE


def _check_slot(slot):
    if isinstance(slot, bool) or not isinstance(slot, int) or not 0 <= slot < SLOTS:
        raise ValueError(f"slot must be an integer from 0 to {SLOTS - 1}")


def get_factory(base, slot):
    """The factory in a slot, or None when the slot is empty."""
    _check_slot(slot)
    data = base._save[LOCATION_SECTION].data
    start = _start(base)
    type_id = struct.unpack_from("<h", data, start + TYPE_OFFSET + 2 * slot)[0]
    if type_id == 0:
        return None
    return Factory(
        slot, type_id, factory_name(base._save, type_id), kind_of(type_id),
        struct.unpack_from("<h", data, start + SIZE_OFFSET + 2 * slot)[0],
        struct.unpack_from("<h", data, start + DAMAGE_OFFSET + 2 * slot)[0],
        data[start + PRODUCTION_OFF_OFFSET + slot] == 0,
        data[start + REPAIR_OFF_OFFSET + slot] == 0,
        data[start + UPGRADE_OFF_OFFSET + slot] == 0,
    )


def list_factories(base):
    """Non-empty factories of a base in slot order."""
    return [f for f in (get_factory(base, k) for k in range(SLOTS)) if f is not None]


def set_factory(base, slot, size, damage, production_on, repair_on):
    """Set one slot's editable fields; validate everything before writing."""
    factory = get_factory(base, slot)
    if factory is None:
        raise ValueError(f"slot {slot} is empty")
    for label, value in (("Size", size), ("Damage", damage)):
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{label} must be an integer")
    for label, value in (("Production", production_on), ("Repair", repair_on)):
        if not isinstance(value, bool):
            raise ValueError(f"{label} must be True or False")
    if not 0 <= size <= MAX_SIZE:
        raise ValueError(f"Size must be between 0 and {MAX_SIZE}")
    if not 0 <= damage <= size:
        raise ValueError(f"Damage must be between 0 and the size ({size})")
    # Only block switching off; a locked slot already stored as off must stay editable.
    if not production_on and factory.production_on and production_locked(factory.type):
        raise ValueError(f"{factory.name} production cannot be switched off")
    data = base._save[LOCATION_SECTION].data
    start = _start(base)
    struct.pack_into("<h", data, start + SIZE_OFFSET + 2 * slot, size)
    struct.pack_into("<h", data, start + DAMAGE_OFFSET + 2 * slot, damage)
    data[start + PRODUCTION_OFF_OFFSET + slot] = 0 if production_on else 1
    data[start + REPAIR_OFF_OFFSET + slot] = 0 if repair_on else 1
