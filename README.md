# WitP:AE base editor

A small savegame editor for War in the Pacific: Admiral's Edition, focused on
bases. Python 3.8+, standard library only (tkinter for the GUI).

## Run

    python witpae_editor.py [path\to\save.pws]

File > Open defaults to `..\SAVE`. Pick a base, edit its fields, press Apply
(edited rows are highlighted), then File > Save As. Saving over an existing
file asks first and copies the old file to `<name>.bak`. The save title can
also be edited (under 1000 bytes, latin-1).

Tests: `python -m unittest discover -s tests -v`

## Fields

| Field | Status |
|---|---|
| Supply, Fuel, Resource storage, Oil storage, Port size, Airfield size, Forts | verified in-game, editable |
| Port max, Airfield max (the bracketed sizes) | values verified in-game, editable |
| Fuel requested, Value to Japan/Allies multipliers, Port damage, Airfield runway/service damage | verified in-game, editable |
| Build/expand switches (Port, Airfield, Forts; off writes 0, on restores the saved value as the game does) | verified in-game, editable |
| Stockpile Yes/No switches (Supply, Fuel, Resources, Oil; one bitfield byte, other bits preserved) | verified in-game, editable |
| Factories (per base, 20 slots: size, damage, production Yes/No, repair Yes/No; production cannot be switched off for Oil, Resources, Manpower, Repair Shipyard, Light Industry) | verified, editable |
| Factory Keep/Upgd switch (aircraft and engine factories) and aircraft availability date | verified in-game; switch editable, date display only |
| Supply required, Aviation support, Ships in port, Aircraft at base | verified, display only (recalculated by the game) |

Name, side and hex coordinates are read-only. The field table is in
`witpae/bases.py`; adding a field is one line.

## Backups

Always keep a copy of your saves before editing. Prefer saving to a new file
name rather than over the original, and test unverified fields on a copy.
