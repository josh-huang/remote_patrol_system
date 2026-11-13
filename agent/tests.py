from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from .models import AgentAction


class AgentActionPermissionTests(APITestCase):
    def setUp(self):
        User = get_user_model()
        self.guard = User.objects.create_user(username="guard", role=User.Role.GUARD)
        self.admin = User.objects.create_user(username="admin", role=User.Role.ADMIN)
        self.pending = AgentAction.objects.create(
            tool_name="create_patrol_plan", arguments={}, summary="Pending dispatch"
        )

    def test_guards_cannot_confirm_or_reject_actions(self):
        self.client.force_authenticate(self.guard)
        for action in ("confirm", "reject"):
            with self.subTest(action=action), patch(
                f"agent.engine.{action}_action", return_value=self.pending
            ) as resolve:
                response = self.client.post(
                    reverse(f"v1:agent-action-{action}", args=[self.pending.pk])
                )
                self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
                resolve.assert_not_called()
                self.pending.refresh_from_db()
                self.assertEqual(self.pending.status, AgentAction.Status.PENDING)

    def test_admin_can_confirm_action(self):
        self.client.force_authenticate(self.admin)
        with patch("agent.engine.tools.execute", return_value={"plan_id": 1}) as execute:
            response = self.client.post(reverse("v1:agent-action-confirm", args=[self.pending.pk]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        execute.assert_called_once_with("create_patrol_plan", {})
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.status, AgentAction.Status.CONFIRMED)
        self.assertEqual(self.pending.resolved_by, self.admin)

    def test_admin_can_reject_action(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(reverse("v1:agent-action-reject", args=[self.pending.pk]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.status, AgentAction.Status.REJECTED)
        self.assertEqual(self.pending.resolved_by, self.admin)

    def test_guards_can_still_read_pending_actions(self):
        self.client.force_authenticate(self.guard)
        response = self.client.get(reverse("v1:agent-action-detail", args=[self.pending.pk]))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_anonymous_users_cannot_resolve_actions(self):
        for action in ("confirm", "reject"):
            response = self.client.post(reverse(f"v1:agent-action-{action}", args=[self.pending.pk]))
            self.assertIn(response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))
