import os
import unittest

from witpae import bases, factories, industry, regions
from witpae.container import SaveFile, SaveFormatError

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
SAVE_015 = os.path.join(DATA_DIR, "going2_411210.pws")


def by_group(type_rows):
    return {r.group: r for r in type_rows}


def by_material(balance):
    return {r.material: r for r in balance}


class FlowRuleTests(unittest.TestCase):
    def factory(self, type_id, size, production_on=True):
        return factories.Factory(0, type_id, "x", factories.kind_of(type_id), size, 0, production_on, True, False,
                                 None)

    def test_rules(self):
        flow = industry.factory_flow(self.factory(521, 10))
        self.assertEqual(flow.uses, {"resources": 200, "fuel": 20})
        self.assertEqual(flow.makes, {"hi": 20, "supply": 20})
        self.assertEqual(industry.factory_flow(self.factory(528, 3)).makes, {"fuel": 27, "supply": 3})
        self.assertEqual(industry.factory_flow(self.factory(526, 2)).uses, {"hi": 12})
        self.assertEqual(industry.factory_flow(self.factory(524, 50)), industry.NO_FLOW)

    def test_aircraft_and_engines_have_unknown_inputs(self):
        for type_id in (2001, 12):
            flow = industry.factory_flow(self.factory(type_id, 60))
            self.assertFalse(flow.uses_known)
            self.assertEqual(list(flow.makes.values()), [2])

    def test_production_off_does_nothing(self):
        for type_id in (521, 519, 2001):
            self.assertEqual(industry.factory_flow(self.factory(type_id, 10, production_on=False)), industry.NO_FLOW)

    def test_flow_text(self):
        self.assertEqual(industry.flow_text({"hi": 14548, "supply": 14548}), "14,548 HI, 14,548 supply")
        self.assertEqual(industry.flow_text({"aircraft": 28.5}), "28.5 aircraft")
        self.assertEqual(industry.flow_text({}), "-")


@unittest.skipUnless(os.path.exists(SAVE_015), "sample save missing")
class IndustryReportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.save = SaveFile.load(SAVE_015)
        cls.places = industry.list_industry_places(cls.save)
        cls.allied = industry.filter_places(cls.places, "Allied")

    def test_minor_places_are_included(self):
        by_id = {p.id: p for p in self.places}
        self.assertEqual(by_id[926].kind, "Minor")
        self.assertEqual(by_id[926].name, "Corunna Downs")
        self.assertTrue(any(f.type == 519 for f in factories.list_factories(by_id[926].base)))
        self.assertEqual(by_id[233].kind, "Minor")
        self.assertEqual(by_id[506].kind, "Base")
        self.assertEqual(by_id[506].region, "Continental US")
        listed = {b.id for b in bases.list_bases(self.save, include_towns=True)}
        self.assertTrue(listed < set(by_id))
        self.assertEqual({p.kind for p in self.places}, {"Base", "Town", "Minor"})

    def test_non_place_type_zero_records_are_excluded(self):
        listed = {p.id for p in self.places}
        for loc_id in (3327, 14425, 14474):
            self.assertNotIn(loc_id, listed)
        self.assertEqual(sum(1 for p in self.places if p.kind == "Minor"), 102)

    def test_allied_totals(self):
        type_rows, _balance = industry.summarize(self.allied)
        rows = by_group(type_rows)
        expected = {"Oil": (26, 6133, 247), "Resources": (252, 25969, 179), "Manpower": (181, 1174, 13),
                    "Heavy Industry": (46, 7274, 87), "Light Industry": (138, 17836, 199),
                    "Refinery": (20, 7665, 150), "Repair Shipyard": (35, 4778, 7), "Aircraft": (33, 856, 0)}
        for group, counts in expected.items():
            r = rows[group]
            self.assertEqual((r.count, r.size, r.damage), counts, group)
        # The sample save has no factory switched off.
        self.assertTrue(all(r.production_off == 0 for r in type_rows))
        self.assertEqual(industry.flow_text(rows["Heavy Industry"].makes), "14,548 HI, 14,548 supply")
        self.assertEqual(industry.flow_text(rows["Heavy Industry"].uses), "145,480 resources, 14,548 fuel")
        self.assertFalse(rows["Aircraft"].uses_known)

    def test_allied_balance(self):
        _types, balance = industry.summarize(self.allied)
        rows = by_material(balance)
        self.assertEqual([r.label for r in balance],
                         ["Oil", "Resources", "Fuel", "Supply", "Manpower", "HI points", "Armament points",
                          "Vehicle points", "Naval points", "Merchant points"])
        self.assertEqual((rows["resources"].produced, rows["resources"].used), (519380, 413020))
        self.assertEqual(rows["resources"].used, 7274 * 20 + 17836 * 15)
        self.assertEqual((rows["oil"].produced, rows["oil"].used), (61330, 76650))
        self.assertEqual(rows["fuel"].produced, 68985)
        self.assertEqual(rows["fuel"].used, 14548)
        self.assertEqual(rows["supply"].produced, 40049)
        self.assertEqual(rows["manpower"].produced, 1174 * 5)
        self.assertEqual(rows["hi"].produced, 7274 * 2)
        # Oil runs down, so days left is stored / -net; the others do not.
        self.assertEqual((rows["oil"].allotted, rows["oil"].net), (50, -15270))
        self.assertAlmostEqual(rows["oil"].days, rows["oil"].stored / 15270)
        self.assertEqual((rows["supply"].allotted, rows["supply"].used, rows["supply"].net), (98992, 0, 139041))
        self.assertEqual((rows["fuel"].allotted, rows["fuel"].net), (69350, 123787))
        self.assertEqual(rows["oil"].stored, sum(p.base.get("oil") for p in self.allied))
        self.assertIsNone(rows["resources"].days)
        self.assertIsNone(rows["manpower"].stored)  # no pools given
        self.assertIsNone(rows["hi"].stored)

    def test_pool_rows(self):
        pools = industry.side_pools(self.save)[1]
        _types, balance = industry.summarize(self.allied, pools)
        rows = by_material(balance)
        self.assertEqual({k: rows[k].stored for k in industry.POOLS},
                         {"manpower": 17555, "hi": 37846, "naval": 0, "merchant": 0, "armament": 0, "vehicle": 0})
        self.assertEqual((rows["hi"].produced, rows["hi"].used, rows["hi"].net), (14548, 0, 14548))
        self.assertIsNone(rows["hi"].days)
        # A pool that is used faster than it is made has days left, unless a region is selected.
        sf = SaveFile.load(SAVE_015)
        places = industry.filter_places(industry.list_industry_places(sf), "Allied")
        us = industry.filter_places(places, region_id=17)
        rows = by_material(industry.summarize(us, {"hi": 100, "manpower": 5}, regional=True)[1])
        self.assertEqual(rows["hi"].stored, 100)
        self.assertTrue(all(rows[k].days is None for k in industry.POOLS))
        # Without a region filter the same pool does get days left once its net is negative.
        rows = by_material(industry.summarize(us, {"hi": 100})[1])
        self.assertEqual(rows["hi"].days is None, rows["hi"].net >= 0)

    def test_side_pools(self):
        pools = industry.side_pools(self.save)
        self.assertEqual(pools[1], {"manpower": 17555, "hi": 37846, "naval": 0, "merchant": 0, "armament": 0,
                                    "vehicle": 0})
        self.assertEqual(pools[0], {"manpower": 27426, "hi": 58193, "naval": 1, "merchant": 1113,
                                    "armament": 18387, "vehicle": 20})

    def test_side_pools_bad_section(self):
        sf = SaveFile.load(SAVE_015)
        sf[industry.POOL_SECTION].data = sf[industry.POOL_SECTION].data[:8000]
        with self.assertRaises(SaveFormatError):
            industry.side_pools(sf)
        del sf._by_id[industry.POOL_SECTION]
        with self.assertRaises(SaveFormatError):
            industry.side_pools(sf)

    def test_allotments(self):
        given = {p.id: industry.allotment(p) for p in self.places if industry.allotment(p)}
        self.assertEqual(len(given), 40)
        self.assertEqual({p.id for p in self.places if industry.allotment(p)} - {p.id for p in self.allied}, set())
        for key, total in (("supply", 98992), ("fuel", 69350), ("oil", 50)):
            self.assertEqual(sum(a.get(key, 0) for a in given.values()), total, key)
        self.assertEqual(industry.allotment(next(p for p in self.places if p.id == 615)),
                         {"supply": 65000, "fuel": 40000})
        self.assertEqual(industry.allotment(next(p for p in self.places if p.id == 819)),
                         {"supply": 9000, "fuel": 1000})
        self.assertEqual(industry.allotment(next(p for p in self.places if p.id == 614)),
                         {"supply": 5000, "fuel": 8000})
        top = sorted(given, key=lambda i: -given[i].get("supply", 0))[:3]
        self.assertEqual(top, [615, 819, 614])
        self.assertEqual([p for p in industry.filter_places(self.places, "Japanese") if industry.allotment(p)], [])

    def test_production_off_contributes_no_flows(self):
        sf = SaveFile.load(SAVE_015)
        allied = industry.filter_places(industry.list_industry_places(sf), "Allied")
        before = by_material(industry.summarize(allied)[1])
        place, f = next((p, f) for p in allied for f in factories.list_factories(p.base)
                        if f.type == 521 and f.size > 0)
        factories.set_factory(place.base, f.slot, f.size, f.damage, False, f.repair_on)
        types, balance = industry.summarize(allied)
        after = by_material(balance)
        self.assertEqual(after["hi"].produced, before["hi"].produced - 2 * f.size)
        self.assertEqual(after["resources"].used, before["resources"].used - 20 * f.size)
        self.assertEqual(after["fuel"].used, before["fuel"].used - 2 * f.size)
        self.assertEqual(after["supply"].produced, before["supply"].produced - 2 * f.size)
        self.assertEqual(by_group(types)["Heavy Industry"].production_off, f.size)
        row = next(r for r in industry.factory_rows([place]) if r.factory.slot == f.slot)
        self.assertEqual((row.flow.makes, row.flow.uses), ({}, {}))

    def test_regions_add_up(self):
        all_rows = by_material(industry.summarize(self.allied)[1])
        ids = [rid for rid, _name in regions.default_regions().regions()] + [regions.UNASSIGNED_ID]
        totals = dict.fromkeys(all_rows, 0)
        for rid in ids:
            rows = by_material(industry.summarize(industry.filter_places(self.allied, region_id=rid))[1])
            for key, r in rows.items():
                totals[key] += r.produced
        us = by_material(industry.summarize(industry.filter_places(self.allied, region_id=17))[1])
        self.assertTrue(0 < us["resources"].produced < all_rows["resources"].produced)
        for key, r in all_rows.items():
            self.assertEqual(totals[key], r.produced, key)

    def test_raw_rows(self):
        rows = industry.raw_rows(self.allied)
        by_id = {r.place.id: r for r in rows}
        self.assertIn(926, by_id)
        us = by_id[615]  # Eastern USA
        self.assertEqual(us.allotment, {"supply": 65000, "fuel": 40000})
        flows = [industry.factory_flow(f) for f in factories.list_factories(us.place.base)]
        self.assertEqual(us.net["supply"], 65000 + sum(fl.makes.get("supply", 0) - fl.uses.get("supply", 0)
                                                       for fl in flows))
        # A place with an allotment but no producing factory is still listed by default.
        sourced = [r for r in rows if r.allotment and not any(
            f.size > 0 and industry.factory_flow(f).makes for f in factories.list_factories(r.place.base))]
        self.assertTrue(sourced)
        self.assertGreater(len(industry.raw_rows(self.allied, only_industry=False)), len(rows))
        for r in rows:
            if r.shortest:
                key, days = r.shortest
                self.assertLess(r.net[key], 0)
                self.assertAlmostEqual(days, r.stored[key] / -r.net[key])
                for other in industry.STORED:
                    if r.net[other] < 0:
                        self.assertLessEqual(days, r.stored[other] / -r.net[other])
            else:
                self.assertTrue(all(v >= 0 for v in r.net.values()))

    def test_factory_rows(self):
        rows = industry.factory_rows(self.allied)
        types = industry.summarize(self.allied)[0]
        self.assertEqual(len(rows), sum(r.count for r in types))
        self.assertEqual({r.group for r in rows}, {r.group for r in types})


if __name__ == "__main__":
    unittest.main()
