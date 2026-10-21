"""Turn history: one snapshot per game date, kept next to the saves, for WiTPTracker-style trends.

Each time a save is opened (or imported) a snapshot of both sides is stored as a gzip-compressed JSON file,
<save folder>/history/<campaign slug>/<YYYYMMDD>.json.gz. A save inside a folder named "autosave" uses the parent
folder, so the game's SAVE/autosave saves share the history of SAVE. The campaign slug is the scenario name from
section 0x01 (latin-1 text, NUL-terminated, at offset 64932, at most 100 bytes), lowercased with every run of
other characters turned into "-"; two campaigns of the same scenario therefore share a folder. The player's side
is not reliably stored in a save, so a snapshot holds both sides and the GUI filters.

Schema version 1:
  {"version", "date" (YYMMDD int), "turn", "scenario", "source" (file name of the save), "recorded" (ISO time),
   "sides": {"Allied": {metric: int}, "Japanese": {...}}, the metrics listed in SIDE_METRICS,
   "bases": {"<location id>": [side id, supply, fuel, resources, oil]} for every place with any stock,
   "aircraft": {"<aircraft id>": [side id, pool, air, ground, flak, ops]} for models with a pool or total losses}
The side totals cover the places of the Industry report (bases, towns and minor places), so they match WiTPTracker.

A snapshot is written when no file exists for the date, or when the existing one came from the same save file
(a refresh). Otherwise the existing one is kept, so an edited test copy cannot clobber a real turn, until the user
asks for a replacement. Files are written atomically. Nothing here writes to a .pws save.
"""

import datetime
import gzip
import json
import os
import re
import struct
import tempfile
import zlib
from collections import namedtuple

from . import aircraft, bases, industry, losses, reports, shiprepair
from .container import SaveFile, SaveFormatError
from .fileio import is_pbem

VERSION = 1
SCENARIO_SECTION = 0x01
SCENARIO_OFFSET = 64932
SCENARIO_MAX = 100
HISTORY_DIR = "history"
AUTOSAVE_DIR = "autosave"
SUFFIX = ".json.gz"
SIDE_NAMES = ("Allied", "Japanese")
SIDE_IDS = {"Allied": 1, "Japanese": 0}

# Metric key -> display label, in the order the GUI lists them.
SIDE_METRICS = {
    "supply": "Supply stored", "fuel": "Fuel stored", "resources": "Resources stored", "oil": "Oil stored",
    "manpower": "Manpower pool", "hi": "HI pool", "naval": "Naval points pool", "merchant": "Merchant points pool",
    "armament": "Armament points pool", "vehicle": "Vehicle points pool",
    "allot_supply": "Supply allotment per day", "allot_fuel": "Fuel allotment per day",
    "allot_oil": "Oil allotment per day",
    "aircraft_pool": "Aircraft in pool",
    "loss_turn_air": "Aircraft lost to air combat (turn)", "loss_turn_ground": "Aircraft lost on the ground (turn)",
    "loss_turn_flak": "Aircraft lost to flak (turn)", "loss_turn_ops": "Aircraft lost in operations (turn)",
    "loss_turn_total": "Aircraft lost (turn)",
    "loss_air": "Aircraft lost to air combat (total)", "loss_ground": "Aircraft lost on the ground (total)",
    "loss_flak": "Aircraft lost to flak (total)", "loss_ops": "Aircraft lost in operations (total)",
    "loss_total": "Aircraft lost (total)",
    "ships_sunk": "Ships sunk", "damaged_ships": "Damaged ships", "damaged_tons": "Damaged tonnage",
    "damaged_in_port": "Damaged ships in port",
}
# Stock fields of a base entry (after the side id) and their labels.
BASE_METRICS = {"supply": "Supply", "fuel": "Fuel", "resources": "Resources", "oil": "Oil"}
BASE_KEYS = tuple(BASE_METRICS)
STOCK_KEYS = BASE_KEYS
ALLOTMENT_KEYS = ("supply", "fuel", "oil")
LOSS_KINDS = ("air", "ground", "flak", "ops")

RecordResult = namedtuple("RecordResult", "status date source path")
RECORDED, REFRESHED, REPLACED, KEPT, SKIPPED_PBEM = "recorded", "refreshed", "replaced", "kept", "skipped-pbem"
ImportResult = namedtuple("ImportResult", "imported skipped")  # [(file name, date)], [(file name, reason)]
LoadResult = namedtuple("LoadResult", "snapshots problems")  # snapshots by date, [(file name, reason)]


class HistoryError(Exception):
    """A snapshot file that cannot be used."""


class UnsupportedVersion(HistoryError):
    """A well-formed snapshot of another schema version."""


# ---- paths and dates ----------------------------------------------------

def slug(scenario):
    return re.sub(r"[^a-z0-9]+", "-", scenario.lower()).strip("-") or "unknown"


def scenario_name(save):
    if SCENARIO_SECTION not in save:
        return ""
    data = bytes(save[SCENARIO_SECTION].data[SCENARIO_OFFSET:SCENARIO_OFFSET + SCENARIO_MAX])
    return data.split(b"\0", 1)[0].decode("latin-1").strip()


def campaign_dir(save, save_path, root=None):
    """The folder of this save's campaign; root replaces <save folder>/history (used by tests)."""
    folder = os.path.dirname(os.path.abspath(save_path))
    if os.path.basename(folder).lower() == AUTOSAVE_DIR:
        folder = os.path.dirname(folder)
    return os.path.join(root if root is not None else os.path.join(folder, HISTORY_DIR), slug(scenario_name(save)))


def game_date(save):
    """(YYMMDD int, turn) of the save."""
    day, month, year = reports.game_date(save)
    yy = year - 1900
    if not (0 <= yy <= 99 and 1 <= month <= 12 and 1 <= day <= 31):
        raise SaveFormatError(f"implausible game date {day}/{month}/{year}")
    return yy * 10000 + month * 100 + day, struct.unpack_from("<H", save[reports.DATE_SECTION].data, 30)[0]


def snapshot_name(date):
    return f"{1900 + date // 10000:04d}{date // 100 % 100:02d}{date % 100:02d}{SUFFIX}"


def date_of_name(name):
    """The YYMMDD int of a snapshot file name, None for any other name."""
    m = re.fullmatch(r"(19\d\d)(\d\d)(\d\d)" + re.escape(SUFFIX), name)
    return None if m is None else (int(m.group(1)) - 1900) * 10000 + int(m.group(2)) * 100 + int(m.group(3))


def date_ordinal(date):
    """Days since 1 Jan 1900 of a YYMMDD int, for a time axis."""
    return (datetime.date(1900 + date // 10000, date // 100 % 100, date % 100) - datetime.date(1900, 1, 1)).days


# ---- building a snapshot ------------------------------------------------

def build_snapshot(save, source_name, places=None):
    """The snapshot dict of a save; places is the Industry report's place list when already built."""
    date, turn = game_date(save)
    places = industry.list_industry_places(save) if places is None else places
    sides = {name: dict.fromkeys(SIDE_METRICS, 0) for name in SIDE_NAMES}
    base_entries = {}
    for p in places:
        stock = [p.base.get(key) for key in STOCK_KEYS]
        given = industry.allotment(p)
        side = sides.get(p.base.side)
        if side is not None:
            for key, value in zip(STOCK_KEYS, stock):
                side[key] += value
            for key in ALLOTMENT_KEYS:
                side["allot_" + key] += given.get(key, 0)
        if any(stock):
            base_entries[str(p.id)] = [p.base.side_id, *stock]
    pools = industry.side_pools(save)
    for name, side in sides.items():
        side.update(pools[SIDE_IDS[name]])
    sunk = losses.sunk_ships(save)
    loss_rows = losses.aircraft_losses(save)
    for s in losses.summary_rows(sunk, loss_rows):
        side = sides[s.side]
        side["ships_sunk"] = s.ships
        for kind in LOSS_KINDS:
            side["loss_turn_" + kind] = getattr(s, "turn_" + kind)
            side["loss_" + kind] = getattr(s, kind)
        side["loss_turn_total"], side["loss_total"] = s.turn_total, s.total
    for s in shiprepair.summary_rows(shiprepair.damaged_ships(save)):
        side = sides[s.side]
        side["damaged_ships"], side["damaged_tons"], side["damaged_in_port"] = s.ships, s.tons, s.in_port
    loss_by_id = {r.id: r for r in loss_rows}
    aircraft_entries = {}
    for a in aircraft.list_aircraft(save):
        pool = a.pool
        row = loss_by_id.get(a.id)
        if a.side_id in (0, 1):
            sides[bases.SIDES[a.side_id]]["aircraft_pool"] += pool
        if pool or row:
            aircraft_entries[str(a.id)] = [a.side_id, pool, *(getattr(row, k) if row else 0 for k in LOSS_KINDS)]
    return {"version": VERSION, "date": date, "turn": turn, "scenario": scenario_name(save), "source": source_name,
            "recorded": datetime.datetime.now().isoformat(timespec="seconds"), "sides": sides,
            "bases": base_entries, "aircraft": aircraft_entries}


# ---- files --------------------------------------------------------------

def write_snapshot(directory, snap):
    """Write atomically (temporary file, then os.replace); returns the path."""
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, snapshot_name(snap["date"]))
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".tmp-", suffix=SUFFIX)
    try:
        with os.fdopen(fd, "wb") as raw:
            with gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as gz:
                gz.write(json.dumps(snap, separators=(",", ":")).encode("utf-8"))
        os.replace(tmp, path)
    except BaseException:
        try:
            os.remove(tmp)
        except OSError:
            pass
        raise
    return path


def read_snapshot(path):
    """The snapshot at path; HistoryError when it is unreadable, UnsupportedVersion for another schema."""
    try:
        with gzip.open(path, "rb") as f:
            snap = json.loads(f.read().decode("utf-8"))
    except (OSError, EOFError, zlib.error, ValueError) as exc:
        raise HistoryError(f"unreadable ({exc})") from None
    if not isinstance(snap, dict):
        raise HistoryError("not a snapshot")
    if snap.get("version") != VERSION:
        raise UnsupportedVersion(f"schema version {snap.get('version')!r} (this editor reads {VERSION})")
    if (not isinstance(snap.get("date"), int) or not isinstance(snap.get("turn"), int)
            or not all(isinstance(snap.get(k), dict) for k in ("sides", "bases", "aircraft"))):
        raise HistoryError("missing fields")
    return snap


def load_history(directory):
    """LoadResult: the snapshots sorted by date, and (file name, reason) for each file that was skipped."""
    snaps, problems = [], []
    try:
        names = sorted(os.listdir(directory))
    except OSError:
        return LoadResult([], [])
    for name in names:
        if date_of_name(name) is None:
            continue
        try:
            snaps.append(read_snapshot(os.path.join(directory, name)))
        except HistoryError as exc:
            problems.append((name, str(exc)))
    snaps.sort(key=lambda s: s["date"])
    return LoadResult(snaps, problems)


def delete_snapshot(directory, date):
    os.remove(os.path.join(directory, snapshot_name(date)))


def record(save, save_path, replace=False, root=None, places=None):
    """Store the snapshot of an opened save under the rule in the module docstring; returns a RecordResult.

    replace=True overwrites a snapshot that came from another file. Errors (file system, unreadable save)
    are raised for the caller to show.
    """
    if is_pbem(save):
        return RecordResult(SKIPPED_PBEM, None, None, None)
    date, _turn = game_date(save)
    directory = campaign_dir(save, save_path, root)
    path = os.path.join(directory, snapshot_name(date))
    source = os.path.basename(save_path)
    status = RECORDED
    if os.path.exists(path):
        try:
            existing = read_snapshot(path)
        except UnsupportedVersion as exc:
            if not replace:
                return RecordResult(KEPT, date, f"another editor version ({exc})", path)
            status = REPLACED
        except HistoryError:
            pass  # a corrupt file holds nothing worth keeping
        else:
            if existing.get("source") == source:
                status = REFRESHED
            elif replace:
                status = REPLACED
            else:
                return RecordResult(KEPT, date, existing.get("source", "?"), path)
    write_snapshot(directory, build_snapshot(save, source, places))
    return RecordResult(status, date, source, path)


def import_saves(paths, root=None, progress=None):
    """Replace the snapshot of each save's date; PBEM and unreadable saves are skipped. Returns an ImportResult."""
    imported, skipped = [], []
    for path in paths:
        name = os.path.basename(path)
        if progress:
            progress(name)
        try:
            save = SaveFile.load(path)
        except (OSError, SaveFormatError, KeyError, struct.error, ValueError) as exc:
            skipped.append((name, f"unreadable: {exc}"))
            continue
        try:
            result = record(save, path, replace=True, root=root)
        except (SaveFormatError, KeyError, struct.error, ValueError) as exc:
            skipped.append((name, f"unreadable: {exc}"))
            continue
        if result.status == SKIPPED_PBEM:
            skipped.append((name, "PBEM"))
        else:
            imported.append((name, result.date))
    return ImportResult(imported, skipped)


# ---- series for the views -----------------------------------------------

def side_series(snaps, metric):
    """[(date, turn, allied, japanese)] in snapshot order; a value is None when the snapshot lacks the metric."""
    return [(s["date"], s["turn"], *(s["sides"].get(side, {}).get(metric) for side in SIDE_NAMES)) for s in snaps]


def base_series(snaps, loc_id, metric):
    """[(date, turn, side id, value)] for one base; side id and value are None where the base is not recorded."""
    index = 1 + BASE_KEYS.index(metric)
    out = []
    for s in snaps:
        entry = s["bases"].get(str(loc_id))
        out.append((s["date"], s["turn"], *((entry[0], entry[index]) if entry else (None, None))))
    return out


def bases_seen(snaps):
    """Sorted ids of the bases recorded in any snapshot."""
    return sorted({int(k) for s in snaps for k in s["bases"]})


def base_choices(snaps, names):
    """[(label, id)] sorted by name; names is {id: name} from the open save, unknown ids are shown as "#id"."""
    items = [(f"{names[i]} ({i})" if i in names else f"#{i}", i) for i in bases_seen(snaps)]
    return sorted(items, key=lambda t: (t[0].lower(), t[1]))


def changes(values):
    """Change of each value from the previous recorded one; None for a missing value and for the first."""
    out, previous = [], None
    for v in values:
        out.append(None if v is None or previous is None else v - previous)
        if v is not None:
            previous = v
    return out
