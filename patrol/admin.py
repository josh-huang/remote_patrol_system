from django.contrib import admin

from .models import PatrolPlan, PatrolRecord, PatrolStop, VehiclePing


class PatrolStopInline(admin.TabularInline):
    model = PatrolStop
    extra = 0


@admin.register(PatrolPlan)
class PatrolPlanAdmin(admin.ModelAdmin):
    list_display = ["name", "date", "status", "total_distance_km", "total_emission_kg"]
    list_filter = ["status", "date"]
    inlines = [PatrolStopInline]


@admin.register(PatrolRecord)
class PatrolRecordAdmin(admin.ModelAdmin):
    list_display = ["vehicle", "location", "distance_km", "emission_kg", "created_at"]
    list_filter = ["vehicle", "location"]


@admin.register(VehiclePing)
class VehiclePingAdmin(admin.ModelAdmin):
    list_display = ["vehicle", "latitude", "longitude", "speed_kmh", "recorded_at"]
