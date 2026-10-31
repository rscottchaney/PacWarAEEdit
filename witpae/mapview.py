"""The game's map art and the overlays drawn on it, for the Map tab. Nothing here writes to the save.

Map art: the game's ART folder has WPEH00.bmp..WPEH41.bmp (hex grid drawn) and WPEN00..41 (no grid), uncompressed
24-bit bottom-up BMPs. Tile n = row * 7 + col sits at (col * 1500, row * 1500) of a 9703 x 7767 px map; most tiles are
1500 x 1500, column 6 is 703 wide and row 5 is 267 high. The sizes are read from the headers, not assumed: the width
of column c is that of the row-0 tile and the height of row r that of the column-0 tile, and every other tile must
match them. render subsamples by nearest neighbour (every step-th pixel of a global grid, so tiles line up) and builds
a P6 PPM in memory for tk.PhotoImage; the full size (step 1) is too big for a Tk image. Every failure is a ValueError.

Hexes: the centre of hex (x, y) is at px = x * 42 - 6 + (21 if y is odd else 0), py = y * 38 - 18 in full-size pixels
(checked: Pearl Harbor lands on Oahu). pixel_to_hex inverts this.

Overlays are plain namedtuples built from the save, one builder per overlay. Search arcs use the group's search (or
ASW) patrol %, its maximum range setting and the aircraft's normal radius: radius = min(range setting, normal radius),
or the normal radius when the setting is 0; a group with radius 0, 0 % patrol, no location or an unknown ship is left
out. A group aboard a ship (location >= 18000) is placed at the ship's task force, or at its port. The arc is in
degrees, 0 = north, clockwise from start to end. UNVERIFIED: a start equal to the end is taken as a full circle, the
tracker's "Random" (the others being "Defined"); only one arc pair is known, so it is used for both Naval and ASW;
the patrol range may not be capped exactly like this in the game. Combat actions come from the combat reports and are
not tied to a side, so the Side choice does not apply to them. Colours, scales and the drawing are in the editor.

Support uses the editor's estimate from current equipment, the same one the Land Units tab shows: one support squad
per non-support element; Support and Motorized Support supply it; Aviation and Naval Support neither supply nor need
it. That estimate reflects unsaved edits, but it is not the game's stored per-unit value and matches it on most
units, not all. Units are placed by their own record hex; those at (0,0) are left out.

Supply compares, per side and hex, the supply available with the supply required, as WitpStaff does. A base's
requirement already includes that of the land units based there (their location is the base), so those units' own
stock is not added; units in the hex but not based there (on the march, or at location 0) add both their supplies and
their requirement. A hex with no base of its side sums its units. Supply carried on ships is not counted. A hex is
shown when something is required there, when a unit is short of supplies, or when its base spoils supply (supply over
the limit of reports.spoilage_limits); a hex that only holds supply that nothing needs is left out. The bar is
quadratic like WitpStaff's: a surplus of 100000 is 1.5 hexes (45000 = 1), a lack of 10000 is 1.5 hexes (4400 = 1). The
nearest supply is a straight line over the hexes and ignores terrain, sea and enemy territory.
"""

import math
import os
from collections import namedtuple

from . import aircraft, airgroups, bases, landunits, planeart, regions, reports, shiprecords, taskforces

COLUMNS, ROWS = 7, 6
STYLES = {"Hexes": "WPEH", "No hexes": "WPEN"}
HEX_W, HEX_H = 42, 38
ORIGIN_X, ORIGIN_Y = -6, -18
FULL_SIZE = (9703, 7767)  # of the real art; used only to size a plain background when there is none
SHIP_LOCATION_BASE = airgroups.SHIP_LOCATION_BASE

LocationMark = namedtuple("LocationMark", "id name side x y kind")
SearchArc = namedtuple("SearchArc", "group_id name side x y radius start end full kind")
TaskForceMark = namedtuple("TaskForceMark", "id name side x y mission ships dest_id dest_x dest_y")
CombatMark = namedtuple("CombatMark", "date kind phase place x y title action")
UnitSupport = namedtuple("UnitSupport", "id name side x y support needed")
SupportMark = namedtuple("SupportMark", "side x y support needed units")
UnitSupply = namedtuple("UnitSupply", "id name side x y supplies required short at_base")
SupplyMark = namedtuple("SupplyMark", "side x y base available required short_units spoiling units")


# ---- hexes ---------------------------------------------------------------

def hex_to_pixel(x, y):
    """Centre of hex (x, y) in full-size map pixels."""
    return x * HEX_W + ORIGIN_X + (HEX_W // 2 if y % 2 else 0), y * HEX_H + ORIGIN_Y


def pixel_to_hex(px, py):
    """The hex whose centre is nearest to a full-size map pixel."""
    row = round((py - ORIGIN_Y) / HEX_H)
    best = None
    for y in (row - 1, row, row + 1):
        x = round((px - ORIGIN_X - (HEX_W // 2 if y % 2 else 0)) / HEX_W)
        cx, cy = hex_to_pixel(x, y)
        dist = (cx - px) ** 2 + (cy - py) ** 2
        if best is None or dist < best[0]:
            best = (dist, x, y)
    return best[1], best[2]


def compass_to_tk(start, end):
    """(start, extent) of a Tk arc for a compass arc: Tk counts degrees counter-clockwise from east."""
    return (90 - end) % 360, (end - start) % 360 or 360


# ---- art -----------------------------------------------------------------

def tile_name(style, n):
    return f"{STYLES[style]}{n:02d}.bmp"


def find_art(candidates, style):
    """The first candidate folder that has all 42 tiles of the style, or None."""
    names = [tile_name(style, n) for n in range(COLUMNS * ROWS)]
    for folder in candidates:
        if folder and all(os.path.isfile(os.path.join(folder, name)) for name in names):
            return folder
    return None


def _tile_sizes(folder, style):
    """({tile number: (data position, width, height)}, column widths, row heights), checked to form a grid."""
    if style not in STYLES:
        raise ValueError(f"unknown map style {style!r}")
    info = {}
    for n in range(COLUMNS * ROWS):
        name = tile_name(style, n)
        try:
            with open(os.path.join(folder, name), "rb") as f:
                info[n] = planeart._header(f)
        except OSError as exc:
            raise ValueError(f"cannot read {name}: {exc.strerror or exc}") from None
        except ValueError as exc:
            raise ValueError(f"{name}: {exc}") from None
    widths = [info[c][1] for c in range(COLUMNS)]
    heights = [info[r * COLUMNS][2] for r in range(ROWS)]
    for n, (_pos, w, h) in info.items():
        if (w, h) != (widths[n % COLUMNS], heights[n // COLUMNS]):
            raise ValueError(f"{tile_name(style, n)} is {w} x {h}, expected {widths[n % COLUMNS]} x "
                             f"{heights[n // COLUMNS]}")
    return info, widths, heights


def map_size(folder, style):
    """(width, height) of the whole map in full-size pixels."""
    _info, widths, heights = _tile_sizes(folder, style)
    return sum(widths), sum(heights)


def render(folder, style, step):
    """(width, height, PPM bytes) of the map with every step-th pixel kept (step 8 = 12 %, 4 = 25 %, 2 = 50 %, 1 = 100 %)."""
    if not isinstance(step, int) or isinstance(step, bool) or step < 1:
        raise ValueError("step must be a positive whole number")
    info, widths, heights = _tile_sizes(folder, style)
    out_w, out_h = -(-sum(widths) // step), -(-sum(heights) // step)
    head = b"P6\n%d %d\n255\n" % (out_w, out_h)
    out = bytearray(head) + bytearray(out_w * out_h * 3)
    base = len(head)
    y0 = 0
    for row in range(ROWS):
        x0 = 0
        for col in range(COLUMNS):
            n = row * COLUMNS + col
            data_pos, w, h = info[n]
            name = tile_name(style, n)
            try:
                with open(os.path.join(folder, name), "rb") as f:
                    raw = f.read()
            except OSError as exc:
                raise ValueError(f"cannot read {name}: {exc.strerror or exc}") from None
            stride = (w * 3 + 3) // 4 * 4  # rows are padded to 4 bytes and stored bottom-up
            if len(raw) < data_pos + stride * (h - 1) + w * 3:
                raise ValueError(f"{name} is truncated")
            c0, r0 = -x0 % step, -y0 % step  # first source column and row on the global grid
            ox = (x0 + c0) // step
            for sr in range(r0, h, step):
                pos = data_pos + (h - 1 - sr) * stride
                line = raw[pos + 3 * c0:pos + w * 3]
                count = len(line[0::3 * step])
                if not count:
                    continue
                px = bytearray(3 * count)
                px[0::3], px[1::3], px[2::3] = line[2::3 * step], line[1::3 * step], line[0::3 * step]
                dest = base + (((y0 + sr) // step) * out_w + ox) * 3
                out[dest:dest + 3 * count] = px
            x0 += w
        y0 += heights[row]
    return out_w, out_h, bytes(out)


# ---- overlays ------------------------------------------------------------

def _side_ok(side, wanted):
    return wanted in (None, "All") or side == wanted


def location_marks(save, include_towns=False, side="All", region=None):
    """Bases (and towns) as LocationMarks; region is a region id, or None for all."""
    names = regions.default_regions() if region is not None else None
    out = []
    for b in bases.list_bases(save, include_towns=include_towns):
        if not _side_ok(b.side, side):
            continue
        if names is not None and names.region_of(b.id)[0] != region:
            continue
        out.append(LocationMark(b.id, b.name, b.side, b.x, b.y, b.kind))
    return out


def group_hex(save, group):
    """(x, y) of an arrived air group (at a place, or aboard a ship in a task force or port), else None."""
    loc = group.location_id
    if bases.is_place(save, loc):
        return bases.place_hex(save, loc)
    if loc < SHIP_LOCATION_BASE:
        return None
    return ship_hex(save, loc - SHIP_LOCATION_BASE)


def ship_hex(save, ship_id):
    """(x, y) of a ship: its task force's hex, else its port's, else None (also for an unknown ship)."""
    if not taskforces._ship_exists(save, ship_id):
        return None
    tf = taskforces._ship(save, ship_id, shiprecords.TASK_FORCE_OFFSET)
    if tf and taskforces.is_task_force(save, tf):
        return bases.place_hex(save, tf)
    port = taskforces._ship(save, ship_id, shiprecords.BASE_OFFSET)
    return bases.place_hex(save, port) if bases.is_place(save, port) else None


def search_arcs(save, kind="Naval", mode="All", side="All"):
    """SearchArcs of the groups on Naval (search patrol) or ASW patrol; mode is All, Defined or Random."""
    field = {"Naval": "search", "ASW": "asw"}[kind]
    if mode not in ("All", "Defined", "Random"):
        raise ValueError(f"unknown arc mode {mode!r}")
    normal_radius = {}
    out = []
    for g in airgroups.list_airgroups(save):
        if g.get(field) == 0 or not _side_ok(g.side, side):
            continue
        full = g.get("arc_start") == g.get("arc_end")
        if mode != "All" and full != (mode == "Random"):
            continue
        aid = g.aircraft_id
        if aid not in normal_radius:
            normal_radius[aid] = aircraft.Aircraft(save, aid, "").get("normal_radius_hex")
        normal, limit = normal_radius[aid], g.get("range")
        radius = min(limit, normal) if limit else normal
        pos = group_hex(save, g) if radius > 0 else None
        if pos is None:
            continue
        out.append(SearchArc(g.id, g.name, g.side, pos[0], pos[1], radius, g.get("arc_start"), g.get("arc_end"),
                             full, kind))
    return out


def task_force_marks(save, side="All"):
    """TaskForceMarks; the destination hex is None when the TF has none or it is not a place or task force."""
    out = []
    for tf in taskforces.list_task_forces(save):
        if not _side_ok(tf.side, side):
            continue
        dest = tf.destination
        dest_hex = None
        if dest and (bases.is_place(save, dest) or taskforces.is_task_force(save, dest)):
            dest_hex = bases.place_hex(save, dest)
        x, y = tf.hex
        out.append(TaskForceMark(tf.id, tf.name, tf.side, x, y, tf.mission_label, len(tf.ships), dest,
                                 *(dest_hex or (None, None))))
    return out


def combat_marks(actions, kind="All"):
    """CombatMarks of the actions that have a hex (and are of the kind, unless All)."""
    return [CombatMark(a.date, a.kind, a.phase, a.place, a.x, a.y, a.title, a)
            for a in actions if a.x is not None and a.y is not None and kind in ("All", a.kind)]


def _units_on_map(save, side):
    """(land unit, x, y) of the arrived units of a side that are on the map, by the unit's own record hex."""
    for u in landunits.list_land_units(save):
        if not u.arrived or not _side_ok(u.side, side):
            continue
        x, y = u._i16(bases.X_OFFSET), u._i16(bases.Y_OFFSET)
        if (x, y) != (0, 0):  # (0,0) is not on the map
            yield u, x, y


def unit_support(save, side="All"):
    """UnitSupports of the arrived land units that are on the map, by the unit's own record hex.

    Not the location's hex: units on the march and field units at location 0 are really in their hex.
    """
    out = []
    for u, x, y in _units_on_map(save, side):
        support, needed = u.support_estimate()
        out.append(UnitSupport(u.id, u.display_name, u.side, x, y, support, needed))
    return out


def support_marks(save, side="All"):
    """SupportMarks per (side, hex) with land units, sorted by x, y, side.

    A hex whose units neither need nor give support is left out.
    """
    groups = {}
    for u in unit_support(save, side):
        groups.setdefault((u.side, u.x, u.y), []).append(u)
    out = []
    for (s, x, y), units in sorted(groups.items(), key=lambda kv: (kv[0][1], kv[0][2], kv[0][0])):
        support, needed = sum(u.support for u in units), sum(u.needed for u in units)
        if support or needed:
            out.append(SupportMark(s, x, y, support, needed, units))
    return out


def support_bar(diff):
    """Bar length in hexes for support minus needed, quadratic as in WitpStaff: 15 = 1/4, 60 = 1/2, 230 = 1, max 1.5."""
    return min(1.5, math.sqrt(abs(diff) / 230)) if diff else 0


SUPPLY_SURPLUS_SCALE = 44444  # a surplus of 100000 is 1.5 hexes
SUPPLY_LACK_SCALE = 4444  # a lack of 10000 is 1.5 hexes


def supply_marks(save, side="All"):
    """SupplyMarks per (side, hex) with a base, a town or land units, sorted by x, y, side.

    With a base (or town) of the side in the hex, available is its supply plus the supplies of the hex's units that
    are not based there, and required its requirement plus theirs; units based there are already in the base's
    requirement. Without one, both are sums over the units. Two places of one side in a hex are summed. A hex is kept
    when required > 0, a unit is short, or the base spoils supply; one that only holds unneeded supply is left out.
    """
    groups = {}
    for b in bases.list_bases(save, include_towns=True):
        if _side_ok(b.side, side):
            groups.setdefault((b.side, b.x, b.y), ([], []))[0].append(b)
    for u, x, y in _units_on_map(save, side):
        groups.setdefault((u.side, x, y), ([], []))[1].append(u)
    spoiling = {id(r.base) for r in reports.spoilage_rows([b for bs, _ in groups.values() for b in bs])
                if r.supply_over > 0}
    out = []
    for (s, x, y), (places, land) in sorted(groups.items(), key=lambda kv: (kv[0][1], kv[0][2], kv[0][0])):
        ids = {b.id for b in places}
        available = sum(b.get("supply") for b in places)
        required = sum(b.get("supply_required") for b in places)
        units = []
        for u in land:
            at_base = u.location_id in ids
            if not at_base:
                available += u.get("supplies")
                required += u.supplies_required
            units.append(UnitSupply(u.id, u.display_name, u.side, x, y, u.get("supplies"), u.supplies_required,
                                    u.supplies_short, at_base))
        short_units = sum(u.short for u in units)
        spoils = any(id(b) in spoiling for b in places)
        if required > 0 or short_units or spoils:
            out.append(SupplyMark(s, x, y, places[0] if places else None, available, required, short_units, spoils,
                                  units))
    return out


def supply_bar(diff):
    """Bar length in hexes for available minus required supply, quadratic as in WitpStaff and asymmetric, max 1.5."""
    if diff > 0:
        return min(1.5, math.sqrt(diff / SUPPLY_SURPLUS_SCALE))
    return min(1.5, math.sqrt(-diff / SUPPLY_LACK_SCALE))


def hex_distance(a, b):
    """Number of hexes between (x, y) pairs a and b on the offset grid (odd rows shifted half a hex right)."""
    def cube(x, y):
        return x - (y - (y & 1)) // 2, y
    (q1, r1), (q2, r2) = cube(*a), cube(*b)
    dq, dr = q1 - q2, r1 - r2
    return max(abs(dq), abs(dr), abs(dq + dr))


def nearest_supply(save, side, x, y, count=3, minimum=20000):
    """Up to count (base, surplus, distance) of the side's bases and towns with more than minimum spare supply.

    Nearest first by straight-line hex_distance, which ignores terrain, sea and enemy territory (as in WitpStaff).
    The hex (x, y) itself is excluded.
    """
    found = []
    for b in bases.list_bases(save, include_towns=True):
        surplus = b.get("supply") - b.get("supply_required")
        if b.side == side and surplus > minimum and (b.x, b.y) != (x, y):
            found.append((b, surplus, hex_distance((x, y), (b.x, b.y))))
    found.sort(key=lambda t: (t[2], -t[1]))
    return found[:count]


INDEX_CATEGORIES = ("Places", "Land units", "Support", "Supply", "Task forces", "Air groups searching", "Combat")


def hex_index(save, actions):
    """{(x, y): {category: [mark, ...]}} of everything the overlays can show, for the click report.

    Places are bases and towns, Land units and Support are the arrived land units on the map and the totals of their
    hexes (both sides), Supply is the SupplyMarks of both sides, Air groups searching are SearchArcs of both kinds
    (a group on both patrols is listed twice), Combat is every action with a hex.
    """
    index = {}

    def add(category, marks):
        for m in marks:
            index.setdefault((m.x, m.y), {}).setdefault(category, []).append(m)

    add("Places", location_marks(save, include_towns=True))
    add("Land units", unit_support(save))
    add("Support", support_marks(save))
    add("Supply", supply_marks(save))
    add("Task forces", task_force_marks(save))
    add("Air groups searching", search_arcs(save, "Naval") + search_arcs(save, "ASW"))
    add("Combat", combat_marks(actions))
    return index
