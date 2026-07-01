from rest_framework import serializers

from .models import Location, Vehicle


class LocationSerializer(serializers.ModelSerializer):
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
            "is_active",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class VehicleSerializer(serializers.ModelSerializer):
    driver_name = serializers.SerializerMethodField()

    class Meta:
        model = Vehicle
        fields = [
            "id",
            "plate_number",
            "contact_number",
            "engine_type",
            "odometer_km",
            "maintenance_status",
            "is_available",
            "current_latitude",
            "current_longitude",
            "driver_name",
            "created_at",
        ]
        read_only_fields = ["id", "created_at", "current_latitude", "current_longitude"]

    def get_driver_name(self, obj) -> str | None:
        driver = obj.driver_in_charge
        if not driver:
            return None
        return driver.user.get_full_name() or driver.user.username
