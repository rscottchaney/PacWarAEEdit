"""What happened between turns, found by comparing consecutive history snapshots.

Ported from the Events tab of WitpStaff. A snapshot (witpae/history.py) holds the optional keys places, ships, units,
groups; each kind of event but the last is the difference of one of them between two snapshots:

- Base captured: a place whose side changed (the event's side is the new owner).
- Ship arrived (not yet arrived -> arrived) and Ship sunk (arrived or not yet arrived -> sunk).
- Land unit arrived and Air group arrived: an id in the later snapshot's list but not in the earlier one.
- Leader skill changed: an entry of the campaign's leader log (history.update_leader_log), dated as recorded.

An id found in only one of the two snapshots (a place, ship or leader) is ignored. A kind is skipped for a pair of
snapshots when either lacks its key, which is the case for snapshots recorded by an older editor. Snapshots hold no
names, so the open save supplies names, sides and hexes (event_names); an id it does not know shows as "<kind> <id>".
Nothing here reads or writes a file.
"""

from collections import namedtuple

from . import airgroups, bases, history, landunits, leaders, shiprecords

Event = namedtuple("Event", "date kind side subject_kind subject_id subject detail x y")
Skipped = namedtuple("Skipped", "date keys")  # a pair of snapshots (by the later date) that lacked these keys
EventResult = namedtuple("EventResult", "events skipped")

PLACE, SHIP, LAND_UNIT, AIR_GROUP, LEADER = "place", "ship", "land unit", "air group", "leader"
KINDS = ("Base captured", "Ship arrived", "Ship sunk", "Land unit arrived", "Air group arrived",
         "Leader skill changed")
KEYS_OF_KIND = {"Base captured": "places", "Ship arrived": "ships", "Ship sunk": "ships",
                "Land unit arrived": "units", "Air group arrived": "groups", "Leader skill changed": "leader log"}
_ORDER = {kind: n for n, kind in enumerate(KINDS)}


def event_names(save):
    """{(subject kind, id): (name, side, (x, y) or None)} for the places, ships, land units, groups and leaders."""
    out = {}
    for b in bases.list_bases(save, include_towns=True, include_minor=True):
        out[PLACE, b.id] = (b.name, b.side, bases.place_hex(save, b.id))
    for r in shiprecords.list_ship_records(save):
        out[SHIP, r.id] = (r.name, r.side, None)
    for u in landunits.list_land_units(save):
        out[LAND_UNIT, u.id] = (u.display_name, u.side, None)
    for g in airgroups.list_airgroups(save):
        out[AIR_GROUP, g.id] = (g.name, g.side, None)
    for row in leaders.list_leaders(save):
        out[LEADER, row.id] = (row.name, row.side, None)
    return out


def _subject(names, subject_kind, subject_id, side=None):
    """(subject text, side text, x, y) for an event."""
    name, known_side, where = names.get((subject_kind, subject_id), (f"{subject_kind} {subject_id}", "", None))
    x, y = where or (None, None)
    return name, known_side if side is None else side, x, y


def _make(date, kind, subject_kind, subject_id, detail, names, side=None):
    name, side, x, y = _subject(names, subject_kind, subject_id, side)
    return Event(date, kind, side, subject_kind, subject_id, name, detail, x, y)


def _missing(prev, cur):
    """The event keys that either snapshot lacks, in history.EVENT_KEYS order."""
    return [k for k in history.EVENT_KEYS if k not in prev or k not in cur]


def _rating_changes(old, new):
    """"Naval 54 -> 56, Aggression 60 -> 58" from two hex strings of the ratings; "" when nothing differs."""
    try:
        before, after = bytes.fromhex(old), bytes.fromhex(new)
    except (ValueError, TypeError):
        return ""
    if len(before) != len(after) or len(before) != len(leaders.RATING_NAMES):
        return ""
    return ", ".join(f"{name.capitalize()} {a} -> {b}"
                     for name, a, b in zip(leaders.RATING_NAMES, before, after) if a != b)


def events_between(prev, cur, names):
    """The Events of the later snapshot cur against the earlier prev, in KINDS order then by subject."""
    date, missing = cur["date"], _missing(prev, cur)
    out = []
    if "places" not in missing:
        for loc, side_id in cur["places"].items():
            old = prev["places"].get(loc)
            if old is not None and old != side_id:
                detail = f"{bases.SIDES.get(old, old)} -> {bases.SIDES.get(side_id, side_id)}"
                out.append(_make(date, "Base captured", PLACE, int(loc), detail, names, bases.SIDES.get(side_id, "")))
    if "ships" not in missing:
        for ship, status in cur["ships"].items():
            old = prev["ships"].get(ship)
            if old is None or old == status:
                continue
            if old == history.SHIP_PENDING and status == history.SHIP_ARRIVED:
                out.append(_make(date, "Ship arrived", SHIP, int(ship), "", names))
            elif status == history.SHIP_SUNK:
                out.append(_make(date, "Ship sunk", SHIP, int(ship), "", names))
    for key, kind, subject_kind in (("units", "Land unit arrived", LAND_UNIT),
                                    ("groups", "Air group arrived", AIR_GROUP)):
        if key not in missing:
            before = set(prev[key])
            out.extend(_make(date, kind, subject_kind, i, "", names) for i in cur[key] if i not in before)
    out.sort(key=lambda e: (_ORDER[e.kind], e.subject.lower(), e.subject_id))
    return out


def leader_events(log, names):
    """The Leader skill changed events of a leader log (history.read_leader_log; None gives no events)."""
    out = []
    for date, leader, old, new in (log or {}).get("changes", ()):
        detail = _rating_changes(old, new)
        if detail:
            out.append(_make(date, "Leader skill changed", LEADER, leader, detail, names))
    return out


def all_events(snaps, names, log=None):
    """EventResult: the events of every consecutive pair of snapshots (date order), a Skipped for each pair that
    lacked keys, and the leader log's changes. An event's date is the later snapshot's (the log's own date for a
    leader change). The events are sorted by date, then KINDS, then subject."""
    ordered = sorted(snaps, key=lambda s: s["date"])
    events, skipped = [], []
    for prev, cur in zip(ordered, ordered[1:]):
        missing = _missing(prev, cur)
        if missing:
            skipped.append(Skipped(cur["date"], missing))
        events.extend(events_between(prev, cur, names))
    events.extend(leader_events(log, names))
    events.sort(key=lambda e: (e.date, _ORDER[e.kind], e.subject.lower(), e.subject_id))
    return EventResult(events, skipped)


def without_event_data(snaps):
    """Dates of the snapshots that lack any of the event keys."""
    return [s["date"] for s in snaps if any(k not in s for k in history.EVENT_KEYS)]
