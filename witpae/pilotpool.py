"""Replacement pilot pool per nation, in section 0x01 of a WitP:AE save.

Offsets come from WitPTracker's compiled code (ReadPilotPool, ReadPilotTrainingPool) and
have not yet been checked against the game's Pilot Pool screen. Views read and write the
section's bytearray in place; only the fields listed here are ever written.
"""

import struct

from .container import SaveFormatError
from .nations import nation_label
from .shiprecords import JAPANESE_NATIONS

SECTION = 0x01
NATION_IDS = range(1, 19)
POOL_BASE = 65132  # i16 pilots available, 2 bytes per nation from nation 1
EXPERIENCE_BASE = 65168  # i16 pool experience, 16 bytes per nation
RATE_BASE = 65482  # i16 pilots per month, 16 bytes per nation
TRAINING_BASE = 97918  # 72 bytes per nation from nation 1
TRAINING_STRIDE = 72
TRAINING_COUNT_OFFSET = 0  # 12 x i16
TRAINING_EXPERIENCE_OFFSET = 48  # 12 x u8
INTAKES = 12
MAX_COUNT = 32767
MAX_EXPERIENCE = 99
SECTION_END = TRAINING_BASE + TRAINING_STRIDE * len(NATION_IDS)


LABELS = {"pool": "Pool", "experience": "Experience", "rate": "Rate per month"}
FIELD_NAMES = ["pool", "experience", "rate"] + [f"count{k}" for k in range(INTAKES)] + [
    f"exp{k}" for k in range(INTAKES)]


def field_label(name):
    if name in LABELS:
        return LABELS[name]
    if name.startswith("count"):
        return f"Intake {int(name[5:]) + 1} count"
    return f"Intake {int(name[3:]) + 1} experience"


class PilotPool:
    def __init__(self, save, nation_id):
        self._save = save
        self.nation_id = nation_id

    @property
    def _data(self):
        return self._save[SECTION].data

    @property
    def label(self):
        return nation_label(self.nation_id)

    @property
    def side(self):
        return "Japanese" if self.nation_id in JAPANESE_NATIONS else "Allied"

    def _location(self, name):
        """(absolute offset, struct code, max) of a field."""
        n = self.nation_id
        if name == "pool":
            return POOL_BASE + 2 * (n - 1), "h", MAX_COUNT
        if name == "experience":
            return EXPERIENCE_BASE + 16 * n, "h", MAX_EXPERIENCE
        if name == "rate":
            return RATE_BASE + 16 * n, "h", MAX_COUNT
        start = TRAINING_BASE + TRAINING_STRIDE * (n - 1)
        for prefix, offset, size, code, top in (
                ("count", TRAINING_COUNT_OFFSET, 2, "h", MAX_COUNT),
                ("exp", TRAINING_EXPERIENCE_OFFSET, 1, "B", MAX_EXPERIENCE)):
            suffix = name[len(prefix):]
            if name.startswith(prefix) and suffix.isdigit() and int(suffix) < INTAKES:
                return start + offset + size * int(suffix), code, top
        raise ValueError(f"unknown pilot pool field {name!r}")

    def get(self, name):
        pos, code, _top = self._location(name)
        return struct.unpack_from("<" + code, self._data, pos)[0]

    def validate(self, name, value):
        """Return value as a checked int, or raise ValueError naming the field."""
        _pos, _code, top = self._location(name)
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{field_label(name)} must be an integer")
        if not 0 <= value <= top:
            raise ValueError(f"{field_label(name)} must be between 0 and {top}")
        return value

    def set(self, name, value):
        value = self.validate(name, value)
        pos, code, _top = self._location(name)
        struct.pack_into("<" + code, self._data, pos, value)

    def set_many(self, values):
        """Validate everything first so a bad value never leaves a partial edit."""
        checked = {name: self.validate(name, v) for name, v in values.items()}
        for name, v in checked.items():
            self.set(name, v)

    @property
    def counts(self):
        return [self.get(f"count{k}") for k in range(INTAKES)]

    @property
    def experiences(self):
        return [self.get(f"exp{k}") for k in range(INTAKES)]

    @property
    def in_training(self):
        return sum(self.counts)

    @property
    def is_empty(self):
        # The pool experience of an empty nation is still a default like 35, so it does not count.
        return not (self.get("pool") or self.get("rate") or any(self.counts))


def list_pools(save):
    """One PilotPool per nation 1..18; raises SaveFormatError if the section is missing or short."""
    if SECTION not in save:
        raise SaveFormatError(f"section 0x{SECTION:02x} (pilot pool) is missing")
    if len(save[SECTION].data) < SECTION_END:
        raise SaveFormatError(f"section 0x{SECTION:02x} is too short for the pilot pool")
    return [PilotPool(save, n) for n in NATION_IDS]
