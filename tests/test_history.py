import gzip
import json
import os
import tempfile
import unittest
from unittest import mock

from witpae import bases, chart, history, industry, losses, shiprepair
from witpae.container import SaveFile

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
SAVE_015 = os.path.join(DATA_DIR, "going2_411210.pws")


class Section:
    def __init__(self, data):
        self.data = data


def scenario_save(text):
    """A save holding just section 0x01 with the scenario name."""
    data = bytearray(70000)
    data[64932:64932 + len(text)] = text
    return {1: Section(data)}


@unittest.skipUnless(os.path.exists(SAVE_015), "sample save missing")
class SnapshotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.save = SaveFile.load(SAVE_015)
        cls.places = industry.list_industry_places(cls.save)
        cls.snap = history.build_snapshot(cls.save, "going2_411210.pws", cls.places)

    def test_header(self):
        s = self.snap
        self.assertEqual((s["version"], s["date"], s["turn"], s["scenario"], s["source"]),
                         (1, 411210, 4, "grand campaign", "going2_411210.pws"))
        self.assertEqual(history.game_date(self.save), (411210, 4))
        self.assertEqual(history.snapshot_name(411210), "19411210.json.gz")
        self.assertEqual(history.date_of_name("19411210.json.gz"), 411210)
        self.assertIsNone(history.date_of_name("notes.json.gz"))
        self.assertEqual(set(s["sides"]), {"Allied", "Japanese"})
        for metrics in s["sides"].values():
            self.assertEqual(list(metrics), list(history.SIDE_METRICS))

    def test_stock_totals_match_industry_report(self):
        for side in history.SIDE_NAMES:
            _types, balance = industry.summarize(industry.filter_places(self.places, side=side))
            stored = {r.material: r.stored for r in balance}
            for key in history.STOCK_KEYS:
                self.assertEqual(self.snap["sides"][side][key], stored[key], (side, key))
        self.assertEqual(self.snap["sides"]["Allied"]["supply"], 5590712)
        self.assertEqual(self.snap["sides"]["Japanese"]["oil"], 3207504)

    def test_pools_and_allotments(self):
        pools = industry.side_pools(self.save)
        for side, side_id in history.SIDE_IDS.items():
            for key, value in pools[side_id].items():
                self.assertEqual(self.snap["sides"][side][key], value)
        self.assertEqual(self.snap["sides"]["Japanese"]["hi"], 58193)
        self.assertEqual(self.snap["sides"]["Allied"]["allot_supply"], 98992)
        self.assertEqual(self.snap["sides"]["Allied"]["aircraft_pool"], 670)

    def test_losses_and_repair_match_reports(self):
        sunk = losses.sunk_ships(self.save)
        summary = {s.side: s for s in losses.summary_rows(sunk, losses.aircraft_losses(self.save))}
        repair = {s.side: s for s in shiprepair.summary_rows(shiprepair.damaged_ships(self.save))}
        for side in history.SIDE_NAMES:
            m = self.snap["sides"][side]
            self.assertEqual((m["ships_sunk"], m["loss_total"], m["loss_turn_total"]),
                             (summary[side].ships, summary[side].total, summary[side].turn_total))
            self.assertEqual((m["damaged_ships"], m["damaged_tons"], m["damaged_in_port"]),
                             (repair[side].ships, repair[side].tons, repair[side].in_port))
        a = self.snap["sides"]["Allied"]
        self.assertEqual((a["ships_sunk"], a["loss_total"], a["damaged_ships"]), (11, 184, 69))
        self.assertEqual(self.snap["sides"]["Japanese"]["damaged_tons"], 101365)

    def test_mines_laid(self):
        self.assertEqual(history.SIDE_METRICS["mines"], "Mines laid")
        self.assertEqual((self.snap["sides"]["Allied"]["mines"], self.snap["sides"]["Japanese"]["mines"]),
                         (10108, 8988))

    def test_victory_points(self):
        self.assertEqual(history.SIDE_METRICS["vp"], "Victory points")
        self.assertEqual((self.snap["sides"]["Allied"]["vp"], self.snap["sides"]["Japanese"]["vp"]), (11303, 2165))

    def test_bases_and_aircraft_entries(self):
        pearl = self.snap["bases"]["584"]
        self.assertEqual(pearl[:2], [1, 982531])
        self.assertTrue(all(any(e[1:]) for e in self.snap["bases"].values()))
        self.assertEqual(len(self.snap["bases"]), 874)
        for entry in self.snap["aircraft"].values():
            self.assertEqual(len(entry), 6)
            self.assertTrue(entry[1] or any(entry[2:]))
        self.assertEqual(sum(e[1] for e in self.snap["aircraft"].values() if e[0] == 1), 670)

    def test_json_serialisable(self):
        self.assertEqual(json.loads(json.dumps(self.snap)), self.snap)

    def test_event_keys(self):
        s = self.snap
        self.assertEqual(history.VERSION, 1)
        self.assertTrue(all(k in s for k in history.EVENT_KEYS))
        self.assertEqual(s["places"]["584"], 1)  # Pearl Harbor, Allied
        self.assertEqual(s["places"]["222"], 0)  # Akita, Japanese
        self.assertEqual(s["ships"]["3002"], history.SHIP_ARRIVED)  # Lexington
        self.assertEqual(s["ships"]["3152"], history.SHIP_SUNK)
        self.assertIn(history.SHIP_PENDING, s["ships"].values())
        self.assertEqual(s["units"], sorted(s["units"]))
        self.assertEqual(s["groups"], sorted(s["groups"]))
        self.assertTrue(s["units"] and s["groups"])
        self.assertNotIn("leaders", s)  # the ratings live in the campaign's leader log
        ratings = history.leader_ratings(self.save)
        self.assertTrue(ratings and all(len(v) == 14 for v in ratings.values()))  # seven bytes as hex

    def test_units_leave_out_fragments_and_unarrived(self):
        from witpae import landunits
        arrived = {u.id: (u.side, u.display_name) for u in landunits.list_land_units(self.save) if u.arrived}
        self.assertEqual(set(self.snap["units"]) - set(arrived), set())
        keys = [arrived[i] for i in self.snap["units"]]
        self.assertEqual(len(keys), len(set(keys)))  # one record per side and name
        self.assertLess(len(self.snap["units"]), len(arrived))  # the sample has fragment records


class PathTests(unittest.TestCase):
    def test_slug(self):
        self.assertEqual(history.slug("Grand Campaign"), "grand-campaign")
        self.assertEqual(history.slug("  Scen #2: Coral Sea!! "), "scen-2-coral-sea")
        self.assertEqual(history.slug(""), "unknown")
        self.assertEqual(history.slug("***"), "unknown")

    def test_scenario_name_is_nul_terminated_and_capped(self):
        self.assertEqual(history.scenario_name(scenario_save(b"Caf\xe9 One\0zzz")), "Caf\xe9 One")
        self.assertEqual(len(history.scenario_name(scenario_save(b"a" * 150))), 100)
        self.assertEqual(history.scenario_name({}), "")

    def test_campaign_dir(self):
        save = scenario_save(b"grand campaign")
        base = os.path.abspath(os.path.join("x", "SAVE"))
        expected = os.path.join(base, "history", "grand-campaign")
        self.assertEqual(history.campaign_dir(save, os.path.join(base, "a.pws")), expected)
        for name in ("autosave", "AutoSave"):
            self.assertEqual(history.campaign_dir(save, os.path.join(base, name, "w_#26_19411210.pws")), expected)
        self.assertEqual(history.campaign_dir(save, os.path.join(base, "other", "a.pws")),
                         os.path.join(base, "other", "history", "grand-campaign"))
        root = os.path.abspath("r")
        self.assertEqual(history.campaign_dir(save, os.path.join(base, "a.pws"), root=root),
                         os.path.join(root, "grand-campaign"))


def fake_snap(date, turn, allied, japanese, bases_=None):
    return {"version": 1, "date": date, "turn": turn, "scenario": "s", "source": "a.pws", "recorded": "t",
            "sides": {"Allied": {"supply": allied}, "Japanese": {"supply": japanese}},
            "bases": bases_ or {}, "aircraft": {}}


@unittest.skipUnless(os.path.exists(SAVE_015), "sample save missing")
class FileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.save = SaveFile.load(SAVE_015)
        cls.places = industry.list_industry_places(cls.save)

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = self._tmp.name
        self.root = os.path.join(self.tmp, "hist")
        self.folder = os.path.join(self.root, "grand-campaign")
        self.path = os.path.join(self.folder, "19411210.json.gz")

    def record(self, name="a.pws", **kw):
        return history.record(self.save, os.path.join(self.tmp, name), root=self.root, places=self.places, **kw)

    def test_atomic_write_and_roundtrip(self):
        snap = history.build_snapshot(self.save, "a.pws", self.places)
        path = history.write_snapshot(self.folder, snap)
        self.assertEqual(path, self.path)
        self.assertEqual(os.listdir(self.folder), ["19411210.json.gz"])  # no temporary file left behind
        self.assertEqual(history.read_snapshot(path), snap)
        history.write_snapshot(self.folder, dict(snap, turn=9))
        self.assertEqual(history.read_snapshot(path)["turn"], 9)
        self.assertEqual(os.listdir(self.folder), ["19411210.json.gz"])

    def test_snapshot_without_the_event_keys_still_reads(self):
        snap = history.build_snapshot(self.save, "a.pws", self.places)
        old = {k: v for k, v in snap.items() if k not in history.EVENT_KEYS}
        path = history.write_snapshot(self.folder, old)
        self.assertEqual(history.read_snapshot(path), old)
        self.assertEqual(self.record("a.pws").status, history.REFRESHED)  # same source: refreshed with the new keys
        self.assertIn("places", history.read_snapshot(path))

    def test_snapshot_with_a_leaders_key_still_reads(self):
        snap = dict(history.build_snapshot(self.save, "a.pws", self.places), leaders={"1": "00" * 7})
        self.assertEqual(history.read_snapshot(history.write_snapshot(self.folder, snap)), snap)

    def test_record_creates_the_leader_log_and_a_kept_snapshot_leaves_it(self):
        log_path = os.path.join(self.folder, history.LEADER_LOG)
        self.assertEqual(self.record("a.pws").status, history.RECORDED)
        log = history.read_leader_log(self.folder)
        self.assertEqual((log["date"], log["changes"]), (411210, []))
        self.assertEqual(log["ratings"], history.leader_ratings(self.save))
        self.assertEqual(sorted(os.listdir(self.folder)), ["19411210.json.gz", history.LEADER_LOG])
        sentinel = dict(log, ratings={"1": "00" * 7})
        history.update_leader_log(self.tmp, 411209, {})  # not the campaign folder: nothing to compare with
        history._write_gzip_json(self.folder, history.LEADER_LOG, sentinel)
        with open(log_path, "rb") as f:
            before = f.read()
        self.assertEqual(self.record("b.pws").status, history.KEPT)
        with open(log_path, "rb") as f:
            self.assertEqual(f.read(), before)
        self.assertEqual(self.record("a.pws").status, history.REFRESHED)  # same date as the log: ratings replaced
        self.assertEqual(history.read_leader_log(self.folder)["ratings"], history.leader_ratings(self.save))

    def test_leader_log_rules(self):
        a, b, c = {"1": "01" * 7, "2": "02" * 7}, {"1": "03" + "01" * 6, "2": "02" * 7, "3": "09" * 7}, {"1": "04" * 7}
        history.update_leader_log(self.folder, 411210, a)
        self.assertEqual(history.read_leader_log(self.folder)["changes"], [])
        history.update_leader_log(self.folder, 411212, b)  # appended, dated by the new turn; leader 3 is new
        log = history.read_leader_log(self.folder)
        self.assertEqual(log["changes"], [[411212, 1, "01" * 7, "03" + "01" * 6]])
        self.assertEqual((log["date"], log["ratings"], log["previous"]), (411212, b, {"date": 411210, "ratings": a}))
        history.update_leader_log(self.folder, 411211, c)  # an older turn after a newer one: nothing
        self.assertEqual(history.read_leader_log(self.folder), log)
        history.update_leader_log(self.folder, 411212, c)  # refresh of the latest turn: recomputed
        log = history.read_leader_log(self.folder)
        self.assertEqual(log["changes"], [[411212, 1, "01" * 7, "04" * 7]])
        self.assertEqual((log["date"], log["ratings"], log["previous"]["date"]), (411212, c, 411210))
        history.update_leader_log(self.folder, 411212, a)  # refreshed back: no change left
        self.assertEqual(history.read_leader_log(self.folder)["changes"], [])
        history.update_leader_log(self.folder, 411213, b)
        self.assertEqual([c[0] for c in history.read_leader_log(self.folder)["changes"]], [411213])
        self.assertEqual(os.listdir(self.folder), [history.LEADER_LOG])  # no temporary file left

    def test_unreadable_leader_log_is_none(self):
        os.makedirs(self.folder)
        self.assertIsNone(history.read_leader_log(self.folder))
        with open(os.path.join(self.folder, history.LEADER_LOG), "wb") as f:
            f.write(b"junk")
        self.assertIsNone(history.read_leader_log(self.folder))

    def test_failed_write_leaves_old_file_and_no_temporary_file(self):
        snap = history.build_snapshot(self.save, "a.pws", self.places)
        history.write_snapshot(self.folder, snap)
        with self.assertRaises(TypeError):
            history.write_snapshot(self.folder, dict(snap, turn=object()))
        self.assertEqual(os.listdir(self.folder), ["19411210.json.gz"])
        self.assertEqual(history.read_snapshot(self.path)["turn"], 4)

    def test_record_rules(self):
        r = self.record("a.pws")
        self.assertEqual((r.status, r.date, r.path), (history.RECORDED, 411210, self.path))
        self.assertEqual(self.record("a.pws").status, history.REFRESHED)
        with open(self.path, "rb") as f:
            before = f.read()
        r = self.record("b.pws")
        self.assertEqual((r.status, r.source), (history.KEPT, "a.pws"))
        with open(self.path, "rb") as f:
            self.assertEqual(f.read(), before)
        self.assertEqual(self.record("b.pws", replace=True).status, history.REPLACED)
        self.assertEqual(history.read_snapshot(self.path)["source"], "b.pws")
        self.assertEqual(self.record("b.pws").status, history.REFRESHED)

    def test_corrupt_existing_file_is_replaced_but_future_version_is_kept(self):
        os.makedirs(self.folder)
        with open(self.path, "wb") as f:
            f.write(b"garbage")
        self.assertEqual(self.record().status, history.RECORDED)
        future = dict(history.read_snapshot(self.path), version=2)
        with gzip.open(self.path, "wb") as f:
            f.write(json.dumps(future).encode())
        with open(self.path, "rb") as f:
            before = f.read()
        self.assertEqual(self.record().status, history.KEPT)
        with open(self.path, "rb") as f:
            self.assertEqual(f.read(), before)
        self.assertEqual(self.record(replace=True).status, history.REPLACED)

    def test_pbem_is_skipped(self):
        save = SaveFile.load(SAVE_015)
        bases.set_title(save, "(PBEM) game")
        r = history.record(save, os.path.join(self.tmp, "p.pws"), root=self.root)
        self.assertEqual(r.status, history.SKIPPED_PBEM)
        self.assertFalse(os.path.exists(self.root))

    def test_import_saves(self):
        pbem = SaveFile.load(SAVE_015)
        bases.set_title(pbem, "(PBEM) game")
        pbem_path = os.path.join(self.tmp, "pbem.pws")
        pbem.save(pbem_path)
        bad = os.path.join(self.tmp, "bad.pws")
        with open(bad, "wb") as f:
            f.write(b"not a save")
        self.record("a.pws")
        seen = []
        result = history.import_saves([SAVE_015, pbem_path, bad, os.path.join(self.tmp, "missing.pws")],
                                      root=self.root, progress=seen.append)
        self.assertEqual(result.imported, [("going2_411210.pws", 411210)])
        self.assertEqual([(n, why.split(":")[0]) for n, why in result.skipped],
                         [("pbem.pws", "PBEM"), ("bad.pws", "unreadable"), ("missing.pws", "unreadable")])
        self.assertEqual(seen, ["going2_411210.pws", "pbem.pws", "bad.pws", "missing.pws"])
        self.assertEqual(history.read_snapshot(self.path)["source"], "going2_411210.pws")  # replaced a.pws
        self.assertEqual(history.read_leader_log(self.folder)["date"], 411210)

    def test_import_applies_the_leader_log_in_date_order(self):
        calls = []
        real = history.update_leader_log
        paths = [os.path.join(self.tmp, n) for n in ("late.pws", "early.pws")]
        dates = {paths[0]: 411212, paths[1]: 411211}
        loaded = {}
        real_load = SaveFile.load

        def load(path):
            save = real_load(SAVE_015)
            loaded[id(save)] = dates[path]
            return save

        with mock.patch.object(history.SaveFile, "load", side_effect=load), \
                mock.patch.object(history, "game_date", side_effect=lambda s: (loaded[id(s)], 1)), \
                mock.patch.object(history, "update_leader_log", side_effect=lambda *a: calls.append(a[1]) or real(*a)):
            result = history.import_saves(paths, root=self.root)
        self.assertEqual([d for _n, d in result.imported], [411212, 411211])
        self.assertEqual(calls, [411211, 411212])

    def test_load_history_orders_and_skips_bad_files(self):
        base = history.build_snapshot(self.save, "a.pws", self.places)
        for date, turn in ((411212, 6), (411210, 4), (411211, 5)):
            history.write_snapshot(self.folder, dict(base, date=date, turn=turn))
        with open(os.path.join(self.folder, "19411209.json.gz"), "wb") as f:
            f.write(b"junk")
        with gzip.open(os.path.join(self.folder, "19411208.json.gz"), "wb") as f:
            f.write(json.dumps(dict(base, version=2)).encode())
        with gzip.open(os.path.join(self.folder, "19411207.json.gz"), "wb") as f:
            f.write(b"[1]")
        open(os.path.join(self.folder, "readme.txt"), "w").close()
        loaded = history.load_history(self.folder)
        self.assertEqual([(s["date"], s["turn"]) for s in loaded.snapshots],
                         [(411210, 4), (411211, 5), (411212, 6)])
        self.assertEqual([n for n, _w in loaded.problems],
                         ["19411207.json.gz", "19411208.json.gz", "19411209.json.gz"])
        self.assertIn("version", dict(loaded.problems)["19411208.json.gz"])
        self.assertEqual(history.load_history(os.path.join(self.tmp, "nothing")), ([], []))

    def test_delete_snapshot(self):
        self.record()
        history.delete_snapshot(self.folder, 411210)
        self.assertEqual(history.load_history(self.folder).snapshots, [])
        with self.assertRaises(OSError):
            history.delete_snapshot(self.folder, 411210)


class SeriesTests(unittest.TestCase):
    def setUp(self):
        self.snaps = [
            fake_snap(411210, 4, 100, 50, {"584": [1, 10, 1, 2, 3], "7": [0, 5, 0, 0, 0]}),
            fake_snap(411211, 5, 90, 70, {"584": [1, 12, 1, 2, 3]}),
            fake_snap(411212, 6, 95, 70, {"584": [0, 8, 2, 2, 3]}),
        ]
        self.snaps[1]["sides"]["Allied"].pop("supply")

    def test_side_series(self):
        self.assertEqual(history.side_series(self.snaps, "supply"),
                         [(411210, 4, 100, 50), (411211, 5, None, 70), (411212, 6, 95, 70)])
        self.assertEqual(history.side_series(self.snaps, "nothing")[0], (411210, 4, None, None))

    def test_side_series_of_a_snapshot_without_the_mines_metric(self):
        # Snapshots recorded before the metric existed have no "mines" key: a gap, not a crash.
        self.snaps[2]["sides"]["Allied"]["mines"] = 7
        self.assertEqual(history.side_series(self.snaps, "mines"),
                         [(411210, 4, None, None), (411211, 5, None, None), (411212, 6, 7, None)])
        self.assertEqual(history.changes([r[2] for r in history.side_series(self.snaps, "mines")]),
                         [None, None, None])

    def test_side_series_of_a_snapshot_without_the_vp_metric(self):
        self.snaps[2]["sides"]["Japanese"]["vp"] = 2165
        self.assertEqual(history.side_series(self.snaps, "vp"),
                         [(411210, 4, None, None), (411211, 5, None, None), (411212, 6, None, 2165)])
        self.assertEqual(history.changes([r[3] for r in history.side_series(self.snaps, "vp")]), [None, None, None])

    def test_base_series_with_gaps_and_owner(self):
        self.assertEqual(history.base_series(self.snaps, 584, "supply"),
                         [(411210, 4, 1, 10), (411211, 5, 1, 12), (411212, 6, 0, 8)])
        self.assertEqual(history.base_series(self.snaps, 7, "fuel"),
                         [(411210, 4, 0, 0), (411211, 5, None, None), (411212, 6, None, None)])
        self.assertEqual(history.base_series(self.snaps, 584, "fuel")[2][3], 2)

    def test_bases_and_choices(self):
        self.assertEqual(history.bases_seen(self.snaps), [7, 584])
        self.assertEqual(history.base_choices(self.snaps, {584: "Pearl Harbor"}),
                         [("#7", 7), ("Pearl Harbor (584)", 584)])

    def test_changes(self):
        self.assertEqual(history.changes([10, None, 15, 12]), [None, None, 5, -3])


class AircraftSeriesTests(unittest.TestCase):
    def setUp(self):
        self.snaps = [fake_snap(411210, 4, 1, 1), fake_snap(411211, 5, 1, 1), fake_snap(411212, 6, 1, 1),
                      fake_snap(411213, 7, 1, 1)]
        self.snaps[1]["aircraft"] = {"5": [0, 30, 1, 2, 3, 4]}
        self.snaps[2]["aircraft"] = {"9": [1, 7, 0, 0, 0, 0]}
        self.snaps[3]["aircraft"] = {"5": [0, 25, 2, 2, 3, 4], "9": [1, 0, 1, 0, 0, 0]}

    def test_values_zero_after_first_appearance_none_before(self):
        series = history.aircraft_series(self.snaps, 5, "pool")
        self.assertEqual([r[3] for r in series], [None, 30, 0, 25])
        self.assertEqual([r[:3] for r in series][:2], [(411210, 4, 0), (411211, 5, 0)])
        self.assertEqual([r[3] for r in history.aircraft_series(self.snaps, 9, "pool")], [None, None, 7, 0])
        self.assertEqual([r[3] for r in history.aircraft_series(self.snaps, 77, "pool")], [None] * 4)

    def test_metrics(self):
        for metric, expected in (("lost", [None, 10, 0, 11]), ("air", [None, 1, 0, 2]), ("ground", [None, 2, 0, 2]),
                                 ("flak", [None, 3, 0, 3]), ("ops", [None, 4, 0, 4])):
            self.assertEqual([r[3] for r in history.aircraft_series(self.snaps, 5, metric)], expected, metric)
        self.assertEqual(list(history.AIRCRAFT_METRICS), ["pool", "lost", "air", "ground", "flak", "ops"])
        self.assertEqual(history.AIRCRAFT_METRICS["lost"], "Lost (total)")

    def test_side_of_series(self):
        self.assertEqual({r[2] for r in history.aircraft_series(self.snaps, 9, "pool")}, {1})

    def test_seen_and_choices(self):
        self.assertEqual(history.aircraft_seen(self.snaps), [5, 9])
        self.assertEqual(history.aircraft_choices(self.snaps, {5: "A6M2 Zero"}),
                         [("#9 (Allied)", 9), ("A6M2 Zero (Japanese)", 5)])
        dup = history.aircraft_choices(self.snaps, {5: "Same", 9: "Same"})
        self.assertEqual(len(dup), 2)
        same_side = [fake_snap(411210, 4, 1, 1)]
        same_side[0]["aircraft"] = {"1": [1, 1, 0, 0, 0, 0], "2": [1, 1, 0, 0, 0, 0]}
        self.assertEqual(history.aircraft_choices(same_side, {1: "P-40E", 2: "P-40E"}),
                         [("P-40E (Allied, #1)", 1), ("P-40E (Allied, #2)", 2)])


class ChartMathTests(unittest.TestCase):
    def test_nice_ticks(self):
        self.assertEqual(chart.nice_ticks(0, 100), [0, 25, 50, 75, 100])
        ticks = chart.nice_ticks(0, 982531)
        self.assertEqual(ticks[0], 0)
        self.assertGreaterEqual(ticks[-1], 982531)
        self.assertTrue(4 <= len(ticks) <= 7)
        flat = chart.nice_ticks(5, 5)
        self.assertLess(flat[0], 5)
        self.assertGreater(flat[-1], 5)
        self.assertLessEqual(chart.nice_ticks(-30, 10)[0], -30)

    def test_labels(self):
        self.assertEqual(chart.format_int(1234567), "1,234,567")
        self.assertEqual(chart.date_label(411210), "10 Dec 41")
        self.assertEqual(chart.date_label(450802), "2 Aug 45")
        self.assertEqual(chart.ordinal_date(history.date_ordinal(411210)), 411210)
        self.assertEqual(chart.x_ticks(5, 5, 600), [5])
        ticks = chart.x_ticks(0, 1500, 800)
        self.assertEqual((ticks[0], ticks[-1]), (0, 1500))
        self.assertLessEqual(len(ticks), 6)


if __name__ == "__main__":
    unittest.main()
