"""Event-driven autonomy — the agent acting without being asked.

When a high/critical incident is analysed at a known site, the agent raises an
emergency alert on the noticeboard and proposes dispatching the nearest
operational vehicle, with its route dynamically re-planned from the emergency
site. Following the system's governance model, the dispatch is queued as a
PENDING action for an operator to confirm rather than executed automatically.
"""

from __future__ import annotations

import logging

from incidents.models import EmergencyAlert, IncidentReport
from patrol import services

from .models import AgentAction

logger = logging.getLogger(__name__)

AUTO_DISPATCH_SEVERITIES = {
    IncidentReport.Severity.HIGH,
    IncidentReport.Severity.CRITICAL,
}


def evaluate_incident(incident: IncidentReport) -> AgentAction | None:
    """Raise an alert + queue a pending dispatch for serious incidents."""
    if incident.ai_severity not in AUTO_DISPATCH_SEVERITIES or not incident.location:
        return None

    alert, _ = services.raise_alert(
        incident.location,
        description=incident.ai_summary or incident.description[:280],
        source=EmergencyAlert.Source.INCIDENT,
        user=incident.reporter,
        incident=incident,
    )
    if alert.status != EmergencyAlert.Status.ACTIVE:
        return None  # already being handled

    # Idempotency: one pending autonomous dispatch per alert.
    if AgentAction.objects.filter(
        origin=AgentAction.Origin.AUTONOMOUS,
        status=AgentAction.Status.PENDING,
        tool_name="dispatch_emergency",
        arguments__alert_id=alert.id,
    ).exists():
        return None

    loc = incident.location
    vehicle, distance = services.nearest_vehicle(loc.latitude, loc.longitude)
    if vehicle is None:
        logger.warning("No operational vehicle to propose for alert #%s", alert.id)
        return None

    away = f" ({distance} km away)" if distance is not None else ""
    return AgentAction.objects.create(
        origin=AgentAction.Origin.AUTONOMOUS,
        tool_name="dispatch_emergency",
        arguments={"alert_id": alert.id, "vehicle_id": vehicle.id},
        summary=(
            f"⚠ {incident.ai_severity.upper()} {incident.ai_category or 'incident'} at "
            f"{loc.name}. Dispatch nearest vehicle {vehicle.plate_number}{away} and "
            f"re-plan its remaining route from the site."
        ),
    )
