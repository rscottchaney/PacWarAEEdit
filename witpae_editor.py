"""Tkinter front end for the WitP:AE base editor.

Usage: python witpae_editor.py [save.pws]

All data logic lives in the witpae package; this file only wires widgets.
"""

import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from witpae import bases, factories
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
        self.current = None
        self.factory_slot = None

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
        body = ttk.Frame(self.root, padding=4)
        body.pack(side="top", fill="both", expand=True)

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
        self.apply_btn = ttk.Button(right, text="Apply", command=self.apply)
        self.apply_btn.grid(row=stock_row + 1, column=0, columnspan=2, pady=(10, 0))

    def _build_factories(self, parent):
        box = ttk.LabelFrame(parent, text="Factories", padding=4)
        box.pack(side="bottom", fill="x", pady=(6, 0))
        cols = [("slot", "Slot", 40), ("name", "Name", 150), ("kind", "Kind", 65), ("size", "Size", 55),
                ("damage", "Damage", 60), ("production", "Production", 75), ("repair", "Repair", 55),
                ("upgrade", "Upgrade (unverified)", 120)]
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
        ttk.Label(edit, text="Size:").pack(side="left")
        ttk.Entry(edit, textvariable=self.factory_size_var, width=8).pack(side="left", padx=(2, 8))
        ttk.Label(edit, text="Damage:").pack(side="left")
        ttk.Entry(edit, textvariable=self.factory_damage_var, width=8).pack(side="left", padx=(2, 8))
        self.factory_production_check = ttk.Checkbutton(edit, text="Production", variable=self.factory_production_var)
        self.factory_production_check.pack(side="left", padx=4)
        ttk.Checkbutton(edit, text="Repair", variable=self.factory_repair_var).pack(side="left", padx=4)
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
        except (OSError, SaveFormatError, KeyError) as exc:
            messagebox.showerror("Cannot open save", f"{path}\n\n{exc}")
            return False
        self.save, self.path = save, path
        self.bases = {b.id: b for b in blist}
        self.edited.clear()
        self.dirty = False
        self.current = None
        self.factory_slot = None
        self.file_label.set(f"File: {os.path.basename(path)}    Key variant: {save.variant}")
        self.title_var.set(save.description)
        self.status.set(f"{path} - {len(blist)} bases")
        self.refresh_list()
        self.show_detail(None)
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
            for var in self.stockpile_vars.values():
                var.set(False)
            self.show_factories(None)
            return
        self.detail_title.set(f"{base.name} (#{base.id}, {base.side}, hex {base.x},{base.y})")
        for f in bases.FIELDS:
            self.field_vars[f.name].set(str(base.get(f.name)))
        for name, on in base.get_stockpile().items():
            self.stockpile_vars[name].set(on)
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
                f.slot, f.name, f.kind, f.size, f.damage, yn(f.production_on), yn(f.repair_on), yn(f.upgrade_on)))
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
            self.factory_production_check.state(["disabled"])
            return
        self.factory_size_var.set(str(factory.size))
        self.factory_damage_var.set(str(factory.damage))
        self.factory_production_var.set(factory.production_on)
        self.factory_repair_var.set(factory.repair_on)
        self.factory_production_check.state(["disabled" if factories.production_locked(factory.type) else "!disabled"])

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
                                  bool(self.factory_production_var.get()), bool(self.factory_repair_var.get()))
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
        base.set_many(values)
        base.set_stockpile(flags)
        if before != values or flags_before != flags:
            self.edited.add(base.id)
            self.dirty = True
        self.refresh_list()
        self.show_detail(base)

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
