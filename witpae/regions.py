"""Region of each location, from Kull's region file (witpae/data/regions).

The file has one line per location: location id, name, region id, region name,
TAB-separated, lines ended by CR (also read with LF or CRLF). The location ids
are those of the save's location table. A region name can repeat under two ids
("Line Islands"), so regions are told apart by id.
"""

import os
import re

UNASSIGNED_ID = 0
UNASSIGNED_NAME = "Unassigned"
UNASSIGNED = (UNASSIGNED_ID, UNASSIGNED_NAME)

DEFAULT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "regions",
                            "Kull_Regions_v131a.txt")

_default = None


class RegionMap:
    def __init__(self, locations, names):
        self._locations = locations  # location id -> region id
        self._names = names  # region id -> region name

    def __len__(self):
        return len(self._locations)

    def region_of(self, loc_id):
        """(region id, region name) of a location, UNASSIGNED when the file does not list it."""
        region_id = self._locations.get(loc_id)
        return UNASSIGNED if region_id is None else (region_id, self._names[region_id])

    def regions(self):
        """Every region of the file as (id, name), sorted by id."""
        return sorted(self._names.items())


def load_regions(path=None):
    """Parse a region file; ValueError names the first bad line number."""
    with open(DEFAULT_PATH if path is None else path, "rb") as fh:
        text = fh.read().decode("latin-1")
    locations, names = {}, {}
    for number, line in enumerate(re.split(r"\r\n|\r|\n", text), 1):
        if not line.strip():
            continue
        fields = line.split("\t")
        if len(fields) != 4:
            raise ValueError(f"line {number}: expected 4 tab-separated fields, found {len(fields)}")
        try:
            loc_id, region_id = int(fields[0]), int(fields[2])
        except ValueError:
            raise ValueError(f"line {number}: location id and region id must be integers") from None
        locations[loc_id] = region_id
        names[region_id] = fields[3].strip()
    return RegionMap(locations, names)


def default_regions():
    """The bundled Kull file, parsed once."""
    global _default
    if _default is None:
        _default = load_regions()
    return _default
