import os
import tempfile
import unittest

from witpae import combat, intel

DASHES = "-" * 80

# Synthetic text in the shapes of the game's combatreport files.
REPORT = [
    "AFTER ACTION REPORTS FOR Dec 10, 41",
    DASHES,
    "Morning Air attack on TF, near Legaspi at 82,82",
    " ",
    "Weather in hex: Clear sky",
    " ",
    "Japanese aircraft",
    "      G4M1 Betty x 12",
    "      A6M2 Zero x 6",
    " ",
    "Allied aircraft",
    "      B-17D Fortress x 4",
    " ",
    "Japanese aircraft losses",
    "      G4M1 Betty: 2 destroyed, 3 damaged",
    "      A6M2 Zero: 1 destroyed by flak",
    " ",
    "Allied aircraft losses",
    "      B-17D Fortress: 1 destroyed",
    "      B-17D Fortress: 2 damaged",
    " ",
    "Japanese Ships",
    "      CA Atago, Bomb hits 2, Torpedo hits 1,  heavy fires,  heavy damage",
    "      BB Kongo",
    "      DD Oite, Shell hits 1",
    " ",
    "Allied Ships",
    "      PT-34, Bomb hits 1, and is sunk",
    "      xAK Ewa",
    " ",
    "Aircraft Attacking:",
    "       4 x B-17D Fortress bombing from 15000 feet",
    " ",
    " ",
    DASHES,
    "Afternoon Air attack on Hong Kong , at 77,61 ",
    "Allied aircraft",
    "      no flights",
    "No Allied losses",
    " ",
    "Allied aircraft losses",
    "      Hudson I: 4 destroyed on ground",
    "      Hudson I: 1 damaged",
    DASHES,
    "Night Air attack on 40th Chinese Corps, at 88,44 (Chengchow)",
    "No Japanese losses",
    DASHES,
    "Day Time Surface Combat, near Midway Island at 158,91",
    DASHES,
    "Morning Air attack on Hong Kong Fortress, at 77,61 (Hong Kong)",
    DASHES,
    "Amphibious Assault at Makin (136,125)",
    " ",
    "Allied ground losses:",
    "      3 casualties reported",
    "         Squads: 2 destroyed, 5 disabled",
    "         Non Combat: 1 destroyed, 0 disabled",
    "         Engineers: 0 destroyed, 3 disabled",
    "      Guns lost 4 (2 destroyed, 2 disabled)",
    " ",
    "Japanese ground losses:",
    "      Vehicles lost 3 (3 destroyed, 0 disabled)",
    "      Units destroyed 1",
    DASHES,
    "Ground combat at 71,56 (near Lang Son)",
    " ",
    "Japanese Deliberate attack",
    " ",
    "Attacking force 3517 troops, 32 guns, 0 vehicles, Assault Value = 118",
    " ",
    "Defending force 8114 troops, 33 guns, 0 vehicles, Assault Value = 160",
    " ",
    "Allied ground losses:",
    "      50 casualties reported",
    "         Squads: 0 destroyed, 6 disabled",
    "         Engineers: 1 destroyed, 0 disabled",
    DASHES,
    "Invasion Support action off Wake Island (136,98)",
    DASHES,
    "Pre-Invasion action off Miri (64,87) - Coastal Guns Fire Back!",
    DASHES,
    "ASW attack near Laoag  at 80,71",
    DASHES,
    "Sub attack near Takao  at 84,66",
    DASHES,
    "Submarine attack near Takao  at 84,66",
    DASHES,
    "Sub vs Sub: SS I-175 attacking SS Dolphin  at 178,105  - near Lihue",
    DASHES,
    "Naval bombardment of Midway Island at 158,91 - Coastal Guns Fire Back!",
    DASHES,
    "TF 156 encounters mine field at Bataan (78,77)",
    "Allied Ships",
    "      SS Tarpon, Mine hits 1,  on fire,  heavy damage",
    DASHES,
    "Night Time Surface Combat at 50,50",
    DASHES,
    "Something the game may add one day",
    DASHES,
    DASHES,
    " ",
    DASHES,
]


def write(folder, name, lines, newline="\r\n"):
    with open(os.path.join(folder, name), "wb") as f:
        f.write(newline.join(lines).encode("latin-1") + newline.encode())


def action(actions, fragment):
    return next(a for a in actions if fragment in a.title)


class CombatTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.folder = tmp.name
        write(self.folder, "combatreport_411210.txt", REPORT)
        self.actions = combat.load_actions(self.folder)

    def test_block_splitting(self):
        # Header, leading/trailing/doubled separators and blank blocks add nothing; Other blocks are kept.
        self.assertEqual(len(self.actions), 17)
        self.assertTrue(all(a.date == 411210 for a in self.actions))
        self.assertEqual([a.index for a in self.actions], list(range(1, 18)))
        self.assertEqual(self.actions[0].title, "Morning Air attack on TF, near Legaspi at 82,82")
        self.assertEqual(self.actions[-1].title, "Something the game may add one day")

    def test_kinds_and_phases(self):
        expected = {
            "near Legaspi": ("Air attack", "Morning"), "Hong Kong ,": ("Air attack", "Afternoon"),
            "40th Chinese": ("Air attack", "Night"), "Day Time": ("Surface combat", "Day"),
            "Amphibious": ("Amphibious assault", ""), "Ground combat": ("Ground combat", ""),
            "Invasion Support": ("Invasion support", ""), "Pre-Invasion": ("Pre-invasion", ""),
            "ASW": ("ASW", ""), "Sub attack": ("Submarine", ""), "Submarine attack": ("Submarine", ""),
            "Sub vs Sub": ("Sub vs sub", ""), "bombardment": ("Bombardment", ""), "mine field": ("Mine field", ""),
            "Night Time": ("Surface combat", "Night"), "may add": ("Other", "")}
        for fragment, (kind, phase) in expected.items():
            a = action(self.actions, fragment)
            self.assertEqual((a.kind, a.phase), (kind, phase), fragment)
        self.assertEqual({a.kind for a in self.actions}, set(combat.KINDS))

    def test_places(self):
        expected = {
            "near Legaspi": ("Legaspi", 82, 82),  # a TF is the target, the place follows "near"
            "Hong Kong ,": ("Hong Kong", 77, 61),  # a base is both target and place
            "40th Chinese": ("Chengchow", 88, 44),  # a land unit: the place is the name in brackets
            "Hong Kong Fortress": ("Hong Kong", 77, 61),
            "Amphibious": ("Makin", 136, 125), "Ground combat": ("Lang Son", 71, 56),
            "Invasion Support": ("Wake Island", 136, 98), "Pre-Invasion": ("Miri", 64, 87),
            "ASW": ("Laoag", 80, 71), "Sub attack": ("Takao", 84, 66), "Sub vs Sub": ("Lihue", 178, 105),
            "bombardment": ("Midway Island", 158, 91), "mine field": ("Bataan", 78, 77),
            "Night Time": ("", 50, 50), "may add": ("", None, None), "Day Time": ("Midway Island", 158, 91)}
        for fragment, (place, x, y) in expected.items():
            a = action(self.actions, fragment)
            self.assertEqual((a.place, a.x, a.y), (place, x, y), fragment)

    def test_air_and_ships(self):
        a = self.actions[0]
        self.assertEqual((a.japanese_aircraft, a.allied_aircraft), (18, 4))
        self.assertEqual((a.japanese_air_lost, a.allied_air_lost), (3, 1))  # destroyed only, flak included
        self.assertEqual((a.japanese_ships, a.allied_ships), (3, 2))
        self.assertEqual(a.ships_hit, 3)  # Atago, Oite and the PT boat; Kongo and Ewa have no damage
        self.assertEqual((a.allied_ships_sunk, a.japanese_ships_sunk), (1, 0))
        self.assertEqual(a.ships[0], combat.Ship("Japanese", "CA Atago",
                                                 "Bomb hits 2, Torpedo hits 1, heavy fires, heavy damage"))
        self.assertEqual(a.ships[1], combat.Ship("Japanese", "BB Kongo", ""))
        self.assertEqual(a.ships[3], combat.Ship("Allied", "PT-34", "Bomb hits 1, and is sunk"))
        self.assertIn("Aircraft Attacking:", a.text)  # the whole block is kept
        hk = action(self.actions, "Hong Kong ,")
        self.assertEqual((hk.allied_aircraft, hk.allied_air_lost, hk.japanese_air_lost), (0, 4, 0))
        mine = action(self.actions, "mine field")
        self.assertEqual((mine.allied_ships, mine.ships_hit, mine.allied_ships_sunk), (1, 1, 0))

    def test_ground(self):
        makin = action(self.actions, "Amphibious")
        self.assertEqual((makin.allied_ground_lost, makin.japanese_ground_lost), (5, 3))
        self.assertEqual((makin.attack_value, makin.defence_value), (None, None))
        lang = action(self.actions, "Ground combat")
        self.assertEqual((lang.allied_ground_lost, lang.japanese_ground_lost), (1, 0))
        self.assertEqual((lang.attack_value, lang.defence_value), (118, 160))

    def test_select_and_totals(self):
        air = combat.select(self.actions, "Air attack")
        self.assertEqual(len(air), 4)
        self.assertEqual(len(combat.select(self.actions, "All", "lang son")), 1)
        self.assertEqual(len(combat.select(self.actions, "All", "", "With ships sunk")), 1)
        self.assertEqual(len(combat.select(self.actions, "All", "", "With aircraft lost")), 2)
        self.assertEqual(combat.select(self.actions, "ASW", "legaspi"), [])
        self.assertEqual(combat.totals(air), {"actions": 4, "allied_air_lost": 5, "japanese_air_lost": 3,
                                              "allied_ships_sunk": 1, "japanese_ships_sunk": 0})

    def test_dates_and_undated_copy(self):
        write(self.folder, "combatreport_411209.txt", ["AFTER ACTION REPORTS FOR Dec 9, 41", DASHES,
                                                       "ASW attack near Laoag  at 80,71"])
        write(self.folder, "combatreport.txt", REPORT)  # a copy of a turn that has its own file: ignored
        actions = combat.load_actions(self.folder)
        self.assertEqual(len(actions), 18)
        self.assertEqual([a.date for a in actions][:2], [411209, 411210])
        self.assertEqual(len(combat.select(intel.recent(actions, 1))), 17)
        # An undated file alone (or of a new turn) is used, dated by its header.
        write(self.folder, "combatreport.txt", ["AFTER ACTION REPORTS FOR Dec 11, 41", DASHES, "Ground combat at 1,2"])
        actions = combat.load_actions(self.folder)
        self.assertEqual((len(actions), actions[-1].date, actions[-1].kind), (19, 411211, "Ground combat"))

    def test_cr_only_and_missing(self):
        write(self.folder, "combatreport_411210.txt", REPORT, newline="\r")
        self.assertEqual(len(combat.load_actions(self.folder)), 17)
        write(self.folder, "combatreport_411210.txt", REPORT, newline="\n")
        self.assertEqual(len(combat.load_actions(self.folder)), 17)
        self.assertEqual(combat.load_actions(os.path.join(self.folder, "nope")), [])
        self.assertEqual(combat.load_actions(None), [])
        write(self.folder, "Combat_Events_411210.txt", ["Morning Air attack on Iba , at 78,75"])
        self.assertEqual(len(combat.load_actions(self.folder)), 17)  # engine logs are ignored


if __name__ == "__main__":
    unittest.main()
