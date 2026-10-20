"""Tkinter front end for the WitP:AE base editor.

Usage: python witpae_editor.py [save.pws]

All data logic lives in the witpae package; this file only wires widgets.
"""

import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from witpae import (aircraft, airgroups, bases, factories, industry, landunits, regions, reports, shiprecords,
                    ships, taskforces)
from witpae.container import SaveFile, SaveFormatError
from witpae.fileio import is_pbem, save_with_backup

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DIR = os.path.normpath(os.path.join(HERE, "..", "SAVE"))

# (column id, heading, width, numeric, value getter)
COLUMNS = [
    ("id", "ID", 55, True, lambda b: b.id),
    ("name", "Name", 150, False, lambda b: b.name),
    ("kind", "Type", 50, False, lambda b: b.kind),
    ("side", "Side", 70, False, lambda b: b.side),
    ("hex", "Hex x,y", 70, True, lambda b: (b.x, b.y)),
    ("supply", "Supply", 80, True, lambda b: b.get("supply")),
    ("fuel", "Fuel", 80, True, lambda b: b.get("fuel")),
    ("port", "Port", 45, True, lambda b: b.get("port")),
    ("airfield", "Airfield", 60, True, lambda b: b.get("airfield")),
]
COLUMN_BY_ID = {c[0]: c for c in COLUMNS}

AIRCRAFT_COLUMNS = [
    ("id", "ID", 55, True, lambda a: a.id),
    ("name", "Name", 170, False, lambda a: a.name),
    ("nation", "Nation", 70, False, lambda a: a.nation),
    ("type", "Type", 110, False, lambda a: a.type),
    ("from", "From", 60, True, lambda a: a.get_date("from")[::-1]),
    ("to", "To", 60, True, lambda a: a.get_date("to")[::-1]),
    ("pool", "Pool", 55, True, lambda a: a.pool),
]
AIRCRAFT_COLUMN_BY_ID = {c[0]: c for c in AIRCRAFT_COLUMNS}

SHIP_COLUMNS = [
    ("id", "ID", 55, True, lambda s: s.id),
    ("name", "Name", 170, False, lambda s: s.name),
    ("type", "Type", 70, False, lambda s: s.type),
    ("nation", "Nation", 70, False, lambda s: s.nation),
    ("date", "Date", 60, True, lambda s: s.date[::-1]),
    ("speed", "Speed", 50, True, lambda s: s.get("speed")),
    ("durability", "Durability", 70, True, lambda s: s.get("durability")),
]
SHIP_COLUMN_BY_ID = {c[0]: c for c in SHIP_COLUMNS}

SHIPREC_COLUMNS = [
    ("id", "ID", 55, True, lambda s: s.id),
    ("name", "Name", 150, False, lambda s: s.name),
    ("type", "Type", 60, False, lambda s: s.type),
    ("class", "Class", 130, False, lambda s: s.class_name),
    ("nation", "Nation", 60, False, lambda s: s.nation),
    ("side", "Side", 65, False, lambda s: s.side),
    ("location", "Location", 120, False, lambda s: s.location),
]
SHIPREC_COLUMN_BY_ID = {c[0]: c for c in SHIPREC_COLUMNS}

# Rows are dicts built by EditorApp._tf_row.
TF_COLUMNS = [
    ("id", "ID", 55, True, lambda r: r["id"]),
    ("name", "Name", 170, False, lambda r: r["name"]),
    ("side", "Side", 65, False, lambda r: r["side"]),
    ("location", "Location", 140, False, lambda r: r["location"]),
    ("mission", "Mission", 120, False, lambda r: r["mission"]),
    ("destination", "Destination", 120, False, lambda r: r["destination"]),
    ("ships", "Ships", 45, True, lambda r: r["ships"]),
    ("flagship", "Flagship", 130, False, lambda r: r["flagship"]),
]
TF_COLUMN_BY_ID = {c[0]: c for c in TF_COLUMNS}
TF_SHIP_COLUMNS = [
    ("flag", "Flag", 35), ("name", "Name", 130), ("type", "Type", 50), ("class", "Class", 110),
    ("fuel", "Fuel", 90), ("sys", "Sys", 35), ("float", "Float", 40), ("eng", "Eng", 35), ("fires", "Fires", 40),
]

GROUP_COLUMNS = [
    ("id", "ID", 55, True, lambda g: g.id),
    ("name", "Name", 170, False, lambda g: g.name),
    ("aircraft", "Aircraft", 120, False, lambda g: g.aircraft_name),
    ("planes", "Planes", 55, True, lambda g: g.planes),
    # Active pilots from the pilot table; the group's own count byte disagrees for many groups.
    ("pilots", "Pilots", 50, True, lambda g: g.active_pilots),
    ("morale", "Morale", 55, True, lambda g: g.get("morale")),
    ("exp", "Exp", 45, True, lambda g: g.get("experience")),
    ("location", "Location", 120, False, lambda g: g.location_name),
]
GROUP_COLUMN_BY_ID = {c[0]: c for c in GROUP_COLUMNS}

UNIT_COLUMNS = [
    ("id", "ID", 55, True, lambda u: u.id),
    ("name", "Name", 190, False, lambda u: u.display_name),
    ("type", "Type", 50, False, lambda u: u.type),
    ("hq", "HQ", 110, False, lambda u: u.hq_name),
    ("location", "Location", 110, False, lambda u: u.location_name),
    ("exp", "Exp", 45, True, lambda u: u.get("experience")),
    ("morale", "Morale", 55, True, lambda u: u.get("morale")),
    ("fatigue", "Fatigue", 55, True, lambda u: u.get("fatigue")),
    ("supplies", "Supplies", 70, True, lambda u: u.get("supplies")),
]
UNIT_COLUMN_BY_ID = {c[0]: c for c in UNIT_COLUMNS}

# Report rows are the namedtuples of witpae.reports. Over values, dates and due months sort
# on the raw getter value and are shown through the *_TEXT formatters.
SPOILAGE_COLUMNS = [
    ("id", "ID", 55, True, lambda r: r.base.id),
    ("name", "Name", 150, False, lambda r: r.base.name),
    ("kind", "Type", 50, False, lambda r: r.base.kind),
    ("side", "Side", 70, False, lambda r: r.base.side),
    ("region", "Region", 110, False, lambda r: regions.default_regions().region_of(r.base.id)[1]),
    ("port", "Port", 45, True, lambda r: r.base.get("port")),
    ("airfield", "Airfield", 60, True, lambda r: r.base.get("airfield")),
    ("supply", "Supply", 80, True, lambda r: r.supply),
    ("supply_limit", "Supply limit", 80, True, lambda r: r.supply_limit),
    ("supply_over", "Supply over", 80, True, lambda r: r.supply_over),
    ("fuel", "Fuel", 80, True, lambda r: r.fuel),
    ("fuel_limit", "Fuel limit", 80, True, lambda r: r.fuel_limit),
    ("fuel_over", "Fuel over", 80, True, lambda r: r.fuel_over),
]
SPOILAGE_COLUMN_BY_ID = {c[0]: c for c in SPOILAGE_COLUMNS}
SPOILAGE_TEXT = {cid: (lambda v: v if v > 0 else "-") for cid in ("supply_over", "fuel_over")}
SPOILAGE_NOTE = ("Limits from the game manual: none when port + airfield size is 10 or more; "
                 "supply 5000 + 3000 x s\u00b2, fuel 1000 + 2000 x s\u00b2 (s = port + airfield size).")


def _due_text(months):
    if months <= 0:
        return "now"
    return "1 month" if months == 1 else f"{months} months"


def _class_text(cls):
    return f"{cls.name} #{cls.id}"


UPGRADE_COLUMNS = [
    ("id", "ID", 55, True, lambda r: r.ship.id),
    ("ship", "Ship", 150, False, lambda r: r.ship.name),
    ("type", "Type", 60, False, lambda r: r.ship.type),
    ("side", "Side", 65, False, lambda r: r.ship.side),
    ("class", "Class", 150, False, lambda r: _class_text(r.current)),
    ("target", "Upgrade to", 150, False, lambda r: _class_text(r.target)),
    ("change", "Type change", 80, False, lambda r: r.type_change),
    ("date", "Date", 55, True, lambda r: (r.year, r.month)),
    ("due", "Due", 75, True, lambda r: r.months),
    ("yard", "Yard?", 50, True, lambda r: r.yard),
    ("location", "Location", 120, False, lambda r: r.location),
]
UPGRADE_COLUMN_BY_ID = {c[0]: c for c in UPGRADE_COLUMNS}
UPGRADE_TEXT = {"date": lambda v: f"{v[1]}/{v[0]:02d}", "due": _due_text}
# "Due within" choices: label -> months, None for all.
UPGRADE_DUE = {"Now": 0, "1 month": 1, "3 months": 3, "6 months": 6, "12 months": 12, "All": None}


def _num(v):
    return f"{v:,}"


def _rate(v):
    return f"{v:+,}" if v else "0"


def _flow_cell(amounts):
    # None marks inputs that are not mapped (aircraft and engine factories).
    return "-" if amounts is None else industry.flow_text(amounts)


def _shortest_text(v):
    days, key = v
    if not key:
        return "-"
    n = int(days)
    return f"{industry.BALANCE_ROWS[key]}: {n} day{'' if n == 1 else 's'}"


def _days_text(days):
    return "-" if days is None else _num(int(days))


# The Industry report: one table of factory types, one of daily material balances.
INDUSTRY_COLUMNS = [
    ("group", "Type", 130, False, lambda r: r.group),
    ("count", "Factories", 70, True, lambda r: r.count),
    ("size", "Size", 80, True, lambda r: r.size),
    ("damage", "Damaged", 80, True, lambda r: r.damage),
    ("production_off", "Production off", 90, True, lambda r: r.production_off),
    ("repair_off", "Repair off", 80, True, lambda r: r.repair_off),
    ("output", "Daily output", 260, False, lambda r: r.makes),
    ("input", "Daily input", 260, False, lambda r: r.uses if r.uses_known else None),
]
INDUSTRY_TEXT = {"count": _num, "size": _num, "damage": _num, "production_off": _num, "repair_off": _num,
                 "output": _flow_cell, "input": _flow_cell}
BALANCE_COLUMNS = [
    ("label", "Material", 130, False, lambda r: r.label),
    ("stored", "Stored", 100, True, lambda r: r.stored),
    ("produced", "Produced/day", 100, True, lambda r: r.produced),
    ("allotted", "Allotted/day", 100, True, lambda r: r.allotted),
    ("used", "Used/day", 100, True, lambda r: r.used),
    ("net", "Net/day", 100, True, lambda r: r.net),
    ("days", "Days left", 80, True, lambda r: r.days),
]
BALANCE_TEXT = {"stored": lambda v: "?" if v is None else _num(v), "produced": _num, "allotted": _num, "used": _num,
                "net": _rate,
                "days": _days_text}
INDUSTRY_NOTE = ("Factory flows (game manual 13.2) plus the places' daily supply, fuel and oil allotments. Not "
                 "included: supply used by units, fuel used by ships. Manpower and the point rows are side-wide pools, "
                 "so they show no days left when a region is selected.")

FACTORY_COLUMNS = [
    ("id", "Place ID", 60, True, lambda r: r.place.id),
    ("place", "Place", 140, False, lambda r: r.place.name),
    ("kind", "Kind", 50, False, lambda r: r.place.kind),
    ("side", "Side", 70, False, lambda r: r.place.base.side),
    ("region", "Region", 110, False, lambda r: r.place.region),
    ("slot", "Slot", 40, True, lambda r: r.factory.slot),
    ("factory", "Factory", 150, False, lambda r: r.factory.name),
    ("size", "Size", 60, True, lambda r: r.factory.size),
    ("damage", "Damage", 60, True, lambda r: r.factory.damage),
    ("production", "Production", 70, False, lambda r: "Yes" if r.factory.production_on else "No"),
    ("repair", "Repair", 55, False, lambda r: "Yes" if r.factory.repair_on else "No"),
    ("output", "Daily output", 200, False, lambda r: industry.flow_text(r.flow.makes)),
    ("input", "Daily input", 200, False, lambda r: industry.flow_text(r.flow.uses) if r.flow.uses_known else "-"),
]
FACTORY_COLUMN_BY_ID = {c[0]: c for c in FACTORY_COLUMNS}
FACTORY_TYPE_ALL = "All types"

RAW_COLUMNS = [
    ("id", "Place ID", 60, True, lambda r: r.place.id),
    ("place", "Place", 140, False, lambda r: r.place.name),
    ("kind", "Kind", 50, False, lambda r: r.place.kind),
    ("side", "Side", 70, False, lambda r: r.place.base.side),
    ("region", "Region", 110, False, lambda r: r.place.region),
    ("allotment", "Allotment/day", 170, False, lambda r: industry.flow_text(r.allotment)),
    ("oil", "Oil", 80, True, lambda r: r.stored["oil"]),
    ("oil_day", "Oil/day", 70, True, lambda r: r.net["oil"]),
    ("resources", "Resources", 80, True, lambda r: r.stored["resources"]),
    ("resources_day", "Res/day", 70, True, lambda r: r.net["resources"]),
    ("fuel", "Fuel", 80, True, lambda r: r.stored["fuel"]),
    ("fuel_day", "Fuel/day", 70, True, lambda r: r.net["fuel"]),
    ("supply", "Supply", 80, True, lambda r: r.stored["supply"]),
    ("supply_day", "Supply/day", 70, True, lambda r: r.net["supply"]),
    # (days, material) so it sorts by days; places where nothing runs down sort last.
    ("shortest", "Shortest", 130, True, lambda r: (r.shortest[1], r.shortest[0]) if r.shortest else (float("inf"), "")),
]
RAW_COLUMN_BY_ID = {c[0]: c for c in RAW_COLUMNS}
RAW_TEXT = {"oil": _num, "resources": _num, "fuel": _num, "supply": _num, "oil_day": _rate,
            "resources_day": _rate, "fuel_day": _rate, "supply_day": _rate, "shortest": _shortest_text}
RAW_NOTE = ("Per place, from that place's own factories and daily allotment. The game moves oil, resources and "
            "fuel overland between connected places, so a local shortfall does not always stop a factory.")

REGION_ALL = "All regions"


def region_choices():
    """Region combobox label -> region id (None for all), in id order; a repeated name gets its id."""
    found = regions.default_regions().regions()
    names = [name for _id, name in found]
    choices = {REGION_ALL: None}
    for region_id, name in found:
        choices[f"{name} ({region_id})" if names.count(name) > 1 else name] = region_id
    choices[regions.UNASSIGNED_NAME] = regions.UNASSIGNED_ID
    return choices


MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


class EditorApp:
    def __init__(self, root):
        self.root = root
        root.title("WitP:AE Base Editor")
        self.save = None
        self.path = None
        self.bases = {}
        self.edited = set()
        self.dirty = False
        self.pbem = False
        self.sort_col = "id"
        self.sort_reverse = False
        self.field_vars = {}
        self.stockpile_vars = {}
        self.building_vars = {}
        self.field_entries = {}
        self.building_checks = {}
        self.current = None
        self.factory_slot = None
        self.aircraft = {}
        self.aircraft_edited = set()
        self.aircraft_sort_col = "id"
        self.aircraft_sort_reverse = False
        self.aircraft_vars = {}
        self.aircraft_current = None
        self.ships = {}
        self.ships_edited = set()
        self.ship_sort_col = "id"
        self.ship_sort_reverse = False
        self.ship_vars = {}
        self.ship_current = None
        self.ship_slot = None
        self.shiprecs = {}
        self.shiprecs_edited = set()
        self.shiprec_sort_col = "id"
        self.shiprec_sort_reverse = False
        self.shiprec_vars = {}
        self.shiprec_current = None
        self.shiprec_slot = None
        self.taskforces = {}
        self.tfs_edited = set()
        self.tf_sort_col = "id"
        self.tf_sort_reverse = False
        self.tf_current = None
        self.tf_info = {}
        self.tf_ship_current = None
        self.tf_destinations = []
        self.tf_add_ships = []
        self.tf_flag_ships = []
        self.places_by_hex = {}
        self.places_by_id = {}
        self.tf_port_items = []
        self.tf_dest_items = []
        self.tf_home_shown = []
        self.tf_dest_shown = []
        self.groups = {}
        self.pilot_index = {}
        self.groups_edited = set()
        self.group_sort_col = "id"
        self.group_sort_reverse = False
        self.group_vars = {}
        self.group_current = None
        self.pilot_current = None
        self.pilot_vars = {}
        self.leader_vars = {}
        self.leader_current = None
        self.place_ids = {}
        self.place_labels = {}
        self.device_ids = {}
        self.device_labels = {}
        self.aircraft_ids = {}
        self.aircraft_labels = {}
        self.units = {}
        self.units_edited = set()
        self.unit_sort_col = "id"
        self.unit_sort_reverse = False
        self.unit_vars = {}
        self.unit_current = None
        self.unit_slot = None
        self.spoilage_all = []
        self.spoilage_sort_col = "total"
        self.spoilage_sort_reverse = True
        self.upgrades_all = []
        self.upgrade_sort_col = "due"
        self.upgrade_sort_reverse = False
        self.industry_places = []
        self.region_ids = region_choices()
        self.factory_report_sort_col = "id"
        self.factory_report_sort_reverse = False
        self.raw_sort_col = "shortest"
        self.raw_sort_reverse = False

        self._build_menu()
        self._build_header()
        self._build_body()
        self.status = tk.StringVar(value="No save loaded")
        ttk.Label(root, textvariable=self.status, relief="sunken", anchor="w").pack(side="bottom", fill="x")
        root.protocol("WM_DELETE_WINDOW", self.quit)

    # ---- widgets -------------------------------------------------------

    def _build_menu(self):
        menu = tk.Menu(self.root)
        file_menu = tk.Menu(menu, tearoff=False)
        file_menu.add_command(label="Open...", command=self.open_dialog, accelerator="Ctrl+O")
        file_menu.add_command(label="Save As...", command=self.save_as, accelerator="Ctrl+S")
        file_menu.add_separator()
        file_menu.add_command(label="Quit", command=self.quit)
        menu.add_cascade(label="File", menu=file_menu)
        self.root.config(menu=menu)
        self.root.bind("<Control-o>", lambda e: self.open_dialog())
        self.root.bind("<Control-s>", lambda e: self.save_as())

    def _build_header(self):
        head = ttk.Frame(self.root, padding=4)
        head.pack(side="top", fill="x")
        self.file_label = tk.StringVar(value="File: (none)")
        ttk.Label(head, textvariable=self.file_label).grid(row=0, column=0, columnspan=3, sticky="w")
        ttk.Label(head, text="Save title:").grid(row=1, column=0, sticky="w")
        self.title_var = tk.StringVar()
        ttk.Entry(head, textvariable=self.title_var, width=50).grid(row=1, column=1, sticky="we", padx=4)
        ttk.Button(head, text="Apply title", command=self.apply_title).grid(row=1, column=2)
        head.columnconfigure(1, weight=1)

    def _build_body(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(side="top", fill="both", expand=True)
        body = self.bases_tab = ttk.Frame(self.notebook, padding=4)
        self.notebook.add(body, text="Bases")
        self._build_aircraft_tab()
        self._build_ships_tab()
        self._build_shiprecs_tab()
        self._build_taskforces_tab()
        self._build_groups_tab()
        self._build_units_tab()
        self._build_reports_tab()

        left = ttk.Frame(body)
        left.pack(side="left", fill="both", expand=True)
        bar = ttk.Frame(left)
        bar.pack(side="top", fill="x")
        ttk.Label(bar, text="Search:").pack(side="left")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *a: self.refresh_list())
        ttk.Entry(bar, textvariable=self.search_var, width=20).pack(side="left", padx=4)
        ttk.Label(bar, text="Side:").pack(side="left")
        self.side_var = tk.StringVar(value="All")
        side_box = ttk.Combobox(bar, textvariable=self.side_var, values=["All", "Allied", "Japanese"],
                                state="readonly", width=9)
        side_box.pack(side="left", padx=4)
        side_box.bind("<<ComboboxSelected>>", lambda e: self.refresh_list())

        self._build_factories(left)

        self.tree = ttk.Treeview(left, columns=[c[0] for c in COLUMNS], show="headings", selectmode="browse")
        for cid, heading, width, _numeric, _get in COLUMNS:
            self.tree.heading(cid, text=heading, command=lambda c=cid: self.sort_by(c))
            self.tree.column(cid, width=width, anchor="w" if cid in ("name", "kind", "side") else "e")
        self.tree.tag_configure("edited", background="#fff2b3")
        scroll = ttk.Scrollbar(left, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", lambda e: self.on_select())

        right = ttk.LabelFrame(body, text="Base", padding=8)
        right.pack(side="right", fill="y", padx=(8, 0))
        self.detail_title = tk.StringVar(value="(select a base)")
        ttk.Label(right, textvariable=self.detail_title, font=("TkDefaultFont", 11, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
        for row, f in enumerate(bases.FIELDS, start=1):
            label = f.label + ("" if f.verified else " (unverified)") + ("" if f.editable else " (read-only)")
            ttk.Label(right, text=label).grid(row=row, column=0, sticky="w", pady=2)
            var = tk.StringVar()
            self.field_vars[f.name] = var
            entry = ttk.Entry(right, textvariable=var, width=14, state="normal" if f.editable else "readonly")
            self.field_entries[f.name] = entry
            entry.grid(row=row, column=1, padx=(8, 0), pady=2)
        stock_row = len(bases.FIELDS) + 1
        ttk.Label(right, text="Stockpile").grid(row=stock_row, column=0, sticky="nw", pady=2)
        stock_box = ttk.Frame(right)
        stock_box.grid(row=stock_row, column=1, sticky="w", padx=(8, 0), pady=2)
        for name, label, _bit in bases.STOCKPILE_FLAGS:
            var = tk.BooleanVar()
            self.stockpile_vars[name] = var
            ttk.Checkbutton(stock_box, text=label, variable=var).pack(anchor="w")
        build_row = stock_row + 1
        ttk.Label(right, text="Build/expand").grid(row=build_row, column=0, sticky="nw", pady=2)
        build_box = ttk.Frame(right)
        build_box.grid(row=build_row, column=1, sticky="w", padx=(8, 0), pady=2)
        for name, label, _live, _copy in bases.BUILD_SWITCHES:
            var = tk.BooleanVar()
            self.building_vars[name] = var
            check = ttk.Checkbutton(build_box, text=label, variable=var)
            check.pack(anchor="w")
            self.building_checks[name] = check
        self.apply_btn = ttk.Button(right, text="Apply", command=self.apply)
        self.apply_btn.grid(row=build_row + 1, column=0, columnspan=2, pady=(10, 0))

    def _build_reports_tab(self):
        tab = self.reports_tab = ttk.Frame(self.notebook, padding=4)
        self.notebook.add(tab, text="Reports")
        self.game_date_var = tk.StringVar(value="Game date: unknown")
        ttk.Label(tab, textvariable=self.game_date_var).pack(side="top", anchor="w")
        self.reports_notebook = ttk.Notebook(tab)
        self.reports_notebook.pack(side="top", fill="both", expand=True, pady=(4, 0))

        spoil = ttk.Frame(self.reports_notebook, padding=4)
        self.reports_notebook.add(spoil, text="Spoilage")
        bar = ttk.Frame(spoil)
        bar.pack(side="top", fill="x")
        ttk.Label(bar, text="Side:").pack(side="left")
        self.spoilage_side_var = tk.StringVar(value="All")
        side_box = ttk.Combobox(bar, textvariable=self.spoilage_side_var, values=["All", "Allied", "Japanese"],
                                state="readonly", width=9)
        side_box.pack(side="left", padx=4)
        side_box.bind("<<ComboboxSelected>>", lambda e: self.refresh_spoilage_list())
        self.spoilage_count = tk.StringVar()
        ttk.Label(bar, textvariable=self.spoilage_count).pack(side="left", padx=8)
        ttk.Label(spoil, text=SPOILAGE_NOTE).pack(side="bottom", anchor="w", pady=(4, 0))
        self.spoilage_tree = self._report_tree(spoil, SPOILAGE_COLUMNS, self.sort_spoilage_by,
                                               ("name", "kind", "side", "region"), self.jump_to_spoilage_base)

        ups = ttk.Frame(self.reports_notebook, padding=4)
        self.reports_notebook.add(ups, text="Ship upgrades")
        bar = ttk.Frame(ups)
        bar.pack(side="top", fill="x")
        ttk.Label(bar, text="Search:").pack(side="left")
        self.upgrade_search_var = tk.StringVar()
        self.upgrade_search_var.trace_add("write", lambda *a: self.refresh_upgrade_list())
        ttk.Entry(bar, textvariable=self.upgrade_search_var, width=20).pack(side="left", padx=4)
        ttk.Label(bar, text="Side:").pack(side="left")
        self.upgrade_side_var = tk.StringVar(value="All")
        side_box = ttk.Combobox(bar, textvariable=self.upgrade_side_var, values=["All", "Allied", "Japanese"],
                                state="readonly", width=9)
        side_box.pack(side="left", padx=4)
        side_box.bind("<<ComboboxSelected>>", lambda e: self.refresh_upgrade_list())
        ttk.Label(bar, text="Due within:").pack(side="left")
        self.upgrade_due_var = tk.StringVar(value="3 months")
        due_box = ttk.Combobox(bar, textvariable=self.upgrade_due_var, values=list(UPGRADE_DUE),
                               state="readonly", width=10)
        due_box.pack(side="left", padx=4)
        due_box.bind("<<ComboboxSelected>>", lambda e: self.refresh_upgrade_list())
        self.upgrade_count = tk.StringVar()
        ttk.Label(bar, textvariable=self.upgrade_count).pack(side="left", padx=8)
        self.upgrade_tree = self._report_tree(ups, UPGRADE_COLUMNS, self.sort_upgrades_by,
                                              ("ship", "type", "side", "class", "target", "change", "location"),
                                              self.jump_to_upgrade_ship)

        self._build_industry_reports()

        # Bound last so the handlers never run before the lists exist.
        self.notebook.bind("<<NotebookTabChanged>>", lambda e: self._reports_shown())
        self.reports_notebook.bind("<<NotebookTabChanged>>", lambda e: self._reports_shown())

    def _report_combo(self, bar, label, var, values, command, width):
        ttk.Label(bar, text=label).pack(side="left")
        box = ttk.Combobox(bar, textvariable=var, values=list(values), state="readonly", width=width)
        box.pack(side="left", padx=(4, 8))
        box.bind("<<ComboboxSelected>>", lambda e: command())

    def _build_industry_reports(self):
        sides = ["All", "Allied", "Japanese"]

        ind = ttk.Frame(self.reports_notebook, padding=4)
        self.reports_notebook.add(ind, text="Industry")
        bar = ttk.Frame(ind)
        bar.pack(side="top", fill="x")
        self.industry_side_var = tk.StringVar(value="Allied")
        self._report_combo(bar, "Side:", self.industry_side_var, sides[1:], self.refresh_industry_report, 9)
        self.industry_region_var = tk.StringVar(value=REGION_ALL)
        self._report_combo(bar, "Region:", self.industry_region_var, self.region_ids, self.refresh_industry_report, 22)
        ttk.Label(ind, text=INDUSTRY_NOTE).pack(side="bottom", anchor="w", pady=(4, 0))
        top = ttk.Frame(ind)
        top.pack(side="top", fill="both", expand=True, pady=(4, 0))
        self.industry_tree = self._report_tree(top, INDUSTRY_COLUMNS, lambda c: None, ("group", "output", "input"),
                                               lambda: None)
        ttk.Label(ind, text="Daily balance (factories and allotments)").pack(side="top", anchor="w", pady=(6, 0))
        low = ttk.Frame(ind)
        low.pack(side="top", fill="x")
        self.balance_tree = self._report_tree(low, BALANCE_COLUMNS, lambda c: None, ("label",), lambda: None)
        self.balance_tree.configure(height=10)

        fac = ttk.Frame(self.reports_notebook, padding=4)
        self.reports_notebook.add(fac, text="Factories")
        bar = ttk.Frame(fac)
        bar.pack(side="top", fill="x")
        self.factory_report_side_var = tk.StringVar(value="All")
        self._report_combo(bar, "Side:", self.factory_report_side_var, sides, self.refresh_factory_report, 9)
        self.factory_report_region_var = tk.StringVar(value=REGION_ALL)
        self._report_combo(bar, "Region:", self.factory_report_region_var, self.region_ids,
                           self.refresh_factory_report, 22)
        self.factory_report_type_var = tk.StringVar(value=FACTORY_TYPE_ALL)
        self._report_combo(bar, "Factory type:", self.factory_report_type_var,
                           [FACTORY_TYPE_ALL] + industry.GROUP_ORDER, self.refresh_factory_report, 16)
        self.factory_report_problem_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(bar, text="Only damaged or switched off", variable=self.factory_report_problem_var,
                        command=self.refresh_factory_report).pack(side="left", padx=(0, 8))
        self.factory_report_count = tk.StringVar()
        ttk.Label(bar, textvariable=self.factory_report_count).pack(side="left", padx=8)
        self.factory_report_tree = self._report_tree(
            fac, FACTORY_COLUMNS, self.sort_factory_report_by,
            ("place", "kind", "side", "region", "factory", "production", "repair", "output", "input"),
            lambda: self.jump_to_industry_place(self.factory_report_tree))

        raw = ttk.Frame(self.reports_notebook, padding=4)
        self.reports_notebook.add(raw, text="Raw materials")
        bar = ttk.Frame(raw)
        bar.pack(side="top", fill="x")
        self.raw_side_var = tk.StringVar(value="All")
        self._report_combo(bar, "Side:", self.raw_side_var, sides, self.refresh_raw_list, 9)
        self.raw_region_var = tk.StringVar(value=REGION_ALL)
        self._report_combo(bar, "Region:", self.raw_region_var, self.region_ids, self.refresh_raw_list, 22)
        self.raw_only_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(bar, text="Only places with industry", variable=self.raw_only_var,
                        command=self.refresh_raw_list).pack(side="left", padx=(0, 8))
        self.raw_count = tk.StringVar()
        ttk.Label(bar, textvariable=self.raw_count).pack(side="left", padx=8)
        ttk.Label(raw, text=RAW_NOTE).pack(side="bottom", anchor="w", pady=(4, 0))
        self.raw_tree = self._report_tree(raw, RAW_COLUMNS, self.sort_raw_by, ("place", "kind", "side", "region"),
                                          lambda: self.jump_to_industry_place(self.raw_tree))

    def _report_tree(self, parent, columns, sort_command, left_aligned, on_open):
        tree = ttk.Treeview(parent, columns=[c[0] for c in columns], show="headings", selectmode="browse")
        for cid, heading, width, _numeric, _get in columns:
            tree.heading(cid, text=heading, command=lambda c=cid: sort_command(c))
            tree.column(cid, width=width, anchor="w" if cid in left_aligned else "e")
        scroll = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        tree.pack(side="left", fill="both", expand=True)
        tree.bind("<Double-1>", lambda e: on_open())
        return tree

    def _build_aircraft_tab(self):
        tab = ttk.Frame(self.notebook, padding=4)
        self.notebook.add(tab, text="Aircraft")
        left = ttk.Frame(tab)
        left.pack(side="left", fill="both", expand=True)
        bar = ttk.Frame(left)
        bar.pack(side="top", fill="x")
        ttk.Label(bar, text="Search:").pack(side="left")
        self.aircraft_search_var = tk.StringVar()
        self.aircraft_search_var.trace_add("write", lambda *a: self.refresh_aircraft_list())
        ttk.Entry(bar, textvariable=self.aircraft_search_var, width=20).pack(side="left", padx=4)
        self.aircraft_tree = ttk.Treeview(left, columns=[c[0] for c in AIRCRAFT_COLUMNS], show="headings",
                                          selectmode="browse")
        for cid, heading, width, _numeric, _get in AIRCRAFT_COLUMNS:
            self.aircraft_tree.heading(cid, text=heading, command=lambda c=cid: self.sort_aircraft_by(c))
            self.aircraft_tree.column(cid, width=width, anchor="w" if cid in ("name", "nation", "type") else "e")
        self.aircraft_tree.tag_configure("edited", background="#fff2b3")
        scroll = ttk.Scrollbar(left, orient="vertical", command=self.aircraft_tree.yview)
        self.aircraft_tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.aircraft_tree.pack(side="left", fill="both", expand=True)
        self.aircraft_tree.bind("<<TreeviewSelect>>", lambda e: self.on_aircraft_select())

        right = ttk.LabelFrame(tab, text="Aircraft", padding=8)
        right.pack(side="right", fill="y", padx=(8, 0))
        self.aircraft_title = tk.StringVar(value="(select an aircraft)")
        ttk.Label(right, textvariable=self.aircraft_title, font=("TkDefaultFont", 11, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
        rows = [(f.name, f.label) for f in aircraft.SCALAR_FIELDS] + [("from", "Available from (m/yy)"),
                                                                ("to", "Available to (m/yy)"),
                                                                ("pool", "In pool")]
        row = 1
        for name, label in rows:
            ttk.Label(right, text=label).grid(row=row, column=0, sticky="w", pady=2)
            self.aircraft_vars[name] = tk.StringVar()
            ttk.Entry(right, textvariable=self.aircraft_vars[name], width=14).grid(
                row=row, column=1, padx=(8, 0), pady=2)
            row += 1
        for name, label, _hex, _miles in aircraft.RANGES:
            ttk.Label(right, text=label + " (hex, mi)").grid(row=row, column=0, sticky="w", pady=2)
            pair = ttk.Frame(right)
            pair.grid(row=row, column=1, padx=(8, 0), pady=2, sticky="w")
            for suffix in ("_hex", "_miles"):
                self.aircraft_vars[name + suffix] = tk.StringVar()
                ttk.Entry(pair, textvariable=self.aircraft_vars[name + suffix], width=6).pack(side="left", padx=(0, 2))
            row += 1
        self.aircraft_carrier_var = tk.BooleanVar()
        ttk.Checkbutton(right, text="Carrier capable", variable=self.aircraft_carrier_var).grid(
            row=row, column=0, columnspan=2, sticky="w", pady=2)
        row += 1
        ttk.Button(right, text="Apply", command=self.apply_aircraft).grid(row=row, column=0, columnspan=2, pady=6)
        row += 1
        self.aircraft_info = {}
        for name, label in (("type", "Type (read-only)"), ("nation", "Nation (read-only)"),
                            ("upgrade", "Upgrade (read-only)"), ("gun", "Gun value (read-only)"),
                            ("endurance", "Endurance (calculated)"),
                            ("used", "Used (read-only)"), ("last_turn", "Produced last turn (read-only)"),
                            ("this_month", "Produced this month (read-only)"),
                            ("mods", "Maneuver mods (read-only)")):
            ttk.Label(right, text=label).grid(row=row, column=0, sticky="w", pady=1)
            self.aircraft_info[name] = tk.StringVar()
            ttk.Label(right, textvariable=self.aircraft_info[name]).grid(row=row, column=1, sticky="w", padx=(8, 0))
            row += 1
        self.aircraft_weapon_trees = {}
        for key, title in (("max", "Weapons, max load"), ("reduced", "Weapons, reduced load")):
            box = ttk.LabelFrame(right, text=title, padding=2)
            box.grid(row=row, column=0, columnspan=2, sticky="we", pady=(4, 0))
            tree = ttk.Treeview(box, columns=("name", "count", "facing"), show="headings", height=5,
                                selectmode="none")
            for cid, heading, width in (("name", "Name", 150), ("count", "Count", 50), ("facing", "Facing", 50)):
                tree.heading(cid, text=heading)
                tree.column(cid, width=width, anchor="w" if cid == "name" else "e")
            tree.pack(fill="x")
            self.aircraft_weapon_trees[key] = tree
            row += 1

    def _build_ships_tab(self):
        tab = ttk.Frame(self.notebook, padding=4)
        self.notebook.add(tab, text="Ship Classes")
        left = ttk.Frame(tab)
        left.pack(side="left", fill="both", expand=True)
        bar = ttk.Frame(left)
        bar.pack(side="top", fill="x")
        ttk.Label(bar, text="Search:").pack(side="left")
        self.ship_search_var = tk.StringVar()
        self.ship_search_var.trace_add("write", lambda *a: self.refresh_ship_list())
        ttk.Entry(bar, textvariable=self.ship_search_var, width=20).pack(side="left", padx=4)
        self.ship_tree = ttk.Treeview(left, columns=[c[0] for c in SHIP_COLUMNS], show="headings",
                                      selectmode="browse")
        for cid, heading, width, _numeric, _get in SHIP_COLUMNS:
            self.ship_tree.heading(cid, text=heading, command=lambda c=cid: self.sort_ships_by(c))
            self.ship_tree.column(cid, width=width, anchor="w" if cid in ("name", "type", "nation") else "e")
        self.ship_tree.tag_configure("edited", background="#fff2b3")
        scroll = ttk.Scrollbar(left, orient="vertical", command=self.ship_tree.yview)
        self.ship_tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.ship_tree.pack(side="left", fill="both", expand=True)
        self.ship_tree.bind("<<TreeviewSelect>>", lambda e: self.on_ship_select())

        right = ttk.LabelFrame(tab, text="Ship class", padding=8)
        right.pack(side="right", fill="y", padx=(8, 0))
        self.ship_title = tk.StringVar(value="(select a ship class)")
        ttk.Label(right, textvariable=self.ship_title, font=("TkDefaultFont", 11, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
        row = 1
        for f in ships.FIELDS:
            ttk.Label(right, text=f.label).grid(row=row, column=0, sticky="w", pady=2)
            self.ship_vars[f.name] = tk.StringVar()
            ttk.Entry(right, textvariable=self.ship_vars[f.name], width=14).grid(
                row=row, column=1, padx=(8, 0), pady=2)
            row += 1
        ttk.Button(right, text="Apply", command=self.apply_ship).grid(row=row, column=0, columnspan=2, pady=6)
        row += 1
        self.ship_info = {}
        for name, label in (("type", "Type (read-only)"), ("nation", "Nation (read-only)"),
                            ("displacement", "Displacement (unverified, read-only)"),
                            ("date", "Date (unverified, read-only)")):
            ttk.Label(right, text=label).grid(row=row, column=0, sticky="w", pady=1)
            self.ship_info[name] = tk.StringVar()
            ttk.Label(right, textvariable=self.ship_info[name]).grid(row=row, column=1, sticky="w", padx=(8, 0))
            row += 1
        box = ttk.LabelFrame(right, text="Weapons and electronics", padding=2)
        box.grid(row=row, column=0, columnspan=2, sticky="we", pady=(4, 0))
        cols = [("name", "Name", 150), ("num", "Num", 40), ("face", "Face", 40), ("mount", "Mount", 50),
                ("armor", "Armor", 50), ("ammo", "Ammo", 50)]
        self.ship_weapon_tree = ttk.Treeview(box, columns=[c[0] for c in cols], show="headings",
                                             selectmode="browse", height=8)
        for cid, heading, width in cols:
            self.ship_weapon_tree.heading(cid, text=heading)
            self.ship_weapon_tree.column(cid, width=width, anchor="w" if cid == "name" else "e")
        self.ship_weapon_tree.pack(side="top", fill="x")
        self.ship_weapon_tree.bind("<<TreeviewSelect>>", lambda e: self.on_ship_weapon_select())
        edit = ttk.Frame(box)
        edit.pack(side="top", fill="x", pady=(4, 0))
        self.ship_weapon_vars = {}
        for name, label, width in (("num", "Num", 5), ("face", "Face", 5), ("mount", "Mount", 5),
                                   ("armor", "Armor", 5), ("ammo", "Ammo", 5)):
            ttk.Label(edit, text=label + ":").pack(side="left")
            var = tk.StringVar()
            self.ship_weapon_vars[name] = var
            if name == "face":
                ttk.Combobox(edit, textvariable=var, values=list(ships.FACES.values()), width=width).pack(
                    side="left", padx=(2, 6))
            else:
                ttk.Entry(edit, textvariable=var, width=width).pack(side="left", padx=(2, 6))
        ttk.Button(edit, text="Apply weapon", command=self.apply_ship_weapon).pack(side="left", padx=4)

    def _build_shiprecs_tab(self):
        tab = self.shiprec_tab = ttk.Frame(self.notebook, padding=4)
        self.notebook.add(tab, text="Ships")
        left = ttk.Frame(tab)
        left.pack(side="left", fill="both", expand=True)
        bar = ttk.Frame(left)
        bar.pack(side="top", fill="x")
        ttk.Label(bar, text="Search:").pack(side="left")
        self.shiprec_search_var = tk.StringVar()
        self.shiprec_search_var.trace_add("write", lambda *a: self.refresh_shiprec_list())
        ttk.Entry(bar, textvariable=self.shiprec_search_var, width=20).pack(side="left", padx=4)
        ttk.Label(bar, text="Side:").pack(side="left")
        self.shiprec_side_var = tk.StringVar(value="All")
        side_box = ttk.Combobox(bar, textvariable=self.shiprec_side_var, values=["All", "Allied", "Japanese"],
                                state="readonly", width=9)
        side_box.pack(side="left", padx=4)
        side_box.bind("<<ComboboxSelected>>", lambda e: self.refresh_shiprec_list())
        self.shiprec_tree = ttk.Treeview(left, columns=[c[0] for c in SHIPREC_COLUMNS], show="headings",
                                         selectmode="browse")
        for cid, heading, width, _numeric, _get in SHIPREC_COLUMNS:
            self.shiprec_tree.heading(cid, text=heading, command=lambda c=cid: self.sort_shiprecs_by(c))
            self.shiprec_tree.column(cid, width=width, anchor="e" if cid == "id" else "w")
        self.shiprec_tree.tag_configure("edited", background="#fff2b3")
        scroll = ttk.Scrollbar(left, orient="vertical", command=self.shiprec_tree.yview)
        self.shiprec_tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.shiprec_tree.pack(side="left", fill="both", expand=True)
        self.shiprec_tree.bind("<<TreeviewSelect>>", lambda e: self.on_shiprec_select())

        right = ttk.LabelFrame(tab, text="Ship", padding=8)
        right.pack(side="right", fill="y", padx=(8, 0))
        self.shiprec_title = tk.StringVar(value="(select a ship)")
        ttk.Label(right, textvariable=self.shiprec_title, font=("TkDefaultFont", 11, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
        row = 1
        for f in shiprecords.FIELDS:
            ttk.Label(right, text=f.label).grid(row=row, column=0, sticky="w", pady=2)
            self.shiprec_vars[f.name] = tk.StringVar()
            ttk.Entry(right, textvariable=self.shiprec_vars[f.name], width=10).grid(
                row=row, column=1, padx=(8, 0), pady=2)
            row += 1
        buttons = ttk.Frame(right)
        buttons.grid(row=row, column=0, columnspan=2, pady=6)
        ttk.Button(buttons, text="Apply", command=self.apply_shiprec).pack(side="left", padx=4)
        ttk.Button(buttons, text="Repair all", command=self.repair_shiprec).pack(side="left", padx=4)
        row += 1
        self.shiprec_info = {}
        for name, label in (("class", "Class (read-only)"), ("nation", "Nation (read-only)"),
                            ("base", "Current base (read-only)"), ("tf", "Task force (read-only)"),
                            ("arrival", "Days to arrival (read-only)")):
            ttk.Label(right, text=label).grid(row=row, column=0, sticky="w", pady=1)
            self.shiprec_info[name] = tk.StringVar()
            ttk.Label(right, textvariable=self.shiprec_info[name]).grid(row=row, column=1, sticky="w", padx=(8, 0))
            row += 1
        move = ttk.LabelFrame(right, text="Move between task forces and ports", padding=4)
        move.grid(row=row, column=0, columnspan=2, sticky="we", pady=(4, 0))
        self.shiprec_move_var = tk.StringVar()
        self.shiprec_move_box = ttk.Combobox(move, textvariable=self.shiprec_move_var, state="readonly", width=34)
        self.shiprec_move_box.pack(side="left")
        self.shiprec_move_button = ttk.Button(move, text="Move", command=self.move_shiprec)
        self.shiprec_move_button.pack(side="left", padx=4)
        self.shiprec_move_note = tk.StringVar()
        ttk.Label(move, textvariable=self.shiprec_move_note).pack(side="left")
        self.shiprec_destinations = []
        row += 1
        box = ttk.LabelFrame(right, text="Weapons and electronics", padding=2)
        box.grid(row=row, column=0, columnspan=2, sticky="we", pady=(4, 0))
        cols = [("name", "Name", 150), ("num", "Num", 40), ("face", "Face", 40), ("mount", "Mount", 50),
                ("armor", "Armor", 50), ("ammo", "Ammo", 50)]
        self.shiprec_weapon_tree = ttk.Treeview(box, columns=[c[0] for c in cols], show="headings",
                                                selectmode="browse", height=8)
        for cid, heading, width in cols:
            self.shiprec_weapon_tree.heading(cid, text=heading)
            self.shiprec_weapon_tree.column(cid, width=width, anchor="w" if cid == "name" else "e")
        self.shiprec_weapon_tree.pack(side="top", fill="x")
        self.shiprec_weapon_tree.bind("<<TreeviewSelect>>", lambda e: self.on_shiprec_weapon_select())
        edit = ttk.Frame(box)
        edit.pack(side="top", fill="x", pady=(4, 0))
        self.shiprec_weapon_vars = {}
        for name, label in (("num", "Num"), ("ammo", "Ammo")):
            ttk.Label(edit, text=label + ":").pack(side="left")
            self.shiprec_weapon_vars[name] = tk.StringVar()
            ttk.Entry(edit, textvariable=self.shiprec_weapon_vars[name], width=6).pack(side="left", padx=(2, 6))
        ttk.Button(edit, text="Apply weapon", command=self.apply_shiprec_weapon).pack(side="left", padx=4)

    def _build_taskforces_tab(self):
        tab = ttk.Frame(self.notebook, padding=4)
        self.notebook.add(tab, text="Task Forces")
        left = ttk.Frame(tab)
        left.pack(side="left", fill="both", expand=True)
        bar = ttk.Frame(left)
        bar.pack(side="top", fill="x")
        ttk.Label(bar, text="Search:").pack(side="left")
        self.tf_search_var = tk.StringVar()
        self.tf_search_var.trace_add("write", lambda *a: self.refresh_tf_list())
        ttk.Entry(bar, textvariable=self.tf_search_var, width=20).pack(side="left", padx=4)
        ttk.Label(bar, text="Side:").pack(side="left")
        self.tf_side_var = tk.StringVar(value="All")
        side_box = ttk.Combobox(bar, textvariable=self.tf_side_var, values=["All", "Allied", "Japanese"],
                                state="readonly", width=9)
        side_box.pack(side="left", padx=4)
        side_box.bind("<<ComboboxSelected>>", lambda e: self.refresh_tf_list())
        self.tf_tree = ttk.Treeview(left, columns=[c[0] for c in TF_COLUMNS], show="headings", selectmode="browse")
        for cid, heading, width, numeric, _get in TF_COLUMNS:
            self.tf_tree.heading(cid, text=heading, command=lambda c=cid: self.sort_tfs_by(c))
            self.tf_tree.column(cid, width=width, anchor="e" if numeric else "w")
        self.tf_tree.tag_configure("edited", background="#fff2b3")
        scroll = ttk.Scrollbar(left, orient="vertical", command=self.tf_tree.yview)
        self.tf_tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.tf_tree.pack(side="left", fill="both", expand=True)
        self.tf_tree.bind("<<TreeviewSelect>>", lambda e: self.on_tf_select())

        right = ttk.LabelFrame(tab, text="Task force", padding=8)
        right.pack(side="right", fill="y", padx=(8, 0))
        self.tf_title = tk.StringVar(value="(select a task force)")
        ttk.Label(right, textvariable=self.tf_title, font=("TkDefaultFont", 11, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
        row = 1
        for name, label in (("hex", "Hex x,y (read-only)"), ("location", "Location (read-only)"),
                            ("side", "Side (read-only)")):
            ttk.Label(right, text=label).grid(row=row, column=0, sticky="w", pady=1)
            self.tf_info[name] = tk.StringVar()
            ttk.Label(right, textvariable=self.tf_info[name]).grid(row=row, column=1, sticky="w", padx=(8, 0))
            row += 1
        orders = ttk.LabelFrame(right, text="Orders", padding=4)
        orders.grid(row=row, column=0, columnspan=2, sticky="we", pady=(4, 0))
        self.tf_mission_var = tk.StringVar()
        self.tf_home_var = tk.StringVar()
        self.tf_dest_var = tk.StringVar()
        self.tf_dest_filter_var = tk.StringVar()
        self.tf_dest_filter_var.trace_add("write", lambda *a: self.show_tf_destinations())
        self.tf_mission_box = ttk.Combobox(orders, textvariable=self.tf_mission_var, state="readonly", width=30,
                                           values=[f"{code:02d} - {label}" for code, label in taskforces.MISSIONS.items()])
        self.tf_home_box = ttk.Combobox(orders, textvariable=self.tf_home_var, state="readonly", width=30)
        self.tf_dest_box = ttk.Combobox(orders, textvariable=self.tf_dest_var, state="readonly", width=30)
        for name, label, widget, command, r in (
                ("mission", "Mission", self.tf_mission_box, self.set_tf_mission, 0),
                ("home_port", "Home port", self.tf_home_box, self.set_tf_home_port, 2),
                ("destination", "Destination", self.tf_dest_box, self.set_tf_destination, 5)):
            ttk.Label(orders, text=label + ":").grid(row=r, column=0, sticky="w")
            widget.grid(row=r, column=1, sticky="w", padx=2)
            ttk.Button(orders, text="Set", command=command).grid(row=r, column=2, padx=2)
            self.tf_info[name] = tk.StringVar()
            ttk.Label(orders, text="now:").grid(row=r + 1, column=0, sticky="e")
            ttk.Label(orders, textvariable=self.tf_info[name]).grid(row=r + 1, column=1, sticky="w", padx=2)
        ttk.Label(orders, text="Dest. filter:").grid(row=4, column=0, sticky="w")
        ttk.Entry(orders, textvariable=self.tf_dest_filter_var, width=20).grid(row=4, column=1, sticky="w", padx=2)
        row += 1
        box = ttk.LabelFrame(right, text="Ships (chain order)", padding=2)
        box.grid(row=row, column=0, columnspan=2, sticky="we", pady=(4, 0))
        self.tf_ship_tree = ttk.Treeview(box, columns=[c[0] for c in TF_SHIP_COLUMNS], show="headings",
                                         selectmode="browse", height=10)
        for cid, heading, width in TF_SHIP_COLUMNS:
            self.tf_ship_tree.heading(cid, text=heading)
            self.tf_ship_tree.column(cid, width=width, anchor="w" if cid in ("name", "type", "class") else "e")
        self.tf_ship_tree.pack(side="top", fill="x")
        self.tf_ship_tree.bind("<<TreeviewSelect>>", lambda e: self.on_tf_ship_select())
        row += 1
        flag = ttk.LabelFrame(right, text="Flagship", padding=4)
        flag.grid(row=row, column=0, columnspan=2, sticky="we", pady=(4, 0))
        self.tf_flag_var = tk.StringVar()
        self.tf_flag_box = ttk.Combobox(flag, textvariable=self.tf_flag_var, state="readonly", width=30)
        self.tf_flag_box.pack(side="left")
        ttk.Button(flag, text="Set flagship", command=self.set_tf_flagship).pack(side="left", padx=4)
        row += 1
        move = ttk.LabelFrame(right, text="Move the selected ship", padding=4)
        move.grid(row=row, column=0, columnspan=2, sticky="we", pady=(4, 0))
        self.tf_move_var = tk.StringVar()
        self.tf_move_box = ttk.Combobox(move, textvariable=self.tf_move_var, state="readonly", width=34)
        self.tf_move_box.pack(side="left")
        self.tf_move_button = ttk.Button(move, text="Move", command=self.move_tf_ship)
        self.tf_move_button.pack(side="left", padx=4)
        self.tf_move_note = tk.StringVar()
        ttk.Label(move, textvariable=self.tf_move_note).pack(side="left")
        row += 1
        add = ttk.LabelFrame(right, text="Add ship from port", padding=4)
        add.grid(row=row, column=0, columnspan=2, sticky="we", pady=(4, 0))
        self.tf_add_var = tk.StringVar()
        self.tf_add_box = ttk.Combobox(add, textvariable=self.tf_add_var, state="readonly", width=34)
        self.tf_add_box.pack(side="left")
        self.tf_add_button = ttk.Button(add, text="Add", command=self.add_tf_ship)
        self.tf_add_button.pack(side="left", padx=4)
        self.tf_add_note = tk.StringVar()
        ttk.Label(add, textvariable=self.tf_add_note).pack(side="left")
        row += 1
        quick = ttk.Frame(right)
        quick.grid(row=row, column=0, columnspan=2, pady=(8, 0))
        ttk.Button(quick, text="Repair all ships", command=self.repair_tf).pack(side="left", padx=4)
        ttk.Button(quick, text="Refuel all ships", command=self.refuel_tf).pack(side="left", padx=4)

    def _build_groups_tab(self):
        tab = ttk.Frame(self.notebook, padding=4)
        self.notebook.add(tab, text="Air Groups")
        right = ttk.LabelFrame(tab, text="Air group", padding=8)
        right.pack(side="right", fill="y", padx=(8, 0))
        left = ttk.Frame(tab)
        left.pack(side="left", fill="both", expand=True)

        bar = ttk.Frame(left)
        bar.pack(side="top", fill="x")
        ttk.Label(bar, text="Search:").pack(side="left")
        self.group_search_var = tk.StringVar()
        self.group_search_var.trace_add("write", lambda *a: self.refresh_group_list())
        ttk.Entry(bar, textvariable=self.group_search_var, width=20).pack(side="left", padx=4)
        ttk.Label(bar, text="Side:").pack(side="left")
        self.group_side_var = tk.StringVar(value="All")
        side_box = ttk.Combobox(bar, textvariable=self.group_side_var, values=["All", "Allied", "Japanese"],
                                state="readonly", width=9)
        side_box.pack(side="left", padx=4)
        side_box.bind("<<ComboboxSelected>>", lambda e: self.refresh_group_list())

        # Pilots and commander sit below the list so the tab stays short enough for small screens.
        lower = ttk.Frame(left)
        lower.pack(side="bottom", fill="x", pady=(6, 0))
        self._build_pilots(lower)
        self._build_leader(lower)

        self.group_tree = ttk.Treeview(left, columns=[c[0] for c in GROUP_COLUMNS], show="headings",
                                       selectmode="browse", height=8)
        for cid, heading, width, _numeric, _get in GROUP_COLUMNS:
            self.group_tree.heading(cid, text=heading, command=lambda c=cid: self.sort_groups_by(c))
            self.group_tree.column(cid, width=width, anchor="w" if cid in ("name", "aircraft", "location") else "e")
        self.group_tree.tag_configure("edited", background="#fff2b3")
        scroll = ttk.Scrollbar(left, orient="vertical", command=self.group_tree.yview)
        self.group_tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.group_tree.pack(side="left", fill="both", expand=True)
        self.group_tree.bind("<<TreeviewSelect>>", lambda e: self.on_group_select())

        self.group_title = tk.StringVar(value="(select an air group)")
        ttk.Label(right, textvariable=self.group_title, font=("TkDefaultFont", 11, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
        row = 1
        for f in airgroups.GROUP_FIELDS:
            ttk.Label(right, text=f.label + ("" if f.verified else " (unverified)")).grid(
                row=row, column=0, sticky="w", pady=2)
            self.group_vars[f.name] = tk.StringVar()
            ttk.Entry(right, textvariable=self.group_vars[f.name],
                      width=12 if f.name in airgroups.DATE_FIELDS else 10).grid(
                row=row, column=1, padx=(8, 0), pady=2)
            row += 1
        ttk.Button(right, text="Apply", command=self.apply_group).grid(row=row, column=0, columnspan=2, pady=6)
        row += 1
        self.group_info = {}
        for name, label in (("aircraft", "Aircraft"), ("upgrade", "Upgrade to"), ("planes", "Aircraft total (read-only)"),
                            ("pilots", "Pilot count byte (read-only, meaning unclear)"), ("leader", "Commander (read-only)"),
                            ("formation", "Formation (read-only)"), ("parent", "Parent group (read-only)"),
                            ("return_as", "Returns as (read-only)"), ("location", "Location")):
            ttk.Label(right, text=label).grid(row=row, column=0, sticky="w", pady=1)
            self.group_info[name] = tk.StringVar()
            ttk.Label(right, textvariable=self.group_info[name]).grid(row=row, column=1, sticky="w", padx=(8, 0))
            row += 1
        self._build_planes(right, row)
        row += 1
        self._build_schedule(right, row)
        row += 1
        self.group_move_var, self.group_move_box, self.group_move_button, self.group_move_note = self._build_move_row(
            right, row, self.move_group)
        row += 3
        ttk.Label(right, text="Change aircraft").grid(row=row, column=0, sticky="w", pady=(8, 2))
        self.group_aircraft_var = tk.StringVar()
        self.group_aircraft_box = ttk.Combobox(right, textvariable=self.group_aircraft_var, state="disabled", width=24)
        self.group_aircraft_box.grid(row=row, column=1, padx=(8, 0), pady=(8, 2))
        self.group_aircraft_button = ttk.Button(right, text="Change", command=self.change_group_aircraft)
        self.group_aircraft_button.grid(row=row + 1, column=0, columnspan=2, pady=2)
        row += 2
        ttk.Label(right, text="Upgrade to").grid(row=row, column=0, sticky="w", pady=(8, 2))
        self.group_upgrade_var = tk.StringVar()
        self.group_upgrade_box = ttk.Combobox(right, textvariable=self.group_upgrade_var, state="disabled", width=24)
        self.group_upgrade_box.grid(row=row, column=1, padx=(8, 0), pady=(8, 2))
        self.group_upgrade_button = ttk.Button(right, text="Set upgrade", command=self.change_group_upgrade)
        self.group_upgrade_button.grid(row=row + 1, column=0, columnspan=2, pady=2)
        row += 2
        ttk.Label(right, text="The game probably recalculates\naverage experience from the pilots.",
                  foreground="gray40").grid(row=row, column=0, columnspan=2, sticky="w", pady=(6, 0))

    def _build_planes(self, parent, row):
        """Ready / maintenance / damaged / reserve split of the group's planes; the total stays fixed."""
        box = ttk.LabelFrame(parent, text="Planes", padding=4)
        box.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(8, 2))
        self.plane_vars, self.plane_entries = {}, []
        for k, (name, label) in enumerate((("ready", "Ready"), ("maintenance", "Maintenance"),
                                           ("damaged", "Damaged"), ("reserve", "Reserve"))):
            r, c = divmod(k, 2)
            ttk.Label(box, text=label).grid(row=r, column=2 * c, sticky="w", padx=(0, 2), pady=1)
            self.plane_vars[name] = tk.StringVar()
            entry = ttk.Entry(box, textvariable=self.plane_vars[name], width=5, state="disabled")
            entry.grid(row=r, column=2 * c + 1, sticky="w", padx=(0, 10), pady=1)
            self.plane_entries.append(entry)
        ttk.Label(box, text="Total").grid(row=2, column=0, sticky="w", pady=1)
        self.plane_total = tk.StringVar()
        ttk.Label(box, textvariable=self.plane_total).grid(row=2, column=1, sticky="w", pady=1)
        self.plane_apply_button = ttk.Button(box, text="Apply planes", command=self.apply_planes, state="disabled")
        self.plane_apply_button.grid(row=3, column=0, columnspan=2, sticky="w", pady=(2, 0))
        self.plane_repair_button = ttk.Button(box, text="Repair all", command=self.repair_planes, state="disabled")
        self.plane_repair_button.grid(row=3, column=2, columnspan=2, sticky="w", pady=(2, 0))
        self.plane_note = tk.StringVar()
        ttk.Label(box, textvariable=self.plane_note, foreground="gray40").grid(
            row=4, column=0, columnspan=4, sticky="w")

    def _build_schedule(self, parent, row):
        """The group's five scheduled size changes (date, new size); schedule data, so always editable."""
        box = ttk.LabelFrame(parent, text="Size changes", padding=4)
        box.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(8, 2))
        ttk.Label(box, text="Date (e.g. Jul 42)").grid(row=0, column=0, sticky="w")
        ttk.Label(box, text="New size").grid(row=0, column=1, sticky="w", padx=(8, 0))
        self.schedule_vars = []
        for k in range(airgroups.SCHEDULE_COUNT):
            date_var, size_var = tk.StringVar(), tk.StringVar()
            ttk.Entry(box, textvariable=date_var, width=12).grid(row=k + 1, column=0, sticky="w", pady=1)
            ttk.Entry(box, textvariable=size_var, width=6).grid(row=k + 1, column=1, sticky="w", padx=(8, 0), pady=1)
            self.schedule_vars.append((date_var, size_var))
        ttk.Button(box, text="Apply size changes", command=self.apply_schedule).grid(
            row=airgroups.SCHEDULE_COUNT + 1, column=0, columnspan=2, sticky="w", pady=(2, 0))

    def _build_pilots(self, parent):
        box = ttk.LabelFrame(parent, text="Pilots", padding=4)
        box.pack(side="top", fill="x")
        cols = [("id", "ID", 50), ("name", "Name", 100), ("status", "Status", 60), ("experience", "Exp", 35)] + [
            ("skill_" + n.lower(), n, 38) for n in airgroups.SKILLS]
        self.pilot_tree = ttk.Treeview(box, columns=[c[0] for c in cols], show="headings",
                                       selectmode="browse", height=4)
        for cid, heading, width in cols:
            self.pilot_tree.heading(cid, text=heading)
            self.pilot_tree.column(cid, width=width, anchor="w" if cid == "name" else "e")
        self.pilot_tree.pack(side="top", fill="x")
        self.pilot_tree.bind("<<TreeviewSelect>>", lambda e: self.on_pilot_select())
        edit = ttk.Frame(box)
        edit.pack(side="top", fill="x", pady=(4, 0))
        # Four label/entry pairs per row so the full skill names fit.
        per_row = 4
        for k, f in enumerate(airgroups.PILOT_FIELDS):
            row, col = divmod(k, per_row)
            ttk.Label(edit, text=f.label).grid(row=row, column=2 * col, sticky="w", padx=(0, 2), pady=1)
            self.pilot_vars[f.name] = tk.StringVar()
            ttk.Entry(edit, textvariable=self.pilot_vars[f.name], width=4).grid(
                row=row, column=2 * col + 1, sticky="w", padx=(0, 12), pady=1)
        k = len(airgroups.PILOT_FIELDS)
        ttk.Button(edit, text="Apply pilot", command=self.apply_pilot).grid(
            row=k // per_row, column=2 * (k % per_row), columnspan=2, sticky="w", pady=1)

    def _build_leader(self, parent):
        box = ttk.LabelFrame(parent, text="Commander", padding=4)
        box.pack(side="top", fill="x", pady=(6, 0))
        self.leader_name = tk.StringVar(value="(none)")
        ttk.Label(box, textvariable=self.leader_name).grid(row=0, column=0, columnspan=2, sticky="w", pady=1)
        self.leader_age = tk.StringVar()
        ttk.Label(box, text="Age (unverified)").grid(row=0, column=2, sticky="w", padx=(0, 2), pady=1)
        ttk.Label(box, textvariable=self.leader_age).grid(row=0, column=3, sticky="w", pady=1)
        # Same four-per-row grid as the pilot editor, below the name row.
        per_row = 4
        self.leader_entries = []
        for k, f in enumerate(airgroups.LEADER_FIELDS):
            row, col = divmod(k, per_row)
            ttk.Label(box, text=f.label).grid(row=row + 1, column=2 * col, sticky="w", padx=(0, 2), pady=1)
            self.leader_vars[f.name] = tk.StringVar()
            entry = ttk.Entry(box, textvariable=self.leader_vars[f.name], width=4)
            entry.grid(row=row + 1, column=2 * col + 1, sticky="w", padx=(0, 12), pady=1)
            self.leader_entries.append(entry)
        k = len(airgroups.LEADER_FIELDS)
        self.leader_button = ttk.Button(box, text="Apply commander", command=self.apply_leader)
        self.leader_button.grid(row=k // per_row + 1, column=2 * (k % per_row), columnspan=2, sticky="w", pady=1)

    def _build_units_tab(self):
        tab = ttk.Frame(self.notebook, padding=4)
        self.notebook.add(tab, text="Land Units")
        right = ttk.LabelFrame(tab, text="Land unit", padding=8)
        right.pack(side="right", fill="y", padx=(8, 0))
        left = ttk.Frame(tab)
        left.pack(side="left", fill="both", expand=True)

        bar = ttk.Frame(left)
        bar.pack(side="top", fill="x")
        ttk.Label(bar, text="Search:").pack(side="left")
        self.unit_search_var = tk.StringVar()
        self.unit_search_var.trace_add("write", lambda *a: self.refresh_unit_list())
        ttk.Entry(bar, textvariable=self.unit_search_var, width=20).pack(side="left", padx=4)
        ttk.Label(bar, text="Side:").pack(side="left")
        self.unit_side_var = tk.StringVar(value="All")
        side_box = ttk.Combobox(bar, textvariable=self.unit_side_var, values=["All", "Allied", "Japanese"],
                                state="readonly", width=9)
        side_box.pack(side="left", padx=4)
        side_box.bind("<<ComboboxSelected>>", lambda e: self.refresh_unit_list())

        box = ttk.LabelFrame(left, text="Equipment", padding=4)
        box.pack(side="bottom", fill="x", pady=(6, 0))
        cols = [("slot", "Slot", 40), ("device", "Device", 150), ("count", "Count", 55),
                ("disabled", "Disabled", 60), ("toe_device", "TOE device", 150), ("toe_count", "TOE count", 65)]
        self.unit_equipment_tree = ttk.Treeview(box, columns=[c[0] for c in cols], show="headings",
                                                selectmode="browse", height=6)
        for cid, heading, width in cols:
            self.unit_equipment_tree.heading(cid, text=heading)
            self.unit_equipment_tree.column(cid, width=width, anchor="w" if "device" in cid else "e")
        self.unit_equipment_tree.pack(side="top", fill="x")
        self.unit_equipment_tree.bind("<<TreeviewSelect>>", lambda e: self.on_unit_equipment_select())
        edit = ttk.Frame(box)
        edit.pack(side="top", fill="x", pady=(4, 0))
        self.unit_equipment_vars = {}
        for name, label in (("count", "Count"), ("disabled", "Disabled")):
            ttk.Label(edit, text=label + ":").pack(side="left")
            self.unit_equipment_vars[name] = tk.StringVar()
            ttk.Entry(edit, textvariable=self.unit_equipment_vars[name], width=8).pack(side="left", padx=(2, 8))
        ttk.Button(edit, text="Apply equipment", command=self.apply_unit_equipment).pack(side="left", padx=4)
        add = ttk.Frame(box)
        add.pack(side="top", fill="x", pady=(4, 0))
        ttk.Label(add, text="Add:").pack(side="left")
        self.unit_add_device_var = tk.StringVar()
        self.unit_add_box = ttk.Combobox(add, textvariable=self.unit_add_device_var, state="disabled", width=26)
        self.unit_add_box.pack(side="left", padx=(2, 8))
        self.unit_add_vars = {}
        for name, label, default in (("count", "Count", ""), ("disabled", "Disabled", "0")):
            ttk.Label(add, text=label + ":").pack(side="left")
            self.unit_add_vars[name] = tk.StringVar(value=default)
            ttk.Entry(add, textvariable=self.unit_add_vars[name], width=6).pack(side="left", padx=(2, 8))
        self.unit_add_button = ttk.Button(add, text="Add equipment", command=self.add_unit_equipment)
        self.unit_add_button.pack(side="left", padx=4)

        self.unit_tree = ttk.Treeview(left, columns=[c[0] for c in UNIT_COLUMNS], show="headings",
                                      selectmode="browse", height=8)
        for cid, heading, width, _numeric, _get in UNIT_COLUMNS:
            self.unit_tree.heading(cid, text=heading, command=lambda c=cid: self.sort_units_by(c))
            self.unit_tree.column(cid, width=width, anchor="w" if cid in ("name", "type", "hq", "location") else "e")
        self.unit_tree.tag_configure("edited", background="#fff2b3")
        scroll = ttk.Scrollbar(left, orient="vertical", command=self.unit_tree.yview)
        self.unit_tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.unit_tree.pack(side="left", fill="both", expand=True)
        self.unit_tree.bind("<<TreeviewSelect>>", lambda e: self.on_unit_select())

        self.unit_title = tk.StringVar(value="(select a land unit)")
        ttk.Label(right, textvariable=self.unit_title, font=("TkDefaultFont", 11, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))
        row = 1
        for f in landunits.FIELDS:
            ttk.Label(right, text=f.label + ("" if f.verified else " (unverified)")).grid(
                row=row, column=0, sticky="w", pady=2)
            self.unit_vars[f.name] = tk.StringVar()
            ttk.Entry(right, textvariable=self.unit_vars[f.name], width=12).grid(
                row=row, column=1, padx=(8, 0), pady=2)
            row += 1
        ttk.Button(right, text="Apply", command=self.apply_unit).grid(row=row, column=0, columnspan=2, pady=6)
        row += 1
        self.unit_info = {}
        for name, label in (("hq", "HQ (read-only)"), ("location", "Location"),
                            ("target", "Target (set by a move)"), ("required", "Supplies required (read-only)"),
                            ("support", "Support (approx., read-only)"),
                            ("support_required", "Support required (approx., read-only)")):
            ttk.Label(right, text=label).grid(row=row, column=0, sticky="w", pady=1)
            self.unit_info[name] = tk.StringVar()
            ttk.Label(right, textvariable=self.unit_info[name]).grid(row=row, column=1, sticky="w", padx=(8, 0))
            row += 1
        self.unit_move_var, self.unit_move_box, self.unit_move_button, self.unit_move_note = self._build_move_row(
            right, row, self.move_unit)

    def _build_move_row(self, parent, row, command):
        """Destination box, Move button and a gray note for why moving is not possible."""
        ttk.Label(parent, text="Move to").grid(row=row, column=0, sticky="w", pady=(8, 2))
        var = tk.StringVar()
        box = ttk.Combobox(parent, textvariable=var, state="readonly", width=24)
        box.grid(row=row, column=1, padx=(8, 0), pady=(8, 2))
        button = ttk.Button(parent, text="Move", command=command)
        button.grid(row=row + 1, column=0, columnspan=2, pady=2)
        note = tk.StringVar()
        ttk.Label(parent, textvariable=note, foreground="gray40").grid(row=row + 2, column=0, columnspan=2, sticky="w")
        return var, box, button, note

    def _show_move(self, record, var, box, button, note):
        """Fill the destination box for a record, or disable it and say why it cannot move."""
        if record is None or not record.can_move:
            var.set("")
            box.configure(values=[], state="disabled")
            button.state(["disabled"])
            note.set(f"Cannot move: {record.move_blocker}" if record is not None else "")
            return
        box.configure(values=self.place_labels.get(record.side, []), state="readonly")
        button.state(["!disabled"])
        note.set("")
        var.set("")

    def _build_factories(self, parent):
        box = ttk.LabelFrame(parent, text="Factories", padding=4)
        box.pack(side="bottom", fill="x", pady=(6, 0))
        cols = [("slot", "Slot", 40), ("name", "Name", 150), ("kind", "Kind", 65), ("size", "Size", 55),
                ("damage", "Damage", 60), ("production", "Production", 75), ("repair", "Repair", 55),
                ("upgrade", "Upgrade", 60), ("available", "Available", 65)]
        self.factory_tree = ttk.Treeview(box, columns=[c[0] for c in cols], show="headings",
                                         selectmode="browse", height=6)
        for cid, heading, width in cols:
            self.factory_tree.heading(cid, text=heading)
            self.factory_tree.column(cid, width=width, anchor="w" if cid in ("name", "kind") else "e")
        self.factory_tree.pack(side="top", fill="x")
        self.factory_tree.bind("<<TreeviewSelect>>", lambda e: self.on_factory_select())
        edit = ttk.Frame(box)
        edit.pack(side="top", fill="x", pady=(4, 0))
        self.factory_size_var = tk.StringVar()
        self.factory_damage_var = tk.StringVar()
        self.factory_production_var = tk.BooleanVar()
        self.factory_repair_var = tk.BooleanVar()
        self.factory_upgrade_var = tk.BooleanVar()
        ttk.Label(edit, text="Size:").pack(side="left")
        ttk.Entry(edit, textvariable=self.factory_size_var, width=8).pack(side="left", padx=(2, 8))
        ttk.Label(edit, text="Damage:").pack(side="left")
        ttk.Entry(edit, textvariable=self.factory_damage_var, width=8).pack(side="left", padx=(2, 8))
        self.factory_production_check = ttk.Checkbutton(edit, text="Production", variable=self.factory_production_var)
        self.factory_production_check.pack(side="left", padx=4)
        ttk.Checkbutton(edit, text="Repair", variable=self.factory_repair_var).pack(side="left", padx=4)
        self.factory_upgrade_check = ttk.Checkbutton(edit, text="Upgrade", variable=self.factory_upgrade_var)
        self.factory_upgrade_check.pack(side="left", padx=4)
        ttk.Button(edit, text="Apply factory", command=self.apply_factory).pack(side="left", padx=8)

    # ---- loading -------------------------------------------------------

    def open_dialog(self, initial_dir=None):
        if not self.confirm_discard():
            return
        start = initial_dir if initial_dir else (DEFAULT_DIR if os.path.isdir(DEFAULT_DIR) else HERE)
        path = filedialog.askopenfilename(title="Open save", initialdir=start,
                                          filetypes=[("WitP:AE saves", "*.pws"), ("All files", "*.*")])
        if path:
            self.load(path)

    def load(self, path):
        # Windows reports opening a folder as "Permission denied", which is misleading.
        if os.path.isdir(path):
            messagebox.showerror("Cannot open save", f"{path}\n\nThis is a folder. Choose a .pws save file inside it.")
            return False
        if not os.path.isfile(path):
            messagebox.showerror("Cannot open save", f"{path}\n\nFile not found.")
            return False
        try:
            save = SaveFile.load(path)
            blist = bases.list_bases(save, include_towns=True)
            alist = aircraft.list_aircraft(save)
            slist = ships.list_ships(save)
            srlist = shiprecords.list_ship_records(save)
            tflist = self._load_task_forces(save)
            glist = airgroups.list_airgroups(save)
            ulist = landunits.list_land_units(save)
            pindex = airgroups.pilots_by_group(save)
            places = bases.list_places(save)
            devices = landunits.available_devices(save)
        except (OSError, SaveFormatError, KeyError) as exc:
            messagebox.showerror("Cannot open save", f"{path}\n\n{exc}")
            return False
        self.save, self.path = save, path
        # Judged on the title as loaded, so retitling the save cannot lift the block.
        self.pbem = is_pbem(save)
        self.bases = {b.id: b for b in blist}
        self.edited.clear()
        self.dirty = False
        self.current = None
        self.factory_slot = None
        self.aircraft = {a.id: a for a in alist}
        self.aircraft_edited.clear()
        self.aircraft_current = None
        self.ships = {x.id: x for x in slist}
        self.ships_edited.clear()
        self.ship_current = None
        self.ship_slot = None
        self.shiprecs = {x.id: x for x in srlist}
        self.shiprecs_edited.clear()
        self.shiprec_current = None
        self.shiprec_slot = None
        self.places_by_hex = {}
        for p in places:
            self.places_by_hex.setdefault((p.x, p.y), []).append(p)
        self.places_by_id = {p.id: p for p in places}
        # Built once per load: list_places is slow, and the orders boxes filter these lists.
        self.tf_port_items = [(p, f"{p.name} ({p.id})") for p in places if taskforces.port_size(save, p.id) > 0]
        self.tf_dest_items = [(p, f"{p.name} ({p.id}, {bases.SIDES.get(p.side_id, '?')})") for p in places]
        self.taskforces = {t.id: t for t in tflist}
        self.tfs_edited.clear()
        self.tf_current = None
        self.tf_ship_current = None
        self.groups = {g.id: g for g in glist}
        self.pilot_index = pindex
        for g in glist:
            g.active_pilots = sum(1 for p in pindex.get(g.id, []) if p.status == 1)
        self.groups_edited.clear()
        self.group_current = None
        self.pilot_current = None
        self.leader_current = None
        # Built once per load: decrypting every place name is slow.
        self.place_ids = {}
        self.place_labels = {}
        for p in sorted(places, key=lambda p: (p.name.lower(), p.id)):
            label = f"{p.name} ({p.id})"
            self.place_ids[label] = p.id
            self.place_labels.setdefault(bases.SIDES.get(p.side_id, "Unknown"), []).append(label)
        self.device_ids = {}
        self.device_labels = {}
        for side_id, items in devices.items():
            for device_id, name in items:
                label = f"{name} ({device_id})"
                self.device_ids[label] = device_id
                self.device_labels.setdefault(bases.SIDES[side_id], []).append(label)
        self.aircraft_ids = {}
        self.aircraft_labels = {}
        for a in sorted(alist, key=lambda a: (a.name.lower(), a.id)):
            month, year = a.get_date("from")
            label = f"{a.name} ({a.id}, {aircraft.format_date(month, year)})"
            self.aircraft_ids[label] = a.id
            self.aircraft_labels.setdefault(bases.SIDES.get(a.side_id, "Unknown"), []).append(label)
        self.units = {u.id: u for u in ulist}
        self.units_edited.clear()
        self.unit_current = None
        self.unit_slot = None
        self.file_label.set(f"File: {os.path.basename(path)}    Key variant: {save.variant}")
        self.title_var.set(save.description)
        self.status.set(f"{path} - {len(blist)} bases and towns, {len(alist)} aircraft, {len(slist)} ship classes, {len(srlist)} ships, {len(glist)} air groups, {len(ulist)} land units"
                        + (" - PBEM game: saving is disabled" if self.pbem else ""))
        self.refresh_list()
        self.show_detail(None)
        self.refresh_aircraft_list()
        self.show_aircraft(None)
        self.refresh_ship_list()
        self.show_ship(None)
        self.refresh_shiprec_list()
        self.show_shiprec(None)
        self.refresh_tf_list()
        self.show_tf(None)
        self.refresh_group_list()
        self.show_group(None)
        self.refresh_unit_list()
        self.show_unit(None)
        self.industry_places = industry.list_industry_places(save, regions.default_regions())
        self.refresh_reports()
        return True

    def confirm_discard(self):
        if not self.dirty:
            return True
        return messagebox.askyesno("Unsaved changes", "There are unsaved changes. Discard them?")

    def quit(self):
        if self.confirm_discard():
            self.root.destroy()

    # ---- list ----------------------------------------------------------

    def _row_values(self, b):
        vals = []
        for cid, _h, _w, _n, get in COLUMNS:
            v = get(b)
            vals.append(f"{v[0]},{v[1]}" if cid == "hex" else v)
        return vals

    def _sort_key(self, b):
        _cid, _h, _w, numeric, get = COLUMN_BY_ID[self.sort_col]
        v = get(b)
        return v if numeric else str(v).lower()

    def refresh_list(self):
        selected = self.current
        self.tree.delete(*self.tree.get_children())
        needle = self.search_var.get().strip().lower()
        side = self.side_var.get()
        rows = [b for b in self.bases.values()
                if needle in b.name.lower() and (side == "All" or b.side == side)]
        rows.sort(key=self._sort_key, reverse=self.sort_reverse)
        for b in rows:
            tags = ("edited",) if b.id in self.edited else ()
            self.tree.insert("", "end", iid=str(b.id), values=self._row_values(b), tags=tags)
        if selected is not None and self.tree.exists(str(selected)):
            self.tree.selection_set(str(selected))

    def sort_by(self, col):
        self.sort_reverse = (not self.sort_reverse) if col == self.sort_col else False
        self.sort_col = col
        self.refresh_list()

    # ---- detail --------------------------------------------------------

    def on_select(self):
        sel = self.tree.selection()
        self.show_detail(self.bases[int(sel[0])] if sel else None)

    def show_detail(self, base):
        previous = self.current
        self.current = base.id if base else None
        if base is None:
            self.detail_title.set("(select a base)")
            for var in self.field_vars.values():
                var.set("")
            for var in list(self.stockpile_vars.values()) + list(self.building_vars.values()):
                var.set(False)
            self._set_port_editable(True)
            self.show_factories(None)
            return
        self._set_port_editable(base.kind != "Town")
        self.detail_title.set(f"{base.name} (#{base.id}, {base.side}, hex {base.x},{base.y})")
        for f in bases.FIELDS:
            self.field_vars[f.name].set(str(base.get(f.name)))
        for name, on in base.get_stockpile().items():
            self.stockpile_vars[name].set(on)
        for name, on in base.get_building().items():
            self.building_vars[name].set(on)
        if base.id != previous:
            self.factory_slot = None
        self.show_factories(base)

    def _set_port_editable(self, editable):
        """Towns have no port, so lock the port entries and build switch for them."""
        state = ["!disabled"] if editable else ["disabled"]
        for name in bases.TOWN_READONLY_FIELDS:
            self.field_entries[name].state(state)
        self.building_checks["port"].state(state)

    def show_factories(self, base):
        self.factory_tree.delete(*self.factory_tree.get_children())
        if base is None:
            self.factory_slot = None
            self._fill_factory_edit(None)
            return
        yn = lambda v: "Yes" if v else "No"
        for f in factories.list_factories(base):
            self.factory_tree.insert("", "end", iid=str(f.slot), values=(
                f.slot, f.name, f.kind, f.size, f.damage, yn(f.production_on), yn(f.repair_on),
                "-" if factories.upgrade_locked(f.type) else ("Upgd" if f.upgrade_on else "Keep"),
                f"{f.available[0]}/{f.available[1]}" if f.available else ""))
        slot = self.factory_slot
        if slot is not None and self.factory_tree.exists(str(slot)):
            self.factory_tree.selection_set(str(slot))
        else:
            self.factory_slot = None
            self._fill_factory_edit(None)

    def _fill_factory_edit(self, factory):
        if factory is None:
            self.factory_size_var.set("")
            self.factory_damage_var.set("")
            self.factory_production_var.set(True)
            self.factory_repair_var.set(True)
            self.factory_upgrade_var.set(False)
            self.factory_production_check.state(["disabled"])
            self.factory_upgrade_check.state(["disabled"])
            return
        self.factory_size_var.set(str(factory.size))
        self.factory_damage_var.set(str(factory.damage))
        self.factory_production_var.set(factory.production_on)
        self.factory_repair_var.set(factory.repair_on)
        self.factory_upgrade_var.set(factory.upgrade_on)
        self.factory_production_check.state(["disabled" if factories.production_locked(factory.type) else "!disabled"])
        self.factory_upgrade_check.state(["disabled" if factories.upgrade_locked(factory.type) else "!disabled"])

    def on_factory_select(self):
        sel = self.factory_tree.selection()
        if not sel or self.current is None:
            return
        self.factory_slot = int(sel[0])
        self._fill_factory_edit(factories.get_factory(self.bases[self.current], self.factory_slot))

    def apply_factory(self):
        if self.current is None or self.factory_slot is None:
            return
        base = self.bases[self.current]
        before = factories.get_factory(base, self.factory_slot)
        try:
            size = int(self.factory_size_var.get().strip())
            damage = int(self.factory_damage_var.get().strip())
        except ValueError:
            messagebox.showerror("Invalid value", "Size and damage must be whole numbers.")
            return
        try:
            factories.set_factory(base, self.factory_slot, size, damage,
                                  bool(self.factory_production_var.get()), bool(self.factory_repair_var.get()),
                                  None if factories.upgrade_locked(before.type) else bool(self.factory_upgrade_var.get()))
        except ValueError as exc:
            messagebox.showerror("Invalid value", str(exc))
            return
        if factories.get_factory(base, self.factory_slot) != before:
            self.edited.add(base.id)
            self.dirty = True
        self.refresh_list()
        self.show_factories(base)

    def apply(self):
        if self.current is None:
            return
        base = self.bases[self.current]
        values = {}
        is_town = base.kind == "Town"
        for f in bases.FIELDS:
            if not f.editable or (is_town and f.name in bases.TOWN_READONLY_FIELDS):
                continue
            text = self.field_vars[f.name].get().strip()
            try:
                values[f.name] = int(text)
                base.validate(f.name, values[f.name])
            except ValueError:
                messagebox.showerror("Invalid value",
                                     f"{f.label} must be a whole number from {f.min} to {f.max} (got {text!r}).")
                return
        before = {n: base.get(n) for n in values}
        flags = {n: bool(v.get()) for n, v in self.stockpile_vars.items()}
        flags_before = base.get_stockpile()
        building = {n: bool(v.get()) for n, v in self.building_vars.items() if not (is_town and n == "port")}
        building_before = {n: v for n, v in base.get_building().items() if n in building}
        base.set_many(values)
        base.set_stockpile(flags)
        base.set_building(building)
        if before != values or flags_before != flags or building_before != building:
            self.edited.add(base.id)
            self.dirty = True
        self.refresh_list()
        self.show_detail(base)

    # ---- aircraft ------------------------------------------------------

    def _aircraft_row(self, a):
        return [aircraft.format_date(*a.get_date(cid)) if cid in ("from", "to") else get(a)
                for cid, _h, _w, _n, get in AIRCRAFT_COLUMNS]

    def _aircraft_sort_key(self, a):
        _cid, _h, _w, numeric, get = AIRCRAFT_COLUMN_BY_ID[self.aircraft_sort_col]
        v = get(a)
        # Ties fall back to the id so the order is stable.
        return (v if numeric else str(v).lower(), a.id)

    def refresh_aircraft_list(self):
        selected = self.aircraft_current
        self.aircraft_tree.delete(*self.aircraft_tree.get_children())
        needle = self.aircraft_search_var.get().strip().lower()
        rows = [a for a in self.aircraft.values() if needle in a.name.lower()]
        rows.sort(key=self._aircraft_sort_key, reverse=self.aircraft_sort_reverse)
        for a in rows:
            tags = ("edited",) if a.id in self.aircraft_edited else ()
            self.aircraft_tree.insert("", "end", iid=str(a.id), values=self._aircraft_row(a), tags=tags)
        if selected is not None and self.aircraft_tree.exists(str(selected)):
            self.aircraft_tree.selection_set(str(selected))

    def sort_aircraft_by(self, col):
        self.aircraft_sort_reverse = (not self.aircraft_sort_reverse) if col == self.aircraft_sort_col else False
        self.aircraft_sort_col = col
        self.refresh_aircraft_list()

    def on_aircraft_select(self):
        sel = self.aircraft_tree.selection()
        self.show_aircraft(self.aircraft[int(sel[0])] if sel else None)

    def show_aircraft(self, a):
        self.aircraft_current = a.id if a else None
        for tree in self.aircraft_weapon_trees.values():
            tree.delete(*tree.get_children())
        if a is None:
            self.aircraft_title.set("(select an aircraft)")
            for var in list(self.aircraft_vars.values()) + list(self.aircraft_info.values()):
                var.set("")
            self.aircraft_carrier_var.set(False)
            return
        self.aircraft_title.set(f"{a.name} (#{a.id})")
        for f in aircraft.FIELDS:
            self.aircraft_vars[f.name].set(str(a.get(f.name)))
        for name in ("from", "to"):
            self.aircraft_vars[name].set(aircraft.format_date(*a.get_date(name)))
        self.aircraft_vars["pool"].set(str(a.pool))
        self.aircraft_carrier_var.set(a.get_carrier())
        info = {"type": a.type, "nation": a.nation,
                "upgrade": f"{a.upgrade_id} {a.upgrade_name} (unverified)",
                "gun": str(a.gun_value),
                "endurance": "-" if a.endurance is None else str(a.endurance),
                "used": str(a.used), "last_turn": str(a.last_turn), "this_month": str(a.this_month),
                "mods": ", ".join(f"{band} {m}" for band, m in zip(aircraft.MANEUVER_MOD_BANDS, a.maneuver_mods))}
        for name, text in info.items():
            self.aircraft_info[name].set(text)
        for key, weapons in (("max", a.max_weapons), ("reduced", a.reduced_weapons)):
            for w in weapons:
                self.aircraft_weapon_trees[key].insert("", "end", values=w)

    def apply_aircraft(self):
        if self.aircraft_current is None:
            return
        a = self.aircraft[self.aircraft_current]
        values, dates = {}, {}
        try:
            for f in aircraft.FIELDS:
                text = self.aircraft_vars[f.name].get().strip()
                try:
                    values[f.name] = a.validate(f.name, int(text))
                except ValueError:
                    raise ValueError(f"{f.label} must be a whole number from {f.min} to {f.max} (got {text!r}).")
            for name in ("from", "to"):
                dates[name] = aircraft.parse_date(self.aircraft_vars[name].get())
            text = self.aircraft_vars["pool"].get().strip()
            try:
                pool = aircraft.check_pool(int(text))
            except ValueError:
                raise ValueError(f"In pool must be a whole number from 0 to {aircraft.MAX_POOL} (got {text!r}).")
        except ValueError as exc:
            messagebox.showerror("Invalid value", str(exc))
            return
        carrier = bool(self.aircraft_carrier_var.get())
        before = ({n: a.get(n) for n in values}, {n: a.get_date(n) for n in dates}, a.get_carrier(), a.pool)
        a.set_many(values)
        for name, value in dates.items():
            a.set_date(name, value)
        a.set_carrier(carrier)
        a.set_pool(pool)
        if before != (values, dates, carrier, pool):
            self.aircraft_edited.add(a.id)
            self.dirty = True
        self.refresh_aircraft_list()
        self.show_aircraft(a)

    # ---- ships ---------------------------------------------------------

    def _ship_row(self, x):
        return [aircraft.format_date(*x.date) if cid == "date" else get(x)
                for cid, _h, _w, _n, get in SHIP_COLUMNS]

    def _ship_sort_key(self, x):
        _cid, _h, _w, numeric, get = SHIP_COLUMN_BY_ID[self.ship_sort_col]
        v = get(x)
        return (v if numeric else str(v).lower(), x.id)

    def refresh_ship_list(self):
        selected = self.ship_current
        self.ship_tree.delete(*self.ship_tree.get_children())
        needle = self.ship_search_var.get().strip().lower()
        rows = [x for x in self.ships.values() if needle in x.name.lower()]
        rows.sort(key=self._ship_sort_key, reverse=self.ship_sort_reverse)
        for x in rows:
            tags = ("edited",) if x.id in self.ships_edited else ()
            self.ship_tree.insert("", "end", iid=str(x.id), values=self._ship_row(x), tags=tags)
        if selected is not None and self.ship_tree.exists(str(selected)):
            self.ship_tree.selection_set(str(selected))

    def sort_ships_by(self, col):
        self.ship_sort_reverse = (not self.ship_sort_reverse) if col == self.ship_sort_col else False
        self.ship_sort_col = col
        self.refresh_ship_list()

    def on_ship_select(self):
        sel = self.ship_tree.selection()
        self.show_ship(self.ships[int(sel[0])] if sel else None)

    def show_ship(self, x):
        previous = self.ship_current
        self.ship_current = x.id if x else None
        if x is None or x.id != previous:
            self.ship_slot = None
        if x is None:
            self.ship_title.set("(select a ship class)")
            for var in list(self.ship_vars.values()) + list(self.ship_info.values()):
                var.set("")
            self.show_ship_weapons(None)
            return
        self.ship_title.set(f"{x.name} (#{x.id}, {aircraft.format_date(*x.date)})")
        for f in ships.FIELDS:
            self.ship_vars[f.name].set(str(x.get(f.name)))
        self.ship_info["type"].set(x.type)
        self.ship_info["nation"].set(x.nation)
        self.ship_info["displacement"].set(str(x.displacement))
        self.ship_info["date"].set(aircraft.format_date(*x.date))
        self.show_ship_weapons(x)

    def show_ship_weapons(self, x):
        self.ship_weapon_tree.delete(*self.ship_weapon_tree.get_children())
        if x is not None:
            for slot, w in x.list_weapons():
                self.ship_weapon_tree.insert("", "end", iid=str(slot), values=(
                    w["name"], w["num"], ships.face_label(w["face"]), w["mount"], w["armor"], w["ammo"]))
        if x is not None and self.ship_slot is not None and self.ship_weapon_tree.exists(str(self.ship_slot)):
            self.ship_weapon_tree.selection_set(str(self.ship_slot))
        else:
            self.ship_slot = None
            self._fill_ship_weapon_edit(None)

    def _fill_ship_weapon_edit(self, w):
        for name, var in self.ship_weapon_vars.items():
            var.set("" if w is None else (ships.face_label(w[name]) if name == "face" else str(w[name])))

    def on_ship_weapon_select(self):
        sel = self.ship_weapon_tree.selection()
        if not sel or self.ship_current is None:
            return
        self.ship_slot = int(sel[0])
        self._fill_ship_weapon_edit(self.ships[self.ship_current].get_weapon(self.ship_slot))

    def apply_ship(self):
        if self.ship_current is None:
            return
        x = self.ships[self.ship_current]
        values = {}
        for f in ships.FIELDS:
            text = self.ship_vars[f.name].get().strip()
            try:
                values[f.name] = x.validate(f.name, int(text))
            except ValueError:
                messagebox.showerror("Invalid value",
                                     f"{f.label} must be a whole number from {f.min} to {f.max} (got {text!r}).")
                return
        before = {n: x.get(n) for n in values}
        x.set_many(values)
        if before != values:
            self.ships_edited.add(x.id)
            self.dirty = True
        self.refresh_ship_list()
        self.show_ship(x)

    def apply_ship_weapon(self):
        if self.ship_current is None or self.ship_slot is None:
            return
        x = self.ships[self.ship_current]
        values = {}
        try:
            for name, var in self.ship_weapon_vars.items():
                text = var.get().strip()
                if name == "face":
                    values[name] = ships.parse_face(text)
                else:
                    label = ships.WEAPON_FIELDS[name][0]
                    try:
                        values[name] = int(text)
                    except ValueError:
                        raise ValueError(f"{label} must be a whole number (got {text!r}).") from None
            x.check_weapon(self.ship_slot, **values)
        except ValueError as exc:
            messagebox.showerror("Invalid value", str(exc))
            return
        before = x.get_weapon(self.ship_slot)
        x.set_weapon(self.ship_slot, **values)
        if any(before[n] != v for n, v in values.items()):
            self.ships_edited.add(x.id)
            self.dirty = True
        self.refresh_ship_list()
        self.show_ship_weapons(x)

    # ---- ships in play -------------------------------------------------

    def _shiprec_sort_key(self, x):
        _cid, _h, _w, numeric, get = SHIPREC_COLUMN_BY_ID[self.shiprec_sort_col]
        v = get(x)
        return (v if numeric else str(v).lower(), x.id)

    def refresh_shiprec_list(self):
        selected = self.shiprec_current
        self.shiprec_tree.delete(*self.shiprec_tree.get_children())
        needle = self.shiprec_search_var.get().strip().lower()
        side = self.shiprec_side_var.get()
        rows = [x for x in self.shiprecs.values()
                if needle in x.name.lower() and (side == "All" or x.side == side)]
        rows.sort(key=self._shiprec_sort_key, reverse=self.shiprec_sort_reverse)
        for x in rows:
            tags = ("edited",) if x.id in self.shiprecs_edited else ()
            self.shiprec_tree.insert("", "end", iid=str(x.id), values=[get(x) for *_, get in SHIPREC_COLUMNS],
                                     tags=tags)
        if selected is not None and self.shiprec_tree.exists(str(selected)):
            self.shiprec_tree.selection_set(str(selected))

    def sort_shiprecs_by(self, col):
        self.shiprec_sort_reverse = (not self.shiprec_sort_reverse) if col == self.shiprec_sort_col else False
        self.shiprec_sort_col = col
        self.refresh_shiprec_list()

    def on_shiprec_select(self):
        sel = self.shiprec_tree.selection()
        self.show_shiprec(self.shiprecs[int(sel[0])] if sel else None)

    def show_shiprec(self, x):
        previous = self.shiprec_current
        self.shiprec_current = x.id if x else None
        if x is None or x.id != previous:
            self.shiprec_slot = None
        if x is None:
            self.shiprec_title.set("(select a ship)")
            for var in list(self.shiprec_vars.values()) + list(self.shiprec_info.values()):
                var.set("")
            self.show_shiprec_move(None)
            self.show_shiprec_weapons(None)
            return
        self.shiprec_title.set(f"{x.name} (#{x.id})")
        for f in shiprecords.FIELDS:
            self.shiprec_vars[f.name].set(str(x.get(f.name)))
        self.shiprec_info["class"].set(f"{x.class_name} ({x.type}, #{x.class_id})")
        self.shiprec_info["nation"].set(f"{x.nation} ({x.side})")
        self.shiprec_info["base"].set(x.base_name or "at sea")
        self.shiprec_info["tf"].set(self._shiprec_tf_text(x))
        self.shiprec_info["arrival"].set(str(x.days_to_arrival) if x.days_to_arrival else "arrived")
        self.show_shiprec_move(x)
        self.show_shiprec_weapons(x)

    def _shiprec_tf_text(self, x):
        if not x.task_force:
            return "none"
        try:
            tf = taskforces.TaskForce(self.save, x.task_force)
        except ValueError:
            return str(x.task_force)
        flag = self.shiprecs.get(tf.flagship)
        text = " ".join(p for p in (str(tf.id), tf.name) if p)
        return f"{text} (flagship {flag.name})" if flag else text

    def show_shiprec_move(self, x):
        self.shiprec_destinations = taskforces.destinations(self.save, x.id) if x else []
        box = self.shiprec_move_box
        box.configure(values=[d.label for d in self.shiprec_destinations])
        self.shiprec_move_var.set("")
        if self.shiprec_destinations:
            box.configure(state="readonly")
            box.current(0)
            self.shiprec_move_button.state(["!disabled"])
            self.shiprec_move_note.set("")
        else:
            box.configure(state="disabled")
            self.shiprec_move_button.state(["disabled"])
            self.shiprec_move_note.set("no valid destination" if x else "")

    def move_shiprec(self):
        if self.shiprec_current is None or not self.shiprec_destinations:
            return
        index = self.shiprec_move_box.current()
        if index < 0:
            return
        x = self.shiprecs[self.shiprec_current]
        old_tf, dest = x.task_force, self.shiprec_destinations[index].id
        try:
            taskforces.move_ship(self.save, x.id, dest)
        except ValueError as exc:
            messagebox.showerror("Cannot move ship", str(exc))
            return
        # Redraws both tabs: the move changes ship counts (and maybe the flagship) of both TFs.
        self._tf_edited([old_tf, dest], [x.id])
        self.show_shiprec(x)

    def show_shiprec_weapons(self, x):
        tree = self.shiprec_weapon_tree
        tree.delete(*tree.get_children())
        if x is not None:
            for slot, w in x.list_weapons():
                tree.insert("", "end", iid=str(slot), values=(
                    w["name"], w["num"], ships.face_label(w["face"]), w["mount"], w["armor"], w["ammo"]))
        if x is not None and self.shiprec_slot is not None and tree.exists(str(self.shiprec_slot)):
            tree.selection_set(str(self.shiprec_slot))
        else:
            self.shiprec_slot = None
            self._fill_shiprec_weapon_edit(None)

    def _fill_shiprec_weapon_edit(self, w):
        for name, var in self.shiprec_weapon_vars.items():
            var.set("" if w is None else str(w[name]))

    def on_shiprec_weapon_select(self):
        sel = self.shiprec_weapon_tree.selection()
        if not sel or self.shiprec_current is None:
            return
        self.shiprec_slot = int(sel[0])
        self._fill_shiprec_weapon_edit(self.shiprecs[self.shiprec_current].get_weapon(self.shiprec_slot))

    def apply_shiprec(self):
        if self.shiprec_current is None:
            return
        x = self.shiprecs[self.shiprec_current]
        values = self._read_entries(x, shiprecords.FIELDS, self.shiprec_vars)
        if values is None:
            return
        before = {n: x.get(n) for n in values}
        try:
            x.set_many(values)
        except ValueError as exc:
            messagebox.showerror("Invalid value", str(exc))
            return
        if before != values:
            self.shiprecs_edited.add(x.id)
            self.dirty = True
        self.refresh_shiprec_list()
        self.show_shiprec(x)
        self._refresh_tf_of(x)

    def repair_shiprec(self):
        if self.shiprec_current is None:
            return
        x = self.shiprecs[self.shiprec_current]
        if any(x.get(n) for n in shiprecords.DAMAGE_FIELDS):
            x.repair_all()
            self.shiprecs_edited.add(x.id)
            self.dirty = True
        self.refresh_shiprec_list()
        self.show_shiprec(x)
        self._refresh_tf_of(x)

    def _refresh_tf_of(self, x):
        """Redraw the Task Forces detail when it shows the ship's TF (its fuel/damage grid)."""
        if self.tf_current is not None and x.task_force == self.tf_current:
            self.show_tf(self.taskforces[self.tf_current])

    def apply_shiprec_weapon(self):
        if self.shiprec_current is None or self.shiprec_slot is None:
            return
        x = self.shiprecs[self.shiprec_current]
        values = {}
        try:
            for name, var in self.shiprec_weapon_vars.items():
                text = var.get().strip()
                try:
                    values[name] = int(text)
                except ValueError:
                    raise ValueError(f"{shiprecords.WEAPON_FIELDS[name][0]} must be a whole number "
                                     f"(got {text!r}).") from None
            x.check_weapon(self.shiprec_slot, **values)
        except ValueError as exc:
            messagebox.showerror("Invalid value", str(exc))
            return
        before = x.get_weapon(self.shiprec_slot)
        x.set_weapon(self.shiprec_slot, **values)
        if any(before[n] != v for n, v in values.items()):
            self.shiprecs_edited.add(x.id)
            self.dirty = True
        self.refresh_shiprec_list()
        self.show_shiprec_weapons(x)

    # ---- task forces ---------------------------------------------------

    @staticmethod
    def _load_task_forces(save):
        """Task forces with ships and a readable chain; a damaged chain only hides its own TF."""
        out = []
        for i in range(taskforces.TF_BASE_ID, bases.RECORD_COUNT):
            if not taskforces.is_task_force(save, i):
                continue
            tf = taskforces.TaskForce(save, i)
            if tf.ship_count:
                try:
                    tf.ships
                except ValueError:
                    continue
                out.append(tf)
        return out

    def _tf_location(self, tf):
        places = self.places_by_hex.get(tf.hex)
        if places:
            return f"{places[0].name} (in port)"
        return "at sea {},{}".format(*tf.hex)

    def _place_name(self, place_id):
        place = self.places_by_id.get(place_id)
        return place.name if place else ("-" if not place_id else str(place_id))

    def _tf_row(self, tf):
        flag = self.shiprecs.get(tf.flagship)
        return {"id": tf.id, "name": tf.name, "side": tf.side, "location": self._tf_location(tf),
                "mission": tf.mission_label, "destination": self._place_name(tf.destination),
                "ships": tf.ship_count, "flagship": flag.name if flag else ""}

    def _tf_sort_key(self, row):
        _cid, _h, _w, numeric, get = TF_COLUMN_BY_ID[self.tf_sort_col]
        v = get(row)
        return (v if numeric else str(v).lower(), row["id"])

    def refresh_tf_list(self):
        selected = self.tf_current
        self.tf_tree.delete(*self.tf_tree.get_children())
        needle = self.tf_search_var.get().strip().lower()
        side = self.tf_side_var.get()
        rows = []
        for tf in self.taskforces.values():
            try:
                row = self._tf_row(tf)
            except ValueError:
                continue
            if needle in row["name"].lower() and (side == "All" or row["side"] == side):
                rows.append(row)
        rows.sort(key=self._tf_sort_key, reverse=self.tf_sort_reverse)
        for row in rows:
            tags = ("edited",) if row["id"] in self.tfs_edited else ()
            self.tf_tree.insert("", "end", iid=str(row["id"]), values=[get(row) for *_, get in TF_COLUMNS],
                                tags=tags)
        if selected is not None and self.tf_tree.exists(str(selected)):
            self.tf_tree.selection_set(str(selected))

    def sort_tfs_by(self, col):
        self.tf_sort_reverse = (not self.tf_sort_reverse) if col == self.tf_sort_col else False
        self.tf_sort_col = col
        self.refresh_tf_list()

    def on_tf_select(self):
        sel = self.tf_tree.selection()
        self.show_tf(self.taskforces[int(sel[0])] if sel else None)

    def show_tf(self, tf):
        previous = self.tf_current
        self.tf_current = tf.id if tf else None
        if tf is None or tf.id != previous:
            self.tf_ship_current = None
        tree = self.tf_ship_tree
        tree.delete(*tree.get_children())
        self.tf_flag_ships = []
        self.tf_flag_box.configure(values=[])
        self.tf_flag_var.set("")
        if tf is None:
            self.tf_title.set("(select a task force)")
            for var in self.tf_info.values():
                var.set("")
            self.show_tf_move(None)
            self.show_tf_add(None)
            self.show_tf_orders(None)
            return
        self.tf_title.set(f"{tf.name} (TF {tf.id})")
        self.tf_info["hex"].set("{},{}".format(*tf.hex))
        self.tf_info["location"].set(self._tf_location(tf))
        self.tf_info["side"].set(tf.side)
        flagship = tf.flagship
        ship_ids = tf.ships
        for sid in ship_ids:
            x = self.shiprecs[sid]
            top = x.max_fuel
            tree.insert("", "end", iid=str(sid), values=(
                "*" if sid == flagship else "", x.name, x.type, x.class_name,
                f"{x.get('fuel')}/{top if top is not None else '?'}", x.get("sys_dmg"), x.get("float_dmg"),
                x.get("eng_dmg"), x.get("fires")))
        if self.tf_ship_current in ship_ids:
            tree.selection_set(str(self.tf_ship_current))
        else:
            self.tf_ship_current = None
        self.tf_flag_ships = ship_ids
        self.tf_flag_box.configure(values=[f"{self.shiprecs[s].name} ({s})" for s in ship_ids])
        if flagship in ship_ids:
            self.tf_flag_box.current(ship_ids.index(flagship))
        self.show_tf_move(self.tf_ship_current)
        self.show_tf_add(tf)
        self.show_tf_orders(tf)

    def show_tf_orders(self, tf):
        """Fill the Orders box: current values and the home port list for the TF's side."""
        self.tf_home_shown = []
        if tf is None:
            for name in ("mission", "home_port", "destination"):
                self.tf_info[name].set("")
            self.tf_mission_var.set("")
            self.tf_home_box.configure(values=[])
            self.tf_home_var.set("")
        else:
            self.tf_info["mission"].set(f"{tf.mission:02d} - {tf.mission_label}")
            home = tf.home_port
            self.tf_info["home_port"].set(f"{self._place_name(home)} ({home})" if home else "-")
            dest = tf.destination
            self.tf_info["destination"].set(f"{self._place_name(dest)} ({dest})" if dest else "-")
            self.tf_mission_var.set(f"{tf.mission:02d} - {taskforces.MISSIONS[tf.mission]}"
                                    if tf.mission in taskforces.MISSIONS else "")
            side = tf.side
            self.tf_home_shown = [p for p, _label in self.tf_port_items if bases.SIDES.get(p.side_id) == side]
            labels = {p.id: label for p, label in self.tf_port_items}
            self.tf_home_box.configure(values=[labels[p.id] for p in self.tf_home_shown])
            self.tf_home_var.set("")
        self.show_tf_destinations()

    def show_tf_destinations(self):
        """Destination choices: every base and town whose label contains the filter text."""
        needle = self.tf_dest_filter_var.get().strip().lower()
        items = [(p, label) for p, label in self.tf_dest_items if needle in label.lower()]
        self.tf_dest_shown = [p for p, _label in items]
        self.tf_dest_box.configure(values=[label for _p, label in items])
        self.tf_dest_var.set("")

    def on_tf_ship_select(self):
        sel = self.tf_ship_tree.selection()
        self.tf_ship_current = int(sel[0]) if sel else None
        self.show_tf_move(self.tf_ship_current)

    def show_tf_move(self, ship_id):
        self.tf_destinations = taskforces.destinations(self.save, ship_id) if ship_id is not None else []
        box = self.tf_move_box
        box.configure(values=[d.label for d in self.tf_destinations])
        self.tf_move_var.set("")
        if self.tf_destinations:
            box.configure(state="readonly")
            box.current(0)
            self.tf_move_button.state(["!disabled"])
            self.tf_move_note.set("")
        else:
            box.configure(state="disabled")
            self.tf_move_button.state(["disabled"])
            self.tf_move_note.set("no valid destination" if ship_id is not None else "select a ship")

    def show_tf_add(self, tf):
        """Ships docked in the TF's port hex that may join it."""
        self.tf_add_ships = []
        if tf is not None:
            for place in self.places_by_hex.get(tf.hex, []):
                try:
                    docked = taskforces.chain(self.save, place.id)
                except ValueError:
                    continue
                self.tf_add_ships += [s for s in docked if taskforces.can_move(self.save, s, tf.id)]
        box = self.tf_add_box
        box.configure(values=[f"{self.shiprecs[s].name} ({s})" for s in self.tf_add_ships])
        self.tf_add_var.set("")
        if self.tf_add_ships:
            box.configure(state="readonly")
            box.current(0)
            self.tf_add_button.state(["!disabled"])
            self.tf_add_note.set("")
        else:
            box.configure(state="disabled")
            self.tf_add_button.state(["disabled"])
            self.tf_add_note.set("" if tf is None else
                                 "no ship in port can join" if self.places_by_hex.get(tf.hex) else "not in a port")

    def _tf_edited(self, tf_ids, ship_ids):
        """Mark rows edited, then redraw this tab and the Ships tab."""
        self.tfs_edited.update(i for i in tf_ids if i in self.taskforces)
        self.shiprecs_edited.update(ship_ids)
        self.dirty = True
        self.refresh_tf_list()
        self.refresh_shiprec_list()
        if self.shiprec_current in ship_ids:
            self.show_shiprec(self.shiprecs[self.shiprec_current])
        self.show_tf(self.taskforces[self.tf_current] if self.tf_current is not None else None)

    def set_tf_flagship(self):
        if self.tf_current is None:
            return
        index = self.tf_flag_box.current()
        if index < 0:
            return
        tf = self.taskforces[self.tf_current]
        before = tf.flagship
        try:
            taskforces.set_flagship(self.save, tf.id, self.tf_flag_ships[index])
        except ValueError as exc:
            messagebox.showerror("Cannot set flagship", str(exc))
            return
        if tf.flagship != before:
            self._tf_edited([tf.id], [])

    def _apply_tf_order(self, action, value, title):
        if self.tf_current is None or value is None:
            return
        tf = self.taskforces[self.tf_current]
        before = (tf.mission, tf.home_port, tf.destination)
        try:
            action(self.save, tf.id, value)
        except ValueError as exc:
            messagebox.showerror(title, str(exc))
            return
        if (tf.mission, tf.home_port, tf.destination) != before:
            self._tf_edited([tf.id], [])

    def set_tf_mission(self):
        text = self.tf_mission_var.get()
        code = int(text.split(" - ", 1)[0]) if " - " in text else None
        self._apply_tf_order(taskforces.set_mission, code, "Cannot set mission")

    def set_tf_home_port(self):
        index = self.tf_home_box.current()
        place = self.tf_home_shown[index] if index >= 0 else None
        self._apply_tf_order(taskforces.set_home_port, place.id if place else None, "Cannot set home port")

    def set_tf_destination(self):
        index = self.tf_dest_box.current()
        place = self.tf_dest_shown[index] if index >= 0 else None
        self._apply_tf_order(taskforces.set_destination, place.id if place else None, "Cannot set destination")

    def _move_ship_to(self, ship_id, dest_id):
        tf_ids = [i for i in (self.shiprecs[ship_id].task_force, dest_id) if i >= taskforces.TF_BASE_ID]
        try:
            taskforces.move_ship(self.save, ship_id, dest_id)
        except ValueError as exc:
            messagebox.showerror("Cannot move ship", str(exc))
            return
        self._tf_edited(tf_ids, [ship_id])

    def move_tf_ship(self):
        if self.tf_ship_current is None or not self.tf_destinations:
            return
        index = self.tf_move_box.current()
        if index >= 0:
            self._move_ship_to(self.tf_ship_current, self.tf_destinations[index].id)

    def add_tf_ship(self):
        if self.tf_current is None or not self.tf_add_ships:
            return
        index = self.tf_add_box.current()
        if index >= 0:
            self._move_ship_to(self.tf_add_ships[index], self.tf_current)

    def _tf_quick(self, action, title):
        if self.tf_current is None:
            return
        try:
            changed = action(self.save, self.tf_current)
        except ValueError as exc:
            messagebox.showerror(title, str(exc))
            return
        if changed:
            self._tf_edited([self.tf_current], changed)

    def repair_tf(self):
        self._tf_quick(taskforces.repair_task_force, "Cannot repair ships")

    def refuel_tf(self):
        self._tf_quick(taskforces.refuel_task_force, "Cannot refuel ships")

    # ---- air groups ----------------------------------------------------

    def _group_sort_key(self, g):
        _cid, _h, _w, numeric, get = GROUP_COLUMN_BY_ID[self.group_sort_col]
        v = get(g)
        return (v if numeric else str(v).lower(), g.id)

    def refresh_group_list(self):
        selected = self.group_current
        self.group_tree.delete(*self.group_tree.get_children())
        needle = self.group_search_var.get().strip().lower()
        side = self.group_side_var.get()
        rows = [g for g in self.groups.values()
                if needle in g.name.lower() and (side == "All" or g.side == side)]
        rows.sort(key=self._group_sort_key, reverse=self.group_sort_reverse)
        for g in rows:
            tags = ("edited",) if g.id in self.groups_edited else ()
            self.group_tree.insert("", "end", iid=str(g.id), values=[get(g) for *_, get in GROUP_COLUMNS],
                                   tags=tags)
        if selected is not None and self.group_tree.exists(str(selected)):
            self.group_tree.selection_set(str(selected))

    def sort_groups_by(self, col):
        self.group_sort_reverse = (not self.group_sort_reverse) if col == self.group_sort_col else False
        self.group_sort_col = col
        self.refresh_group_list()

    def on_group_select(self):
        sel = self.group_tree.selection()
        self.show_group(self.groups[int(sel[0])] if sel else None)

    def show_group(self, g):
        previous = self.group_current
        self.group_current = g.id if g else None
        if g is None or g.id != previous:
            self.pilot_current = None
        if g is None:
            self.group_title.set("(select an air group)")
            for var in list(self.group_vars.values()) + list(self.group_info.values()):
                var.set("")
            self._show_move(None, self.group_move_var, self.group_move_box, self.group_move_button,
                            self.group_move_note)
            self._show_aircraft_choice(None)
            self._show_planes(None)
            self._show_schedule(None)
            self.show_pilots(None)
            self.show_leader(None)
            return
        self.group_title.set(f"{g.name} (#{g.id})")
        for f in airgroups.GROUP_FIELDS:
            value = g.get(f.name)
            self.group_vars[f.name].set(airgroups.format_day_date(value) if f.name in airgroups.DATE_FIELDS
                                        else str(value))
        leader = airgroups.get_leader(self.save, g.leader_id)
        self.group_info["aircraft"].set(f"{g.aircraft_id} {g.aircraft_name}")
        self.group_info["upgrade"].set(f"{g.upgrade_id} {g.upgrade_name}")
        self.group_info["planes"].set(str(g.planes))
        self.group_info["pilots"].set(str(g.pilot_count))
        self.group_info["leader"].set(f"{g.leader_id} {leader.name}" if leader else str(g.leader_id))
        self.group_info["formation"].set(g.formation_label)
        self.group_info["parent"].set(g.related_label(g.parent_id))
        self.group_info["return_as"].set(g.related_label(g.return_as_id))
        self.group_info["location"].set(f"{g.location_id} {g.location_name}")
        self._show_move(g, self.group_move_var, self.group_move_box, self.group_move_button, self.group_move_note)
        self._show_aircraft_choice(g)
        self._show_planes(g)
        self._show_schedule(g)
        self.show_pilots(g)
        self.show_leader(leader)

    def _show_schedule(self, g):
        entries = g.size_schedule() if g is not None else [None] * airgroups.SCHEDULE_COUNT
        for (date_var, size_var), entry in zip(self.schedule_vars, entries):
            date_var.set("" if entry is None or entry[0] == 0 else airgroups.format_month_date(entry[0]))
            size_var.set("" if entry is None or entry[0] == 0 else str(entry[1]))

    def apply_schedule(self):
        if self.group_current is None:
            return
        g = self.groups[self.group_current]
        entries = []
        for k, (date_var, size_var) in enumerate(self.schedule_vars, 1):
            try:
                date = airgroups.parse_month_date(date_var.get())
            except ValueError as exc:
                messagebox.showerror("Invalid value", f"Size change {k}: {exc}")
                return
            text = size_var.get().strip()
            try:
                size = int(text) if text not in ("", "-") else 0
            except ValueError:
                messagebox.showerror("Invalid value", f"Size change {k}: size must be a whole number (got {text!r}).")
                return
            entries.append((date, size))
        before = g.size_schedule()
        try:
            g.set_size_schedule(entries)
        except ValueError as exc:
            messagebox.showerror("Cannot change size changes", str(exc))
            return
        if before != entries:
            self.groups_edited.add(g.id)
            self.dirty = True
        self.refresh_group_list()
        self.show_group(g)

    def _show_planes(self, g):
        counts = {} if g is None else {"ready": g.ready, "maintenance": g.maintenance,
                                       "damaged": g.damaged, "reserve": g.reserve}
        for name, var in self.plane_vars.items():
            var.set(str(counts[name]) if g is not None else "")
        self.plane_total.set(str(g.planes) if g is not None else "")
        state = "normal" if g is not None and g.arrived else "disabled"
        for entry in self.plane_entries:
            entry.configure(state=state)
        for button in (self.plane_apply_button, self.plane_repair_button):
            button.state(["disabled"] if state == "disabled" else ["!disabled"])
        self.plane_note.set("not arrived" if g is not None and not g.arrived else "")

    def apply_planes(self):
        if self.group_current is None:
            return
        g = self.groups[self.group_current]
        counts = []
        for name in ("ready", "maintenance", "damaged", "reserve"):
            text = self.plane_vars[name].get().strip()
            try:
                counts.append(int(text))
            except ValueError:
                messagebox.showerror("Invalid value", f"{name.capitalize()} must be a whole number (got {text!r}).")
                return
        self._change_planes(g, lambda: g.set_plane_status(*counts))

    def repair_planes(self):
        if self.group_current is None:
            return
        g = self.groups[self.group_current]
        self._change_planes(g, g.repair_all)

    def _change_planes(self, g, change):
        before = (g.ready, g.maintenance, g.damaged, g.reserve)
        try:
            change()
        except ValueError as exc:
            messagebox.showerror("Cannot change planes", str(exc))
            return
        if before != (g.ready, g.maintenance, g.damaged, g.reserve):
            self.groups_edited.add(g.id)
            self.dirty = True
        self.refresh_group_list()
        self.show_group(g)

    def _show_aircraft_choice(self, g):
        for var, box, button in ((self.group_aircraft_var, self.group_aircraft_box, self.group_aircraft_button),
                                 (self.group_upgrade_var, self.group_upgrade_box, self.group_upgrade_button)):
            var.set("")
            if g is None:
                box.configure(values=[], state="disabled")
                button.state(["disabled"])
            else:
                box.configure(values=self.aircraft_labels.get(g.side, []), state="readonly")
                button.state(["!disabled"])

    def change_group_aircraft(self):
        self._change_group_model(self.group_aircraft_var, airgroups.AirGroup.set_aircraft, "Cannot change aircraft")

    def change_group_upgrade(self):
        self._change_group_model(self.group_upgrade_var, airgroups.AirGroup.set_upgrade, "Cannot set upgrade")

    def _change_group_model(self, var, setter, title):
        if self.group_current is None:
            messagebox.showerror(title, "Select an air group first.")
            return
        g = self.groups[self.group_current]
        aircraft_id = self.aircraft_ids.get(var.get())
        if aircraft_id is None:
            messagebox.showerror(title, "Choose an aircraft first.")
            return
        try:
            setter(g, aircraft_id)
        except ValueError as exc:
            messagebox.showerror(title, str(exc))
            return
        self.groups_edited.add(g.id)
        self.dirty = True
        self.refresh_group_list()
        self.show_group(g)

    def move_group(self):
        if self.group_current is None:
            return
        g = self.groups[self.group_current]
        dest = self.place_ids.get(self.group_move_var.get())
        if dest is None:
            messagebox.showerror("Cannot move", "Choose a destination first.")
            return
        self._move(g, dest, self.groups_edited, self.refresh_group_list, self.show_group)

    def _move(self, record, dest, edited, refresh, show):
        try:
            changed = dest != record.location_id
            record.move_to(dest)
        except ValueError as exc:
            messagebox.showerror("Cannot move", str(exc))
            return
        if changed:
            edited.add(record.id)
            self.dirty = True
        refresh()
        show(record)

    def apply_group(self):
        if self.group_current is None:
            return
        g = self.groups[self.group_current]
        values = {}
        for f in airgroups.GROUP_FIELDS:
            text = self.group_vars[f.name].get().strip()
            if f.name in airgroups.DATE_FIELDS:
                try:
                    values[f.name] = g.validate(f.name, airgroups.parse_day_date(text))
                except ValueError as exc:
                    messagebox.showerror("Invalid value", f"{f.label}: {exc}")
                    return
                continue
            try:
                values[f.name] = g.validate(f.name, int(text))
            except ValueError:
                messagebox.showerror("Invalid value",
                                     f"{f.label} must be a whole number from {f.min} to {f.max} (got {text!r}).")
                return
        before = {n: g.get(n) for n in values}
        g.set_many(values)
        if before != values:
            self.groups_edited.add(g.id)
            self.dirty = True
        self.refresh_group_list()
        self.show_group(g)

    def _read_entries(self, record, fields, vars_):
        """Checked values from a row of entries, or None after showing the error."""
        values = {}
        for f in fields:
            text = vars_[f.name].get().strip()
            try:
                values[f.name] = record.validate(f.name, int(text))
            except ValueError:
                messagebox.showerror("Invalid value",
                                     f"{f.label} must be a whole number from {f.min} to {f.max} (got {text!r}).")
                return None
        return values

    def show_pilots(self, g):
        self.pilot_tree.delete(*self.pilot_tree.get_children())
        if g is not None:
            for p in self.pilot_index.get(g.id, []):
                self.pilot_tree.insert("", "end", iid=str(p.id), values=[p.id, p.name, p.status_label] + [
                    p.get(f.name) for f in airgroups.PILOT_FIELDS])
        if g is not None and self.pilot_current is not None and self.pilot_tree.exists(str(self.pilot_current)):
            self.pilot_tree.selection_set(str(self.pilot_current))
        else:
            self.pilot_current = None
            for var in self.pilot_vars.values():
                var.set("")

    def _selected_pilot(self):
        if self.group_current is None or self.pilot_current is None:
            return None
        return next((p for p in self.pilot_index.get(self.group_current, []) if p.id == self.pilot_current), None)

    def on_pilot_select(self):
        sel = self.pilot_tree.selection()
        if not sel or self.group_current is None:
            return
        self.pilot_current = int(sel[0])
        pilot = self._selected_pilot()
        for f in airgroups.PILOT_FIELDS:
            self.pilot_vars[f.name].set(str(pilot.get(f.name)))

    def apply_pilot(self):
        pilot = self._selected_pilot()
        if pilot is None:
            return
        values = self._read_entries(pilot, airgroups.PILOT_FIELDS, self.pilot_vars)
        if values is None:
            return
        before = {n: pilot.get(n) for n in values}
        pilot.set_many(values)
        if before != values:
            self.groups_edited.add(self.group_current)
            self.dirty = True
        self.refresh_group_list()
        self.show_pilots(self.groups[self.group_current])

    def show_leader(self, leader):
        self.leader_current = leader
        state = "!disabled" if leader else "disabled"
        for widget in self.leader_entries + [self.leader_button]:
            widget.state([state])
        self.leader_name.set(leader.name if leader else "(none)")
        self.leader_age.set(str(leader.age) if leader else "")
        for f in airgroups.LEADER_FIELDS:
            self.leader_vars[f.name].set(str(leader.get(f.name)) if leader else "")

    def apply_leader(self):
        leader = self.leader_current
        if leader is None or self.group_current is None:
            return
        values = self._read_entries(leader, airgroups.LEADER_FIELDS, self.leader_vars)
        if values is None:
            return
        before = {n: leader.get(n) for n in values}
        leader.set_many(values)
        if before != values:
            self.groups_edited.add(self.group_current)
            self.dirty = True
        self.refresh_group_list()
        self.show_leader(leader)

    # ---- land units ----------------------------------------------------

    def _unit_sort_key(self, u):
        _cid, _h, _w, numeric, get = UNIT_COLUMN_BY_ID[self.unit_sort_col]
        v = get(u)
        return (v if numeric else str(v).lower(), u.id)

    def refresh_unit_list(self):
        selected = self.unit_current
        self.unit_tree.delete(*self.unit_tree.get_children())
        needle = self.unit_search_var.get().strip().lower()
        side = self.unit_side_var.get()
        rows = [u for u in self.units.values()
                if needle in u.display_name.lower() and (side == "All" or u.side == side)]
        rows.sort(key=self._unit_sort_key, reverse=self.unit_sort_reverse)
        for u in rows:
            tags = ("edited",) if u.id in self.units_edited else ()
            self.unit_tree.insert("", "end", iid=str(u.id), values=[get(u) for *_, get in UNIT_COLUMNS],
                                  tags=tags)
        if selected is not None and self.unit_tree.exists(str(selected)):
            self.unit_tree.selection_set(str(selected))

    def sort_units_by(self, col):
        self.unit_sort_reverse = (not self.unit_sort_reverse) if col == self.unit_sort_col else False
        self.unit_sort_col = col
        self.refresh_unit_list()

    def on_unit_select(self):
        sel = self.unit_tree.selection()
        self.show_unit(self.units[int(sel[0])] if sel else None)

    def show_unit(self, u):
        previous = self.unit_current
        self.unit_current = u.id if u else None
        if u is None or u.id != previous:
            self.unit_slot = None
        if u is None:
            self.unit_title.set("(select a land unit)")
            for var in list(self.unit_vars.values()) + list(self.unit_info.values()):
                var.set("")
            self._show_move(None, self.unit_move_var, self.unit_move_box, self.unit_move_button, self.unit_move_note)
            self.show_unit_equipment(None)
            self._show_add_equipment(None)
            return
        self.unit_title.set(f"{u.display_name} (#{u.id}, {u.type}, class {u.class_id}, {u.side})")
        for f in landunits.FIELDS:
            self.unit_vars[f.name].set(str(u.get(f.name)))
        self.unit_info["hq"].set(f"{u.hq_id} {u.hq_name}")
        self.unit_info["location"].set(f"{u.location_id} {u.location_name}")
        self.unit_info["target"].set(f"{u.target_id} {u.target_name}")
        self.unit_info["required"].set(str(u.supplies_required))
        self.unit_info["support"].set(str(u.support))
        self.unit_info["support_required"].set(str(u.support_required))
        self._show_move(u, self.unit_move_var, self.unit_move_box, self.unit_move_button, self.unit_move_note)
        self.show_unit_equipment(u)
        self._show_add_equipment(u)

    def move_unit(self):
        if self.unit_current is None:
            return
        u = self.units[self.unit_current]
        dest = self.place_ids.get(self.unit_move_var.get())
        if dest is None:
            messagebox.showerror("Cannot move", "Choose a destination first.")
            return
        self._move(u, dest, self.units_edited, self.refresh_unit_list, self.show_unit)

    def show_unit_equipment(self, u):
        self.unit_equipment_tree.delete(*self.unit_equipment_tree.get_children())
        if u is not None:
            for slot, e in u.list_equipment():
                self.unit_equipment_tree.insert("", "end", iid=str(slot), values=(
                    slot, e["device"], e["count"], e["disabled"], e["toe_device"], e["toe_count"]))
        if u is not None and self.unit_slot is not None and self.unit_equipment_tree.exists(str(self.unit_slot)):
            self.unit_equipment_tree.selection_set(str(self.unit_slot))
        else:
            self.unit_slot = None
            for var in self.unit_equipment_vars.values():
                var.set("")

    def _show_add_equipment(self, u):
        """Offer the unit's side's devices in the Add box; disabled when no unit is selected."""
        self.unit_add_device_var.set("")
        if u is None:
            self.unit_add_box.configure(values=[], state="disabled")
            self.unit_add_button.state(["disabled"])
        else:
            self.unit_add_box.configure(values=self.device_labels.get(u.side, []), state="readonly")
            self.unit_add_button.state(["!disabled"])

    def on_unit_equipment_select(self):
        sel = self.unit_equipment_tree.selection()
        if not sel or self.unit_current is None:
            return
        self.unit_slot = int(sel[0])
        e = self.units[self.unit_current].get_equipment(self.unit_slot)
        self.unit_equipment_vars["count"].set(str(e["count"]))
        self.unit_equipment_vars["disabled"].set(str(e["disabled"]))

    def apply_unit(self):
        if self.unit_current is None:
            return
        u = self.units[self.unit_current]
        values = {}
        for f in landunits.FIELDS:
            text = self.unit_vars[f.name].get().strip()
            try:
                values[f.name] = u.validate(f.name, int(text))
            except ValueError:
                messagebox.showerror("Invalid value",
                                     f"{f.label} must be a whole number from {f.min} to {f.max} (got {text!r}).")
                return
        before = {n: u.get(n) for n in values}
        u.set_many(values)
        if before != values:
            self.units_edited.add(u.id)
            self.dirty = True
        self.refresh_unit_list()
        self.show_unit(u)

    def apply_unit_equipment(self):
        if self.unit_current is None or self.unit_slot is None:
            return
        u = self.units[self.unit_current]
        try:
            count = int(self.unit_equipment_vars["count"].get().strip())
            disabled = int(self.unit_equipment_vars["disabled"].get().strip())
        except ValueError:
            messagebox.showerror("Invalid value", "Count and disabled must be whole numbers.")
            return
        before = u.get_equipment(self.unit_slot)
        try:
            u.set_equipment(self.unit_slot, count, disabled)
        except ValueError as exc:
            messagebox.showerror("Invalid value", str(exc))
            return
        if (before["count"], before["disabled"]) != (count, disabled):
            self.units_edited.add(u.id)
            self.dirty = True
        self.refresh_unit_list()
        self.show_unit_equipment(u)

    def add_unit_equipment(self):
        if self.unit_current is None:
            return
        u = self.units[self.unit_current]
        device_id = self.device_ids.get(self.unit_add_device_var.get())
        if device_id is None:
            messagebox.showerror("Cannot add equipment", "Choose a device first.")
            return
        try:
            count = int(self.unit_add_vars["count"].get().strip())
            disabled = int(self.unit_add_vars["disabled"].get().strip())
        except ValueError:
            messagebox.showerror("Invalid value", "Count and disabled must be whole numbers.")
            return
        allowed = {self.device_ids[label] for label in self.device_labels.get(u.side, [])}
        try:
            slot = u.add_equipment(device_id, count, disabled, allowed)
        except ValueError as exc:
            messagebox.showerror("Cannot add equipment", str(exc))
            return
        self.units_edited.add(u.id)
        self.dirty = True
        self.unit_add_vars["count"].set("")
        self.unit_add_vars["disabled"].set("0")
        self.unit_add_device_var.set("")
        self.refresh_unit_list()
        self.unit_slot = slot
        self.show_unit_equipment(u)
        self.unit_equipment_vars["count"].set(str(count))
        self.unit_equipment_vars["disabled"].set(str(disabled))

    # ---- reports -------------------------------------------------------

    def _reports_shown(self):
        # Edits in the Bases tab change the spoilage list, so rebuild when the reports are opened.
        if self.notebook.select() == str(self.reports_tab):
            self.refresh_reports()

    def refresh_reports(self):
        if self.save is None:
            return
        try:
            day, month, year = reports.game_date(self.save)
            self.game_date_var.set(f"Game date: {day} {MONTH_NAMES[month - 1]} {year}")
            self.upgrades_all = reports.upgrade_rows(self.save, self.shiprecs.values(), self.ships)
        except (SaveFormatError, IndexError):
            self.game_date_var.set("Game date: unknown")
            self.upgrades_all = []
        self.spoilage_all = reports.spoilage_rows(self.bases.values())
        self.refresh_spoilage_list()
        self.refresh_upgrade_list()
        self.refresh_industry_report()
        self.refresh_factory_report()
        self.refresh_raw_list()

    @staticmethod
    def _report_values(columns, texts, row):
        return [texts[cid](get(row)) if cid in texts else get(row) for cid, _h, _w, _n, get in columns]

    def _spoilage_sort_key(self, r):
        if self.spoilage_sort_col == "total":
            return (r.total_over, r.base.name.lower(), r.base.id)
        _cid, _h, _w, numeric, get = SPOILAGE_COLUMN_BY_ID[self.spoilage_sort_col]
        v = get(r)
        return (v if numeric else str(v).lower(), r.base.id)

    def refresh_spoilage_list(self):
        self.spoilage_tree.delete(*self.spoilage_tree.get_children())
        side = self.spoilage_side_var.get()
        rows = [r for r in self.spoilage_all if side == "All" or r.base.side == side]
        rows.sort(key=self._spoilage_sort_key, reverse=self.spoilage_sort_reverse)
        for r in rows:
            self.spoilage_tree.insert("", "end", iid=str(r.base.id),
                                      values=self._report_values(SPOILAGE_COLUMNS, SPOILAGE_TEXT, r))
        self.spoilage_count.set(f"{len(rows)} base{'' if len(rows) == 1 else 's'} over a limit")

    def sort_spoilage_by(self, col):
        self.spoilage_sort_reverse = (not self.spoilage_sort_reverse) if col == self.spoilage_sort_col else False
        self.spoilage_sort_col = col
        self.refresh_spoilage_list()

    def _upgrade_sort_key(self, r):
        _cid, _h, _w, numeric, get = UPGRADE_COLUMN_BY_ID[self.upgrade_sort_col]
        v = get(r)
        return (v if numeric else str(v).lower(), r.months, r.ship.name.lower(), r.ship.id)

    def refresh_upgrade_list(self):
        self.upgrade_tree.delete(*self.upgrade_tree.get_children())
        needle = self.upgrade_search_var.get().strip().lower()
        side = self.upgrade_side_var.get()
        within = UPGRADE_DUE[self.upgrade_due_var.get()]
        rows = [r for r in self.upgrades_all
                if (needle in r.ship.name.lower() or needle in r.current.name.lower())
                and (side == "All" or r.ship.side == side) and (within is None or r.months <= within)]
        rows.sort(key=self._upgrade_sort_key, reverse=self.upgrade_sort_reverse)
        for r in rows:
            self.upgrade_tree.insert("", "end", iid=str(r.ship.id),
                                     values=self._report_values(UPGRADE_COLUMNS, UPGRADE_TEXT, r))
        self.upgrade_count.set(f"{len(rows)} ship{'' if len(rows) == 1 else 's'}")

    def sort_upgrades_by(self, col):
        self.upgrade_sort_reverse = (not self.upgrade_sort_reverse) if col == self.upgrade_sort_col else False
        self.upgrade_sort_col = col
        self.refresh_upgrade_list()

    def _industry_places_for(self, side_var, region_var):
        side = side_var.get()
        return industry.filter_places(self.industry_places, None if side == "All" else side,
                                      self.region_ids[region_var.get()])

    def refresh_industry_report(self):
        side_id = {name: sid for sid, name in bases.SIDES.items()}[self.industry_side_var.get()]
        try:
            pools = industry.side_pools(self.save)[side_id]
        except SaveFormatError:
            pools = None
        type_rows, balance = industry.summarize(
            self._industry_places_for(self.industry_side_var, self.industry_region_var), pools,
            self.region_ids[self.industry_region_var.get()] is not None)
        for tree, columns, texts, rows, key in (
                (self.industry_tree, INDUSTRY_COLUMNS, INDUSTRY_TEXT, type_rows, lambda r: r.group),
                (self.balance_tree, BALANCE_COLUMNS, BALANCE_TEXT, balance, lambda r: r.material)):
            tree.delete(*tree.get_children())
            for r in rows:
                tree.insert("", "end", iid=key(r), values=self._report_values(columns, texts, r))

    @staticmethod
    def _industry_sort_key(columns, col, r, tie):
        _cid, _h, _w, numeric, get = columns[col]
        v = get(r)
        return (v if numeric else str(v).lower(), tie)

    def refresh_factory_report(self):
        self.factory_report_tree.delete(*self.factory_report_tree.get_children())
        rows = industry.factory_rows(self._industry_places_for(self.factory_report_side_var,
                                                               self.factory_report_region_var))
        group = self.factory_report_type_var.get()
        if group != FACTORY_TYPE_ALL:
            rows = [r for r in rows if r.group == group]
        if self.factory_report_problem_var.get():
            rows = [r for r in rows if r.factory.damage > 0 or not r.factory.production_on or not r.factory.repair_on]
        rows.sort(key=lambda r: self._industry_sort_key(FACTORY_COLUMN_BY_ID, self.factory_report_sort_col, r,
                                                        (r.place.id, r.factory.slot)),
                  reverse=self.factory_report_sort_reverse)
        for r in rows:
            self.factory_report_tree.insert("", "end", iid=f"{r.place.id}:{r.factory.slot}",
                                     values=self._report_values(FACTORY_COLUMNS, {}, r))
        self.factory_report_count.set(f"{len(rows)} factor{'y' if len(rows) == 1 else 'ies'}")

    def sort_factory_report_by(self, col):
        same = col == self.factory_report_sort_col
        self.factory_report_sort_reverse = (not self.factory_report_sort_reverse) if same else False
        self.factory_report_sort_col = col
        self.refresh_factory_report()

    def refresh_raw_list(self):
        self.raw_tree.delete(*self.raw_tree.get_children())
        rows = industry.raw_rows(self._industry_places_for(self.raw_side_var, self.raw_region_var),
                                 self.raw_only_var.get())
        rows.sort(key=lambda r: self._industry_sort_key(RAW_COLUMN_BY_ID, self.raw_sort_col, r,
                                                        (r.place.name.lower(), r.place.id)),
                  reverse=self.raw_sort_reverse)
        for r in rows:
            self.raw_tree.insert("", "end", iid=str(r.place.id), values=self._report_values(RAW_COLUMNS, RAW_TEXT, r))
        self.raw_count.set(f"{len(rows)} place{'' if len(rows) == 1 else 's'}")

    def sort_raw_by(self, col):
        self.raw_sort_reverse = (not self.raw_sort_reverse) if col == self.raw_sort_col else False
        self.raw_sort_col = col
        self.refresh_raw_list()

    def jump_to_industry_place(self, report_tree):
        sel = report_tree.selection()
        if not sel:
            return
        place_id = int(sel[0].split(":")[0])
        if place_id not in self.bases:
            # Minor places (location type 0) are not listed in the Bases tab.
            self.status.set(f"{report_tree.set(sel[0], 'place')} (#{place_id}) is a minor place; "
                            "the Bases tab does not list it")
            return
        iid = str(place_id)
        if not self.tree.exists(iid):
            self.search_var.set("")
            self.side_var.set("All")
            self.refresh_list()
        self.notebook.select(self.bases_tab)
        self.tree.selection_set(iid)
        self.tree.see(iid)

    def jump_to_spoilage_base(self):
        sel = self.spoilage_tree.selection()
        if not sel:
            return
        iid = sel[0]
        if not self.tree.exists(iid):
            self.search_var.set("")
            self.side_var.set("All")
            self.refresh_list()
        self.notebook.select(self.bases_tab)
        self.tree.selection_set(iid)
        self.tree.see(iid)

    def jump_to_upgrade_ship(self):
        sel = self.upgrade_tree.selection()
        if not sel:
            return
        iid = sel[0]
        if not self.shiprec_tree.exists(iid):
            self.shiprec_search_var.set("")
            self.shiprec_side_var.set("All")
            self.refresh_shiprec_list()
        self.notebook.select(self.shiprec_tab)
        self.shiprec_tree.selection_set(iid)
        self.shiprec_tree.see(iid)

    def apply_title(self):
        if self.save is None:
            return
        try:
            bases.set_title(self.save, self.title_var.get())
        except ValueError as exc:
            messagebox.showerror("Invalid title", str(exc))
            return
        self.dirty = True
        self.status.set("Title updated (not yet saved)")

    # ---- saving --------------------------------------------------------

    def save_as(self):
        if self.save is None:
            return
        if self.pbem:
            messagebox.showerror("Save refused", "This is a PBEM game. Saving an edited copy would desynchronise "
                                 "the other player, so PBEM saves are never written.")
            return
        # A typed but unapplied title would otherwise be silently dropped.
        if self.title_var.get() != self.save.description:
            try:
                bases.set_title(self.save, self.title_var.get())
            except ValueError as exc:
                messagebox.showerror("Invalid title", str(exc))
                return
        start = DEFAULT_DIR if os.path.isdir(DEFAULT_DIR) else HERE
        path = filedialog.asksaveasfilename(title="Save As", initialdir=start, defaultextension=".pws",
                                            initialfile=os.path.basename(self.path or ""),
                                            confirmoverwrite=False,
                                            filetypes=[("WitP:AE saves", "*.pws"), ("All files", "*.*")])
        if not path:
            return
        if os.path.exists(path) and not messagebox.askyesno(
                "Overwrite?", f"{path} exists. Overwrite it?\n\nThe old file is first copied to {os.path.basename(path)}.bak."):
            return
        try:
            backup = save_with_backup(self.save, path)
        except (OSError, SaveFormatError) as exc:
            messagebox.showerror("Save failed", str(exc))
            return
        self.dirty = False
        self.status.set(f"Saved {path}" + (f" (backup: {backup})" if backup else ""))


def main(argv):
    root = tk.Tk()
    app = EditorApp(root)
    if len(argv) > 1:
        if os.path.isdir(argv[1]):
            root.after_idle(lambda: app.open_dialog(argv[1]))
        else:
            app.load(argv[1])
    root.mainloop()


if __name__ == "__main__":
    main(sys.argv)
