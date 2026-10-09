from drf_spectacular.utils import extend_schema
from rest_framework import serializers as drf_serializers
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core.permissions import IsAdminRole

from .models import Location, Vehicle
from .serializers import LocationSerializer, VehicleSerializer


class TriggerEmergencySerializer(drf_serializers.Serializer):
    description = drf_serializers.CharField(required=False, allow_blank=True, default="")
    auto_dispatch = drf_serializers.BooleanField(default=False)


class LocationViewSet(viewsets.ModelViewSet):
    """Patrol sites (add / edit / remove)."""

    queryset = Location.objects.all()
    serializer_class = LocationSerializer
    permission_classes = [IsAdminRole]
    filterset_fields = ["is_active", "emergency_trigger", "priority"]
    search_fields = ["name", "address"]
    ordering_fields = ["priority", "name", "created_at"]

    @extend_schema(request=TriggerEmergencySerializer, responses=dict)
    @action(detail=True, methods=["post"])
    def trigger_emergency(self, request, pk=None):
        """Raise an emergency alarm at this site (optionally auto-dispatch)."""
        from incidents.models import EmergencyAlert
        from incidents.serializers import EmergencyAlertSerializer
        from patrol import services

        req = TriggerEmergencySerializer(data=request.data)
        req.is_valid(raise_exception=True)
        alert, created = services.raise_alert(
            self.get_object(),
            description=req.validated_data["description"],
            source=EmergencyAlert.Source.MANUAL,
            user=request.user,
        )
        if req.validated_data["auto_dispatch"] and alert.status == EmergencyAlert.Status.ACTIVE:
            try:
                services.dispatch_alert(alert, user=request.user)
            except services.PlanningError as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            EmergencyAlertSerializer(alert, context={"request": request}).data,
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class VehicleViewSet(viewsets.ModelViewSet):
    """Patrol vehicles (add / edit / remove) with live route details."""

    queryset = Vehicle.objects.prefetch_related("assigned_guards__user")
    serializer_class = VehicleSerializer
    permission_classes = [IsAdminRole]
    filterset_fields = ["is_available", "engine_type", "maintenance_status"]
    search_fields = ["plate_number", "contact_number", "model_name"]
