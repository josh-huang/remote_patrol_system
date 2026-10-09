from agent.models import AgentAction
from core.tests.fixtures import PatrolAPITestCase, png
from comms.models import Message
from incidents.models import EmergencyAlert
from patrol.models import PatrolStop


class EmergencyAlertTests(PatrolAPITestCase):
    def _visit_first(self, vehicle, count):
        for stop in PatrolStop.objects.filter(vehicle=vehicle).order_by("order")[:count]:
            res = self.admin_client.post(f"/api/v1/stops/{stop.id}/check_in/", {}, format="multipart")
            self.assertEqual(res.status_code, 201)
            vehicle.current_latitude, vehicle.current_longitude = stop.location.latitude, stop.location.longitude
            vehicle.save()

    def test_raise_dispatch_resolve(self):
        self.make_plan()
        v1 = self.vehicles[0]
        self._visit_first(v1, 2)
        target = PatrolStop.objects.filter(vehicle=self.vehicles[1], is_visited=False).last().location

        res = self.admin_client.post("/api/v1/alerts/", {"location": target.id, "description": "Alarm"})
        self.assertEqual(res.status_code, 201, res.content)
        alert_id = res.json()["id"]
        target.refresh_from_db()
        self.assertTrue(target.emergency_trigger)
        # Raising again at the same site returns the same alert.
        self.assertEqual(self.admin_client.post("/api/v1/alerts/", {"location": target.id}).json()["id"], alert_id)

        res = self.admin_client.post(f"/api/v1/alerts/{alert_id}/dispatch/", {"vehicle_id": v1.id}, format="json")
        self.assertEqual(res.status_code, 200, res.content)
        alert = res.json()
        self.assertEqual(alert["status"], "dispatched")
        self.assertEqual(alert["vehicle_plate"], "SPT1")
        self.assertLessEqual(alert["rerouted_km"], alert["baseline_km"])
        self.assertGreaterEqual(alert["saved_km"], 0)

        # Vehicle 1's next stop is now the emergency site, continuing from there.
        route = self.guard_client.get("/api/v1/mobile/route/").json()
        self.assertEqual(route["next_stop"]["location"], target.id)
        self.assertEqual(route["next_stop"]["source"], "emergency")
        # The site was removed from vehicle 2's remaining route (no double visit).
        self.assertFalse(
            PatrolStop.objects.filter(vehicle=self.vehicles[1], location=target, is_visited=False).exists()
        )
        # The duty phone received the instruction.
        self.assertTrue(Message.objects.filter(vehicle=v1, from_command_centre=True, body__contains="EMERGENCY").exists())
        # Every site is still covered exactly once.
        stops = PatrolStop.objects.all()
        self.assertEqual(sorted(stops.values_list("location_id", flat=True)), sorted(s.id for s in self.sites))

        res = self.admin_client.post(f"/api/v1/alerts/{alert_id}/resolve/")
        self.assertEqual(res.json()["status"], "resolved")
        target.refresh_from_db()
        self.assertFalse(target.emergency_trigger)

    def test_dispatch_defaults_to_nearest_operational_vehicle(self):
        self.make_plan()
        tampines = next(s for s in self.sites if s.name == "Tampines Hub")
        alert = self.admin_client.post(
            f"/api/v1/locations/{tampines.id}/trigger_emergency/", {"auto_dispatch": True}, format="json"
        ).json()
        self.assertEqual(alert["status"], "dispatched")
        self.assertEqual(alert["vehicle_plate"], "SPT2")  # parked at Tampines

    def test_guard_cannot_use_alert_board(self):
        self.assertEqual(self.guard_client.get("/api/v1/alerts/").status_code, 403)


class IncidentTests(PatrolAPITestCase):
    def test_guard_report_with_photos_is_triaged(self):
        res = self.guard_client.post(
            "/api/v1/incidents/",
            {"description": "Graffiti and a smashed window", "location": self.sites[0].id, "uploaded_images": [png()]},
            format="multipart",
        )
        self.assertEqual(res.status_code, 201, res.content)
        body = res.json()
        self.assertEqual(body["ai_category"], "vandalism")
        self.assertEqual(body["vehicle"], self.vehicles[0].id)  # filled from the guard's vehicle
        self.assertEqual(len(body["images"]), 1)
        self.assertIn("photo_attached", body["ai_tags"])

    def test_critical_incident_raises_alert_and_pending_dispatch(self):
        self.make_plan()
        res = self.guard_client.post(
            "/api/v1/incidents/", {"description": "Fire and thick smoke at the gate", "location": self.sites[4].id}
        )
        self.assertEqual(res.json()["ai_severity"], "critical")
        alert = EmergencyAlert.objects.get(location=self.sites[4])
        self.assertEqual(alert.source, "incident")
        action = AgentAction.objects.get(origin="autonomous")
        self.assertEqual(action.tool_name, "dispatch_emergency")
        self.assertEqual(action.arguments["alert_id"], alert.id)

        # Operator confirms → the vehicle is dispatched and re-routed.
        res = self.admin_client.post(f"/api/v1/agent/actions/{action.id}/confirm/")
        self.assertEqual(res.json()["status"], "confirmed", res.content)
        alert.refresh_from_db()
        self.assertEqual(alert.status, "dispatched")

    def test_guards_only_see_their_own_reports(self):
        self.guard_client.post("/api/v1/incidents/", {"description": "All clear"})
        self.other_guard_client.post("/api/v1/incidents/", {"description": "All clear too"})
        self.assertEqual(self.guard_client.get("/api/v1/incidents/").json()["count"], 1)
        self.assertEqual(self.admin_client.get("/api/v1/incidents/").json()["count"], 2)
        incident_id = self.guard_client.get("/api/v1/incidents/").json()["results"][0]["id"]
        self.assertEqual(
            self.guard_client.patch(f"/api/v1/incidents/{incident_id}/", {"status": "resolved"}).status_code, 403
        )
