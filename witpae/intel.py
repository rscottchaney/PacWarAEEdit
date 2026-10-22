"""Intel: the game's daily SIGINT and operations text reports, as WiTPTracker's Intel page reads them.

The game writes, next to the saves, one pair of files per player and turn:
  asigint_YYMMDD.txt / jsigint_YYMMDD.txt              SIGINT for the Allied ("a") / Japanese ("j") player
  aoperationsreport_YYMMDD.txt / joperationsreport_YYMMDD.txt   what that player's side saw and did
plus undated copies (asigint.txt, ...) of the latest turn. A save inside a folder named "autosave" uses the parent
folder (see history.save_folder). The first line is a header ("SIG INT REPORT FOR Dec 10, 41", "OPERATIONAL REPORT
FOR Dec 10, 41"); the date comes from it, with the date in the file name as a fallback. An undated file is used
only when no dated file of the same player and report has its header date. Files are latin-1 text with CR, LF or
CRLF line endings; trailing spaces are stripped and blank lines skipped. Nothing here writes to those files, and
their text is only ever data.

Every non-blank line after the header becomes one IntelLine; a line no rule recognises is kept as kind "Other" with
its full text. Dates are YYMMDD ints like history's. Places named in the text are matched to the save's places by
hex (a base wins over a town, as in the ship repair report) or, when the line has no hex, by exact name.
"""

import os
import re
from collections import namedtuple

from . import bases, chart, history, shiprepair

IntelLine = namedtuple("IntelLine", "date side kind place x y unit detail text")
Resolved = namedtuple("Resolved", "line place_id place")  # place: the text's place, else the resolved place's name
PlaceRow = namedtuple("PlaceRow", "place x y place_id counts first last units total")

SIDE_NAMES = ("Allied", "Japanese")
SIDE_PREFIXES = {"a": "Allied", "j": "Japanese"}
FILE_RE = re.compile(r"(?P<side>[aj])(?P<report>sigint|operationsreport)(?:_(?P<date>\d{6}))?\.txt", re.I)
REPORT_KEYS = {"sigint": "sigint", "operationsreport": "ops"}
HEADER_RE = re.compile(r"\bFOR\s+([A-Za-z]{3})[A-Za-z]*\.?\s+(\d{1,2})\s*,?\s*(\d{2,4})\b")
USED_BY_NAMES = 4  # units listed in a By place row before "(+n more)"

# Turns choices: label -> how many of the newest report dates to keep (None: all).
TURN_CHOICES = {"Latest": 1, "Last 3": 3, "Last 7": 7, "All": None}

SIGINT_KINDS = ("Radio", "Heavy radio", "Unit located", "Loaded on ship", "Moving", "Planning attack",
                "Troop count", "Aircraft count", "Ship count", "Other")

# A place in a SIGINT line: "Matsue (107,57)", "Yenki(110,44)", "70,75" or a bare name.
_WHERE = r"(?P<where>.+?)"
_HEX_TAIL_RE = re.compile(r"^(?:(?P<name>.*?)\s*)?\(?\s*(?P<x>\d+)\s*,\s*(?P<y>\d+)\s*\)?$")

# (kind, regex) in matching order; the named groups are unit, detail and where (a place, with or without a hex).
SIGINT_RULES = (
    ("Heavy radio", re.compile(r"^Heavy Volume of Radio transmissions detected at " + _WHERE + r"\.?$", re.I)),
    ("Radio", re.compile(r"^Radio transmissions detected at " + _WHERE + r"\.?$", re.I)),
    ("Unit located", re.compile(r"^(?P<unit>.+?) is located at " + _WHERE + r"\.?$")),
    ("Loaded on ship", re.compile(r"^(?P<unit>.+?) is loaded on (?P<detail>.+?) moving to " + _WHERE + r"\.?$")),
    ("Moving", re.compile(r"^(?:an? )?(?P<unit>.+?) is moving to " + _WHERE + r"\.?$")),
    ("Planning attack", re.compile(r"^(?P<unit>.+?) is planning for an attack on " + _WHERE + r"\.?$")),
    ("Troop count", re.compile(r"^(?P<detail>[\d,]+) men are based at " + _WHERE + r"\.?$")),
    # No sample shows these two; the wording follows the troop count line.
    ("Aircraft count", re.compile(r"^(?P<detail>[\d,]+) (?:aircraft|planes) are based at " + _WHERE + r"\.?$")),
    ("Ship count", re.compile(r"^(?P<detail>[\d,]+) ships? (?:are|is) based at " + _WHERE + r"\.?$")),
)

OPS_KINDS = ("Sighting", "Submarine", "Pilot", "Air", "Arrival", "Upgrade", "Base", "Capture", "Ship", "Task force",
             "Other")

# Operations category rules; the first row whose pattern matches the line wins, so the order matters.
#   Sighting    Sighting report / Coastwatcher lines; sighted, sights, spotted, detected, detects, snooped, shadowed,
#               followed, observes; "<aircraft> reports <periscope, wake, ...> at x,y"
#   Submarine   "SS <boat> assigned to offensive/defensive patrol", "SS <boat> transfers to", "SS <boat> lays"
#   Pilot       credited with kill, KILLED, wounded, injured, bails out, MIA
#   Air         destroyed by CAP, takes recon photos, "<group> at <base> takes <model> replacements", damaged on
#               landing, crashes on landing/return leg, written off, under attack by aircraft, replacements arrive,
#               transporting supplies, transferred planes
#   Arrival     arrives at
#   Upgrade     Device(s) upgraded, devices have been upgraded, takes replacements [from ...] (land unit devices)
#   Base        expands fortifications, builds, construction of/completed, partisan attack
#   Capture     CAPTURE, is occupied by, destroyed near ... !!!
#   Ship        reported sunk or HIT, sinks in port, Loss of ... is admitted, packing for load, beginning refit
#   Task force  Task Force N / TF N (formed, slows down, merged, disbanded, designated, ...)
# Everything else is "Other".
OPS_RULES = (
    ("Sighting", re.compile(r"^Sighting report|Coastwatcher|\b(?:sighted|sights|spotted|detected|detects|snooped|"
                            r"shadowed|followed|observes)\b|\bsighting\b|\breports? [^:]*\bat \(?\d", re.I)),
    ("Submarine", re.compile(r"^SS .* (?:assigned to (?:offensive|defensive) patrol|transfers to|lays)\b")),
    ("Pilot", re.compile(r"credited with kill|\bKILLED\b|wounded|injured|bails out|\bMIA\b", re.I)),
    ("Air", re.compile(r"destroyed by CAP|takes recon|\btakes .+ replacements$|replacements arrive|damaged on landing|"
                       r"crashes on|is written off|under attack by .*aircraft|transporting supplies|"
                       r"transferred planes", re.I)),
    ("Arrival", re.compile(r"\barrives at\b", re.I)),
    ("Upgrade", re.compile(r"Device\(s\) upgraded|devices have been upgraded|\btakes replacements(?: from\b|$)", re.I)),
    ("Base", re.compile(r"expands fortifications|\bbuilds\b|\bconstruction (?:of|completed)\b|"
                       r"partisan attack", re.I)),
    ("Capture", re.compile(r"\bCAPTURE\b|is occupied by|destroyed near .* !!!")),
    ("Ship", re.compile(r"is reported to have been sunk|\bsinks in port|is reported HIT|^Loss of .* is admitted|"
                        r"packing for load|beginning refit", re.I)),
    ("Task force", re.compile(r"\b(?:Task Force|TF) \d+\b", re.I)),
)

# Operations lines whose unit, place or detail are worth pulling out (named groups unit, place, detail); the first
# pattern that matches supplies them. Hexes and the "near <place>" name are taken from every line afterwards.
OPS_FIELDS = (
    re.compile(r"^(?P<unit>.+?) assigned to (?P<detail>(?:offensive|defensive) patrol [\d,\s-]*?)\s*off\s*(?P<place>.*)$"),
    re.compile(r"^(?P<unit>.+?) transfers to (?P<place>.+)$"),
    re.compile(r"^(?P<unit>.+?) arrives at (?P<place>.+)$"),
    re.compile(r"^(?P<unit>.+?) at (?P<place>.+?) takes (?P<detail>.+) replacements$"),
    re.compile(r"^(?P<unit>.+?) takes replacements from (?P<detail>.+)$"),
    re.compile(r"^(?P<unit>.+?) - some devices have been upgraded at (?P<place>.+)$"),
    re.compile(r"^Device\(s\) upgraded in (?P<unit>.+?) supplied from (?P<place>.+)$"),
    re.compile(r"^(?P<place>.+?) expands fortifications (?P<detail>to size \d+)$"),
    re.compile(r"^(?P<unit>.+?) sighted over (?P<place>.+)$"),
    re.compile(r"^(?P<unit>.+?) takes recon photos of (?P<place>.+)$"),
    re.compile(r"^(?P<unit>(?:Task Force|TF) \d+) formed at (?P<place>.+?) for (?P<detail>.+)$"),
    re.compile(r"^(?P<unit>.+?) lays (?:\w+ )?minefield (?:at|near) (?P<place>.+?)\s*(?:\(.*)?$"),
    re.compile(r"^(?P<unit>.+?) re-embarks landing force at (?P<place>.+?) and retires$"),
    re.compile(r"^(?P<unit>.+?) ordered to return to (?P<place>.+?)(?: due to .*)?$"),
    re.compile(r"^(?P<unit>.+?) aborts mission and returns to (?P<place>.+)$"),
    re.compile(r"^(?P<unit>.+?) designated as (?P<detail>.+?) and ordered to return to (?P<place>.+)$"),
    re.compile(r"^Coastwatcher Report: harbor at (?P<place>.+?) is reported empty$"),
    re.compile(r"^Coastwatcher Report: (?P<detail>.*?) (?:in port )?at (?P<place>.+)$"),
    re.compile(r"^(?:Japanese|Allied) forces CAPTURE (?P<place>.+?)\s*!!!$"),
    re.compile(r"^(?P<place>.+?) is occupied by"),
)
# A trailing subject for lines no pattern above covers: the words before the first verb.
OPS_SUBJECT_RE = re.compile(r"^(?!Sighting report|Coastwatcher)(?P<unit>.+?)\s+(?:sighted|sights|snooped|detected|"
                            r"detects|shadowed|followed|observes|has spotted|spotted|reports|is credited|is KILLED|"
                            r"is reported|is damaged|is written|crashes|slows|has merged|lays|destroyed|sinks|"
                            r"under attack|bails out|is wounded|is injured|sighting)\b")
_OPS_HEX_AT_RE = re.compile(r"\bat\s+\(?\s*(\d+)\s*,\s*(\d+)\s*\)?")
_OPS_HEX_PAREN_RE = re.compile(r"\(\s*(\d+)\s*,\s*(\d+)\s*\)")
_OPS_NEAR_RE = re.compile(r"^.*\bnear\s+(?P<place>.+?)\s*(?:\(|,|$)")  # the last "near": "object near surface ... near X"
_ON_DATE_RE = re.compile(r"\s+on [A-Z][a-z]{2} \d+$")
# "sighted over 41st PA Infantry Division" names a land unit, not a place.
_LAND_UNIT_RE = re.compile(r"\d|\b(?:Division|Brigade|Regiment|Corps|Battalion|Force|Army|Fortress|Defenses|"
                           r"Defences|Company|Group|Command|Rifles|Cavalry|Artillery|Battery)\b")


# ---- files --------------------------------------------------------------

def intel_folder(save_path):
    """The folder holding the report files of a save."""
    return history.save_folder(save_path)


def header_date(line):
    """The YYMMDD int of a report header, None when the line is not one."""
    m = HEADER_RE.search(line)
    if m is None or m.group(1).title() not in chart.MONTHS:
        return None
    month, day, year = chart.MONTHS.index(m.group(1).title()) + 1, int(m.group(2)), int(m.group(3))
    year = year - 1900 if year >= 1900 else year
    if not (1 <= day <= 31 and 0 <= year <= 99):
        return None
    return year * 10000 + month * 100 + day


def read_lines(path):
    """The non-blank lines of a report file, latin-1, CR/LF/CRLF, trailing spaces stripped."""
    with open(path, "rb") as f:
        text = f.read().decode("latin-1")
    return [line.rstrip() for line in re.split(r"\r\n|\r|\n", text) if line.strip()]


def _where(text):
    """(place name, x, y) of "Matsue (107,57)", "Yenki(110,44)", "70,75" or "Wake Island"."""
    text = text.strip().rstrip(".").strip()
    m = _HEX_TAIL_RE.match(text)
    if m is None:
        return text, None, None
    return (m.group("name") or "").strip(), int(m.group("x")), int(m.group("y"))


def _clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def parse_sigint(side, date, text):
    for kind, rule in SIGINT_RULES:
        m = rule.match(text)
        if m is None:
            continue
        place, x, y = _where(m.group("where"))
        fields = m.groupdict()
        detail = _clean(fields.get("detail"))
        if kind in ("Troop count", "Aircraft count", "Ship count"):
            detail = f"{int(detail.replace(',', '')):,} " + {"Troop count": "men", "Aircraft count": "aircraft",
                                                           "Ship count": "ships"}[kind]
        return IntelLine(date, side, kind, _clean(place), x, y, _clean(fields.get("unit")), detail, text)
    return IntelLine(date, side, "Other", "", None, None, "", "", text)


def classify_ops(text):
    for kind, rule in OPS_RULES:
        if rule.search(text):
            return kind
    return "Other"


def parse_ops(side, date, text):
    kind = classify_ops(text)
    fields = {"unit": "", "place": "", "detail": ""}
    for rule in OPS_FIELDS:
        m = rule.match(text)
        if m is not None:
            fields.update({k: v or "" for k, v in m.groupdict().items()})
            break
    else:
        m = OPS_SUBJECT_RE.match(text)
        if m is not None:
            fields["unit"] = m.group("unit")
    x = y = None
    m = _OPS_HEX_AT_RE.search(text) or _OPS_HEX_PAREN_RE.search(text)
    if m is not None:
        x, y = int(m.group(1)), int(m.group(2))
    if not fields["place"]:
        m = _OPS_NEAR_RE.search(text)
        if m is not None:
            fields["place"] = m.group("place")
    place = _clean(_ON_DATE_RE.sub("", _clean(fields["place"])))
    detail = _clean(fields["detail"])
    if place and _LAND_UNIT_RE.search(place) and " over " in text and kind == "Sighting":
        detail, place = f"over {place}", ""
    return IntelLine(date, side, kind, place, x, y, _clean(fields["unit"]), detail, text)


def _report_files(folder):
    """{(side, report key): ([(date from the name, path)], [undated paths])}, in file name order."""
    found = {}
    for name in sorted(os.listdir(folder)):
        m = FILE_RE.fullmatch(name)
        path = os.path.join(folder, name)
        if m is None or not os.path.isfile(path):
            continue
        dated, undated = found.setdefault((SIDE_PREFIXES[m.group("side").lower()],
                                           REPORT_KEYS[m.group("report").lower()]), ([], []))
        if m.group("date"):
            dated.append((int(m.group("date")), path))
        else:
            undated.append(path)
    return found


def load_reports(folder):
    """{"sigint": [IntelLine], "ops": [IntelLine]} of every report in the folder, by date then file line order.

    A missing folder or no report files give empty lists; a file that cannot be read raises OSError.
    """
    out = {"sigint": [], "ops": []}
    if not folder or not os.path.isdir(folder):
        return out
    for (side, key), (dated, undated) in _report_files(folder).items():
        parse = parse_sigint if key == "sigint" else parse_ops
        seen = set()
        for name_date, path in dated + [(None, p) for p in undated]:
            lines = read_lines(path)
            date = header_date(lines[0]) if lines else None
            if date is None:
                date = name_date
            if date is None or (name_date is None and date in seen):
                continue  # an undated copy of a turn that has its own dated file (or of no known turn)
            if name_date is not None:
                seen.add(date)
            body = lines[1:] if lines and header_date(lines[0]) is not None else lines
            out[key].extend(parse(side, date, text) for text in body)
    for key in out:
        out[key].sort(key=lambda line: line.date)  # stable: file line order is kept within a date
    return out


def recent(lines, count):
    """The lines of the newest count distinct dates (count None keeps all)."""
    if count is None:
        return list(lines)
    keep = set(sorted({line.date for line in lines})[-count:])
    return [line for line in lines if line.date in keep]


# ---- places -------------------------------------------------------------

class PlaceIndex:
    """The open save's bases and towns by hex and by lowercase name."""

    def __init__(self, save):
        self.hexes = shiprepair._port_hexes(save)  # a base wins over a town in the same hex
        self.names = {}
        self.by_id = {}
        for p in bases.list_places(save):
            self.by_id[p.id] = p
            self.names.setdefault(p.name.lower(), p.id)

    def find(self, x, y, name):
        """The place id at hex (x, y), else the one called name (exact, case-insensitive), else None."""
        if x is not None and (x, y) in self.hexes:
            return self.hexes[(x, y)]
        return self.names.get(name.lower()) if name else None

    def name(self, place_id):
        return self.by_id[place_id].name if place_id in self.by_id else ""

    def hex(self, place_id):
        p = self.by_id.get(place_id)
        return (p.x, p.y) if p else None


def resolve_lines(lines, index=None):
    """Resolved rows for the lines; index is a PlaceIndex or None (no save open)."""
    out = []
    for line in lines:
        place_id = index.find(line.x, line.y, line.place) if index is not None else None
        out.append(Resolved(line, place_id, line.place or (index.name(place_id) if place_id is not None else "")))
    return out


def by_place(lines, index=None):
    """One PlaceRow per place (or bare hex) with the report counts per kind, for spotting buildups.

    Lines are grouped by the save's place when it resolves, else by hex (a name with no hex of its own borrows the
    hex that another line gives the same name), else by name. Rows are ordered by total, largest first.
    """
    name_hex = {}
    for line in lines:
        if line.place and line.x is not None:
            name_hex.setdefault(line.place.lower(), (line.x, line.y))
    groups = {}
    for line in lines:
        place_id = index.find(line.x, line.y, line.place) if index is not None else None
        hex_ = (line.x, line.y) if line.x is not None else name_hex.get(line.place.lower())
        if place_id is not None:
            key = ("id", place_id)
        elif hex_ is not None:
            key = ("hex", hex_)
        elif line.place:
            key = ("name", line.place.lower())
        else:
            continue  # no place at all (an Other line): nothing to group on
        groups.setdefault(key, []).append((line, place_id, hex_))
    rows = []
    for members in groups.values():
        found = [m for m in members if m[1] is not None]
        place_id = found[0][1] if found else None
        hex_ = next((m[2] for m in members if m[2] is not None), None)
        if hex_ is None and place_id is not None:
            hex_ = index.hex(place_id)
        name = next((m[0].place for m in members if m[0].place), index.name(place_id) if place_id is not None else "")
        counts = {}
        for line, _p, _h in members:
            counts[line.kind] = counts.get(line.kind, 0) + 1
        units = sorted({m[0].unit for m in members if m[0].unit})
        shown = ", ".join(units[:USED_BY_NAMES]) + (f" (+{len(units) - USED_BY_NAMES} more)"
                                                    if len(units) > USED_BY_NAMES else "")
        dates = [m[0].date for m in members]
        rows.append(PlaceRow(name, hex_[0] if hex_ else None, hex_[1] if hex_ else None, place_id, counts,
                             min(dates), max(dates), shown, len(members)))
    rows.sort(key=lambda r: (-r.total, r.place.lower(), r.x if r.x is not None else -1))
    return rows
