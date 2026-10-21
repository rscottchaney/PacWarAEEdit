# WitP:AE base editor

A small savegame editor for War in the Pacific: Admiral's Edition, focused on
bases. Python 3.8+, standard library only (tkinter for the GUI).

## Run

    python witpae_editor.py [path\to\save.pws]

File > Open defaults to `..\SAVE`. Pick a base, edit its fields, press Apply
(edited rows are highlighted), then File > Save As. Saving over an existing
file asks first and copies the old file to `<name>.bak`. The save title can
also be edited (under 1000 bytes, latin-1).

PBEM games (title starting with `(PBEM)` when loaded) can be browsed, but saving them is
refused, even after a retitle, because an edited copy would desynchronise the other player.

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
| Factory model (aircraft factories): the "Model" box under the factory table lists the aircraft models of the same side as the factory's current model, shown as `name (#id)`; "Set model" writes the new type (2000 + aircraft id) to both the type array (offset 136 + 2 x slot) and the original-type array (336 + 2 x slot) and keeps size, damage and the switches. Refused for industry and engine factories, for a model of the other side, for the model it already builds and for a missing model. In the game only the Japanese player can convert factories and the game damages a factory when it converts; the editor does not damage it | not yet tested in-game |
| Supply cap (the "max" on the base screen), Garrison required (Allied) | values verified against game screens, editable (edit not yet tested in-game) |
| Garrison required (Japanese) | unverified (not yet checked on a Japanese-held base), editable |
| Supply required, Aviation support, Ships in port, Aircraft at base | verified, display only (recalculated by the game) |

Towns are listed in the Bases tab too (Type column) and edited the same way, except
that towns have no port, so Port size, Port max, Port damage and the Port build
switch are read-only for them.

Minor places (Type "Minor", for example Kofu, Corunna Downs, Sholapur) are listed
too. Their Supply, Fuel, Resource and Oil storage, Forts, value multipliers, supply
cap, garrison, stockpile switches and factories are editable. They have no port or
airfield, so every port and airfield field (size, max, damage) and the Port and
Airfield build switches are read-only for them. Edits to minor places are not yet
tested in-game. Minor places are not move destinations for units, air groups or
task forces.

Name, side and hex coordinates are read-only. The field table is in
`witpae/bases.py`; adding a field is one line.

## Aircraft

The Aircraft tab lists the aircraft table (section 0x20) with search and
sortable columns. Several models share a name (one per nation), so always check
the ID. Edits use the same Apply button, row highlight and Save As as bases.

| Field | Status |
|---|---|
| Max speed, Cruise speed, Climb, Maneuver, Armor, Durability, Load | verified in-game, editable |
| Production rate, In pool (side-wide aircraft pool) | verified in-game for Allied models, editable. The pool and used tables hold a (Japan, Allies) pair per model and each model reads its own side's half; Japanese values are not yet checked in-game |
| Used, produced last turn, produced this month | verified in-game, read-only |
| Max altitude | verified in-game, editable |
| Max range (hexes, miles) | verified in-game, editable |
| Normal/extended radius and the drop-tank variants of max range and radii (hexes, miles; stored and shown independently, 0/0 = none) | values verified as displayed, editable |
| Endurance (the game ignores the stored value and calculates it from range and cruise speed) | calculated, read-only |
| Available from / to, entered as `m/yy` like the game database ("12/41"); `0/0` or `-` means no date (many records store it for "to") | verified in-game, editable |
| Carrier capable (one bit of a flag byte, other bits preserved) | verified in-game, editable |
| Type: Fighter and Dive Bomber verified; other labels are guesses and end in `?` | read-only |
| Nation: IJA, IJN, USN, USA, NZ verified; other labels are guesses and end in `?`; unknown codes show the number | read-only |
| Weapons (max load and reduced load: name, count, facing F/TR/C/XT), gun value, maneuver modifiers per altitude band | verified, read-only |
| Engines: the engine is weapon slot 9, a device id (i16 at offset 60) and a count (u8 at offset 100; the reduced-load copies at 80 and 120 are not used). Japanese models name a specific engine device (A6M2 Zero: 1 x Nakajima Ha-35; Ki-21-Ic Sally: 2 x Nakajima Ha-5), Allied models use the generic device 1852 "Engine" and show "2 engines" | read-only |
| Picture number (u16 at 26): the tile of the model's side-view picture, see below | verified (Zero, Sally, P-38G, Hellcat show the right pictures), read-only |
| Upgrade (u16 at 192: the model it upgrades to; its own id or 0 means none, shown as `-`) | checked on a few models (SBD-3 -> SBD-5, P-38G -> P-38H, A6M2 Zero -> A6M2 Sen Baku; P-40E has none), labelled unverified, read-only. Earlier versions read offset 26 here, which is the picture number, so they showed unrelated models (the A6M2 Zero "upgraded" to a B-25D) |

The top of the detail pane shows the model's side-view picture (150 x 60), and the buttons "Compare as A" and
"Compare as B" send the selected model to the Aircraft comparison report.

Pictures are not part of the editor and not stored in saves: they are read at run time from the game's ART
folder, `A_PlaneSide.bmp` (Allied) and `J_PlaneSide.bmp` (Japanese), uncompressed 24-bit BMP sheets of 150 x 60
tiles, 4 per row; the tile of a model is its picture number (tile n is at x = (n % 4) x 150, y = (n // 4) x 60).
The editor looks for the ART folder next to the folder of the loaded save (`<game>\ART` for `<game>\SAVE`), then
next to the editor (`<game>\SaveEditor`). Without one, the picture area says "No picture" and nothing else
changes. The code is in `witpae/planeart.py`.

The field table is in `witpae/aircraft.py`.

## Ship Classes

The Ship Classes tab lists the ship class table (section 0x1B). Several records share
a name because they are refit stages of one class (Lexington is #674 to #679),
so check the ID and date.

| Field | Status |
|---|---|
| Fuel, Endurance, Speed, Cruise speed, Maneuver, Durability, Belt/Deck/Tower armor | verified in-game, editable |
| Aircraft capacity (was "Capacity"), Troop capacity, Cargo capacity, Fuel/oil capacity | values verified against game screens, editable (edit not yet tested in-game) |
| Weapon and electronics slots: Num, Face (F, C, R, RS, LS, A; other codes are kept as numbers), Mount, Armor, Ammo | verified in-game, editable per slot (Apply weapon); the device itself is read-only |
| Type (abbreviations from the game executable; DE, TB, PG, LB are guesses ending in `?`) | read-only |
| Nation (shared with aircraft) | read-only |
| Displacement, refit date (`m/yy`) | unverified, read-only |

The field table is in `witpae/ships.py`. Nation labels in `witpae/nations.py`
are verified except China and India, which end in `?`.

## Ships

The Ships tab lists the ships in play (section 0x08, one record per ship, indexed
by ship id; records with an empty name are unused). Search by name and filter by
side; the side comes from the ship's nation (IJA and IJN are Japanese, all
others Allied). The Location column shows the current base, `TF n` for a ship at
sea in a task force, or `at sea`. Offsets were mapped against game screens;
edits have not been tested in-game yet, so try them on a copy.

| Field | Status |
|---|---|
| Experience (day, night), 0..99 | values verified against game screens, edit not yet verified in-game |
| Fuel, 0..32767 | verified in-game (edit) |
| Fires, system damage, flotation damage, major flotation damage, engine damage, major engine damage (0..99) | values verified against game screens; clearing system and engine damage verified in-game, other edits not yet |
| Major flotation damage cannot exceed flotation damage, nor major engine damage engine damage; checked on the final values of an Apply and only when the apply changes that pair (existing ships may already break it, for example sinking ships) | rule enforced by the editor |
| Repair all (sets fires and all six damage values to 0; writes nothing when there is no damage) | verified in-game (through the Task Forces tab's Repair all) |
| Weapon and electronics slots: Num and Ammo (0..999), only slots that hold a device | values verified against game screens, edit not yet verified in-game |
| Weapon device, Face, Mount, Armor | read-only |
| Nation, class (name and type from the ship class table), current base, task force, days to arrival | read-only |
| Task force moves ("Move to" on the ship form): TF to another TF, TF to a port, port to a TF. Rules: the TF and the destination must be in the same hex and on the ship's side; a TF moves only to a TF that has ships; a TF ship goes to a port only at a base or town of its side in the TF's hex (no dropping ships at sea); a docked ship joins only a TF in its port's hex. Refused: the last ship of a TF, ships that have not arrived, ships in no TF or port, moving to where the ship already is, port to port, and any save whose ship chains are inconsistent (nothing is written). A TF takes the ship in ascending ship-id order and a port at the end; if the moved ship was the flagship of its old TF, the TF's new last ship becomes flagship. | layout mapped from in-game saves; editor moves verified in-game (TF to TF, TF to port with the flagship, port to TF; post-turn not yet checked) |

The field table is in `witpae/shiprecords.py`; the chain logic for moves is in `witpae/taskforces.py`.

## Task Forces

The Task Forces tab lists every task force that has ships (location records of
type 12 from section 0x13, with a row in the TF table, section 0x46). Search by
name and filter by side (taken from the TF's ships). The Location column shows
the name of the base or town in the TF's hex as `<name> (in port)`, else
`at sea x,y`; the Mission and Destination columns show its orders. Select a TF to see its ships in chain order with their fuel
(current/class maximum), system, flotation and engine damage and fires; the
flagship is marked. Any edit highlights the TF row and the affected ships in the
Ships tab.

| Feature | Status |
|---|---|
| TF list and ship grid | read-only data |
| Flagship (combobox and Set flagship; u16 at offset 44 of the TF table row) | verified in-game |
| Move the selected ship ("Move to" and Add ship from port) | verified in-game, same rules as the Ships tab moves; Add ship from port offers ships docked at the base in the TF's hex that may join |
| Repair all ships (clears fires and damage of every ship; ships without damage are untouched) | verified in-game |
| Refuel all ships (sets each ship's fuel to its class's fuel; never lowers fuel, ships already full are untouched) | verified in-game |
| Mission (combobox `NN - label` and Set; u8 at offset 349 of the TF table row, only that byte changes). Codes: 1 Air Combat, 2 Surface Combat, 3 Bombardment?, 4 Fast Transport?, 5 Transport, 6 Replenishment, 7 Mine Laying?, 8 Sub Patrol, 9 Sub Minelaying?, 10 Sub Transport?, 11 Cargo, 12 Barge, 13 Air Transport, 14 CV Escort?, 15 Amphibious, 16 ASW Combat, 17 PT Boat, 18 Tanker, 19 Mine Sweeping?, 20 Landing Craft?, 21 Midget Submarine, 22 Support, 23 Local Minesweeper, 24 Midget Sub Carrier, 25 Follow?. A "?" marks a code whose label was not seen in a game save. A stored code outside 1..25 is shown as its number and kept | verified in-game |
| Home port (combobox of the bases and towns of the TF's side that have a port, and Set; u16 at 54, plus the flag bits the game sets with it at 8, 322 and 490) | verified in-game |
| Destination (a text filter, a combobox of every base and town of either side, and Set; refused for the place in the TF's own hex). The editor writes a two-hex route (the TF's hex, then the destination's) and the game plans the real path itself | verified in-game, with a docked TF and a TF at sea |

The model functions are in `witpae/taskforces.py` (`set_flagship`, `set_mission`, `set_home_port`, `set_destination`, `repair_task_force`, `refuel_task_force`, `move_ship`).

## Air Groups

The Air Groups tab lists the air group table (section 0x14; the ID is the group
number shown in the game). Select a group to edit it, its pilots (section
0x16) and its commander (section 0x15). Editing a pilot or commander
highlights the group row. The Side filter uses the group's side byte
(offset 26), so groups aboard ships or not yet arrived are filtered too.

| Field | Status |
|---|---|
| Group morale, maximum range setting, current altitude | verified in-game, editable |
| Group average experience | verified in-game for a group without pilots, editable; the game probably recalculates it from the pilots |
| Group patrol levels: ASW, Search, Train, Rest % | verified in-game, editable |
| Group patrol levels: CAP, LRcap % | follow the game's order, CAP value matched; edit unverified, editable |
| Search arc start/end (degrees, clockwise; stored in tens) | verified in-game, editable |
| Location (Move button) | verified in-game, editable: only to bases and towns on the same side; groups aboard ships (the Location column shows the ship name) or not yet arrived are read-only. A move also sets the group's base ("Based at") when it matched the location; detachments based elsewhere keep their base. Moves to towns verified in-game |
| Pilot count byte (often disagrees with the pilot table), commander link | read-only |
| Ready, maintenance, damaged, reserve planes (Apply planes / Repair all) | editable for arrived groups (including groups aboard ships); the four must add up to the unchanged aircraft total, which is shown read-only. Groups not yet arrived are read-only. Repair all moves maintenance and damaged planes into ready. The game rebuilds these counts from the per-plane records (section 0x17) on load, so the editor changes the status of only as many plane records as needed and keeps the group counts and total repair time in step. Verified in-game (ready, maintenance and damaged on CNAC) |
| Aircraft (Change button) | verified in-game (kept after a turn), editable, own side only (aircraft side byte 228); writes only the aircraft id, like the AE Editor's Air Class. Plane counts and the upgrade target are unchanged, so set the upgrade too if the old target would be a step backwards. |
| Upgrade to (Set upgrade button) | verified in-game, editable, own side only: the model the game swaps in when the pool has enough planes; both stored copies (@308, @574) are written. |
| Withdraw (remove by) and Return date, entered as `14 Dec 1943` or `14 Dec 43`; blank or `-` means none (stored as YYMMDD u32 @392 and @396). Many groups store 9999 as the return date, meaning unknown; it is kept and shown as `9999` | values verified against game screens, edits not yet verified in-game; editable |
| Maximum group size (the bracketed size, u8 @245; the near-copy at @246 is never written) | values verified against game screens, edits not yet verified in-game; editable |
| Size changes (5 entries: date as `Jul 42` or `Jul 1942`, new size 0..255; YYMM u16 @446 and u8 @456; an entry without a date has size 0; gaps are allowed, as in the game data; own Apply button). Also editable for groups not yet arrived | values verified against game screens, edits not yet verified in-game; editable |
| Formation (7 Squadron, 8 Flight, 9 Section; @28), parent group (@38, detachments), returns-as group (@400) | values verified against game screens; read-only |
| Pilot status (1 = Active; 2-4 probably killed/wounded/missing, unverified) | read-only; the Pilots list column counts active pilots |
| Pilot experience | verified in-game, editable |
| Pilot 12 skills (Air, NavB, NavT, NavS, Recn, ASW, Tran, GrdB, LowN, LowG, Staf, Defn) | verified in-game, editable; written to both stored copies |
| Commander leadership, inspiration, naval, air, land, admin, aggression | verified in-game, editable |
| Pilot "Age?" | unverified, read-only |
| Commander rank (shown as text and code, for example `LTC (37)`; same decoding as the Leaders tab) | read-only |

Each pilot skill is stored twice (bytes 65..76 and 78..89). The game's pilot
list shows the second copy, so edits write both. The byte at 122 is left
alone because its purpose is unknown. The commander box is disabled for groups without a commander.

### Pilot pool

The Air Groups tab has a second page, Pilot pool, with one row per nation
(section 0x01, nations 1..18). Nations with no pool, no monthly rate and no pilots in training are hidden
(their experience still shows a default such as 35) unless "Show empty nations" is ticked; the Side filter treats IJA and IJN as Japanese
and every other nation as Allied. Select a row, change the entries and press
Apply pilot pool; edited rows are highlighted. Invalid input shows an error and
writes nothing.

| Column | Stored as |
|---|---|
| Pool (pilots available) | i16 at 65132 + 2 x (nation - 1) |
| Exp (pool experience) | i16 at 65168 + 16 x nation |
| Rate/month | i16 at 65482 + 16 x nation |
| T1..T12 (training intakes, shown as `count (experience)`) | block at 97918 + 72 x (nation - 1): 12 x i16 counts (bytes 0..23), 12 x u8 experience (bytes 48..59); the other bytes are never written |
| In training | sum of the 12 counts, read-only |

Counts and the pool are limited to 0..32767 and experience to 0..99. Experience
rises with the intake index, so T1 (index 0) is presumably the newest intake.

These offsets were taken from WitPTracker's code and the values look right on
three saves, but they are NOT yet checked against the game: compare with the
game's Pilot Pool / Experience screen before relying on edits. Nations 3, 6, 15,
16 and 17 have no confirmed name and are shown by number (nation 3 is skipped by
WitPTracker and is normally empty).

## Land Units

The Land Units tab lists land units (record types INF, ART, ENG, CD, HQ and the
guessed AA and ARM) from the same location table as bases, so the ID is the
location id. Names are shown with the game's unit-kind suffix where the unit
class is known (otherwise the category in brackets), and the HQ column shows
game-style HQ names.

| Field | Status |
|---|---|
| Experience, morale, fatigue (0..99), supplies | verified in-game, editable |
| Disruption (0..99; same offset as runway damage on bases) | verified in-game, editable |
| Equipment count and disabled count per slot (disabled cannot exceed count) | verified in-game, editable |
| Support and support required | matched 2 of 3 units on screen, approximate, read-only |
| Location (Move button) | verified in-game, editable: only to bases and towns on the same side; units not yet arrived or on the march are read-only. A move also sets the unit's hex, its target and its map position (the game names the location after the nearest base to that position). Moves to towns verified in-game |
| Add equipment (Add box, count, disabled): only devices that some land unit of the same side already uses (current or TOE); written to the first empty slot with no TOE entry | verified in-game (kept after a turn), editable |
| HQ, target, supplies required (recalculated by the game), the device of an existing slot, TOE device and TOE count | verified, read-only |
| Types HQ, INF, ART, ENG, CD verified; AA and ARM are guesses ending in `?` | read-only |

Load cost and AV are computed by the game.

## Leaders

The Leaders tab lists every named leader (section 0x15, 50000 records of 180
bytes; the ID is the leader id that air groups, ships and land units refer to).
Filters: Side, Branch (Army, Navy, Air, from the rank), Type, Assigned, and a
Search box that matches the name or the unit the leader commands. All columns
sort. Select a leader to edit the ratings (same Apply, validation and row
highlight as the other tabs); double-click one that commands a unit to jump to
that unit in its tab (Air Groups, Ships, Task Forces or Land Units), with that
tab's filters cleared. Edits in the Air Groups commander box and in this tab
show in both.

| Field | Status |
|---|---|
| Leadership, Inspiration, Naval, Air, Land, Admin, Aggression (0..99; u8 at 26..32) | verified in-game, editable |
| Rank (u8 at 25, not age; text from the game's rank table: 0-9 and 32-42 Army, 10-31 Navy, 43-53 Air; other codes show `Rank n`) and Branch (from the rank) | decoded from WiTPTracker and ae-editor, checked on a save; read-only |
| Nation (u8 at 42, same codes as ships and aircraft; IJA and IJN are Japanese, everything else Allied) | read-only |
| Type (u8 at 49, the best command: None, Headquarters, Large/Small Ground Unit, Task Force, Ship, Air Group; other codes show `Type n`) | decoded, read-only |
| Delay (i32 at 44, days until the leader is available, 0 = available) | decoded, read-only |
| Political points (u8 at 48) | not verified in-game, read-only |

Who commands what is not stored on the leader, so the editor reads it from the
units, once per save load: air groups (i16 at 32 of the group record), ships
(u16 at 32 of the ship record) and location records (u16 at 128: task forces,
shown as `TF <id>`, and land units and HQs, shown by their game name). Only
used records (named, task forces with ships) count. A leader named by more than
one unit shows the first (air groups, then ships, then locations) and `+n`
for the others (70 leaders on the sample save, all of them ships). The unit
fields were checked on the sample save (for example 10,722 of 10,757 ships name
a leader of type Ship) but not in-game. Offset 38 is not used because it names
the unit only for some air group leaders. The code is in `witpae/leaders.py`;
edits go through `airgroups.Leader`.

## Reports

The Reports tab holds twelve reports; only the bulk switch buttons of Air production edit the save. It
shows the game date (section 0x01: day at 42, month at 44, two-digit year at 46,
all i16) and refreshes whenever the tab is shown, so edits made in the Bases tab
are reflected. Double-click a row to jump to that base (Bases tab) or ship (Ships
tab); the target tab's search and side filter are cleared if they hide the row.

| Report | What it shows | Status |
|---|---|---|
| Spoilage | Bases and towns whose supply or fuel exceeds the spoilage limit, largest total excess first (columns can be re-sorted; Side filter; Region column). With s = port size + airfield size, the limit is supply 5000 + 3000 x s squared and fuel 1000 + 2000 x s squared (game manual 15.7); a base of size 1 gets 8000 / 3000, matching the base screen. "Over" is shown as `-` when not over | formula verified for size 1 (Bassein); the rule that there is no limit at s of 10 or more is from the manual and unverified (a patch note suggests the limit is shown below 9) |
| Ship upgrades | One row per arrived ship whose class has a further upgrade (ships not yet arrived are left out, because reinforcements arrive with the upgrades of their arrival date): current class, target class, type change (for example DD -> DE), the date the upgrade becomes available, months until then relative to the game date, and the Location. Search (ship or class name), Side and "Due within" (default 3 months) filters | link (ship class u16 at 256 = next class id, available on the target class's date) matches the game's "Upgrade on" dates for Maryland and Kanawha; chains end when the id is 0, the class itself or an unused record |
| Yard? column (target class i16 at 260) | the shipyard size shown for the upgrade target | unverified |

The code is in `witpae/reports.py`; the upgrade link and yard fields are in `witpae/ships.py`.

### Ship production

Japan only. The "Ship production" sub-tab (after Ship upgrades) is read-only and follows the game manual
(13.4, 13.4.1, 13.2.2.8):

- "Only the Japanese build ships; Allied reinforcements arrive on schedule." The report therefore lists the
  Japanese ship records (nation IJA or IJN) whose days to arrival (u32 at 36) is above 0.
- For a ship with durability D (its class's durability, u8 at 39) and delay L (days to arrival):
  - L over 30 x D is a "Blue print": 1 day of delay is removed free each day; it cannot be accelerated.
  - L over 10 x D up to 30 x D "Can accelerate": 1 day is removed free each day; accelerating removes 1 more
    day per day for D shipyard points.
  - L up to 10 x D is "Building": normal construction needs D shipyard points per day to remove 1 day;
    accelerated construction removes 2 days per day for 3 x D points.
- Midget submarines (class type 28, SSX) are not built with shipyard points. 86 of them sit in the sample save: 83
  at exactly 1 day to arrival in three consecutive saves (wpae003, the test save, autosave 014), where they
  never progress, and 3 at 19999; WitpStaff's readme says midget subs appear in saves like ships in production
  but use no build points. They get the status "Midget sub (no points)", are still listed, cost 0 points
  and are left out of the Building / Can accelerate / Blue print counts and of the points needed.
- Which points a ship needs depends on its class type. Naval shipyard points are used by types 1 CVB, 2 CV,
  3 CVL, 5 BB, 6 BC, 7 CB, 8 CA, 9 CL, 10 CLAA, 12 DD, 13, 14, 15, 16, 17 PF, 19 PC, 21 SC, 22 PT, 23 MTB,
  24 MGB, 25 ML, 26 SS, 27 SST, 28 SSX, 30 CM, 31 CMc, 32 DM, 33 DMS, 38 AVD, 39 AVP and 51 APD (the list
  is WitPTracker's); every other type, including 4 CVE, uses merchant shipyard points.
- Each Naval Shipyard (factory type 522) or Merchant Shipyard (523) size point with production on makes 1
  point per day for 3 HI (13.2.2.8). Only Japanese places count. The pools are the Japanese naval and
  merchant pools (section 0x01, see Industry reports).

Columns of the ship table: ID, Ship, Type, Class, Durability, Yard (Naval or Merchant), Delay, Arrives (game
date plus the delay, `-` when the game date cannot be read), Status, Starts costing in (days until L falls to
10 x D, 0 when Building), Points/day (D when Building, else 0), Points to finish (D x the smaller of L and
10 x D, at the normal rate) and Accelerated/day (3 x D when Building, D when Can accelerate, `-` for a Blue
print or a midget sub). Search (ship or class name), Yard, Status and Type filters; click a heading to sort; double-click
opens the ship in the Ships tab. The table above it gives, per yard, the points made per day (yard size
with production on), HI/day (3 per point), the pool, the points per day needed by the Building ships, the
net per day (made minus needed, ignoring the pool) and the number of ships in each status.

Two things are not known, so the report does not show or guess them: the game's per-ship Normal /
Accelerate / Halt setting (not located in the save yet; Points/day assumes normal construction), and which
Building ships are paid each day when the points run short (not in the manual; only the daily shortfall or
surplus per yard is shown). Not yet checked in-game. The code is in `witpae/shipproduction.py`.

### LCU production

The "LCU production" sub-tab (after Ship production) is read-only and follows the idea of WitPTracker's LCU
Production view: what land units lack against their TOE, what arriving reinforcements will need, what that costs
in armament, vehicle and manpower points, and how that compares with the pools and the daily production.

- Controls: Side (Japanese default, or Allied), Window (7, 14, 30 default, 60, 90, 180, 365 days or All), a
  Units / Devices view switch, a Status filter for the Units view (All, Active, Reinforcement, Not scheduled,
  Not arrived (no date)) and a Search box. Double-click a unit to jump to it in the Land Units tab (its filters
  are cleared if they hide it). The summary table on top has one row per point type: pool, production per day,
  points lacking in arrived units, points needed by the reinforcements in the window, and the days of production
  that cover both.
- Lack of an arrived unit, per slot with a TOE device: TOE count - current count when the slot holds the TOE
  device or is empty (never below 0); when the slot holds a different device (an older model awaiting upgrade)
  the whole TOE count is lacking. Disabled devices repair and are not counted.
- A unit not yet arrived with days to arrival 1..window needs its whole TOE (every slot's TOE count of its TOE
  device). Units that are not scheduled or have no date are listed with no cost.
- Costs, from manual 13.2.2.6 and 13.2.2.7 (checked against the manual's text): a squad costs 1
  armament point plus manpower equal to its load cost; a weapon costs armament points equal to its load cost plus
  the same manpower; a vehicle costs vehicle points equal to its load cost plus the same manpower. Squads are
  device types 23 Squad and 24 Engineer; vehicles are 22 AFV and 25 Vehicle; every other type is a weapon.
- Manual 13.7: Japanese reinforcements must be filled from production when they arrive, otherwise they arrive
  at 25% TOE without charge. Allied units are fed from their device pools, so the report shows Allied lacks and
  pools but daily production (Armament 525, Vehicle 526 and Manpower 520 factories with production on, 1, 1 and
  5 points per size point per day) is only given for the Japanese.
- Device pools: the side's i32 at 8184 + 8 x device + 4 x side of section 0x01, the same table as the HI,
  armament and vehicle pools of Industry reports.

Save offsets: the land unit's days to arrival is the i16 at 564 of the record (section 0x13), found by a
countdown search (it drops by exactly 1 per game day across saves of 8, 9 and 11 Dec 41 for 2272 units); 0
means arrived (or no date), and 9999, 19999 and 29999 are shown as "Not scheduled". Device records (section 0x1f,
236 bytes) hold the name in the first 24 bytes, the device type as u8 at 26 and the load cost as i16 at 28 (the
ae-editor field map marks the load cost unverified; the values look right: IJA Infantry Squad 17, Support 10).
Device types (WitPTracker's names): 0 Aircraft Cannon, 1 GA Rocket, 2 PGM, 3 GP Bomb, 4 AP Bomb, 5 Drop Tank,
6 Radar Detect, 7 Jammer, 8 Nav Radar, 9 Aircraft Radar, 10 Surface Radar, 11 AA Rocket, 12 Flak, 13 Balloon,
14 Factory Machine, 15 ELINT, 16 Torpedo, 17 DP Gun, 18 Navy Gun, 19 Army Weapon, 20 ASW, 21 Mine, 22 AFV,
23 Squad, 24 Engineer, 25 Vehicle, 26 Resource, 27 Engine Factory. None of this is checked in the game yet. The
code is in `witpae/lcuproduction.py`.

### Industry reports

Three more sub-tabs cover factories, using the Region column and filter described
below. They are computed from the factory slots of every named location of type
0, 1 or 5 and are recomputed whenever the Reports tab is shown.

| Report | What it shows |
|---|---|
| Industry | Side (Allied or Japanese; sums across sides are meaningless) and Region filters. One row per factory type present: factories (slots), size, damaged, size with production off, size with repair off, daily output and daily input. Below it a "Daily balance" table for Oil, Resources, Fuel, Supply, Manpower, HI, Armament, Vehicle, Naval and Merchant points: stored (the places' own stocks for the first four, the side's production pool for the rest; `?` if the pools cannot be read), produced/day (factories), allotted/day, used/day, net/day (produced + allotted - used) and days left (stored / -net when net is negative; `-` for the pool rows when a region is selected, since a pool is side-wide) |
| Factories | One row per factory slot: place, kind, side, region, slot, factory, size, damage, production and repair switches, daily output and input. Side, Region and Factory type filters and "Only damaged or switched off" (damage, production off or repair off). Double-click jumps to the place in the Bases tab |
| Raw materials | One row per place: oil, resources, fuel and supply stored, their net daily rate from that place's own factories, and "Shortest", the material that runs out first at that rate (for example `Resources: 3 days`, `-` when nothing runs down). Default sort is shortest first; the Allotment/day column and the /day columns include the place's daily allotment; "Only places with industry" (default on) keeps places with at least one producing factory or a daily allotment. Double-click jumps to the place in the Bases tab |

Production rules (game manual 13.2), per factory size point per day, only for
factories with production switched on (production off uses and makes nothing).
Size is the working size; damage is extra capacity awaiting repair, shown but not
subtracted.

| Factory | Uses | Makes |
|---|---|---|
| Oil (518) | - | 10 oil |
| Resources (519) | - | 20 resources |
| Manpower (520) | - | 5 manpower |
| Heavy Industry (521) | 20 resources, 2 fuel | 2 HI points, 2 supply |
| Light Industry (527) | 15 resources | 1 supply |
| Refinery (528) | 10 oil | 9 fuel, 1 supply |
| Naval Shipyard (522) | 3 HI | 1 naval point |
| Merchant Shipyard (523) | 3 HI | 1 merchant point |
| Armament (525) | 6 HI | 1 armament point |
| Vehicle (526) | 6 HI | 1 vehicle point |
| Repair Shipyard (524) | - | - |
| Aircraft (2000+) factories | 18 HI x engines per aircraft per aircraft built; Japanese aircraft also use one engine per engine fitted (Allied aircraft need none) | size / 30 aircraft |
| Engine factories (a device id such as 237 or 1932) | 18 HI per engine | size / 30 engines |

Aircraft and engine rules are manual 13.2.2.4 and 13.2.2.5 (not yet checked in-game): the size of an
aircraft factory is planes per month, so planes per day = size / 30, HI per day = planes per day x 18 x
engines per aircraft (see the Aircraft tab), and a Japanese aircraft also uses planes per day x engines
engines per day. An aircraft factory whose model is not yet available on the game date (the date shown as
"(yy/m)" in the Bases tab) is researching: it builds and uses nothing yet, so it adds nothing to the
Industry tab's Aircraft row or the HI used. The game date comes from section 0x01; if it cannot be read, no
factory counts as researching. On the sample save (10 Dec 1941) 27 of the 33 Allied aircraft factories
(size 796 of 856) are still researching, so the Allied aircraft HI is 67.8 per day; with every model
available it would be 1096.2. WitPTracker shows 361 HI per day for the Allied airframes of this save, which
these rules do not reproduce; its rule is unknown.

Side-wide production pools (section 0x01): an i32 little-endian at byte
`8184 + 8 * device + 4 * side`, side 0 = Japan, 1 = Allies. Devices: 520 manpower,
521 HI points, 522 naval shipyard points, 523 merchant shipyard points, 525 armament
points, 526 vehicle points. A missing or short section is a format error and the
pool rows then show `?`. The same formula gives the side's pool of an engine: the device id of the engine
(for example 239 Hitachi (early), 242 Mitsubishi Ha-31, 244 Mitsubishi Ha-33) in place of the point
devices, with side 0 for Japan. The offset was found by reading WitPTracker's code; the Japanese values on
the sample save (239: 332, 242: 245, 243: 43, 244: 119, 237: 0) are what it reads there.

Daily allotments: in each location record (section 0x13), u16 at offset 824 = daily
supply, 826 = daily fuel, 828 = daily oil (830 is always 0 in the sample and is not
used). They are fixed amounts the game adds to the place every day.

Both were located by reading WitPTracker's compiled classes and checked against its
screens for both sides of the sample save (for example Allied supply production
139,041 and oil difference -15,270 per day, which the Allied balance reproduces).

Not included: supply used by units and fuel used by ships. There is no "not
building" estimate. For the Allied side of the sample save the totals match
WitPTracker's factory counts and sizes (Resources 252 factories / size 25969,
Manpower 181 / 1174, Light Industry 138 / 17836).

### Aircraft comparison

The last sub-tab shows two aircraft models side by side, like WitPTracker's Aircraft Comparison. Each column (A
and B) has a Side filter (All, Allied, Japanese), a Type filter and a model list ("name (#id), nation", since
several models share a name); A starts as the first Japanese fighter and B as the first Allied fighter. Below
each list is the model's side-view picture (see the Aircraft section), and under both a table with one row
per property: Type, Nation, Available (from to to), Upgrade, Engines, Max speed, Cruise speed, Climb, Max
altitude, Maneuver and the five altitude-band maneuver values, Durability, Armor, Max load, Max range, Normal
radius and Extended radius in hexes (with drop tanks in brackets when the model has them), Endurance (calculated),
Gun value, Carrier capable, Pool, and the armament of the max load and of the reduced load, one weapon per row
(name x count, facing). In the rows where higher is better (speeds, climb, altitude, maneuver, durability,
armor, load, ranges, endurance, gun value) the better value of the two starts with a triangle; equal values are
not marked. Ranges are compared with the drop-tank value when there is one. Service rating is not stored in
saves (it comes from the scenario data), so it is not shown. The code is in `witpae/aircraft.py` (`compare_rows`).

### Air production and Engines

Two more sub-tabs, after Raw materials, report aircraft and engine production for the whole map (minor
places included). Both follow the rules above and are not yet tested in-game.

Air production lists one row per aircraft model, with Search, Side (All, Allied, Japanese) and "Only
models in production or use" (default on: the model has a factory, a pool or an air group). Click a
heading to sort. Columns: ID, Aircraft, Type, Side, Engines ("2 x Nakajima Ha-5" for Japanese models,
"2 engines" for Allied ones), Pool and Used (the side's aircraft pool and the number used), Factories
(slots building the model, all states), Size (planes per month of factories with production on whose
model is available), Research (size of factories whose model is not yet available), Damaged (sum of the
factories' damage), Prod off (size of available factories with production off), Repair off (size of
factories with repair off), Planes/day (size / 30), HI/day (planes/day x 18 x engines), Engines/day
(Japanese models only, `-` for Allied), Groups and In groups (air groups that have arrived flying the model
and the planes they hold), Short (sum over those groups of maximum size minus planes, when positive), Next
group (smallest days to arrival, offset 220, among groups of the model that have not arrived, `-` if none;
many groups store 9999 or a large value there), and Available (from and to dates). Group fields are in `witpae/airgroups.py` (aircraft id i16 at 30, location i16 at 40 with 0 = not
yet arrived, planes u8 at 210, maximum size u8 at 245).

Select a model to list the factories building it below the table: place, kind, side, region, slot, size,
damage, Production and Repair (Yes/No), Upgrade (Keep/Upgd) and the availability date. Double-click
opens the place in the Bases tab. The buttons "Production on", "Production off", "Repair on" and "Repair
off" set that switch in every factory building the selected model (size, damage and the other switches
are kept), mark those bases as edited and report in the status bar how many factories changed. Only the
production-off byte (offset 844 + slot) and the repair-off byte (870 + slot) are written, so factories
whose stored damage is above their size (capacity still being built up, for example size 0 and damage 8)
are switched too. Production cannot be switched off for the locked industry types, which do not occur
among aircraft factories.

Engines lists the Japanese engines (every engine fitted to a Japanese model or built by a Japanese engine
factory; Allied aircraft use the generic engine and do not need engines): Factories, Size (engines per
month of factories with production on), Damaged, Prod off, Pool (the Japanese pool, see the formula above),
Needed/month (for every Japanese aircraft factory with production on and an available model, size x
engines per aircraft), Net/month (size - needed), HI/day (size / 30 x 18) and Used by (model names,
the first four and a count of the rest). The code is in `witpae/airproduction.py`.

Minor places: besides bases (type 1) and towns (type 5), the game has named
locations of type 0 that hold factories and stocks (for example Kofu, Corunna
Downs, Sholapur). The industry reports include them with the kind "Minor", and
double-clicking one jumps to it in the Bases tab. The spoilage report covers only
bases and towns, because it is unknown whether minor places spoil.

Regions: `witpae/data/regions/Kull_Regions_v131a.txt` is the region file by Kull
(version 1.31a, from the `region-mappings` folder of WitPTracker AE Release 1.11),
bundled unchanged (see the README next to it). Each line is location id, name,
region id and region name, TAB-separated with CR line endings, and the location ids
match the save's location table. Locations missing from the file (for example
Truscott, #1601) are "Unassigned". Region names can repeat under two ids ("Line
Islands" is 20 and 36), so the filter lists those with their id. The code is in
`witpae/industry.py` (rules and sums) and `witpae/regions.py` (file reader).

### Losses

The "Losses" sub-tab is read-only. A small table on top gives, per side, the ships sunk and the aircraft
lost this turn and in total (air, ground, flak, operations). Below it: a Side filter (All, Allied, Japanese), a
Ships sunk / Aircraft view switch, a Search box (ship or class name, aircraft model) and a sortable table. Double-click
a sunk ship to open it in the Ships tab (its filters are cleared if they hide it); aircraft rows do nothing.

- Ships sunk: ship records (section 0x08) whose days to arrival (i32 at 36) is 19999. Columns are ID, Ship, Side,
  Nation, Type, Class, Date, Cause, Location and Scuttled. The date is the year (u8 at 358, two digits), month (u8
  at 359) and day (u8 at 360), sorted by YYMMDD. The cause is the u16 at 348: below 2000 it is a device id and shows
  the device name (for example "18in Type 91 Torpedo", "800 kg AP Bomb"); 2000 to 2012 are Destroyed while
  building, Cancelled, Written off, Internal explosion, Grounding, Foundered, Marine casualty, Abandoned, Accident,
  Operational casualty, Hit obstruction, Collision and Kamikaze; anything else shows "Unknown (#n)". The location
  is the hex (x u16 at 352, y u16 at 354) and the base (u16 at 356): when x and y are both 0 the ship sank at that
  base and only the base name is shown, otherwise "x,y near <base>". Scuttled is the u8 at 363 being 1. The u16
  at 350 is unknown and not shown. The date shows the full year ("7 Dec 1941").
- Aircraft: aircraft records (section 0x20) hold eight i32 from offset 196: this turn's losses to air combat,
  on the ground, to flak and in operations, then the same four totals from 212. Models with all eight at 0 are
  not listed. The side is the aircraft's side byte (u8 at 228).
- The sample save (the 10 Dec 41 test save) has 14 sunk ships (Tennessee and Prince of Wales on 7 Dec 41, the
  Indianapolis on 8 Dec 41, three Japanese midget submarines) and 41 aircraft models with losses.
- The offsets come from WiTPTracker's reader and match the game data in the sample saves, but they have not been
  compared with the game's own screens yet. The ship bytes at 337 and 396 hold the other side's sinking claims
  (fog of war); they are not shown. The code is in `witpae/losses.py`.

### Ship repair

The "Ship repair" sub-tab (last) is read-only. A small table on top gives, per side, the damaged ships, how many
are at sea and in port, how many are in Shipyard repair mode and their total tonnage. Below it: a Side filter (All,
Allied, Japanese), a Ships / Ports view switch, a Search box (ship, class or location; port name) and a sortable
table. Double-click a ship to open it in the Ships tab, a port to open it in the Bases tab (filters are cleared if
they hide it).

- Ships: arrived ships (days to arrival 0) with any of the six damage values (fires, system, flotation, major
  flotation, engine, major engine; u8 at 331 to 336) above 0, or damaged weapon mounts. The u8 at 270 + k is the
  number of damaged mounts in weapon slot k (device u16 at 70 + 2k); the text reads like "2x 25mm Type 96 AA Gun".
  Priority is the u8 at 338 (Low, Normal, High, Critical), mode the u8 at 339 (Readiness, Pierside, Repair ship,
  Shipyard) and delay (days) the u16 at 342; other codes show "Unknown (n)". Tons is the class displacement (u16 at
  28 of the ship class). Min port is the smallest port size whose largest ship docked reaches the tonnage ("-" over
  84,000 t) and Min yard the tonnage in thousands, rounded up.
- Location: the base name of a docked ship; "TF n at <base>" for a task force whose hex is the hex of a base of its
  own side (an enemy base does not count); otherwise
  "TF n at sea x,y". Ships in port are grouped by that base for the Ports view.
- Ports: one row for each port holding a damaged ship, with port size, max and damage, the largest ship and total
  tonnage a port of that size can dock (manual 14.2 table), the repair yard (the factory of type 524: size and
  damage), the repair points a day (yard size x 10, manual 14.2.3.1) and the yard capacity (yard size x 1,000 t), the
  damaged ships there, their tonnage, the tonnage in Shipyard mode, the largest damaged ship, and "Too big": the
  number of damaged ships larger than both the port's largest ship and the yard capacity.
- The sample save has 105 damaged ships (69 Allied, 36 Japanese; for example Ushio and Tatsuta in task forces at sea,
  Java in a TF at Soerabaja, Amagisan Maru at Kagoshima). The offsets come from WiTPTracker's reader and match the sample saves;
  they have not been compared with the game's own screens yet. The code is in `witpae/shiprepair.py`.

## History

The History tab (after Reports) shows trends over the turns you have opened, like WiTPTracker. Nothing here writes
to a save.

- What is recorded: one snapshot per game date, both sides. Side metrics: supply, fuel, resources and oil stored
  (summed over the places of the Industry report, so the totals match WiTPTracker), the production pools (manpower,
  HI, naval, merchant, armament, vehicle), the daily supply, fuel and oil allotments, the aircraft pool, aircraft
  lost this turn and in total (air, ground, flak, operations), ships sunk, damaged ships, damaged tonnage and
  damaged ships in port. Per base: side, supply, fuel, resources and oil (only bases with some stock). Per aircraft
  model: pool and total losses. The metric table is `SIDE_METRICS` in `witpae/history.py`.
- Where: `<save folder>\history\<campaign>\<YYYYMMDD>.json.gz`, one gzip-compressed JSON file per date, written
  atomically (temporary file, then rename). A save in a folder called `autosave` uses the parent folder, so
  `SAVE\autosave\...` and `SAVE\...` share one history. The campaign is the scenario name from the save
  ("grand campaign"), lowercased. Known limitation: two campaigns of the same scenario share a folder. The player's side is not
  reliably stored in a save, so both sides are recorded and the tab filters.
- Auto-record: every save you open is recorded after it loads. The snapshot is written when no file exists for that
  date, or when the existing one came from a file with the same name (a refresh). Otherwise the existing snapshot is
  kept, so an edited copy of a save cannot overwrite a real turn; the tab then says "<date> already recorded from
  <file>" and the Record this save button (enabled only then) replaces it with the save as it is on disk. PBEM saves
  are never recorded. A recording failure (permissions, disk full) shows on the tab's status line and does not stop
  the save from opening.
- Import saves...: pick several .pws files (the dialog starts in the current save folder); each replaces the
  snapshot of its date in its own campaign folder. PBEM and unreadable files are skipped and reported ("2 imported,
  1 skipped (...)").
- Delete turn: removes the selected turn's file after asking.
- Views: Sides (a metric from the list, both sides or one) or Base (a base from the recorded ones, with a filter
  box, and Supply, Fuel, Resources or Oil). The Bases tab's History button opens the Base view for the selected
  base. The chart draws one line per side (blue Allied, red Japanese; in the Base view the colour is the owner of
  that turn); a turn without a value leaves a gap. The table lists the turns newest first with the change from the
  previous recorded turn. Base names come from the open save ("#id" if unknown).
- Aircraft view: pick a model (a filter box and a list like "A6M2 Zero (Japanese)"; the Aircraft tab's History button
  opens it for the selected model) and Pool, Lost (total), Lost in air combat, Lost on the ground, Lost to flak or
  Operational losses (all totals, not per turn). One line in the colour of the model's side. Snapshots only store
  models with a pool or losses, so a turn without the model counts as 0 once the model has appeared in the history,
  and is a gap before its first appearance.
- Files that cannot be read (corrupt, or another schema version) are skipped and named on the status line. Auto-record
  replaces a corrupt file for its own date but keeps one of another schema version. The snapshot has `"version": 1`; a future change of layout will raise it, and older
  editors then skip those files.

The code is in `witpae/history.py` (snapshots and files) and `witpae/chart.py` (the line chart).

## Backups

Always keep a copy of your saves before editing. Prefer saving to a new file
name rather than over the original, and test unverified fields on a copy.
