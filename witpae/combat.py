"""Combat: the game's daily after-action reports (combatreport_YYMMDD.txt), one CombatAction per action.

Unlike SIGINT and operations there is one file per turn, holding both sides, plus an undated combatreport.txt copy
of the latest turn. The folder, header date ("AFTER ACTION REPORTS FOR Dec 10, 41"), undated-copy rule, encoding and
line endings are those of intel.py, whose place index and Turns filter are reused. Actions are separated by lines of
40 or more dashes; the first line of a block is its title ("Morning Air attack on TF, near Legaspi at 82,82") and
decides the kind, phase and place. A block no kind rule recognises is kept as "Other". The Combat_Events_*.txt
engine logs are not read. Nothing here writes to the report files, and their text is only ever data.

Sections inside a block are a heading line ("Allied aircraft", "Japanese Ships", "Allied ground losses:") followed
by indented lines:
  aircraft          "      B-17D Fortress x 4" (summed)
  aircraft losses   "      Hudson I: 2 destroyed", "... destroyed on ground", "... 1 destroyed by flak" (destroyed
                    counted, damaged not)
  Ships             "      DD Oite, Shell hits 1", "      CL Yubari", "... Torpedo hits 1, and is sunk"
  ground losses     Squads / Non Combat / Engineers "N destroyed", "Guns lost N (n destroyed, ...)", "Vehicles lost"
"""

import os
import re
from collections import namedtuple

from . import intel

CombatAction = namedtuple(
    "CombatAction", "date index kind phase place x y title allied_aircraft japanese_aircraft allied_air_lost "
    "japanese_air_lost allied_ships japanese_ships ships_hit allied_ships_sunk japanese_ships_sunk allied_ground_lost "
    "japanese_ground_lost attack_value defence_value ships text")
Ship = namedtuple("Ship", "side name damage")

SIDE_NAMES = intel.SIDE_NAMES
FILE_RE = re.compile(r"combatreport(?:_(?P<date>\d{6}))?\.txt", re.I)
SEPARATOR_RE = re.compile(r"^\s*-{40,}\s*$")

KINDS = ("Air attack", "Amphibious assault", "Ground combat", "Invasion support", "Pre-invasion", "ASW", "Submarine",
         "Sub vs sub", "Bombardment", "Mine field", "Surface combat", "Other")
PHASES = ("Morning", "Afternoon", "Night", "Day")
INVOLVED_CHOICES = ("All", "With ships sunk", "With aircraft lost")

# (kind, regex on the title) in matching order; the first match wins.
KIND_RULES = (
    ("Sub vs sub", re.compile(r"^Sub vs Sub\b", re.I)),
    ("Air attack", re.compile(r"\bAir attack\b", re.I)),
    ("Amphibious assault", re.compile(r"^Amphibious Assault\b", re.I)),
    ("Ground combat", re.compile(r"^Ground combat\b", re.I)),
    ("Invasion support", re.compile(r"^Invasion Support\b", re.I)),
    ("Pre-invasion", re.compile(r"^Pre-Invasion\b", re.I)),
    ("ASW", re.compile(r"^ASW attack\b", re.I)),
    ("Submarine", re.compile(r"^Sub(?:marine)? attack\b", re.I)),
    ("Bombardment", re.compile(r"\bbombardment\b", re.I)),
    ("Mine field", re.compile(r"\bmine ?field\b", re.I)),
    ("Surface combat", re.compile(r"\bSurface Combat\b", re.I)),
)
PHASE_RE = re.compile(r"^(Morning|Afternoon|Night|Day)\b", re.I)

# Places in a title, tried in this order (the first that gives a name wins); the hex is the first "x,y".
_HEX_RE = re.compile(r"(?<![\d-])(\d+)\s*,\s*(\d+)(?!\d)")
_PAREN_NAME_RE = re.compile(r"\((?:near\s+)?([A-Za-z][^)]*)\)")  # "at 77,61 (Hong Kong)", "at 71,56 (near Lang Son)"
_DASH_NEAR_RE = re.compile(r"\s-\s+near\s+(.+?)\s*$")  # "at 178,105  - near Lihue"
_NEAR_OFF_RE = re.compile(r"\b(?:near|off)\s+([A-Za-z].*?)\s*(?:\(\s*\d|\bat\s+\d|\s-\s|$)")
_ON_TARGET_RE = re.compile(r"\bon\s+(.+?)\s*,\s*at\b")  # "Air attack on Kota Bharu , at 78,75"
_AT_OF_RE = re.compile(r"\b(?:at|of)\s+([A-Za-z].*?)\s*(?:\(\s*\d|\bat\s+\d|\s-\s|$)")
# An air attack on a TF or a land unit names no place of its own; the place is after it.
_NOT_A_PLACE_RE = re.compile(r"^TF\b|\d|\b(?:Division|Brigade|Regiment|Corps|Battalion|Force|Army|Fortress|Defenses|"
                             r"Defences|Company|Group|Command|Rifles|Cavalry|Artillery|Battery)\b")

_SECTION_RE = re.compile(r"^(Allied|Japanese) (aircraft losses|aircraft|Ships|ground losses:?)$", re.I)
_AIRCRAFT_RE = re.compile(r"^\s+.+ x (\d+)$")
_DESTROYED_RE = re.compile(r"\b(\d+) destroyed\b")
_SHIP_RE = re.compile(r"^\s+(?P<name>[^,]+?)\s*(?:,\s*(?P<damage>.*))?$")
_HITS_RE = re.compile(r"\bhits\s+[1-9]", re.I)
_SQUADS_RE = re.compile(r"^\s+(?:Squads|Non Combat|Engineers):\s*(\d+) destroyed")
_GUNS_VEHICLES_RE = re.compile(r"^\s+(?:Guns|Vehicles) lost \d+ \((\d+) destroyed")
_ASSAULT_RE = re.compile(r"^(Attacking|Defending) force .*Assault Value = (\d+)")


def classify(title):
    for kind, rule in KIND_RULES:
        if rule.search(title):
            return kind
    return "Other"


def parse_title(title):
    """(kind, phase, place, x, y) of a block's first line."""
    m = PHASE_RE.match(title)
    phase = m.group(1).title() if m else ""
    m = _HEX_RE.search(title)
    x, y = (int(m.group(1)), int(m.group(2))) if m else (None, None)
    place = ""
    for rule in (_PAREN_NAME_RE, _DASH_NEAR_RE, _NEAR_OFF_RE, _ON_TARGET_RE, _AT_OF_RE):
        m = rule.search(title)
        if m is None:
            continue
        name = re.sub(r"\s+", " ", m.group(1)).strip()
        if rule is _ON_TARGET_RE and _NOT_A_PLACE_RE.search(name):
            continue
        place = name
        break
    return classify(title), phase, place, x, y


def parse_block(date, index, lines):
    """One CombatAction from the (non-empty) lines of a block."""
    title = lines[0].strip()
    kind, phase, place, x, y = parse_title(title)
    aircraft = {"Allied": 0, "Japanese": 0}
    lost = {"Allied": 0, "Japanese": 0}
    ground = {"Allied": 0, "Japanese": 0}
    ships = []
    values = {}
    side = section = None
    for line in lines[1:]:
        if not line.strip():
            side = section = None
            continue
        m = _SECTION_RE.match(line.strip()) if not line[0].isspace() else None
        if m is not None:
            side, section = m.group(1).title(), m.group(2).lower().rstrip(":")
            continue
        if not line[0].isspace():
            side = section = None
            m = _ASSAULT_RE.match(line)
            if m is not None:
                values[m.group(1)] = int(m.group(2))
            continue
        if section == "aircraft":
            m = _AIRCRAFT_RE.match(line)
            if m is not None:
                aircraft[side] += int(m.group(1))
        elif section == "aircraft losses":
            m = _DESTROYED_RE.search(line)
            if m is not None:
                lost[side] += int(m.group(1))
        elif section == "ships":
            m = _SHIP_RE.match(line)
            if m is not None:
                damage = re.sub(r"\s*,\s*", ", ", re.sub(r"\s+", " ", m.group("damage") or "")).strip(" ,")
                ships.append(Ship(side, m.group("name"), damage))
        elif section == "ground losses":
            m = _SQUADS_RE.match(line) or _GUNS_VEHICLES_RE.match(line)
            if m is not None:
                ground[side] += int(m.group(1))
    hit = sum(1 for s in ships if _HITS_RE.search(s.damage) or "is sunk" in s.damage)
    sunk = {side: sum(1 for s in ships if s.side == side and "is sunk" in s.damage) for side in SIDE_NAMES}
    count = {side: sum(1 for s in ships if s.side == side) for side in SIDE_NAMES}
    # Text: blank runs collapsed so the detail pane stays compact.
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(lines))
    return CombatAction(date, index, kind, phase, place, x, y, title, aircraft["Allied"], aircraft["Japanese"],
                        lost["Allied"], lost["Japanese"], count["Allied"], count["Japanese"], hit, sunk["Allied"],
                        sunk["Japanese"], ground["Allied"], ground["Japanese"], values.get("Attacking"),
                        values.get("Defending"), tuple(ships), text)


def split_blocks(lines):
    """The non-empty blocks (lists of lines, blank edges trimmed) of a report body, split on dash lines."""
    blocks, current = [], []
    for line in [*lines, None]:
        if line is not None and not SEPARATOR_RE.match(line):
            current.append(line)
            continue
        while current and not current[0].strip():
            current.pop(0)
        while current and not current[-1].strip():
            current.pop()
        if current:
            blocks.append(current)
        current = []
    return blocks


def parse_report(date, lines):
    """The CombatActions of one report file's lines (header included)."""
    start = next((i for i, l in enumerate(lines) if l.strip()), len(lines))
    if start < len(lines) and intel.header_date(lines[start]) is not None:
        lines = lines[start + 1:]
    return [parse_block(date, i, block) for i, block in enumerate(split_blocks(lines), 1)]


# ---- files --------------------------------------------------------------

def load_actions(folder):
    """Every CombatAction in the folder's combat reports, by date then file order.

    A missing folder or no report files give []; a file that cannot be read raises OSError. An undated copy is used
    only when no dated file has its header date.
    """
    if not folder or not os.path.isdir(folder):
        return []
    dated, undated = [], []
    for name in sorted(os.listdir(folder)):
        m = FILE_RE.fullmatch(name)
        path = os.path.join(folder, name)
        if m is None or not os.path.isfile(path):
            continue
        if m.group("date"):
            dated.append((int(m.group("date")), path))
        else:
            undated.append((None, path))
    out, seen = [], set()
    for name_date, path in dated + undated:
        lines = intel.read_lines(path, keep_blank=True)
        first = next((l for l in lines if l.strip()), "")
        date = intel.header_date(first)
        if date is None:
            date = name_date
        if date is None or (name_date is None and date in seen):
            continue
        if name_date is not None:
            seen.add(date)
        out.extend(parse_report(date, lines))
    out.sort(key=lambda a: a.date)  # stable: file order is kept within a date
    return out


def select(actions, kind="All", needle="", involved="All"):
    """The actions of one kind (or All) whose title or text contains needle, and that meet the involved choice."""
    needle = needle.strip().lower()
    out = []
    for a in actions:
        if kind != "All" and a.kind != kind:
            continue
        if needle and needle not in a.text.lower():
            continue
        if involved == INVOLVED_CHOICES[1] and not (a.allied_ships_sunk or a.japanese_ships_sunk):
            continue
        if involved == INVOLVED_CHOICES[2] and not (a.allied_air_lost or a.japanese_air_lost):
            continue
        out.append(a)
    return out


def totals(actions):
    """{"actions", "allied_air_lost", "japanese_air_lost", "allied_ships_sunk", "japanese_ships_sunk"} of the actions."""
    return {
        "actions": len(actions),
        "allied_air_lost": sum(a.allied_air_lost for a in actions),
        "japanese_air_lost": sum(a.japanese_air_lost for a in actions),
        "allied_ships_sunk": sum(a.allied_ships_sunk for a in actions),
        "japanese_ships_sunk": sum(a.japanese_ships_sunk for a in actions),
    }
