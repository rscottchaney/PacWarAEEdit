"""Read-only combat ratings of the ship class records (section 0x1B), after WitpStaff's Ship Classes tab.

Each used class record is one refit stage; the ratings come from its 20 weapon slots (device id, num, ammo, see
ships.py) and the device table (section 0x1F). Device offsets, taken from ae-editor's field table and matched against
scenario data: type u8 at 26, range i16 at 30, effect i16 at 32, penetration i16 at 34, accuracy u8 at 36 and ceiling
at 48. The ceiling is read as u16: the 5in/38 DP gun is -28336 as i16 and 37200 as u16. Over all weapon slots of
the sample save the types are 1 GA Rocket (7), 3 GP Bomb (123), 10 Surface Radar (1525), 11 AA Rocket (24), 12 Flak
(5826), 16 Torpedo (1508), 17 DP Gun (2565), 18 Navy Gun (1466), 20 ASW (1148), 21 Mine (255) and 23 Squad (29).
Depth charges, K-guns and mortars are all type 20. Every ship radar, air search ones too, is type 10 (never 6, 8 or
9), so the specials list the devices of types 6, 8, 9, 10 and 11 by name, with " Radar" cut off. Torpedo ammo is the
number of shots per tube carried (Fletcher: 10 tubes, ammo 1; Kagero: 8 tubes, ammo 2), so the total carried is num x
ammo; the "Torpedo Ordnance" dummy slots of carriers have num 0 and count for nothing.

Rules (WitpStaff manual 4.6); a slot only counts with num above 0:
- Main guns: the highest effect among Navy Gun (18) and DP Gun (17) slots, the total num over every such slot whose
  device has that effect (mounts of equal effect merge: Benson has 5in/38 EBR and OBR mounts, 5 guns) and the
  smallest ammo of those slots as salvoes. The name is that of the device with the most guns among them (the lowest
  device id on a tie).
- Low AA: sum of effect x num over Flak (12), DP Gun (17) and AA Rocket (11) slots with a ceiling below 20000,
  halved as the game displays it. High AA: the same from a ceiling of 20000, halved, plus the highest ceiling among
  those slots; sorting on High AA uses that ceiling.
- ASW: the sum of num over ASW (20) slots, and WoOS' ASW rating, the sum of effect x accuracy / 100 x num.
- Torpedoes: the tubes (sum of num over Torpedo (16) slots) and the total carried (sum of num x ammo).
- A/B/S: ships of the class record that are available (arrived), building or not yet arrived, and sunk.
- Side: that of the class's ships, otherwise from the class's nation as for ships.
Nothing here writes to the save.
"""

import struct
from collections import namedtuple

from . import shiprecords, ships
from .factories import DEVICE_RECORD_SIZE, DEVICE_SECTION, _plain_name
from .losses import SUNK

TYPE_OFFSET = 26  # u8
EFFECT_OFFSET = 32  # i16
ACCURACY_OFFSET = 36  # u8
CEILING_OFFSET = 48  # u16

MAIN_GUN_TYPES = frozenset({17, 18})
AA_TYPES = frozenset({11, 12, 17})
SPECIAL_TYPES = frozenset({6, 8, 9, 10, 11})
ASW_TYPE = 20
TORPEDO_TYPE = 16
HIGH_CEILING = 20000

Slot = namedtuple("Slot", "device name type effect accuracy ceiling num ammo")
ClassRating = namedtuple(
    "ClassRating", "class_id name type nation side date speed endurance durability belt deck "
                   "main_gun main_effect main_num main_salvoes low_aa high_aa aa_ceiling asw_count asw_rating "
                   "torp_tubes torp_total specials available building sunk")


def main_gun(slots):
    """(name, effect, num, salvoes) of the best main gun, ("", 0, 0, 0) without one."""
    guns = [s for s in slots if s.type in MAIN_GUN_TYPES and s.num > 0]
    if not guns:
        return "", 0, 0, 0
    effect = max(s.effect for s in guns)
    same = [s for s in guns if s.effect == effect]
    per_device = {}
    for s in same:
        per_device[s.device] = per_device.get(s.device, 0) + s.num
    device = min(per_device, key=lambda d: (-per_device[d], d))
    name = next(s.name for s in same if s.device == device)
    return name, effect, sum(per_device.values()), min(s.ammo for s in same)


def anti_air(slots):
    """(low AA, high AA, highest ceiling): effect x num split at a ceiling of 20000, both halved."""
    aa = [s for s in slots if s.type in AA_TYPES and s.num > 0]
    low = sum(s.effect * s.num for s in aa if s.ceiling < HIGH_CEILING) / 2
    high = sum(s.effect * s.num for s in aa if s.ceiling >= HIGH_CEILING) / 2
    return low, high, max((s.ceiling for s in aa), default=0)


def anti_submarine(slots):
    """(ASW devices, WoOS' ASW rating)."""
    asw = [s for s in slots if s.type == ASW_TYPE and s.num > 0]
    return sum(s.num for s in asw), round(sum(s.effect * s.accuracy / 100 * s.num for s in asw), 1)


def torpedoes(slots):
    """(tubes, total torpedoes carried)."""
    tubes = [s for s in slots if s.type == TORPEDO_TYPE and s.num > 0]
    return sum(s.num for s in tubes), sum(s.num * s.ammo for s in tubes)


def specials(slots):
    """Comma-joined names of the radar and AA rocket devices, each once, in slot order."""
    names = []
    for s in slots:
        name = s.name[:-len(" Radar")] if s.type != 11 and s.name.endswith(" Radar") else s.name
        if s.type in SPECIAL_TYPES and s.num > 0 and name not in names:
            names.append(name)
    return ", ".join(names)


def class_slots(save, ship):
    """The Slot list of a class record, reading the devices from the device table."""
    devices = save[DEVICE_SECTION].data
    out = []
    for k in ship.weapon_slots():
        start = ship.device_id(k) * DEVICE_RECORD_SIZE
        if start < 0 or start + DEVICE_RECORD_SIZE > len(devices):
            continue
        out.append(Slot(ship.device_id(k), _plain_name(devices, start), devices[start + TYPE_OFFSET],
                        struct.unpack_from("<h", devices, start + EFFECT_OFFSET)[0], devices[start + ACCURACY_OFFSET],
                        struct.unpack_from("<H", devices, start + CEILING_OFFSET)[0],
                        ship._i16(ships.NUM_OFFSET + 2 * k), ship._i16(ships.AMMO_OFFSET + 2 * k)))
    return out


def class_ratings(save):
    """One ClassRating per used class record, in class id order."""
    counts = {}
    for rec in shiprecords.list_ship_records(save):
        a, b, s, side = counts.get(rec.class_id, (0, 0, 0, rec.side))
        if rec.days_to_arrival == SUNK:
            s += 1
        elif rec.arrived:
            a += 1
        else:
            b += 1
        counts[rec.class_id] = (a, b, s, side)
    rows = []
    for x in ships.list_ships(save):
        slots = class_slots(save, x)
        a, b, s, side = counts.get(x.id, (0, 0, 0, None))
        if side is None:
            side = "Japanese" if x.nation_id in shiprecords.JAPANESE_NATIONS else "Allied"
        gun, effect, num, salvoes = main_gun(slots)
        low, high, ceiling = anti_air(slots)
        asw_count, asw_rating = anti_submarine(slots)
        tubes, total = torpedoes(slots)
        rows.append(ClassRating(x.id, x.name, x.type, x.nation, side, x.date, x.get("speed"), x.get("endurance"),
                                x.get("durability"), x.get("belt"), x.get("deck"), gun, effect, num, salvoes, low,
                                high, ceiling, asw_count, asw_rating, tubes, total, specials(slots), a, b, s))
    return rows
