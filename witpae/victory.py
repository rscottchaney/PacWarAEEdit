"""Read-only victory points report.

Section 0x01 (scenario) holds the score: the Japanese victory points are the i32 at 116 and the Allied ones the i32 at
120; they are shown as stored. The political points are the i32 at 65788 (Japanese) and 65792 (Allied). The ground
losses are the i32 at 64876 (Japanese) and 64880 (Allied), counted in twelfths of a victory point because the manual
(17.0) gives 1 VP per 3 Allied items, 1 per 12 Chinese or Philippine, 1 per 6 Soviet and 1 per 6 Japanese; the other
side scores the stored value // 12.
The breakdown is an estimate from manual chapter 17. A base or town is worth the owner's basic VP (location record,
value_japan at 782 and value_allies at 784) x (port size + 2 x airfield size); it scores that in full only when fully
supplied, otherwise 25% plus 75% of the supplied share (supply / supply required, at most 1; no requirement counts as
fully supplied), which gives the manual's Rabaul example (69 at 30% supply = 33). Each enemy aircraft destroyed scores
1 VP, 2 for a heavy bomber (engine count u8 at aircraft record offset 100 of 4 or more); the report sums the other
side's aircraft losses. Only the number of enemy ships sunk is shown, there is no ship formula. What the parts leave
out (ships sunk, industry damage, rules not modelled) is the "other" difference, which can be negative.
Victory level (17.1): score ratio of 1.75 or more is decisive, 1.25 or more marginal, otherwise a draw. Automatic
victory (17.2) needs a ratio of 4:1 in 1943, 3:1 in 1944 and 2:1 from 1945. The offsets come from WiTPTracker's
reader and the manual; they have not been compared with the game's Intel screen yet. Nothing here writes to the save.
"""

import struct
from collections import namedtuple

from . import aircraft, bases, losses, regions, reports
from .container import SaveFormatError

SECTION = 0x01
SCORE_OFFSETS = {"Japanese": 116, "Allied": 120}  # i32
POLITICAL_OFFSETS = {"Japanese": 65788, "Allied": 65792}  # i32
GROUND_OFFSETS = {"Japanese": 64876, "Allied": 64880}  # i32 losses, twelfths of a VP
GROUND_UNIT = 12
SIDES = ("Allied", "Japanese")
HEAVY_ENGINES = 4  # a heavy bomber has this many engines or more
HEAVY_POINTS = 2
SUPPLY_FLOOR = 0.25  # share of the value scored with no supply at all
DECISIVE_RATIO = 1.75
MARGINAL_RATIO = 1.25
AUTOMATIC_RATIOS = ((1945, 2), (1944, 3), (1943, 4))  # (from year, ratio), latest first
OTHER_SIDE = {"Allied": "Japanese", "Japanese": "Allied"}

SideScore = namedtuple("SideScore", "side score political_points bases base_points aircraft aircraft_points "
                                    "ground_points ships_sunk other")
BaseVPRow = namedtuple("BaseVPRow", "id name side region value_japan value_allies port airfield supply_pct full "
                                    "scored to_japan to_allies")


def _i32(save, offset):
    if SECTION not in save:
        raise SaveFormatError(f"section 0x{SECTION:02x} (scenario) is missing")
    data = save[SECTION].data
    if len(data) < offset + 4:
        raise SaveFormatError(f"section 0x{SECTION:02x} (scenario) is too short")
    return struct.unpack_from("<i", data, offset)[0]


def place_value(value, port, airfield):
    """Victory points of a base or town to a side: its basic VP x (port size + 2 x airfield size)."""
    return value * (port + 2 * airfield)


def scored_value(full, supply, required):
    """What the owner scores now: 25% of the full value plus 75% x the supplied share (at most 1), rounded."""
    share = 1.0 if required <= 0 else min(1.0, max(0, supply) / required)
    return int(full * (SUPPLY_FLOOR + (1 - SUPPLY_FLOOR) * share) + 0.5)


def base_rows(save):
    """One BaseVPRow per base or town that is worth something to either side, best scored value first."""
    region_map = regions.default_regions()
    rows = []
    for b in bases.list_bases(save, include_towns=True):
        value_japan, value_allies = b.get("value_japan"), b.get("value_allies")
        if not (value_japan or value_allies):
            continue
        port, airfield = b.get("port"), b.get("airfield")
        supply, required = b.get("supply"), b.get("supply_required")
        to_japan, to_allies = place_value(value_japan, port, airfield), place_value(value_allies, port, airfield)
        full = {"Japanese": to_japan, "Allied": to_allies}.get(b.side, 0)
        pct = 100 if required <= 0 else min(100, max(0, supply) * 100 // required)
        rows.append(BaseVPRow(b.id, b.name, b.side, region_map.region_of(b.id)[1], value_japan, value_allies, port,
                              airfield, pct, full, scored_value(full, supply, required) if full else 0, to_japan,
                              to_allies))
    rows.sort(key=lambda r: (-r.scored, r.name))
    return rows


def _aircraft_destroyed(save):
    """{side: (aircraft, VP)} of the aircraft each side has lost; heavy bombers count double."""
    heavy = {a.id for a in aircraft.list_aircraft(save) if a.engine_count >= HEAVY_ENGINES}
    out = {side: [0, 0] for side in SIDES}
    for row in losses.aircraft_losses(save):
        if row.side in out:
            out[row.side][0] += row.total
            out[row.side][1] += row.total * (HEAVY_POINTS if row.id in heavy else 1)
    return out


def scores(save):
    """[Allied, Japanese] SideScore; the points of a side come from what the other side has lost."""
    rows = base_rows(save)
    lost = _aircraft_destroyed(save)
    sunk = losses.sunk_ships(save)
    out = []
    for side in SIDES:
        enemy = OTHER_SIDE[side]
        mine = [r for r in rows if r.side == side and r.full > 0]
        base_points = sum(r.scored for r in mine)
        planes, plane_points = lost[enemy]
        ground_points = _i32(save, GROUND_OFFSETS[enemy]) // GROUND_UNIT
        score = _i32(save, SCORE_OFFSETS[side])
        out.append(SideScore(side, score, _i32(save, POLITICAL_OFFSETS[side]), len(mine), base_points, planes,
                             plane_points, ground_points, sum(1 for s in sunk if s.side == enemy),
                             score - base_points - plane_points - ground_points))
    return out


def victory_level(allied, japanese):
    """"Allied Decisive Victory", "Japanese Marginal Victory" or "Draw" from the two scores (manual 17.1)."""
    leader, high, low = ("Allied", allied, japanese) if allied >= japanese else ("Japanese", japanese, allied)
    if high <= 0 or high == low:
        return "Draw"
    if low <= 0 or high / low >= DECISIVE_RATIO:
        return f"{leader} Decisive Victory"
    if high / low >= MARGINAL_RATIO:
        return f"{leader} Marginal Victory"
    return "Draw"


def ratio_text(allied, japanese):
    """The leader's score ratio, for example "Allied 5.21 : 1"; "Even" when the scores are equal."""
    leader, high, low = ("Allied", allied, japanese) if allied >= japanese else ("Japanese", japanese, allied)
    if high <= 0:
        return "Even 0 : 0"
    if high == low:
        return "Even 1.00 : 1"
    if low <= 0:
        return f"{leader} {high} : 0"
    return f"{leader} {high / low:.2f} : 1"


def automatic_threshold(year):
    """The ratio that ends the game in an automatic victory in that four-digit year (17.2), None before 1943."""
    for first, ratio in AUTOMATIC_RATIOS:
        if year >= first:
            return ratio
    return None


def automatic_text(year):
    """One line on automatic victory (17.2) in the four-digit year."""
    ratio = automatic_threshold(year)
    if ratio is None:
        return f"No automatic victory before {AUTOMATIC_RATIOS[-1][0]}"
    return f"Automatic victory at {ratio}:1 from {year} (after 365 days played)"


def status_lines(save, rows=None):
    """(victory level and ratio, automatic victory line) for the GUI; rows are the scores() of the save."""
    allied, japanese = scores(save) if rows is None else rows
    level = f"{victory_level(allied.score, japanese.score)} ({ratio_text(allied.score, japanese.score)})"
    return level, automatic_text(reports.game_date(save)[2])
