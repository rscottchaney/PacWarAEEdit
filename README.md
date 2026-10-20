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
| Supply cap (the "max" on the base screen), Garrison required (Allied) | values verified against game screens, editable (edit not yet tested in-game) |
| Garrison required (Japanese) | unverified (not yet checked on a Japanese-held base), editable |
| Supply required, Aviation support, Ships in port, Aircraft at base | verified, display only (recalculated by the game) |

Towns are listed in the Bases tab too (Type column) and edited the same way, except
that towns have no port, so Port size, Port max, Port damage and the Port build
switch are read-only for them.

Name, side and hex coordinates are read-only. The field table is in
`witpae/bases.py`; adding a field is one line.

## Aircraft

The Aircraft tab lists the aircraft table (section 0x20) with search and
sortable columns. Several models share a name (one per nation), so always check
the ID. Edits use the same Apply button, row highlight and Save As as bases.

| Field | Status |
|---|---|
| Max speed, Cruise speed, Climb, Maneuver, Armor, Durability, Load | verified in-game, editable |
| Production rate, In pool (side-wide aircraft pool) | verified in-game, editable |
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
| Upgrade (id and name of the record it points at) | unverified, read-only |

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
| Pilot and commander "Age?" | unverified, read-only |

Each pilot skill is stored twice (bytes 65..76 and 78..89). The game's pilot
list shows the second copy, so edits write both. The byte at 122 is left
alone because its purpose is unknown. The commander box is disabled for groups without a commander.

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

## Reports

The Reports tab holds five read-only reports; nothing in them edits the save. It
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

### Industry reports

Three more sub-tabs cover factories, using the Region column and filter described
below. They are computed from the factory slots of every named location of type
0, 1 or 5 and are recomputed whenever the Reports tab is shown.

| Report | What it shows |
|---|---|
| Industry | Side (Allied or Japanese; sums across sides are meaningless) and Region filters. One row per factory type present: factories (slots), size, damaged, size with production off, size with repair off, daily output and daily input. Below it a "Daily balance (factories only)" table for Oil, Resources, Fuel, Supply, Manpower and HI points: stored (the places' own stocks; `?` for manpower and HI, whose side-wide pools are not mapped), produced/day, used/day, net/day and days left (stored / -net when net is negative) |
| Factories | One row per factory slot: place, kind, side, region, slot, factory, size, damage, production and repair switches, daily output and input. Side, Region and Factory type filters and "Only damaged or switched off" (damage, production off or repair off). Double-click jumps to the place in the Bases tab |
| Raw materials | One row per place: oil, resources, fuel and supply stored, their net daily rate from that place's own factories, and "Shortest", the material that runs out first at that rate (for example `Resources: 3 days`, `-` when nothing runs down). Default sort is shortest first; "Only places with industry" (default on) keeps places with at least one producing factory. Double-click jumps to the place in the Bases tab |

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
| Aircraft (2000+) and engine (below 500) factories | HI, unknown (shown as `-`) | size / 30 aircraft or engines |

Not included: supply used by units, fuel used by ships, daily supply and fuel
allotments, and the side-wide HI and manpower pools. There is no "not building"
estimate. For the Allied side of the sample save the totals match WitPTracker's
factory counts and sizes (Resources 252 factories / size 25969, Manpower 181 /
1174, Light Industry 138 / 17836); WitPTracker also adds daily allotments that are
not stored in the fields known here, so its oil, fuel and supply production are
higher.

Minor places: besides bases (type 1) and towns (type 5), the game has named
locations of type 0 that hold factories and stocks (for example Kofu, Corunna
Downs, Sholapur). The industry reports include them with the kind "Minor". The
Bases tab does not list them, so double-clicking one only shows a message in the
status bar.

Regions: `witpae/data/regions/Kull_Regions_v131a.txt` is the region file by Kull
(version 1.31a, from the `region-mappings` folder of WitPTracker AE Release 1.11),
bundled unchanged (see the README next to it). Each line is location id, name,
region id and region name, TAB-separated with CR line endings, and the location ids
match the save's location table. Locations missing from the file (for example
Truscott, #1601) are "Unassigned". Region names can repeat under two ids ("Line
Islands" is 20 and 36), so the filter lists those with their id. The code is in
`witpae/industry.py` (rules and sums) and `witpae/regions.py` (file reader).

## Backups

Always keep a copy of your saves before editing. Prefer saving to a new file
name rather than over the original, and test unverified fields on a copy.
