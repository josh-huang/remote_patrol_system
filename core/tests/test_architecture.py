import io
import json
import random
from unittest import mock

from django.core.cache import cache
from django.core.checks import run_checks
from django.test import SimpleTestCase, override_settings
from rest_framework.test import APIClient
from rest_framework.throttling import ScopedRateThrottle

from core.services import distance, routing
from core.services.routing import Graph, Node
from core.tests.fixtures import PatrolAPITestCase
from incidents.models import IncidentReport
from incidents.signals import incident_triaged
from patrol import services


def _nodes(n, seed=0):
    rnd = random.Random(seed)
    return [Node(i, f"S{i}", 1.28 + rnd.random() * 0.14, 103.68 + rnd.random() * 0.3) for i in range(1, n + 1)]


class MoveCostTests(SimpleTestCase):
    """The O(1) move costs must agree with re-summing the whole path."""

    def setUp(self):
        self.nodes = _nodes(12)
        self.matrix = routing.distance_matrix(Graph.road_network(self.nodes))
        self.order = [n.id for n in self.nodes[1:9]]

    def test_insertion_and_removal_costs(self):
        for start in (None, self.nodes[0].id):
            base = routing.path_length(self.order, self.matrix, start)
            for pos in range(len(self.order) + 1):
                new = self.order[:pos] + [self.nodes[10].id] + self.order[pos:]
                self.assertAlmostEqual(
                    routing.insertion_cost(self.order, pos, self.nodes[10].id, self.matrix, start),
                    routing.path_length(new, self.matrix, start) - base,
                )
            for idx in range(len(self.order)):
                without = self.order[:idx] + self.order[idx + 1 :]
                self.assertAlmostEqual(
                    routing.removal_gain(self.order, idx, self.matrix, start),
                    base - routing.path_length(without, self.matrix, start),
                )

    def test_two_opt_reaches_a_local_optimum(self):
        for start in (None, self.nodes[0].id):
            best = routing.two_opt(self.order, self.matrix, start)
            length = routing.path_length(best, self.matrix, start)
            for i in range(len(best) - 1):
                for j in range(i + 1, len(best)):
                    candidate = best[:i] + best[i : j + 1][::-1] + best[j + 1 :]
                    self.assertGreaterEqual(routing.path_length(candidate, self.matrix, start), length - 1e-9)


class AttachPointsTests(SimpleTestCase):
    def test_points_are_leaves(self):
        sites = _nodes(15)
        matrix = routing.distance_matrix(Graph.road_network(sites))
        points = [Node(-1, "van A", 1.33, 103.80), Node(-2, "van B", 1.30, 103.90)]
        extended = routing.attach_points(matrix, sites, points)
        # Site-to-site distances are untouched and the input is not modified.
        for a in sites:
            for b in sites:
                self.assertEqual(extended[a.id][b.id], matrix[a.id][b.id])
            self.assertNotIn(-1, matrix[a.id])
        # Point distances are symmetric and never shorter than a straight line.
        for p in points:
            self.assertEqual(extended[p.id][p.id], 0.0)
            for s in sites:
                self.assertEqual(extended[p.id][s.id], extended[s.id][p.id])
                self.assertGreaterEqual(extended[p.id][s.id], routing.haversine_km(p.lat, p.lng, s.lat, s.lng))
        self.assertGreater(extended[-1][-2], 0)


def _fake_osrm(url, timeout):
    """A stand-in OSRM table endpoint: distances = 1000 m × |i − j| + 7 m one way."""
    query = url.split("?", 1)[1]
    params = dict(p.split("=", 1) for p in query.split("&"))
    sources = [int(x) for x in params["sources"].split("%3B")]
    destinations = [int(x) for x in params["destinations"].split("%3B")]
    coords = url.split("/driving/", 1)[1].split("?", 1)[0].split(";")
    lngs = [float(c.split(",")[0]) for c in coords]
    rank = {lng: i for i, lng in enumerate(sorted(lngs))}
    rows = [
        [1000 * abs(rank[lngs[s]] - rank[lngs[d]]) + (7 if s < d else 0) if s != d else 0 for d in destinations]
        for s in sources
    ]
    return io.BytesIO(json.dumps({"code": "Ok", "distances": rows}).encode())


class OSRMProviderTests(SimpleTestCase):
    def test_blocks_requests_and_symmetrises(self):
        nodes = [Node(i, str(i), 1.3, 103.7 + i * 0.01) for i in range(1, 8)]
        provider = distance.OSRMProvider(max_coordinates=4)  # forces 4×4 blocks of 2
        with mock.patch("urllib.request.urlopen", side_effect=_fake_osrm) as urlopen:
            matrix = provider.matrix(nodes)
        self.assertEqual(urlopen.call_count, 16)
        self.assertAlmostEqual(matrix[1][4], 3.0035)  # (3007 + 3000) / 2 m → km
        self.assertEqual(matrix[4][1], matrix[1][4])
        self.assertEqual(matrix[2][2], 0.0)

    def test_unavailable_server_falls_back_to_the_model(self):
        nodes = _nodes(6)
        provider = distance.OSRMProvider()
        with mock.patch("urllib.request.urlopen", side_effect=OSError("blocked")):
            with self.assertRaises(distance.ProviderUnavailable):
                provider.matrix(nodes)
            matrix, used = distance.matrix_with_fallback(provider, nodes)
        self.assertEqual(used, "road_network")
        self.assertEqual(matrix, distance.RoadNetworkProvider().matrix(nodes))

    def test_unknown_provider(self):
        with self.assertRaises(ValueError):
            distance.make_provider("teleport")


class DistanceCacheTests(PatrolAPITestCase):
    def setUp(self):
        super().setUp()
        cache.clear()

    def test_matrix_is_computed_once_and_rekeyed_when_a_site_moves(self):
        real = distance.RoadNetworkProvider.matrix
        with mock.patch.object(distance.RoadNetworkProvider, "matrix", autospec=True, side_effect=real) as spy:
            services.site_matrix()
            services.site_matrix()
            self.assertEqual(spy.call_count, 1)
            site = self.sites[0]
            site.latitude += 0.01
            site.save()
            services.site_matrix()
            self.assertEqual(spy.call_count, 2)

    @override_settings(ROUTING_PROVIDER="osrm")
    def test_fallback_matrix_is_cached_briefly(self):
        with mock.patch("urllib.request.urlopen", side_effect=OSError("blocked")), mock.patch.object(
            services.cache, "set", wraps=cache.set
        ) as cache_set:
            matrix, nodes = services.site_matrix()
        self.assertEqual(len(nodes), len(self.sites))
        self.assertEqual(cache_set.call_args.args[2], services.FALLBACK_CACHE_SECONDS)
        self.assertTrue(matrix)


class ConcurrencyAndEventTests(PatrolAPITestCase):
    def test_an_alert_can_only_be_dispatched_once(self):
        self.make_plan()
        alert = self.admin_client.post("/api/v1/alerts/", {"location": self.sites[2].id}).json()
        first = self.admin_client.post(f"/api/v1/alerts/{alert['id']}/dispatch/", {}, format="json")
        self.assertEqual(first.status_code, 200, first.content)
        second = self.admin_client.post(f"/api/v1/alerts/{alert['id']}/dispatch/", {}, format="json")
        self.assertEqual(second.status_code, 400)
        self.assertIn("already", second.json()["detail"])

    def test_a_failing_subscriber_never_breaks_incident_intake(self):
        def explode(**kwargs):
            raise RuntimeError("subscriber bug")

        incident_triaged.connect(explode, dispatch_uid="test-explode")
        try:
            with self.assertLogs("django.dispatch", level="ERROR"):
                res = self.guard_client.post("/api/v1/incidents/", {"description": "Fire at the gate"})
        finally:
            incident_triaged.disconnect(dispatch_uid="test-explode")
        self.assertEqual(res.status_code, 201)
        self.assertEqual(IncidentReport.objects.get().ai_severity, "critical")


class SecurityTests(PatrolAPITestCase):
    def test_login_is_rate_limited(self):
        cache.clear()
        client = APIClient()
        with mock.patch.object(ScopedRateThrottle, "THROTTLE_RATES", {"login": "2/min"}):
            codes = [
                client.post("/api/v1/auth/token/", {"username": "guard1", "password": "not-the-password"}).status_code
                for _ in range(3)
            ]
        cache.clear()
        self.assertEqual(codes, [401, 401, 429])

    def test_health_reports_the_database(self):
        body = APIClient().get("/api/v1/health/").json()
        self.assertEqual(body["database"], "ok")
        self.assertEqual(body["routing_provider"], "road_network")

    def test_deploy_check_flags_the_dev_secret_key(self):
        ids = {m.id for m in run_checks(include_deployment_checks=True)}
        self.assertIn("patrol.E001", ids)
        with override_settings(SECRET_KEY="x" * 60):
            ids = {m.id for m in run_checks(include_deployment_checks=True)}
        self.assertNotIn("patrol.E001", ids)
