import os
import unittest

from witpae import bases, events, history, industry
from witpae.container import SaveFile

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
SAVE_015 = os.path.join(DATA_DIR, "going2_411210.pws")


def snap(date, **keys):
    """A hand-built snapshot with the given event keys."""
    return dict({"version": 1, "date": date, "turn": 1, "sides": {}, "bases": {}, "aircraft": {}}, **keys)


def full(date, **keys):
    base = {"places": {}, "ships": {}, "units": [], "groups": []}
    return snap(date, **dict(base, **keys))


NAMES = {
    (events.PLACE, 5): ("Wake Island", "Allied", (10, 20)),
    (events.SHIP, 7): ("Lexington", "Allied", None),
    (events.LAND_UNIT, 3): ("1st Marines", "Allied", None),
    (events.AIR_GROUP, 4): ("VF-3", "Allied", None),
    (events.LEADER, 9): ("Nimitz", "Allied", None),
}


class BetweenTests(unittest.TestCase):
    def test_capture(self):
        out = events.events_between(full(411210, places={"5": 1, "6": 0}), full(411211, places={"5": 0, "6": 0}), NAMES)
        self.assertEqual(out, [events.Event(411211, "Base captured", "Japanese", "place", 5, "Wake Island",
                                            "Allied -> Japanese", 10, 20)])

    def test_ship_arrival_and_sinking(self):
        prev = full(411210, ships={"1": 1, "2": 0, "3": 1, "4": 2, "7": 1})
        cur = full(411211, ships={"1": 0, "2": 2, "3": 2, "4": 2, "7": 0})
        out = events.events_between(prev, cur, NAMES)
        self.assertEqual(sorted((e.kind, e.subject_id) for e in out),
                         [("Ship arrived", 1), ("Ship arrived", 7), ("Ship sunk", 2), ("Ship sunk", 3)])
        lexington = next(e for e in out if e.subject_id == 7)
        self.assertEqual((lexington.subject, lexington.side, lexington.subject_kind, lexington.x, lexington.y),
                         ("Lexington", "Allied", "ship", None, None))
        unknown = next(e for e in out if e.subject_id == 1)
        self.assertEqual((unknown.subject, unknown.side), ("ship 1", ""))

    def test_unit_and_group_arrival(self):
        out = events.events_between(full(411210, units=[1], groups=[2]), full(411211, units=[1, 3], groups=[2, 4]),
                                    NAMES)
        self.assertEqual([(e.kind, e.subject_kind, e.subject_id, e.subject) for e in out],
                         [("Land unit arrived", "land unit", 3, "1st Marines"),
                          ("Air group arrived", "air group", 4, "VF-3")])

    def test_leader_rating_change_from_the_log(self):
        log = {"version": 1, "date": 411212, "ratings": {}, "changes": [
            [411211, 9, "36" + "3c" + "0a" * 5, "38" + "3a" + "0a" * 5], [411212, 10, "01" * 7, "01" * 7]]}
        out = events.leader_events(log, NAMES)
        self.assertEqual(len(out), 1)  # leader 10 did not change
        e = out[0]
        self.assertEqual(e.date, 411211)
        self.assertEqual((e.kind, e.subject_kind, e.subject, e.side), ("Leader skill changed", "leader", "Nimitz",
                                                                       "Allied"))
        self.assertEqual(e.detail, "Leadership 54 -> 56, Inspiration 60 -> 58")

    def test_missing_keys_skip_that_kind(self):
        prev = snap(411210, places={"5": 1}, ships={"7": 1})
        cur = full(411211, places={"5": 0}, ships={"7": 0}, units=[3], groups=[4])
        self.assertEqual({e.kind for e in events.events_between(prev, cur, NAMES)}, {"Base captured", "Ship arrived"})
        self.assertEqual(events.events_between(snap(411210), cur, NAMES), [])
        self.assertEqual(events.events_between(cur, snap(411212), NAMES), [])

    def test_ids_in_one_snapshot_only_are_ignored(self):
        prev = full(411210, places={"5": 1}, ships={"7": 1})
        cur = full(411211, places={"6": 0}, ships={"8": 2})
        self.assertEqual(events.events_between(prev, cur, NAMES), [])

    def test_events_follow_kinds_order(self):
        prev = full(411210, places={"5": 1}, ships={"7": 1})
        cur = full(411211, places={"5": 0}, ships={"7": 2}, groups=[4], units=[3])
        self.assertEqual([e.kind for e in events.events_between(prev, cur, NAMES)],
                         ["Base captured", "Ship sunk", "Land unit arrived", "Air group arrived"])


class AllEventsTests(unittest.TestCase):
    def test_dates_and_order(self):
        snaps = [full(411212, places={"5": 0}), full(411210, places={"5": 1}), full(411211, places={"5": 1})]
        result = events.all_events(snaps, NAMES)
        self.assertEqual([(e.date, e.kind) for e in result.events], [(411212, "Base captured")])
        self.assertEqual(result.skipped, [])
        flip = [full(411210, places={"5": 1}), full(411211, places={"5": 0}), full(411212, places={"5": 1})]
        self.assertEqual([(e.date, e.detail) for e in events.all_events(flip, NAMES).events],
                         [(411211, "Allied -> Japanese"), (411212, "Japanese -> Allied")])
        self.assertEqual(events.all_events([], NAMES), ([], []))
        self.assertEqual(events.all_events(snaps[:1], NAMES), ([], []))

    def test_log_changes_join_the_snapshot_events_by_date(self):
        log = {"version": 1, "date": 411212, "ratings": {}, "changes": [[411212, 9, "01" * 7, "02" * 7]]}
        snaps = [full(411210, places={"5": 1}), full(411211, places={"5": 0}), full(411212, places={"5": 0})]
        result = events.all_events(snaps, NAMES, log)
        self.assertEqual([(e.date, e.kind) for e in result.events],
                         [(411211, "Base captured"), (411212, "Leader skill changed")])
        self.assertEqual(result.events[1].detail, "Leadership 1 -> 2, Inspiration 1 -> 2, Naval 1 -> 2, Air 1 -> 2, "
                                                  "Land 1 -> 2, Admin 1 -> 2, Aggression 1 -> 2")
        self.assertEqual(events.all_events(snaps, NAMES, None).events, result.events[:1])

    def test_pairs_with_missing_keys_are_reported(self):
        snaps = [snap(411210), snap(411211, places={"5": 1}), full(411212, places={"5": 0}),
                 full(411213, places={"5": 1})]
        result = events.all_events(snaps, NAMES)
        self.assertEqual([(s.date, s.keys) for s in result.skipped],
                         [(411211, list(history.EVENT_KEYS)), (411212, ["ships", "units", "groups"])])
        self.assertEqual([e.date for e in result.events], [411212, 411213])  # places are in both of those pairs
        self.assertEqual(events.without_event_data(snaps), [411210, 411211])


@unittest.skipUnless(os.path.exists(SAVE_015), "sample save missing")
class SaveTests(unittest.TestCase):
    def test_names_and_a_captured_base(self):
        before = SaveFile.load(SAVE_015)
        after = SaveFile.load(SAVE_015)
        data = after[bases.INDEX_SECTION].data
        pos = 584 * bases.INDEX_RECORD_SIZE + bases.SIDE_OFFSET
        data[pos:pos + 4] = (0).to_bytes(4, "little")  # Pearl Harbor goes to the Japanese
        places = industry.list_industry_places(before)
        a = history.build_snapshot(before, "a.pws", places)
        b = history.build_snapshot(after, "b.pws", industry.list_industry_places(after))
        b["date"] = a["date"] + 1
        names = events.event_names(before)
        self.assertEqual(names[events.PLACE, 584][:2], ("Pearl Harbor", "Allied"))
        self.assertEqual(names[events.PLACE, 584][2], bases.place_hex(before, 584))
        result = events.all_events([a, b], names)
        self.assertEqual(result.skipped, [])
        self.assertEqual(len(result.events), 1)
        e = result.events[0]
        self.assertEqual((e.kind, e.side, e.subject, e.detail), ("Base captured", "Japanese", "Pearl Harbor",
                                                                  "Allied -> Japanese"))
        self.assertEqual((e.x, e.y), bases.place_hex(before, 584))
        self.assertEqual(names[events.SHIP, 3002][1], "Allied")


if __name__ == "__main__":
    unittest.main()
