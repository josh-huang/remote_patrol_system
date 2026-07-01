"""Event-driven autonomy — the agent acting without being asked.

When a high/critical incident is analysed, the agent proactively finds the
nearest available vehicle and prepares a dispatch action. Following the
system's governance model, the action is queued as PENDING for an operator to
confirm rather than executed automatically.
"""

from __future__ import annotations

import logging

from core.services.routing import haversine_km
from fleet.models import Vehicle
from incidents.models import IncidentReport

from .models import AgentAction

logger = logging.getLogger(__name__)

AUTO_DISPATCH_SEVERITIES = {
    IncidentReport.Severity.HIGH,
    IncidentReport.Severity.CRITICAL,
}


def _nearest_available_vehicle(lat: float, lng: float) -> Vehicle | None:
    best, best_d = None, float("inf")
    for v in Vehicle.objects.filter(
        is_available=True,
        current_latitude__isnull=False,
        current_longitude__isnull=False,
    ):
        d = haversine_km(lat, lng, v.current_latitude, v.current_longitude)
        if d < best_d:
            best, best_d = v, d
    return best


def evaluate_incident(incident: IncidentReport) -> AgentAction | None:
    """Create a pending auto-dispatch action for serious incidents."""
    if incident.ai_severity not in AUTO_DISPATCH_SEVERITIES:
        return None
    if not incident.location:
        return None

    # Idempotency: don't stack duplicate autonomous actions for the same spot.
    if AgentAction.objects.filter(
        origin=AgentAction.Origin.AUTONOMOUS,
        status=AgentAction.Status.PENDING,
        arguments__location_ids=[incident.location_id],
    ).exists():
        return None

    vehicle = _nearest_available_vehicle(
        incident.location.latitude, incident.location.longitude
    )
    if not vehicle:
        return None

    args = {
        "name": f"Auto-dispatch: {incident.location.name}",
        "vehicle_ids": [vehicle.id],
        "location_ids": [incident.location_id],
    }
    summary = (
        f"⚠ {incident.ai_severity.upper()} incident at {incident.location.name}. "
        f"Auto-dispatch nearest vehicle {vehicle.plate_number} there."
    )
    return AgentAction.objects.create(
        origin=AgentAction.Origin.AUTONOMOUS,
        tool_name="create_patrol_plan",
        arguments=args,
        summary=summary,
    )
