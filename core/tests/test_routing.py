import random

from django.test import SimpleTestCase

from core.services import emissions, routing
from core.services.routing import Graph, Node


def _random_nodes(n, seed=0):
    rnd = random.Random(seed)
    return [
        Node(i, f"S{i}", 1.25 + rnd.random() * 0.18, 103.65 + rnd.random() * 0.35, rnd.choice([1, 1, 2, 3]))
        for i in range(1, n + 1)
    ]


class ShortestPathAlgorithmTests(SimpleTestCase):
    def setUp(self):
        # A small hand-built graph where the direct edge is NOT the shortest.
        self.g = Graph()
        for i in range(1, 5):
            self.g.add_node(Node(i, f"N{i}", 0, 0))
        self.g.add_edge(1, 2, 1.0)
        self.g.add_edge(2, 3, 1.0)
        self.g.add_edge(1, 3, 5.0)
        self.g.add_edge(3, 4, 2.0)

    def test_all_algorithms_find_the_indirect_shortest_path(self):
        for algorithm in routing.ALGORITHMS:
            with self.subTest(algorithm=algorithm):
                result = routing.shortest_path(self.g, 1, 4, algorithm)
                self.assertEqual(result["path"], [1, 2, 3, 4])
                self.assertAlmostEqual(result["distance_km"], 4.0)

    def test_unreachable_target(self):
        self.g.add_node(Node(99, "island", 0, 0))
        for algorithm in routing.ALGORITHMS:
            result = routing.shortest_path(self.g, 1, 99, algorithm)
            self.assertIsNone(result["distance_km"])
            self.assertEqual(result["path"], [])

    def test_bellman_ford_detects_negative_cycle(self):
        g = Graph()
        for i in (1, 2):
            g.add_node(Node(i, str(i), 0, 0))
        g.adjacency[1][2] = -1.0
        g.adjacency[2][1] = -1.0
        with self.assertRaises(ValueError):
            routing.bellman_ford(g, 1)

    def test_distance_matrices_agree_on_road_network(self):
        graph = Graph.road_network(_random_nodes(25))
        reference = routing.distance_matrix(graph, "dijkstra")
        for algorithm in ("bellman_ford", "floyd_warshall"):
            other = routing.distance_matrix(graph, algorithm)
            for a in reference:
                for b in reference:
                    self.assertAlmostEqual(reference[a][b], other[a][b], places=6)

    def test_road_network_is_connected_and_sparse(self):
        nodes = _random_nodes(30)
        graph = Graph.road_network(nodes, neighbours=3)
        dist, _ = routing.dijkstra(graph, nodes[0].id)
        self.assertTrue(all(d < routing.INF for d in dist.values()))
        self.assertLess(graph.edge_count, 30 * 29 / 2)

    def test_haversine_known_distance(self):
        # Marina Bay Sands -> Changi Business Park is ~12.8 km as the crow flies.
        self.assertAlmostEqual(routing.haversine_km(1.2834, 103.8607, 1.3348, 103.9640), 12.8, delta=0.5)


class PlannerTests(SimpleTestCase):
    def test_every_site_covered_exactly_once(self):
        nodes = _random_nodes(40)
        for vehicles in (1, 3, 5):
            routes = routing.plan_patrol_routes(nodes, vehicles)
            covered = sorted(s for r in routes for s in r.stop_order)
            self.assertEqual(covered, [n.id for n in nodes])
            self.assertEqual(len(routes), vehicles)

    def test_workload_is_balanced(self):
        routes = routing.plan_patrol_routes(_random_nodes(40), 4)
        sizes = [len(r.stop_order) for r in routes]
        self.assertLessEqual(max(sizes), 40 // 4 + 1)
        self.assertTrue(all(sizes))

    def test_high_priority_sites_visited_first(self):
        nodes = _random_nodes(20)
        nodes[7].priority = 100  # emergency
        routes = routing.plan_patrol_routes(nodes, 2)
        priority = {n.id: n.priority for n in nodes}
        for r in routes:
            levels = [priority[s] for s in r.stop_order]
            self.assertEqual(levels, sorted(levels, reverse=True))
        self.assertIn(nodes[7].id, [r.stop_order[0] for r in routes])

    def test_optimised_plan_beats_manual_baseline(self):
        nodes = _random_nodes(30, seed=3)
        graph = Graph.road_network(nodes)
        planned = sum(r.total_distance_km for r in routing.plan_patrol_routes(nodes, 3, graph=graph))
        baseline = sum(r.total_distance_km for r in routing.baseline_routes(nodes, 3, graph=graph))
        self.assertLess(planned, baseline)

    def test_vehicle_start_positions_are_respected(self):
        nodes = _random_nodes(12)
        start = Node(-1, "vehicle", 1.30, 103.80)
        graph = Graph.road_network(nodes + [start])
        routes = routing.plan_patrol_routes(nodes, 1, start_ids=[-1], graph=graph)
        self.assertNotIn(-1, routes[0].stop_order)
        self.assertGreater(routes[0].legs_km[0], 0)
        self.assertAlmostEqual(sum(routes[0].legs_km), routes[0].total_distance_km, places=2)

    def test_two_opt_never_worsens(self):
        nodes = _random_nodes(15)
        graph = Graph.road_network(nodes)
        matrix = routing.distance_matrix(graph)
        order = [n.id for n in nodes]
        improved = routing.two_opt(order, matrix)
        self.assertLessEqual(routing.path_length(improved, matrix), routing.path_length(order, matrix) + 1e-9)
        self.assertEqual(sorted(improved), sorted(order))

    def test_invalid_vehicle_count(self):
        with self.assertRaises(ValueError):
            routing.plan_patrol_routes(_random_nodes(3), 0)


class RerouteTests(SimpleTestCase):
    def test_reroute_never_worse_than_driving_back(self):
        for seed in range(15):
            nodes = _random_nodes(15, seed)
            graph = Graph.road_network(nodes)
            ids = [n.id for n in nodes]
            result = routing.reroute_after_emergency(
                graph, current_id=ids[3], emergency_id=ids[10], remaining_ids=ids[4:], resume_id=ids[2]
            )
            self.assertEqual(result.new_order[0], ids[10])
            self.assertEqual(sorted(result.new_order), sorted(ids[4:]))
            self.assertLessEqual(result.rerouted_km, result.baseline_km + 1e-6)
            self.assertGreaterEqual(result.saved_km, 0)

    def test_reroute_saves_mileage_when_resume_point_is_far(self):
        g = Graph()
        coords = {1: (1.30, 103.70), 2: (1.30, 103.95), 3: (1.31, 103.96), 4: (1.29, 103.96), 5: (1.30, 103.71)}
        for i, (lat, lng) in coords.items():
            g.add_node(Node(i, str(i), lat, lng))
        for a in coords:
            for b in coords:
                if a < b:
                    g.add_edge(a, b, routing.haversine_km(*coords[a], *coords[b]))
        # Vehicle at 5 (west, next to resume point 1) sent east to 2;
        # remaining 3 & 4 are also east, so driving back west is wasteful.
        result = routing.reroute_after_emergency(g, 5, 2, [3, 4], resume_id=1)
        self.assertGreater(result.saved_km, 20)


class EmissionTests(SimpleTestCase):
    def test_engine_factors(self):
        self.assertEqual(emissions.estimate_emission_kg(100, "petrol"), 19.2)
        self.assertLess(
            emissions.estimate_emission_kg(100, "electric"), emissions.estimate_emission_kg(100, "hybrid")
        )
        self.assertEqual(emissions.estimate_emission_kg(-5, "petrol"), 0.0)
        self.assertEqual(emissions.factor_for_engine("unknown"), emissions.factor_for_engine("petrol"))

    def test_savings(self):
        s = emissions.savings(200, 150, "diesel")
        self.assertEqual(s["saved_km"], 50)
        self.assertAlmostEqual(s["saved_kg"], 50 * 0.171, places=3)
        self.assertEqual(s["saved_percent"], 25.0)
        self.assertEqual(emissions.savings(100, 120, "petrol")["saved_km"], 0)

    def test_compare_plans(self):
        result = emissions.compare_plans(100, "petrol")
        self.assertEqual(result["shortest_distance_plan_kg"], 19.2)
        self.assertIn(result["recommended"], ("shortest_distance", "best_traffic"))
