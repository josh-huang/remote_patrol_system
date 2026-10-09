from rest_framework.test import APIClient

from core.tests.fixtures import PatrolAPITestCase, png
from patrol.models import PatrolPlan, PatrolRecord, PatrolStop


class AuthTests(PatrolAPITestCase):
    def test_jwt_login_and_me(self):
        client = APIClient()
        res = client.post("/api/v1/auth/token/", {"username": "guard1", "password": "x-guard-pass-123"})
        self.assertEqual(res.status_code, 200)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {res.json()['access']}")
        me = client.get("/api/v1/me/").json()
        self.assertEqual(me["role"], "guard")
        self.assertEqual(me["vehicle"]["plate_number"], "SPT1")

    def test_anonymous_is_rejected(self):
        self.assertEqual(APIClient().get("/api/v1/vehicles/").status_code, 401)

    def test_guard_cannot_manage_fleet_or_plans(self):
        self.assertEqual(self.guard_client.post("/api/v1/vehicles/", {"plate_number": "X"}).status_code, 403)
        self.assertEqual(self.guard_client.post("/api/v1/plans/auto_daily/", {}).status_code, 403)
        self.assertEqual(self.guard_client.get("/api/v1/plans/").status_code, 403)


class PlanningTests(PatrolAPITestCase):
    def test_auto_daily_uses_only_operational_vehicles_and_covers_every_site(self):
        plan = self.make_plan(algorithm="floyd_warshall")
        plates = {s["vehicle_plate"] for s in plan["stops"]}
        self.assertEqual(plates, {"SPT1", "SPT2"})  # SPT3 is in maintenance
        self.assertEqual(sorted(s["location"] for s in plan["stops"]), sorted(l.id for l in self.sites))
        self.assertEqual(plan["status"], "active")
        self.assertEqual(plan["algorithm"], "floyd_warshall")
        self.assertLessEqual(plan["total_distance_km"], plan["baseline_distance_km"])
        self.assertGreaterEqual(plan["emission_saved_kg"], 0)

    def test_rejects_vehicle_in_maintenance(self):
        res = self.admin_client.post(
            "/api/v1/plans/auto_daily/", {"vehicle_ids": [self.vehicles[2].id]}, format="json"
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("not operational", res.json()["detail"])

    def test_plan_route_on_existing_plan(self):
        plan = self.admin_client.post("/api/v1/plans/", {"name": "P", "date": "2026-01-01"}).json()
        res = self.admin_client.post(
            f"/api/v1/plans/{plan['id']}/plan_route/",
            {"vehicle_ids": [self.vehicles[0].id], "location_ids": [s.id for s in self.sites[:4]]},
            format="json",
        )
        self.assertEqual(res.status_code, 200, res.content)
        self.assertEqual(len(res.json()["stops"]), 4)

    def test_manual_route(self):
        plan = self.admin_client.post("/api/v1/plans/", {"name": "Manual", "date": "2026-01-01"}).json()
        routes = [
            {"vehicle_id": self.vehicles[0].id, "location_ids": [self.sites[3].id, self.sites[0].id]},
            {"vehicle_id": self.vehicles[1].id, "location_ids": [self.sites[5].id]},
        ]
        res = self.admin_client.post(f"/api/v1/plans/{plan['id']}/manual_route/", {"routes": routes}, format="json")
        self.assertEqual(res.status_code, 200, res.content)
        body = res.json()
        self.assertEqual(body["mode"], "manual")
        first = [s for s in body["stops"] if s["vehicle"] == self.vehicles[0].id]
        self.assertEqual([s["location"] for s in sorted(first, key=lambda s: s["order"])], [self.sites[3].id, self.sites[0].id])
        self.assertGreater(body["total_distance_km"], 0)

    def test_manual_route_rejects_duplicate_sites(self):
        plan = self.admin_client.post("/api/v1/plans/", {"name": "Dup", "date": "2026-01-01"}).json()
        routes = [
            {"vehicle_id": self.vehicles[0].id, "location_ids": [self.sites[0].id]},
            {"vehicle_id": self.vehicles[1].id, "location_ids": [self.sites[0].id]},
        ]
        res = self.admin_client.post(f"/api/v1/plans/{plan['id']}/manual_route/", {"routes": routes}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_rebalance_moves_stops_off_broken_vehicle(self):
        plan = self.make_plan()
        broken = self.vehicles[1]
        broken.maintenance_status = "out_of_service"
        broken.save()
        res = self.admin_client.post(f"/api/v1/plans/{plan['id']}/rebalance/")
        self.assertEqual(res.status_code, 200, res.content)
        self.assertGreater(res.json()["moved"], 0)
        self.assertFalse(PatrolStop.objects.filter(plan_id=plan["id"], vehicle=broken, is_visited=False).exists())
        self.assertEqual(PatrolStop.objects.filter(plan_id=plan["id"]).count(), len(self.sites))


class MobileFlowTests(PatrolAPITestCase):
    def test_route_next_stop_and_check_in_with_photo(self):
        self.make_plan()
        route = self.guard_client.get("/api/v1/mobile/route/").json()
        self.assertEqual(route["vehicle"]["plate_number"], "SPT1")
        self.assertTrue(route["stops"])
        self.assertTrue(all(s["vehicle"] == self.vehicles[0].id for s in route["stops"]))
        nxt = route["next_stop"]
        self.assertEqual(nxt["order"], 0)

        res = self.guard_client.post(
            f"/api/v1/stops/{nxt['id']}/check_in/",
            {"notes": "Gate locked", "images": [png("a.png"), png("b.png")]},
            format="multipart",
        )
        self.assertEqual(res.status_code, 201, res.content)
        self.assertEqual(len(res.json()["images"]), 2)
        record = PatrolRecord.objects.get(stop_id=nxt["id"])
        self.assertEqual(record.guard, self.guard)
        self.assertEqual(record.notes, "Gate locked")

        after = self.guard_client.get("/api/v1/mobile/route/").json()
        self.assertEqual(after["progress"]["visited"], 1)
        self.assertNotEqual(after["next_stop"]["id"], nxt["id"])

        # Admin sees the stored photos in past patrol records.
        records = self.admin_client.get("/api/v1/records/").json()["results"]
        self.assertEqual(len(records[0]["images"]), 2)

    def test_guard_cannot_check_in_for_another_vehicle(self):
        self.make_plan()
        foreign = PatrolStop.objects.filter(vehicle=self.vehicles[1]).first()
        res = self.guard_client.post(f"/api/v1/stops/{foreign.id}/check_in/", {}, format="multipart")
        self.assertEqual(res.status_code, 404)

    def test_completing_all_stops_completes_plan(self):
        plan = self.make_plan(vehicle_ids=[self.vehicles[0].id], location_ids=[s.id for s in self.sites[:2]])
        for stop in plan["stops"]:
            self.assertEqual(self.guard_client.post(f"/api/v1/stops/{stop['id']}/mark_visited/").status_code, 201)
        self.assertEqual(PatrolPlan.objects.get(id=plan["id"]).status, "completed")

    def test_admin_without_vehicle_has_no_mobile_route(self):
        self.assertEqual(self.admin_client.get("/api/v1/mobile/route/").status_code, 403)


class PingTests(PatrolAPITestCase):
    def test_guard_ping_updates_own_vehicle(self):
        res = self.guard_client.post("/api/v1/pings/", {"latitude": 1.3, "longitude": 103.8, "speed_kmh": 30})
        self.assertEqual(res.status_code, 201, res.content)
        self.vehicles[0].refresh_from_db()
        self.assertEqual(self.vehicles[0].current_latitude, 1.3)
        self.assertIsNotNone(self.vehicles[0].last_seen_at)

    def test_guard_cannot_ping_other_vehicle(self):
        res = self.guard_client.post(
            "/api/v1/pings/", {"vehicle": self.vehicles[1].id, "latitude": 1.3, "longitude": 103.8}
        )
        self.assertEqual(res.status_code, 403)

    def test_live_positions_admin_only(self):
        self.assertEqual(self.guard_client.get("/api/v1/pings/live/").status_code, 403)
        live = self.admin_client.get("/api/v1/pings/live/").json()
        self.assertEqual({v["plate_number"] for v in live}, {"SPT1", "SPT2"})
