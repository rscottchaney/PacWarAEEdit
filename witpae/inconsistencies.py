"""Read-only list of data in a save that contradicts itself, ported from WitpStaff's Inconsistencies tab.

WitpStaff (manual 4.11) lists leaders leading several units, units with no leader or a foreign leader, LCUs with
the wrong suffix or HQ, ships in task forces that do not exist, and task forces with a missing home port. Its notes
say the leader data in saves "seems a bit unreliable", so the rules here are narrower than the manual's list. Each
check was measured on the sample save (going2_411210.pws) and on a real save (wpae018.pws) before it was kept; the
counts below are sample, real:

* Leader commands several units: a leader with more than one entry in `leaders.assignments`, unless the entries are
  exactly one ship and one task force (a captain who also leads the TF; 70 and 86 leaders, all of that shape).
  Fires on 0 and 0.
* Unit without a leader: leader 0 on an arrived air group (3 and 3 of about 1,100), land unit or HQ (0 and 0
  once fragments are skipped: all 187 and 130 hits were per-ship fragment records, ids 10000 and up sharing the
  name of a lower-id unit, which carry no leader of their own) or ship (0 and 0; the 12 and 16 ships with
  leader 0 have not arrived). Task forces are narrowed: 48 of 236 and 84 of 284 have no leader, but every Cargo,
  Transport and Tanker TF has none, which is normal, so the supply missions are skipped (LOGISTICS_MISSIONS); 2 and
  10 TFs remain.
* Leader of the other side: the leader's side (`leaders.side_of` his nation) differs from the unit's side, or the
  leader id names an unused leader record. Fires on 0 and 0 for air groups, ships, land units and task forces.
* Land unit HQ is not an HQ: `LandUnit.hq_id` is non-zero and the record is not type 4 (an HQ naming itself is
  fine). Narrowed to arrived units: all 730 units not yet arrived point at placeholder records (type 1 or 5), so the
  unfiltered check fires on 13% of land units and means nothing. Arrived units: 0 and 0.
* Ship in missing task force: the ship's TF id is non-zero but not a task force. 0 and 0.
* Broken ship chain: `taskforces.chain` raises ValueError for a task force or a port that holds ships; the text is
  the detail. The editor refuses ship moves in such saves. 0 of 377 and 0 of 425 chains.
* Task force home port: non-zero and not a base or town, or a place of the other side. Home port 0 is never seen.
  Fires on 1 and 1 (the Japanese Guam Invasion TF names Guam, an Allied base).

Issue.future marks subjects that have not arrived yet (land units, air groups and ships not arrived, leaders with a
delay); WitpStaff has the same option. Nothing here writes to the save.
"""

import struct
from collections import namedtuple

from . import bases, landunits, leaders, shiprecords, taskforces
from .airgroups import SHIP_RECORD_SIZE, SHIP_SECTION, list_airgroups
from .bases import LOCATION_SECTION, RECORD_SIZE as LOCATION_RECORD_SIZE, SIDES

Issue = namedtuple("Issue", "check side subject_kind subject_id subject detail future")

CHECK_SEVERAL = "Leader commands several units"
CHECK_NO_LEADER = "Unit without a leader"
CHECK_SIDE = "Leader of the other side"
CHECK_HQ = "Land unit HQ is not an HQ"
CHECK_SHIP_TF = "Ship in missing task force"
CHECK_CHAIN = "Broken ship chain"
CHECK_HOME = "Task force home port"
CHECKS = (CHECK_SEVERAL, CHECK_NO_LEADER, CHECK_SIDE, CHECK_HQ, CHECK_SHIP_TF, CHECK_CHAIN, CHECK_HOME)

# Supply and transport task forces normally sail without a leader (measured: every Cargo, Transport and Tanker TF).
LOGISTICS_MISSIONS = frozenset({5, 6, 11, 12, 13, 18})
HQ_TYPE = 4

KIND_LEADER, KIND_GROUP, KIND_SHIP, KIND_TF, KIND_LCU, KIND_PLACE = (
    "leader", "air group", "ship", "task force", "land unit", "place")


class _Context:
    """The inputs several checks share, each built on first use."""

    def __init__(self, save):
        self.save = save
        self._assigned = None
        self._rows = None

    @property
    def assigned(self):
        if self._assigned is None:
            self._assigned = leaders.assignments(self.save)
        return self._assigned

    @property
    def rows(self):
        """{leader id: LeaderRow} of the named leaders."""
        if self._rows is None:
            self._rows = {r.id: r for r in leaders.list_leaders(self.save, self.assigned)}
        return self._rows


def _ctx(save, ctx):
    return ctx if ctx is not None else _Context(save)


def _name(save, loc_id, label):
    name = taskforces._name(save, loc_id)
    return f"{label} {loc_id} {name}" if name else f"{label} {loc_id}"


def _index_side(save, loc_id):
    return SIDES.get(bases.place_side_id(save, loc_id), "Unknown")


def _units(save):
    """(kind, id, name, side, leader id, arrived) of every air group, ship, land unit and TF with ships."""
    out = []
    for g in list_airgroups(save):
        out.append((KIND_GROUP, g.id, g.name, g.side, g.leader_id, g.arrived))
    ship_data = save[SHIP_SECTION].data
    for r in shiprecords.list_ship_records(save):
        leader = struct.unpack_from("<H", ship_data, r.id * SHIP_RECORD_SIZE + leaders.SHIP_LEADER_OFFSET)[0]
        out.append((KIND_SHIP, r.id, r.name, r.side, leader, r.arrived))
    loc_data = save[LOCATION_SECTION].data
    for u in landunits.list_land_units(save):
        leader = struct.unpack_from("<H", loc_data, u.id * LOCATION_RECORD_SIZE + leaders.LOCATION_LEADER_OFFSET)[0]
        out.append((KIND_LCU, u.id, u.display_name, u.side, leader, u.arrived))
    for tf in taskforces.list_task_forces(save):
        leader = struct.unpack_from("<H", loc_data, tf.id * LOCATION_RECORD_SIZE + leaders.LOCATION_LEADER_OFFSET)[0]
        out.append((KIND_TF, tf.id, _name(save, tf.id, "TF"), _index_side(save, tf.id), leader, True))
    return out


def leader_commands_several(save, ctx=None):
    """Leaders with more than one command, except exactly one ship plus one task force."""
    ctx = _ctx(save, ctx)
    out = []
    for leader_id, units in ctx.assigned.items():
        row = ctx.rows.get(leader_id)
        if row is None or len(units) < 2 or sorted(u[0] for u in units) == [leaders.KIND_SHIP, leaders.KIND_TF]:
            continue
        detail = "; ".join(f"{kind} {name}" for kind, _id, name in units)
        out.append(Issue(CHECK_SEVERAL, row.side, KIND_LEADER, leader_id, row.name, detail, row.delay > 0))
    return out


def unit_without_leader(save, ctx=None):
    """Arrived air groups, ships, land units (HQs included) and non-logistics task forces with leader 0.

    A land unit fragment (a record sharing its side and name with a lower id, as a unit split over several ships
    is stored) carries no leader of its own and is skipped.
    """
    units = _units(save)
    first_lcu = {}
    for kind, unit_id, name, side, _leader, _arrived in units:
        if kind == KIND_LCU:
            first_lcu.setdefault((side, name), unit_id)
    out = []
    for kind, unit_id, name, side, leader, arrived in units:
        if leader > 0 or not arrived:
            continue
        if kind == KIND_TF and taskforces.TaskForce(save, unit_id).mission in LOGISTICS_MISSIONS:
            continue
        if kind == KIND_LCU and first_lcu[(side, name)] != unit_id:
            continue
        out.append(Issue(CHECK_NO_LEADER, side, kind, unit_id, name, "Leader id is 0", False))
    return out


def unit_leader_side(save, ctx=None):
    """Units whose leader belongs to the other side, or names an unused leader record."""
    ctx = _ctx(save, ctx)
    out = []
    for kind, unit_id, name, side, leader, arrived in _units(save):
        if leader <= 0:
            continue
        row = ctx.rows.get(leader)
        if row is None:
            detail = f"Leader {leader} is an unused leader record"
        elif side in ("Allied", "Japanese") and row.side != side:
            detail = f"Leader {row.name} (#{leader}) is {row.side}"
        else:
            continue
        out.append(Issue(CHECK_SIDE, side, kind, unit_id, name, detail, not arrived))
    return out


def land_unit_hq(save, ctx=None):
    """Arrived land units whose HQ id is non-zero and not an HQ record; an HQ naming itself is fine."""
    data = save[LOCATION_SECTION].data
    out = []
    for u in landunits.list_land_units(save):
        hq = u.hq_id
        if not u.arrived or hq == 0:
            continue
        in_range = 0 <= hq < bases.RECORD_COUNT and (hq + 1) * LOCATION_RECORD_SIZE <= len(data)
        kind = struct.unpack_from("<h", data, hq * LOCATION_RECORD_SIZE + bases.TYPE_OFFSET)[0] if in_range else None
        if kind != HQ_TYPE:
            shown = "outside the table" if kind is None else f"type {kind}"
            out.append(Issue(CHECK_HQ, u.side, KIND_LCU, u.id, u.display_name,
                             f"HQ id {hq} is not an HQ record ({shown})", False))
    return out


def ship_in_missing_task_force(save, ctx=None):
    """Ships whose task force id is non-zero but not a task force."""
    out = []
    for r in shiprecords.list_ship_records(save):
        tf_id = taskforces._ship(save, r.id, shiprecords.TASK_FORCE_OFFSET)
        if tf_id and not taskforces.is_task_force(save, tf_id):
            out.append(Issue(CHECK_SHIP_TF, r.side, KIND_SHIP, r.id, r.name,
                             f"Task force {tf_id} does not exist", not r.arrived))
    return out


def broken_chains(save, ctx=None):
    """Task forces and ports holding ships whose ship chain fails taskforces.chain; the error is the detail."""
    data = save[LOCATION_SECTION].data
    out = []
    for loc_id in range(min(bases.RECORD_COUNT, len(data) // LOCATION_RECORD_SIZE)):
        if taskforces.is_task_force(save, loc_id):
            kind, name = KIND_TF, _name(save, loc_id, "TF")
        elif bases.is_place(save, loc_id):
            kind, name = KIND_PLACE, taskforces._name(save, loc_id) or f"place {loc_id}"
        else:
            continue
        if not (taskforces._loc(save, loc_id, taskforces.COUNT_OFFSET)
                or taskforces._loc(save, loc_id, taskforces.LAST_OFFSET)):
            continue
        try:
            taskforces.chain(save, loc_id)
        except ValueError as e:
            out.append(Issue(CHECK_CHAIN, _index_side(save, loc_id), kind, loc_id, name, str(e), False))
    return out


def task_force_home_port(save, ctx=None):
    """Task forces whose home port is not a base or town, or belongs to the other side."""
    out = []
    for tf in taskforces.list_task_forces(save):
        port = tf.home_port
        if port == 0:
            continue
        side = _index_side(save, tf.id)
        if not bases.is_place(save, port):
            detail = f"Home port {port} is not a base or town"
        elif SIDES.get(bases.place_side_id(save, port)) != side:
            detail = f"Home port {taskforces._name(save, port)} ({port}) belongs to the other side"
        else:
            continue
        out.append(Issue(CHECK_HOME, side, KIND_TF, tf.id, _name(save, tf.id, "TF"), detail, False))
    return out


_FUNCTIONS = (leader_commands_several, unit_without_leader, unit_leader_side, land_unit_hq,
              ship_in_missing_task_force, broken_chains, task_force_home_port)


def find_issues(save):
    """Every issue of every check, future subjects included, sorted by check and then subject."""
    ctx = _Context(save)
    issues = []
    for check in _FUNCTIONS:
        issues.extend(check(save, ctx))
    order = {c: k for k, c in enumerate(CHECKS)}
    issues.sort(key=lambda i: (order[i.check], i.subject.lower(), i.subject_id))
    return issues
