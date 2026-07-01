from rest_framework import viewsets

from core.permissions import IsAdminRole

from .models import Location, Vehicle
from .serializers import LocationSerializer, VehicleSerializer


class LocationViewSet(viewsets.ModelViewSet):
    queryset = Location.objects.all()
    serializer_class = LocationSerializer
    permission_classes = [IsAdminRole]
    filterset_fields = ["is_active", "emergency_trigger", "priority"]
    search_fields = ["name", "address"]
    ordering_fields = ["priority", "name", "created_at"]


class VehicleViewSet(viewsets.ModelViewSet):
    queryset = Vehicle.objects.all()
    serializer_class = VehicleSerializer
    permission_classes = [IsAdminRole]
    filterset_fields = ["is_available", "engine_type", "maintenance_status"]
    search_fields = ["plate_number", "contact_number"]
