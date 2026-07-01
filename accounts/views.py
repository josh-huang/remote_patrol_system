from drf_spectacular.utils import extend_schema
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core.permissions import IsAdminRole

from .models import SecurityGuard, User
from .serializers import SecurityGuardSerializer, UserSerializer


class SecurityGuardViewSet(viewsets.ModelViewSet):
    """Manage patrol officers and their duty status."""

    queryset = SecurityGuard.objects.select_related("user", "assigned_vehicle")
    serializer_class = SecurityGuardSerializer
    permission_classes = [IsAdminRole]
    filterset_fields = ["is_available", "on_duty", "is_driver", "assigned_vehicle"]
    search_fields = ["badge_number", "user__first_name", "user__last_name"]

    @extend_schema(request=None, responses=SecurityGuardSerializer)
    @action(detail=True, methods=["post"])
    def toggle_duty(self, request, pk=None):
        guard = self.get_object()
        guard.on_duty = not guard.on_duty
        guard.save(update_fields=["on_duty"])
        return Response(self.get_serializer(guard).data)


class MeView(viewsets.ViewSet):
    """Return the authenticated user's profile (used by both clients)."""

    @extend_schema(responses=UserSerializer)
    def list(self, request):
        return Response(UserSerializer(request.user).data)
