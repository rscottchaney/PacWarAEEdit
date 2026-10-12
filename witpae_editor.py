"""Tkinter front end for the WitP:AE base editor.

Usage: python witpae_editor.py [save.pws]

All data logic lives in the witpae package; this file only wires widgets.
"""

import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from witpae import aircraft, airgroups, bases, factories, ships
from witpae.container import SaveFile, SaveFormatError
from witpae.fileio import save_with_backup

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DIR = os.path.normpath(os.path.join(HERE, "..", "SAVE"))

# (column id, heading, width, numeric, value getter)
COLUMNS = [
    ("id", "ID", 55, True, lambda b: b.id),
    ("name", "Name", 150, False, lambda b: b.name),
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

GROUP_COLUMNS = [
    ("id", "ID", 55, True, lambda g: g.id),
    ("name", "Name", 170, False, lambda g: g.name),
    ("aircraft", "Aircraft", 120, False, lambda g: g.aircraft_name),
    ("planes", "Planes", 55, True, lambda g: g.planes),
    # Active pilots from the pilot table; the group's own count byte disagrees for many groups.
    ("pilots", "Pilots", 50, True, lambda g: g.active_pilots),
    ("morale", "Morale", 55, True, lambda g: g.get("morale")),
    ("exp", "Exp", 45, True, lambda g: g.get("experience")),
]
GROUP_COLUMN_BY_ID = {c[0]: c for c in GROUP_COLUMNS}


class EditorApp:
    def __init__(self, root):
        self.root = root
        root.title("WitP:AE Base Editor")
        self.save = None
        self.path = None
        self.bases = {}
        self.edited = set()
        self.dirty = False
        self.sort_col = "id"
        self.sort_reverse = False
        self.field_vars = {}
        self.stockpile_vars = {}
        self.building_vars = {}
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
        body = ttk.Frame(self.notebook, padding=4)
        self.notebook.add(body, text="Bases")
        self._build_aircraft_tab()
        self._build_ships_tab()
        self._build_groups_tab()

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
            self.tree.column(cid, width=width, anchor="w" if cid in ("name", "side") else "e")
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
            ttk.Checkbutton(build_box, text=label, variable=var).pack(anchor="w")
        self.apply_btn = ttk.Button(right, text="Apply", command=self.apply)
        self.apply_btn.grid(row=build_row + 1, column=0, columnspan=2, pady=(10, 0))

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
        self.notebook.add(tab, text="Ships")
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

        # Pilots and commander sit below the list so the tab stays short enough for small screens.
        lower = ttk.Frame(left)
        lower.pack(side="bottom", fill="x", pady=(6, 0))
        self._build_pilots(lower)
        self._build_leader(lower)

        self.group_tree = ttk.Treeview(left, columns=[c[0] for c in GROUP_COLUMNS], show="headings",
                                       selectmode="browse", height=8)
        for cid, heading, width, _numeric, _get in GROUP_COLUMNS:
            self.group_tree.heading(cid, text=heading, command=lambda c=cid: self.sort_groups_by(c))
            self.group_tree.column(cid, width=width, anchor="w" if cid in ("name", "aircraft") else "e")
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
            ttk.Entry(right, textvariable=self.group_vars[f.name], width=10).grid(
                row=row, column=1, padx=(8, 0), pady=2)
            row += 1
        ttk.Button(right, text="Apply", command=self.apply_group).grid(row=row, column=0, columnspan=2, pady=6)
        row += 1
        self.group_info = {}
        for name, label in (("aircraft", "Aircraft (read-only)"), ("planes", "Aircraft total (read-only)"),
                            ("pilots", "Pilot count byte (read-only, meaning unclear)"), ("leader", "Commander (read-only)")):
            ttk.Label(right, text=label).grid(row=row, column=0, sticky="w", pady=1)
            self.group_info[name] = tk.StringVar()
            ttk.Label(right, textvariable=self.group_info[name]).grid(row=row, column=1, sticky="w", padx=(8, 0))
            row += 1
        ttk.Label(right, text="The game probably recalculates\naverage experience from the pilots.",
                  foreground="gray40").grid(row=row, column=0, columnspan=2, sticky="w", pady=(6, 0))

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
        for f in airgroups.PILOT_FIELDS:
            ttk.Label(edit, text="Exp" if f.name == "experience" else f.label).pack(side="left")
            self.pilot_vars[f.name] = tk.StringVar()
            ttk.Entry(edit, textvariable=self.pilot_vars[f.name], width=3).pack(side="left", padx=(1, 4))
        ttk.Button(edit, text="Apply pilot", command=self.apply_pilot).pack(side="left", padx=4)

    def _build_leader(self, parent):
        box = ttk.LabelFrame(parent, text="Commander", padding=4)
        box.pack(side="top", fill="x", pady=(6, 0))
        self.leader_name = tk.StringVar(value="(none)")
        ttk.Label(box, textvariable=self.leader_name, width=18).pack(side="left")
        self.leader_age = tk.StringVar()
        ttk.Label(box, text="Age?").pack(side="left")
        ttk.Label(box, textvariable=self.leader_age, width=4).pack(side="left")
        self.leader_entries = []
        for f in airgroups.LEADER_FIELDS:
            ttk.Label(box, text=f.label[:5] if f.label != "Aggression" else "Aggr").pack(side="left")
            self.leader_vars[f.name] = tk.StringVar()
            entry = ttk.Entry(box, textvariable=self.leader_vars[f.name], width=3)
            entry.pack(side="left", padx=(1, 4))
            self.leader_entries.append(entry)
        self.leader_button = ttk.Button(box, text="Apply commander", command=self.apply_leader)
        self.leader_button.pack(side="left", padx=4)

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
            blist = bases.list_bases(save)
            alist = aircraft.list_aircraft(save)
            slist = ships.list_ships(save)
            glist = airgroups.list_airgroups(save)
            pindex = airgroups.pilots_by_group(save)
        except (OSError, SaveFormatError, KeyError) as exc:
            messagebox.showerror("Cannot open save", f"{path}\n\n{exc}")
            return False
        self.save, self.path = save, path
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
        self.groups = {g.id: g for g in glist}
        self.pilot_index = pindex
        for g in glist:
            g.active_pilots = sum(1 for p in pindex.get(g.id, []) if p.status == 1)
        self.groups_edited.clear()
        self.group_current = None
        self.pilot_current = None
        self.leader_current = None
        self.file_label.set(f"File: {os.path.basename(path)}    Key variant: {save.variant}")
        self.title_var.set(save.description)
        self.status.set(f"{path} - {len(blist)} bases, {len(alist)} aircraft, {len(slist)} ship classes, {len(glist)} air groups")
        self.refresh_list()
        self.show_detail(None)
        self.refresh_aircraft_list()
        self.show_aircraft(None)
        self.refresh_ship_list()
        self.show_ship(None)
        self.refresh_group_list()
        self.show_group(None)
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
            self.show_factories(None)
            return
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
        for f in bases.FIELDS:
            if not f.editable:
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
        building = {n: bool(v.get()) for n, v in self.building_vars.items()}
        building_before = base.get_building()
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

    # ---- air groups ----------------------------------------------------

    def _group_sort_key(self, g):
        _cid, _h, _w, numeric, get = GROUP_COLUMN_BY_ID[self.group_sort_col]
        v = get(g)
        return (v if numeric else str(v).lower(), g.id)

    def refresh_group_list(self):
        selected = self.group_current
        self.group_tree.delete(*self.group_tree.get_children())
        needle = self.group_search_var.get().strip().lower()
        rows = [g for g in self.groups.values() if needle in g.name.lower()]
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
            self.show_pilots(None)
            self.show_leader(None)
            return
        self.group_title.set(f"{g.name} (#{g.id})")
        for f in airgroups.GROUP_FIELDS:
            self.group_vars[f.name].set(str(g.get(f.name)))
        leader = airgroups.get_leader(self.save, g.leader_id)
        self.group_info["aircraft"].set(f"{g.aircraft_id} {g.aircraft_name}")
        self.group_info["planes"].set(str(g.planes))
        self.group_info["pilots"].set(str(g.pilot_count))
        self.group_info["leader"].set(f"{g.leader_id} {leader.name}" if leader else str(g.leader_id))
        self.show_pilots(g)
        self.show_leader(leader)

    def apply_group(self):
        if self.group_current is None:
            return
        g = self.groups[self.group_current]
        values = {}
        for f in airgroups.GROUP_FIELDS:
            text = self.group_vars[f.name].get().strip()
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
