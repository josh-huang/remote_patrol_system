from agent.models import AgentAction
from core.tests.fixtures import PatrolAPITestCase
from patrol.models import PatrolPlan


class AgentTests(PatrolAPITestCase):
    def chat(self, text, conversation_id=None):
        res = self.admin_client.post(
            "/api/v1/agent/chat/", {"message": text, "conversation_id": conversation_id}, format="json"
        )
        self.assertEqual(res.status_code, 200, res.content)
        return res.json()

    def test_overview_uses_tools(self):
        body = self.chat("give me an overview")
        self.assertIn("vehicles operational", body["message"]["content"])
        self.assertEqual(body["message"]["steps"][0]["tool"], "get_dashboard_summary")

    def test_plan_request_is_queued_then_confirmed(self):
        body = self.chat("Plan tonight's patrol route")
        actions = body["message"]["actions"]
        self.assertEqual(actions[0]["tool_name"], "create_patrol_plan")
        self.assertEqual(actions[0]["status"], "pending")
        self.assertFalse(PatrolPlan.objects.exists())  # nothing executed yet

        res = self.admin_client.post(f"/api/v1/agent/actions/{actions[0]['id']}/confirm/").json()
        self.assertEqual(res["status"], "confirmed", res)
        self.assertEqual(PatrolPlan.objects.count(), 1)

    def test_emergency_request_proposes_dispatch(self):
        self.make_plan()
        self.admin_client.post("/api/v1/alerts/", {"location": self.sites[2].id})
        body = self.chat("处理紧急警报")
        self.assertEqual(body["message"]["actions"][0]["tool_name"], "dispatch_emergency")

    def test_reject(self):
        action = self.chat("plan a route")["message"]["actions"][0]
        res = self.admin_client.post(f"/api/v1/agent/actions/{action['id']}/reject/").json()
        self.assertEqual(res["status"], "rejected")
        self.assertEqual(AgentAction.objects.get(id=action["id"]).status, "rejected")

    def test_guard_cannot_use_agent(self):
        res = self.guard_client.post("/api/v1/agent/chat/", {"message": "hi"}, format="json")
        self.assertEqual(res.status_code, 403)
