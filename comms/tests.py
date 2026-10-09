from core.tests.fixtures import PatrolAPITestCase


class MessagingTests(PatrolAPITestCase):
    def test_guard_and_command_centre_conversation(self):
        res = self.guard_client.post("/api/v1/messages/", {"body": "Flat tyre at Orchard"})
        self.assertEqual(res.status_code, 201, res.content)
        self.assertEqual(res.json()["vehicle"], self.vehicles[0].id)
        self.assertFalse(res.json()["from_command_centre"])

        inbox = self.admin_client.get("/api/v1/messages/inbox/").json()
        row = next(r for r in inbox if r["id"] == self.vehicles[0].id)
        self.assertEqual(row["unread"], 1)

        res = self.admin_client.post("/api/v1/messages/", {"vehicle": self.vehicles[0].id, "body": "Backup on the way"})
        self.assertTrue(res.json()["from_command_centre"])
        self.admin_client.post("/api/v1/messages/mark_read/", {"vehicle": self.vehicles[0].id})
        inbox = self.admin_client.get("/api/v1/messages/inbox/").json()
        self.assertEqual(next(r for r in inbox if r["id"] == self.vehicles[0].id)["unread"], 0)

        thread = self.guard_client.get("/api/v1/messages/").json()
        self.assertEqual([m["body"] for m in thread], ["Flat tyre at Orchard", "Backup on the way"])

    def test_guards_cannot_read_other_channels(self):
        self.guard_client.post("/api/v1/messages/", {"body": "private"})
        self.assertEqual(self.other_guard_client.get("/api/v1/messages/").json(), [])
        self.assertEqual(self.guard_client.get("/api/v1/messages/inbox/").status_code, 403)

    def test_admin_must_choose_vehicle(self):
        self.assertEqual(self.admin_client.post("/api/v1/messages/", {"body": "hi"}).status_code, 400)

    def test_contact_number(self):
        self.assertIn("command_centre_phone", self.guard_client.get("/api/v1/messages/contact/").json())
