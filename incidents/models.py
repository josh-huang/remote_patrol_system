from django.conf import settings
from django.db import models

from core.models import TimeStampedModel


class IncidentReport(TimeStampedModel):
    """A field report submitted by a patrol officer.

    On creation the AI analyst (`core.services.llm`) classifies the text and any
    attached photos, populating the `ai_*` fields (severity, category, summary,
    recommended action, anomaly flag). This is the project's primary LLM touch
    point.
    """

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        ACKNOWLEDGED = "acknowledged", "Acknowledged"
        RESOLVED = "resolved", "Resolved"

    class Severity(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        CRITICAL = "critical", "Critical"

    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="incident_reports",
    )
    vehicle = models.ForeignKey(
        "fleet.Vehicle",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="incidents",
    )
    location = models.ForeignKey(
        "fleet.Location",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="incidents",
    )
    description = models.TextField()
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.OPEN
    )

    # --- AI analysis output ---
    ai_category = models.CharField(max_length=32, blank=True)
    ai_severity = models.CharField(
        max_length=16, choices=Severity.choices, blank=True
    )
    ai_summary = models.TextField(blank=True)
    ai_recommended_action = models.TextField(blank=True)
    ai_anomaly_detected = models.BooleanField(default=False)
    ai_tags = models.JSONField(default=list, blank=True)
    ai_source = models.CharField(max_length=16, blank=True)  # "llm" | "mock"
    ai_analyzed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return f"Incident #{self.pk} ({self.ai_severity or 'unassessed'})"


class IncidentImage(models.Model):
    incident = models.ForeignKey(
        IncidentReport, on_delete=models.CASCADE, related_name="images"
    )
    image = models.ImageField(upload_to="incidents/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return f"Image for incident #{self.incident_id}"
