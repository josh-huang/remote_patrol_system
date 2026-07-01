from django.contrib import admin

from .models import IncidentImage, IncidentReport


class IncidentImageInline(admin.TabularInline):
    model = IncidentImage
    extra = 0


@admin.register(IncidentReport)
class IncidentReportAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "ai_severity",
        "ai_category",
        "status",
        "ai_anomaly_detected",
        "created_at",
    ]
    list_filter = ["status", "ai_severity", "ai_category", "ai_anomaly_detected"]
    search_fields = ["description", "ai_summary"]
    inlines = [IncidentImageInline]
