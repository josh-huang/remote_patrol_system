from core.tests.fixtures import PatrolAPITestCase
from patrol.models import PatrolStop


class DashboardAndReportTests(PatrolAPITestCase):
    def _patrol(self):
        self.make_plan()
        for stop in PatrolStop.objects.order_by("vehicle_id", "order")[:4]:
            self.admin_client.post(f"/api/v1/stops/{stop.id}/check_in/", {}, format="multipart")

    def test_dashboard_summary(self):
        self._patrol()
        data = self.admin_client.get("/api/v1/dashboard/summary/").json()
        self.assertEqual(data["vehicles"], {"total": 3, "available": 3, "operational": 2, "in_maintenance": 1})
        self.assertEqual(data["stops_today"]["visited"], 4)
        self.assertGreater(data["total_emission_kg"], 0)
        self.assertGreaterEqual(data["carbon_saved"]["total_saved_kg"], 0)
        self.assertTrue(data["emission_by_vehicle"])
        self.assertEqual(self.guard_client.get("/api/v1/dashboard/summary/").status_code, 403)

    def test_emission_history(self):
        self._patrol()
        data = self.admin_client.get("/api/v1/dashboard/emissions/?days=7").json()
        self.assertEqual(data["days"], 7)
        self.assertTrue(all(s["points"] for s in data["series"]))

    def test_daily_and_monthly_report_and_csv(self):
        self._patrol()
        daily = self.admin_client.get("/api/v1/reports/patrol/?period=daily").json()
        self.assertEqual(daily["total_records"], 4)
        self.assertTrue(daily["narrative"])
        self.assertTrue(daily["per_vehicle"])
        monthly = self.admin_client.get("/api/v1/reports/patrol/?period=monthly").json()
        self.assertEqual(monthly["period_type"], "monthly")

        csv_res = self.admin_client.get("/api/v1/reports/patrol/?period=daily&export=csv")
        self.assertEqual(csv_res["Content-Type"], "text/csv")
        lines = csv_res.content.decode().strip().splitlines()
        self.assertEqual(len([l for l in lines if l.count(",") >= 8]), 5)  # header + 4 visits

    def test_shortest_path_with_algorithm_comparison(self):
        res = self.admin_client.post(
            "/api/v1/routing/shortest-path/",
            {"source_location_id": self.sites[4].id, "target_location_id": self.sites[7].id, "compare": True},
            format="json",
        )
        self.assertEqual(res.status_code, 200, res.content)
        body = res.json()
        self.assertEqual(body["path"][0], self.sites[4].id)
        self.assertEqual(body["path"][-1], self.sites[7].id)
        self.assertGreaterEqual(body["distance_km"], body["straight_line_km"])
        distances = {c["distance_km"] for c in body["comparison"]}
        self.assertEqual(len(distances), 1)  # all three algorithms agree

    def test_compare_emissions(self):
        res = self.admin_client.post("/api/v1/routing/compare-emissions/", {"distance_km": 50, "engine_type": "diesel"})
        self.assertEqual(res.status_code, 200)

    def test_vehicle_details(self):
        self._patrol()
        vehicles = self.admin_client.get("/api/v1/vehicles/").json()["results"]
        spt1 = next(v for v in vehicles if v["plate_number"] == "SPT1")
        self.assertEqual(spt1["driver_name"], "guard1")
        self.assertIsNotNone(spt1["current_plan"])
        self.assertIsNotNone(spt1["next_location"])
        self.assertGreaterEqual(spt1["patrol_mileage_km"], 0)
        spt3 = next(v for v in vehicles if v["plate_number"] == "SPT3")
        self.assertFalse(spt3["is_operational"])

    def test_guard_management(self):
        res = self.admin_client.post(
            "/api/v1/guards/",
            {"username": "newguard", "password": "a-strong-pass-987", "first_name": "New", "badge_number": "B9",
             "assigned_vehicle": self.vehicles[1].id, "is_driver": True},
            format="json",
        )
        self.assertEqual(res.status_code, 201, res.content)
        self.assertEqual(res.json()["vehicle_plate"], "SPT2")
        self.assertEqual(self.guard_client.get("/api/v1/guards/").status_code, 403)

    def test_health_is_public(self):
        from rest_framework.test import APIClient

        self.assertEqual(APIClient().get("/api/v1/health/").json()["status"], "ok")

    def test_openapi_schema_builds(self):
        res = self.admin_client.get("/api/schema/")
        self.assertEqual(res.status_code, 200)
