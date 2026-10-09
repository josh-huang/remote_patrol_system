from rest_framework import serializers

from core.services.routing import ALGORITHMS
from fleet.models import Location, Vehicle

from .models import PatrolPlan, PatrolRecord, PatrolRecordImage, PatrolStop, VehiclePing


class PatrolStopSerializer(serializers.ModelSerializer):
    location_name = serializers.CharField(source="location.name", read_only=True)
    vehicle_plate = serializers.CharField(source="vehicle.plate_number", read_only=True)
    latitude = serializers.FloatField(source="location.latitude", read_only=True)
    longitude = serializers.FloatField(source="location.longitude", read_only=True)
    address = serializers.CharField(source="location.address", read_only=True)
    priority = serializers.IntegerField(source="location.priority", read_only=True)

    class Meta:
        model = PatrolStop
        fields = [
            "id",
            "plan",
            "vehicle",
            "vehicle_plate",
            "location",
            "location_name",
            "address",
            "latitude",
            "longitude",
            "priority",
            "order",
            "leg_distance_km",
            "source",
            "is_visited",
            "visited_at",
        ]
        read_only_fields = ["id", "leg_distance_km", "source", "is_visited", "visited_at"]


class PatrolPlanSerializer(serializers.ModelSerializer):
    stops = PatrolStopSerializer(many=True, read_only=True)
    emission_saved_kg = serializers.FloatField(read_only=True)
    vehicle_count = serializers.SerializerMethodField()
    progress = serializers.SerializerMethodField()

    class Meta:
        model = PatrolPlan
        fields = [
            "id",
            "name",
            "date",
            "status",
            "mode",
            "algorithm",
            "created_by",
            "total_distance_km",
            "total_emission_kg",
            "baseline_distance_km",
            "baseline_emission_kg",
            "reroute_saved_km",
            "reroute_saved_kg",
            "emission_saved_kg",
            "vehicle_count",
            "progress",
            "notes",
            "stops",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "mode",
            "algorithm",
            "created_by",
            "total_distance_km",
            "total_emission_kg",
            "baseline_distance_km",
            "baseline_emission_kg",
            "reroute_saved_km",
            "reroute_saved_kg",
            "created_at",
        ]

    def get_vehicle_count(self, obj) -> int:
        return len({s.vehicle_id for s in obj.stops.all()})

    def get_progress(self, obj) -> dict:
        stops = obj.stops.all()
        return {"visited": sum(s.is_visited for s in stops), "total": len(stops)}


def _validate_ids(model, ids, label):
    if not ids:
        return ids
    existing = set(model.objects.filter(id__in=ids).values_list("id", flat=True))
    if missing := set(ids) - existing:
        raise serializers.ValidationError(f"Unknown {label} ids: {sorted(missing)}")
    return ids


class PlanRouteRequestSerializer(serializers.Serializer):
    """Input for automatic route planning. Empty lists mean "all operational
    vehicles" / "all active locations"."""

    location_ids = serializers.ListField(child=serializers.IntegerField(), required=False, default=list)
    vehicle_ids = serializers.ListField(child=serializers.IntegerField(), required=False, default=list)
    depot_location_id = serializers.IntegerField(required=False, allow_null=True)
    algorithm = serializers.ChoiceField(choices=ALGORITHMS, default="dijkstra")
    from_live_positions = serializers.BooleanField(default=False)

    def validate_vehicle_ids(self, value):
        return _validate_ids(Vehicle, value, "vehicle")

    def validate_location_ids(self, value):
        return _validate_ids(Location, value, "location")


class AutoDailyPlanSerializer(PlanRouteRequestSerializer):
    name = serializers.CharField(required=False, allow_blank=True)
    date = serializers.DateField(required=False)


class ManualRouteSerializer(serializers.Serializer):
    vehicle_id = serializers.IntegerField()
    location_ids = serializers.ListField(child=serializers.IntegerField(), min_length=1)


class ManualPlanSerializer(serializers.Serializer):
    routes = ManualRouteSerializer(many=True, allow_empty=False)
    algorithm = serializers.ChoiceField(choices=ALGORITHMS, default="dijkstra")

    def validate_routes(self, routes):
        seen = set()
        for r in routes:
            dup = seen & set(r["location_ids"])
            if dup or len(set(r["location_ids"])) != len(r["location_ids"]):
                raise serializers.ValidationError("A location may only appear once in a plan.")
            seen |= set(r["location_ids"])
        return routes


class PatrolRecordImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = PatrolRecordImage
        fields = ["id", "image", "uploaded_at"]


class PatrolRecordSerializer(serializers.ModelSerializer):
    location_name = serializers.CharField(source="location.name", read_only=True)
    vehicle_plate = serializers.CharField(source="vehicle.plate_number", read_only=True)
    guard_name = serializers.SerializerMethodField()
    plan_name = serializers.CharField(source="plan.name", read_only=True, default=None)
    images = PatrolRecordImageSerializer(many=True, read_only=True)

    class Meta:
        model = PatrolRecord
        fields = [
            "id",
            "vehicle",
            "vehicle_plate",
            "location",
            "location_name",
            "guard",
            "guard_name",
            "plan",
            "plan_name",
            "stop",
            "distance_km",
            "emission_kg",
            "notes",
            "images",
            "created_at",
        ]
        read_only_fields = fields

    def get_guard_name(self, obj) -> str | None:
        if not obj.guard:
            return None
        return obj.guard.user.get_full_name() or obj.guard.user.username


class CheckInSerializer(serializers.Serializer):
    """Duty-phone check-in at a stop: notes + one or more site photos."""

    notes = serializers.CharField(required=False, allow_blank=True, default="")
    images = serializers.ListField(child=serializers.ImageField(), required=False, default=list)


class VehiclePingSerializer(serializers.ModelSerializer):
    vehicle = serializers.PrimaryKeyRelatedField(queryset=Vehicle.objects.all(), required=False)

    class Meta:
        model = VehiclePing
        fields = ["id", "vehicle", "latitude", "longitude", "speed_kmh", "recorded_at"]
        read_only_fields = ["id", "recorded_at"]


class LiveVehicleSerializer(serializers.ModelSerializer):
    """Latest known position of a vehicle, for the live map."""

    driver_name = serializers.SerializerMethodField()
    is_operational = serializers.BooleanField(read_only=True)

    class Meta:
        model = Vehicle
        fields = [
            "id",
            "plate_number",
            "engine_type",
            "maintenance_status",
            "is_available",
            "is_operational",
            "current_latitude",
            "current_longitude",
            "last_seen_at",
            "driver_name",
        ]

    def get_driver_name(self, obj) -> str | None:
        driver = obj.driver_in_charge
        if not driver:
            return None
        return driver.user.get_full_name() or driver.user.username
