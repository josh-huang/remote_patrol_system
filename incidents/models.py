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


class EmergencyAlert(TimeStampedModel):
    """An emergency alarm raised at a patrol site.

    Shown on the command-centre noticeboard. Dispatching an alert diverts the
    nearest operational vehicle and dynamically re-plans the rest of its
    route (see ``patrol.services.dispatch_alert``); the mileage and CO2e saved
    versus driving back to the original route are recorded here.
    """

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        DISPATCHED = "dispatched", "Vehicle dispatched"
        RESOLVED = "resolved", "Resolved"

    class Source(models.TextChoices):
        ALARM = "alarm", "Site alarm"
        MANUAL = "manual", "Command centre"
        INCIDENT = "incident", "Incident report"
        AGENT = "agent", "AI agent"

    location = models.ForeignKey(
        "fleet.Location", on_delete=models.CASCADE, related_name="alerts"
    )
    description = models.TextField(blank=True)
    source = models.CharField(max_length=16, choices=Source.choices, default=Source.MANUAL)
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.ACTIVE, db_index=True
    )
    incident = models.ForeignKey(
        IncidentReport,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="alerts",
    )
    raised_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="raised_alerts",
    )
    assigned_vehicle = models.ForeignKey(
        "fleet.Vehicle",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="alerts",
    )
    dispatched_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    # Dynamic re-routing outcome.
    baseline_km = models.FloatField(default=0.0)
    rerouted_km = models.FloatField(default=0.0)
    saved_km = models.FloatField(default=0.0)
    saved_kg = models.FloatField(default=0.0)
    reroute_detail = models.JSONField(default=dict, blank=True)

    def __str__(self) -> str:
        return f"Alert #{self.pk} @ {self.location} [{self.status}]"
