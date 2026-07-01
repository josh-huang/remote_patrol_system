from django.contrib import admin

from .models import Location, Vehicle


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    list_display = ["name", "priority", "emergency_trigger", "is_active"]
    list_filter = ["is_active", "emergency_trigger"]
    search_fields = ["name", "address"]


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = [
        "plate_number",
        "engine_type",
        "maintenance_status",
        "is_available",
    ]
    list_filter = ["engine_type", "maintenance_status", "is_available"]
    search_fields = ["plate_number"]
