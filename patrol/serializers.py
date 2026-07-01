from rest_framework import serializers

from fleet.models import Location, Vehicle

from .models import PatrolPlan, PatrolRecord, PatrolStop, VehiclePing


class PatrolStopSerializer(serializers.ModelSerializer):
    location_name = serializers.CharField(source="location.name", read_only=True)
    vehicle_plate = serializers.CharField(source="vehicle.plate_number", read_only=True)
    latitude = serializers.FloatField(source="location.latitude", read_only=True)
    longitude = serializers.FloatField(source="location.longitude", read_only=True)

    class Meta:
        model = PatrolStop
        fields = [
            "id",
            "plan",
            "vehicle",
            "vehicle_plate",
            "location",
            "location_name",
            "latitude",
            "longitude",
            "order",
            "leg_distance_km",
            "is_visited",
            "visited_at",
        ]
        read_only_fields = ["id", "leg_distance_km"]


class PatrolPlanSerializer(serializers.ModelSerializer):
    stops = PatrolStopSerializer(many=True, read_only=True)

    class Meta:
        model = PatrolPlan
        fields = [
            "id",
            "name",
            "date",
            "status",
            "created_by",
            "total_distance_km",
            "total_emission_kg",
            "notes",
            "stops",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "created_by",
            "total_distance_km",
            "total_emission_kg",
            "created_at",
        ]


class PlanRouteRequestSerializer(serializers.Serializer):
    """Input for the automatic route-planning endpoint."""

    location_ids = serializers.ListField(
        child=serializers.IntegerField(), required=False, allow_empty=True
    )
    vehicle_ids = serializers.ListField(
        child=serializers.IntegerField(), min_length=1
    )
    depot_location_id = serializers.IntegerField(required=False, allow_null=True)
    algorithm = serializers.ChoiceField(
        choices=["dijkstra", "bellman_ford", "floyd_warshall"],
        default="dijkstra",
    )

    def validate_vehicle_ids(self, value):
        existing = set(
            Vehicle.objects.filter(id__in=value).values_list("id", flat=True)
        )
        missing = set(value) - existing
        if missing:
            raise serializers.ValidationError(f"Unknown vehicle ids: {sorted(missing)}")
        return value

    def validate_location_ids(self, value):
        if not value:
            return value
        existing = set(
            Location.objects.filter(id__in=value).values_list("id", flat=True)
        )
        missing = set(value) - existing
        if missing:
            raise serializers.ValidationError(f"Unknown location ids: {sorted(missing)}")
        return value


class PatrolRecordSerializer(serializers.ModelSerializer):
    location_name = serializers.CharField(source="location.name", read_only=True)
    vehicle_plate = serializers.CharField(source="vehicle.plate_number", read_only=True)

    class Meta:
        model = PatrolRecord
        fields = [
            "id",
            "vehicle",
            "vehicle_plate",
            "location",
            "location_name",
            "guard",
            "plan",
            "distance_km",
            "emission_kg",
            "notes",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class VehiclePingSerializer(serializers.ModelSerializer):
    class Meta:
        model = VehiclePing
        fields = ["id", "vehicle", "latitude", "longitude", "speed_kmh", "recorded_at"]
        read_only_fields = ["id", "recorded_at"]


class LiveVehicleSerializer(serializers.ModelSerializer):
    """Latest known position of a vehicle, for the live map."""

    driver_name = serializers.SerializerMethodField()

    class Meta:
        model = Vehicle
        fields = [
            "id",
            "plate_number",
            "engine_type",
            "maintenance_status",
            "is_available",
            "current_latitude",
            "current_longitude",
            "driver_name",
        ]

    def get_driver_name(self, obj) -> str | None:
        driver = obj.driver_in_charge
        if not driver:
            return None
        return driver.user.get_full_name() or driver.user.username
