"""Incident intake business logic (AI triage), shared by the API and seeder."""

from __future__ import annotations

from django.utils import timezone

from core.services import llm

from .models import IncidentReport
from .signals import incident_triaged


def analyze_incident(incident: IncidentReport) -> IncidentReport:
    """Run AI triage on an incident and publish ``incident_triaged``.

    Subscribers (e.g. the AI agent's autonomy) run best-effort.
    """
    image_paths = [img.image.path for img in incident.images.all()]
    result = llm.analyze_incident(incident.description, image_paths=image_paths)
    incident.ai_category = result["category"]
    incident.ai_severity = result["severity"]
    incident.ai_summary = result["summary"]
    incident.ai_recommended_action = result["recommended_action"]
    incident.ai_anomaly_detected = result["anomaly_detected"]
    incident.ai_tags = result["tags"]
    incident.ai_source = result["source"]
    incident.ai_analyzed_at = timezone.now()
    incident.save()

    # send_robust logs a failing subscriber (logger "django.dispatch") and
    # carries on, so autonomy can never break intake.
    incident_triaged.send_robust(sender=IncidentReport, incident=incident)
    return incident
