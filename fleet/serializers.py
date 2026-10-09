from django.db.models import Sum
from django.utils import timezone
from rest_framework import serializers

from .models import Location, Vehicle


class LocationSerializer(serializers.ModelSerializer):
    active_alerts = serializers.SerializerMethodField()

    class Meta:
        model = Location
        fields = [
            "id",
            "name",
            "address",
            "latitude",
            "longitude",
            "image",
            "priority",
            "emergency_trigger",
            "contact_number",
            "is_active",
            "active_alerts",
            "created_at",
        ]
        read_only_fields = ["id", "emergency_trigger", "active_alerts", "created_at"]

    def validate_latitude(self, value):
        if not -90 <= value <= 90:
            raise serializers.ValidationError("Latitude must be between -90 and 90.")
        return value

    def validate_longitude(self, value):
        if not -180 <= value <= 180:
            raise serializers.ValidationError("Longitude must be between -180 and 180.")
        return value

    def get_active_alerts(self, obj) -> int:
        return obj.alerts.exclude(status="resolved").count()


class VehicleSerializer(serializers.ModelSerializer):
    """Vehicle details for the dashboard: plate, driver in charge, contact,
    health status, mileage coverage, current route and next location."""

    is_operational = serializers.BooleanField(read_only=True)
    driver_name = serializers.SerializerMethodField()
    driver_phone = serializers.SerializerMethodField()
    current_plan = serializers.SerializerMethodField()
    next_location = serializers.SerializerMethodField()
    route_progress = serializers.SerializerMethodField()
    mileage_today_km = serializers.SerializerMethodField()
    patrol_mileage_km = serializers.SerializerMethodField()
    total_emission_kg = serializers.SerializerMethodField()

    class Meta:
        model = Vehicle
        fields = [
            "id",
            "plate_number",
            "model_name",
            "contact_number",
            "engine_type",
            "odometer_km",
            "maintenance_status",
            "is_available",
            "is_operational",
            "current_latitude",
            "current_longitude",
            "last_seen_at",
            "driver_name",
            "driver_phone",
            "current_plan",
            "next_location",
            "route_progress",
            "mileage_today_km",
            "patrol_mileage_km",
            "total_emission_kg",
        ]
        read_only_fields = ["id", "current_latitude", "current_longitude", "last_seen_at"]

    def _route(self, obj):
        cache = self.context.setdefault("_route_cache", {})
        if obj.pk not in cache:
            from patrol.services import vehicle_route

            cache[obj.pk] = vehicle_route(obj)
        return cache[obj.pk]

    def get_driver_name(self, obj) -> str | None:
        driver = obj.driver_in_charge
        return (driver.user.get_full_name() or driver.user.username) if driver else None

    def get_driver_phone(self, obj) -> str | None:
        driver = obj.driver_in_charge
        return driver.user.phone if driver else None

    def get_current_plan(self, obj) -> dict | None:
        plan, _ = self._route(obj)
        return {"id": plan.id, "name": plan.name, "date": plan.date} if plan else None

    def get_next_location(self, obj) -> dict | None:
        _, stops = self._route(obj)
        stop = next((s for s in stops if not s.is_visited), None)
        if not stop:
            return None
        return {
            "stop_id": stop.id,
            "id": stop.location_id,
            "name": stop.location.name,
            "latitude": stop.location.latitude,
            "longitude": stop.location.longitude,
            "is_emergency": stop.source == "emergency",
        }

    def get_route_progress(self, obj) -> dict:
        _, stops = self._route(obj)
        return {"visited": sum(s.is_visited for s in stops), "total": len(stops)}

    def get_mileage_today_km(self, obj) -> float:
        total = obj.patrol_records.filter(
            created_at__date=timezone.localdate()
        ).aggregate(t=Sum("distance_km"))["t"]
        return round(total or 0.0, 3)

    def get_patrol_mileage_km(self, obj) -> float:
        return round(obj.patrol_records.aggregate(t=Sum("distance_km"))["t"] or 0.0, 3)

    def get_total_emission_kg(self, obj) -> float:
        return round(obj.patrol_records.aggregate(t=Sum("emission_kg"))["t"] or 0.0, 3)
