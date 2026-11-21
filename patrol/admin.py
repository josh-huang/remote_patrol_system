from django.contrib import admin

from .models import PatrolPlan, PatrolRecord, PatrolRecordImage, PatrolStop, VehiclePing


class PatrolStopInline(admin.TabularInline):
    model = PatrolStop
    extra = 0


class PatrolRecordImageInline(admin.TabularInline):
    model = PatrolRecordImage
    extra = 0


@admin.register(PatrolPlan)
class PatrolPlanAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "date",
        "status",
        "mode",
        "algorithm",
        "total_distance_km",
        "baseline_distance_km",
        "total_emission_kg",
    ]
    list_filter = ["status", "mode", "date"]
    inlines = [PatrolStopInline]


@admin.register(PatrolRecord)
class PatrolRecordAdmin(admin.ModelAdmin):
    list_display = ["vehicle", "location", "guard", "distance_km", "emission_kg", "created_at"]
    list_filter = ["vehicle", "location"]
    inlines = [PatrolRecordImageInline]


@admin.register(VehiclePing)
class VehiclePingAdmin(admin.ModelAdmin):
    list_display = ["vehicle", "latitude", "longitude", "speed_kmh", "recorded_at"]
