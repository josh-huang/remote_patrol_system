"""Fast checks of the evaluation code (no OR-Tools, plotting or network)."""

from django.test import SimpleTestCase

from core.services import routing

from . import baselines, experiments, instances, osrm


class InstanceTests(SimpleTestCase):
    def test_random_sites_are_reproducible_and_on_the_island(self):
        a, b = instances.random_sites(30, seed=4), instances.random_sites(30, seed=4)
        self.assertEqual([(n.lat, n.lng) for n in a], [(n.lat, n.lng) for n in b])
        for n in a:
            self.assertTrue(1.28 <= n.lat <= 1.45 and 103.64 <= n.lng <= 103.98)
        self.assertEqual(len(instances.demo_sites()), 20)


class BaselineTests(SimpleTestCase):
    def test_every_method_covers_every_site_once_within_the_cap(self):
        nodes = instances.random_sites(37, seed=1)
        matrix = experiments._model_matrix(nodes)
        k = 4
        for name, method in experiments.METHODS.items():
            with self.subTest(method=name):
                routes = method(nodes, k, matrix)
                self.assertEqual(sorted(s for r in routes for s in r), sorted(n.id for n in nodes))
                if name != "Manual (round-robin)":
                    self.assertLessEqual(max(len(r) for r in routes), baselines.capacity(len(nodes), k))

    def test_this_system_beats_the_simple_heuristics(self):
        nodes = instances.random_sites(50, seed=3)
        matrix = experiments._model_matrix(nodes)
        ours = baselines.total_km(baselines.ours(nodes, 5, matrix), matrix)
        for method in (baselines.greedy_nearest, baselines.sweep, baselines.round_robin):
            self.assertLess(ours, baselines.total_km(method(nodes, 5, matrix), matrix))


class SimulationTests(SimpleTestCase):
    def test_reroutes_never_cost_more_than_driving_back(self):
        nodes = instances.demo_sites()
        rows = experiments.simulate_reroutes(nodes, 4, experiments._model_matrix(nodes), 60, 0, "t")
        self.assertEqual(len(rows), 60)
        for r in rows:
            self.assertGreaterEqual(r["saved_km"], 0)
            self.assertLessEqual(r["rerouted_km"], r["baseline_km"] + 1e-6)
        summary = experiments.summarise_reroutes(rows)[0]
        self.assertEqual(summary["trials"], 60)


class RealRoadDataTests(SimpleTestCase):
    def test_committed_osrm_data_loads(self):
        loaded = osrm.load_or_fetch("demo_20", instances.demo_sites())
        self.assertIsNotNone(loaded, "evaluation/data/osrm_demo_20.json is missing")
        nodes, matrix = loaded
        self.assertEqual(len(nodes), 20)
        for a in nodes:
            for b in nodes:
                self.assertEqual(matrix[a.id][b.id], matrix[b.id][a.id])
                if a.id != b.id:  # real roads are never shorter than a straight line
                    self.assertGreaterEqual(
                        matrix[a.id][b.id] * 1.05, routing.haversine_km(a.lat, a.lng, b.lat, b.lng)
                    )
